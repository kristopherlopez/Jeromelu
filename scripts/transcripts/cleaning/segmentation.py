"""Layer 1.5: Topic segmentation for context-scoped cleaning.

Scans the transcript (after deterministic corrections) to identify
natural topic blocks — game reviews, position analysis, general
discussion — and builds scoped player pools for each block.

This dramatically narrows the candidate pool for phonetic matching,
reducing false positives and allowing higher confidence within
well-defined segments.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .context import POSITION_KEYWORDS, Player, RoundContext, build_team_lookup

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# Minimum segments for a block to be worth scoping
MIN_BLOCK_SIZE = 8

# How many segments to look ahead/behind when resolving block boundaries
BOUNDARY_LOOKAHEAD = 5

# Transition phrases that signal a topic change
_TRANSITION_PATTERNS = [
    r"\bnext\s+(?:game|up|match|one)\b",
    r"\bmoving\s+on\b",
    r"\blet'?s\s+(?:look\s+at|move|go\s+to|talk\s+about|get\s+into)\b",
    r"\bnow\s+(?:onto|to|for|looking)\b",
    r"\bonto\s+the\b",
    r"\ball\s+right\s*,?\s*so\b",
    r"\bokay\s*,?\s*so\b",
    r"\banyway\s*,?\s*(?:so|let)\b",
    r"\bnext\s+(?:team|position|group|segment)\b",
    r"\bmoving\s+(?:to|into)\b",
]
_TRANSITION_RE = re.compile("|".join(_TRANSITION_PATTERNS), re.IGNORECASE)

# Game-specific phrases (e.g. "Broncos vs Eels", "that game", "in that match")
_GAME_PHRASES = re.compile(
    r"\b(?:vs?\.?|versus|against|v)\b", re.IGNORECASE
)


@dataclass
class TopicBlock:
    """A contiguous run of segments sharing a discussion topic."""

    start_idx: int
    end_idx: int  # exclusive
    block_type: str  # "game", "position", "general"
    label: str  # human-readable label e.g. "Broncos vs Eels" or "CTW analysis"
    teams: list[str] = field(default_factory=list)
    positions: list[str] = field(default_factory=list)  # position codes
    player_pool: list[Player] | None = None  # set during scoping phase


def _load_teams_data() -> dict:
    path = DATA_DIR / "teams.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _detect_team_mentions(
    segments: list[dict],
    team_lookup: dict[str, str],
) -> list[list[str]]:
    """For each segment, return list of canonical team short names mentioned."""
    per_segment: list[list[str]] = []
    for seg in segments:
        text = seg["text"].lower()
        teams_found: list[str] = []
        seen: set[str] = set()
        for pattern, canonical in team_lookup.items():
            if canonical not in seen and pattern in text:
                teams_found.append(canonical)
                seen.add(canonical)
        per_segment.append(teams_found)
    return per_segment


def _detect_position_mentions(
    segments: list[dict],
) -> list[list[str]]:
    """For each segment, return list of position codes mentioned."""
    per_segment: list[list[str]] = []
    for seg in segments:
        text = seg["text"].lower()
        codes: set[str] = set()
        for keyword, pos_codes in POSITION_KEYWORDS.items():
            if keyword in text:
                codes.update(pos_codes)
        per_segment.append(list(codes))
    return per_segment


def _detect_transitions(segments: list[dict]) -> list[bool]:
    """For each segment, return whether it contains a transition phrase."""
    return [bool(_TRANSITION_RE.search(seg["text"])) for seg in segments]


def _detect_time_gaps(segments: list[dict], gap_threshold: float = 10.0) -> list[bool]:
    """Detect large time gaps between segments (potential topic boundaries)."""
    gaps = [False]  # first segment has no gap
    for i in range(1, len(segments)):
        prev_end = segments[i - 1].get("end", segments[i - 1].get("start", 0))
        curr_start = segments[i].get("start", 0)
        gaps.append((curr_start - prev_end) > gap_threshold)
    return gaps


def _find_dominant_teams(
    team_mentions: list[list[str]],
    start: int,
    end: int,
    min_mentions: int = 2,
) -> list[str]:
    """Find teams mentioned at least min_mentions times in a segment range."""
    counts: dict[str, int] = {}
    for i in range(start, end):
        for team in team_mentions[i]:
            counts[team] = counts.get(team, 0) + 1
    return [t for t, c in sorted(counts.items(), key=lambda x: -x[1]) if c >= min_mentions]


def _find_dominant_positions(
    pos_mentions: list[list[str]],
    start: int,
    end: int,
    min_mentions: int = 3,
) -> list[str]:
    """Find position codes mentioned at least min_mentions times in a segment range."""
    counts: dict[str, int] = {}
    for i in range(start, end):
        for code in pos_mentions[i]:
            counts[code] = counts.get(code, 0) + 1
    return [p for p, c in sorted(counts.items(), key=lambda x: -x[1]) if c >= min_mentions]


def _find_boundaries(
    segments: list[dict],
    team_mentions: list[list[str]],
    transitions: list[bool],
    time_gaps: list[bool],
) -> list[int]:
    """Identify segment indices where topic boundaries likely occur.

    Combines transition phrases, time gaps, and team mention shifts.
    Returns sorted list of boundary indices.
    """
    n = len(segments)
    boundary_scores: list[float] = [0.0] * n

    # Score each segment as a potential boundary
    for i in range(n):
        score = 0.0

        # Transition phrase is a strong signal
        if transitions[i]:
            score += 2.0

        # Large time gap
        if time_gaps[i]:
            score += 1.5

        # Team mention shift: new team appears that wasn't in recent context
        if team_mentions[i]:
            # Look back 20 segments for recent teams
            recent_teams: set[str] = set()
            for j in range(max(0, i - 20), i):
                recent_teams.update(team_mentions[j])

            new_teams = set(team_mentions[i]) - recent_teams
            if new_teams:
                score += 1.0 * len(new_teams)

        boundary_scores[i] = score

    # Find peaks (local maxima above threshold)
    threshold = 2.0
    boundaries: list[int] = [0]  # always start at 0

    for i in range(1, n - 1):
        if boundary_scores[i] < threshold:
            continue
        # Must be a local max (or tied) within a window
        window = 10
        local_max = max(boundary_scores[max(0, i - window):min(n, i + window + 1)])
        if boundary_scores[i] >= local_max:
            # Don't place boundaries too close together
            if boundaries and i - boundaries[-1] < MIN_BLOCK_SIZE:
                # Keep the higher-scoring one
                prev = boundaries[-1]
                if boundary_scores[i] > boundary_scores[prev]:
                    boundaries[-1] = i
            else:
                boundaries.append(i)

    return boundaries


def _classify_block(
    team_mentions: list[list[str]],
    pos_mentions: list[list[str]],
    start: int,
    end: int,
) -> tuple[str, str, list[str], list[str]]:
    """Classify a block and return (block_type, label, teams, positions).

    Priority:
    1. If 2+ teams dominate and appear together → "game" (e.g. "Broncos vs Eels")
    2. If position codes dominate without clear team focus → "position"
    3. Otherwise → "general"
    """
    dominant_teams = _find_dominant_teams(team_mentions, start, end, min_mentions=2)
    dominant_positions = _find_dominant_positions(pos_mentions, start, end, min_mentions=3)

    # Game block: at least 2 teams with significant mentions
    if len(dominant_teams) >= 2:
        # Take the top 2 teams as the likely matchup
        label = f"{dominant_teams[0]} vs {dominant_teams[1]}"
        if len(dominant_teams) > 2:
            label += f" (+{len(dominant_teams) - 2} more)"
        return "game", label, dominant_teams, dominant_positions

    # Position block: clear position focus without strong team signal
    # If 4+ distinct position codes are mentioned, it's too broad to be useful scoping
    if dominant_positions and len(dominant_teams) < 2:
        unique_codes = set(dominant_positions)
        if len(unique_codes) >= 4:
            return "general", "General discussion", dominant_teams, dominant_positions
        pos_label = "/".join(sorted(unique_codes))
        return "position", f"Position analysis ({pos_label})", dominant_teams, list(unique_codes)

    # Single team focus (still useful for scoping)
    if len(dominant_teams) == 1:
        return "game", f"{dominant_teams[0]} discussion", dominant_teams, dominant_positions

    return "general", "General discussion", dominant_teams, dominant_positions


def _scope_player_pool(
    block: TopicBlock,
    round_context: RoundContext,
) -> list[Player]:
    """Build a scoped player pool for a topic block.

    - Game blocks: players from the discussed teams (primary), rest as secondary
    - Position blocks: players matching the discussed positions (primary), rest as secondary
    - General blocks: all players (no scoping)
    """
    all_players = round_context.all_players

    if block.block_type == "game" and block.teams:
        # Primary: players from discussed teams
        # Secondary: everyone else (still available but not boosted)
        scoped: list[Player] = []
        for p in all_players:
            player = Player(
                name=p.name,
                team=p.team,
                positions=p.positions,
                is_primary=p.team in block.teams,
            )
            scoped.append(player)
        return scoped

    if block.block_type == "position" and block.positions:
        scoped = []
        for p in all_players:
            has_position = any(pos in block.positions for pos in p.positions)
            player = Player(
                name=p.name,
                team=p.team,
                positions=p.positions,
                is_primary=has_position,
            )
            scoped.append(player)
        return scoped

    # General: preserve original primary/secondary from round context
    return all_players


def _merge_related_blocks(
    blocks: list[TopicBlock],
    team_mentions: list[list[str]],
    pos_mentions: list[list[str]],
) -> list[TopicBlock]:
    """Merge adjacent blocks that share dominant teams.

    When a game discussion is fragmented by small position/general blocks,
    this pass merges them into a single game block. For example:
      [1294-1306] position (CTW) with tigers/cowboys mentions
      [1306-1343] position (2RF)  with cowboys mentions
      [1343-1449] position (CTW)  with cowboys mentions
      [1449-1716] game (Cowboys vs Tigers)
    All get merged into one [1294-1716] game (Cowboys vs Tigers) block.
    """
    if len(blocks) <= 1:
        return blocks

    # Run merge passes until stable (merging can reclassify blocks,
    # enabling further merges on the next pass)
    prev_count = len(blocks) + 1
    while len(blocks) < prev_count:
        prev_count = len(blocks)
        blocks = _merge_pass(blocks, team_mentions, pos_mentions)

    return blocks


def _merge_pass(
    blocks: list[TopicBlock],
    team_mentions: list[list[str]],
    pos_mentions: list[list[str]],
) -> list[TopicBlock]:
    """Single merge pass over blocks."""
    merged: list[TopicBlock] = [blocks[0]]

    for block in blocks[1:]:
        prev = merged[-1]

        # Check if this block should merge into the previous one.
        # Only merge small fragments into an adjacent game block, not
        # two large blocks that happen to mention the same team.
        should_merge = False

        prev_size = prev.end_idx - prev.start_idx
        curr_size = block.end_idx - block.start_idx
        smaller_size = min(prev_size, curr_size)

        # Only consider merging if at least one block is small (< 80 segments)
        if smaller_size < 80:
            # Scale min_mentions by block size — in a 12-segment block,
            # even 1 team mention is significant
            prev_min = 1 if prev_size < 50 else 2
            curr_min = 1 if curr_size < 50 else 2
            prev_teams = set(_find_dominant_teams(
                team_mentions, prev.start_idx, prev.end_idx, min_mentions=prev_min,
            ))
            curr_teams = set(_find_dominant_teams(
                team_mentions, block.start_idx, block.end_idx, min_mentions=curr_min,
            ))
            shared_teams = prev_teams & curr_teams

            if len(shared_teams) >= 2:
                # Two shared teams = clearly same game discussion
                should_merge = True
            elif shared_teams and (prev.block_type == "game" or block.block_type == "game"):
                # One shared team and one is already a game block — absorb fragment
                should_merge = True

        if should_merge:
            # Extend previous block to cover this one, reclassify
            combined_start = prev.start_idx
            combined_end = block.end_idx
            block_type, label, teams, positions = _classify_block(
                team_mentions, pos_mentions, combined_start, combined_end,
            )
            merged[-1] = TopicBlock(
                start_idx=combined_start,
                end_idx=combined_end,
                block_type=block_type,
                label=label,
                teams=teams,
                positions=positions,
            )
        else:
            merged.append(block)

    return merged


def segment_transcript(
    segments: list[dict],
    round_context: RoundContext,
    team_lookup: dict[str, str] | None = None,
) -> list[TopicBlock]:
    """Segment a transcript into topic blocks with scoped player pools.

    Should be called AFTER deterministic corrections (Layer 1) so that
    team names are already cleaned up for reliable detection.

    Returns list of TopicBlock objects covering the entire transcript.
    """
    if not segments:
        return []

    # Build team lookup if not provided
    if team_lookup is None:
        teams_data = _load_teams_data()
        team_lookup = build_team_lookup(teams_data)

    # Detect signals across all segments
    team_mentions = _detect_team_mentions(segments, team_lookup)
    pos_mentions = _detect_position_mentions(segments)
    transitions = _detect_transitions(segments)
    time_gaps = _detect_time_gaps(segments)

    # Find topic boundaries
    boundaries = _find_boundaries(segments, team_mentions, transitions, time_gaps)

    # Build initial blocks from boundaries
    raw_blocks: list[TopicBlock] = []
    for b_idx in range(len(boundaries)):
        start = boundaries[b_idx]
        end = boundaries[b_idx + 1] if b_idx + 1 < len(boundaries) else len(segments)

        block_type, label, teams, positions = _classify_block(
            team_mentions, pos_mentions, start, end,
        )

        raw_blocks.append(TopicBlock(
            start_idx=start,
            end_idx=end,
            block_type=block_type,
            label=label,
            teams=teams,
            positions=positions,
        ))

    # Merge pass: adjacent blocks that share dominant teams belong to
    # the same game discussion (e.g. small position/general fragments
    # between two Cowboys/Tigers blocks should merge into one game block)
    blocks = _merge_related_blocks(raw_blocks, team_mentions, pos_mentions)

    # Scope player pools for final blocks
    for block in blocks:
        block.player_pool = _scope_player_pool(block, round_context)

    return blocks

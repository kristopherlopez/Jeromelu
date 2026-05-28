"""Step 0: Round-level and segment-level context resolution.

Identifies what round a transcript covers, builds a scoped player pool,
and tracks local context (active team/position) as discussion shifts
within the transcript.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# Position keyword → players.yaml position codes
POSITION_KEYWORDS: dict[str, list[str]] = {
    "halfback": ["HFB"],
    "half": ["HFB"],
    "halves": ["HFB", "5/8"],
    "hooker": ["HOK"],
    "dummy half": ["HOK"],
    "fullback": ["FLB"],
    "centre": ["CTW"],
    "centers": ["CTW"],
    "winger": ["CTW"],
    "wing": ["CTW"],
    "outside back": ["CTW", "FLB"],
    "outside backs": ["CTW", "FLB"],
    "back": ["CTW", "FLB"],
    "backs": ["CTW", "FLB"],
    "prop": ["FRF"],
    "front row": ["FRF"],
    "front rower": ["FRF"],
    "second row": ["2RF"],
    "second rower": ["2RF"],
    "edge": ["2RF"],
    "lock": ["LCK"],
    "middle": ["FRF", "LCK"],
    "middles": ["FRF", "LCK"],
    "forward": ["FRF", "2RF", "LCK"],
    "forwards": ["FRF", "2RF", "LCK"],
    "five-eighth": ["5/8"],
    "five eighth": ["5/8"],
    "five-eight": ["5/8"],
    "spine": ["HFB", "5/8", "HOK", "FLB"],
}

# Phrases that signal a game/topic transition
TRANSITION_PATTERNS = [
    r"\bnext\s+(?:game|up|match)\b",
    r"\bmoving\s+on\s+to\b",
    r"\blet'?s\s+(?:look|move|go)\b",
    r"\bnow\s+(?:onto|to|for)\b",
    r"\bonto\s+the\b",
]
_TRANSITION_RE = re.compile("|".join(TRANSITION_PATTERNS), re.IGNORECASE)

# Round number extraction
_ROUND_RE = re.compile(r"(?:round|rd?|r)\s*(\d{1,2})\b", re.IGNORECASE)


@dataclass
class Player:
    name: str
    team: str
    positions: list[str]
    is_primary: bool = False  # from round's teams


@dataclass
class RoundContext:
    round_num: int | None
    teams_playing: list[str]
    bye_teams: list[str]
    primary_players: list[Player]
    secondary_players: list[Player]
    confidence: str  # "round", "partial", "fallback"

    @property
    def all_players(self) -> list[Player]:
        return self.primary_players + self.secondary_players


@dataclass
class LocalContext:
    """Tracks what's being discussed right now in the transcript."""

    # (team_name, segment_idx_when_mentioned)
    _team_mentions: list[tuple[str, int]] = field(default_factory=list)
    # (position_codes, segment_idx_when_mentioned)
    _position_mentions: list[tuple[list[str], int]] = field(default_factory=list)

    # Decay windows (in segments)
    TEAM_DECAY = 15
    POSITION_DECAY = 8

    def update(self, segment_idx: int, text: str, team_lookup: dict[str, str]) -> None:
        """Scan segment text for team/position mentions and update state."""
        text_lower = text.lower()

        # Detect team mentions
        for pattern, canonical in team_lookup.items():
            if pattern in text_lower:
                self._team_mentions.append((canonical, segment_idx))

        # Detect position mentions
        for keyword, codes in POSITION_KEYWORDS.items():
            if keyword in text_lower:
                self._position_mentions.append((codes, segment_idx))

        # Detect transitions — reset context on game/topic change
        if _TRANSITION_RE.search(text):
            # Don't clear entirely, but accelerate decay by shifting timestamps back
            self._team_mentions = [(t, max(0, idx - self.TEAM_DECAY // 2)) for t, idx in self._team_mentions]

    def active_teams(self, current_idx: int) -> list[str]:
        """Return teams mentioned within decay window, most recent first."""
        teams = []
        seen = set()
        for team, idx in reversed(self._team_mentions):
            if current_idx - idx <= self.TEAM_DECAY and team not in seen:
                teams.append(team)
                seen.add(team)
        return teams

    def active_positions(self, current_idx: int) -> list[str]:
        """Return position codes mentioned within decay window."""
        codes = set()
        for pos_codes, idx in reversed(self._position_mentions):
            if current_idx - idx <= self.POSITION_DECAY:
                codes.update(pos_codes)
        return list(codes)

    def boost_score(self, player: Player, current_idx: int) -> float:
        """Return context-based score boost (0.0 - 0.15)."""
        boost = 0.0
        active = self.active_teams(current_idx)
        if active and player.team in active:
            boost += 0.10
        active_pos = self.active_positions(current_idx)
        if active_pos and any(p in active_pos for p in player.positions):
            boost += 0.05
        return boost


def _load_teams(path: Path | None = None) -> dict:
    if path is None:
        path = DATA_DIR / "teams.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_players(path: Path | None = None) -> dict:
    if path is None:
        path = DATA_DIR / "players.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_fixtures(path: Path | None = None) -> dict:
    if path is None:
        path = DATA_DIR / "fixtures.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_team_lookup(teams_data: dict) -> dict[str, str]:
    """Build a lowercase pattern → canonical short name lookup.

    Includes full name, short name, and aliases.
    """
    lookup: dict[str, str] = {}
    for _key, team in teams_data.get("teams", {}).items():
        short = team["short"]
        lookup[team["name"].lower()] = short
        lookup[short.lower()] = short
        for alias in team.get("aliases", []):
            lookup[alias.lower()] = short
    return lookup


def resolve_round(title: str, fixtures_data: dict) -> tuple[int | None, dict | None]:
    """Extract round number from video title and find matching fixture round."""
    m = _ROUND_RE.search(title)
    if not m:
        return None, None

    round_num = int(m.group(1))
    for rd in fixtures_data.get("rounds", []):
        if rd.get("round") == round_num:
            return round_num, rd
    return round_num, None


def build_round_context(
    title: str,
    teams_path: Path | None = None,
    players_path: Path | None = None,
    fixtures_path: Path | None = None,
) -> RoundContext:
    """Build scoped player pool from video title + fixtures."""
    teams_data = _load_teams(teams_path)
    players_data = _load_players(players_path)
    fixtures_data = _load_fixtures(fixtures_path)
    team_lookup = build_team_lookup(teams_data)

    round_num, round_data = resolve_round(title, fixtures_data)

    # Determine which teams are playing this round
    playing_teams: set[str] = set()
    bye_teams_list: list[str] = []

    if round_data:
        for match in round_data.get("matches", []):
            home = match.get("home", "")
            away = match.get("away", "")
            # Resolve to short names
            for team_name in [home, away]:
                short = team_lookup.get(team_name.lower())
                if short:
                    playing_teams.add(short)
                else:
                    # Try partial match
                    for pattern, canonical in team_lookup.items():
                        if pattern in team_name.lower() or team_name.lower() in pattern:
                            playing_teams.add(canonical)
                            break
        for bye_team in round_data.get("byes", []):
            short = team_lookup.get(bye_team.lower())
            bye_teams_list.append(short or bye_team)

    # Build player lists
    primary: list[Player] = []
    secondary: list[Player] = []

    for _team_key, team_info in players_data.get("teams", {}).items():
        team_short = team_info.get("short", team_info.get("name", ""))
        for p in team_info.get("players", []):
            player = Player(
                name=p["name"],
                team=team_short,
                positions=p.get("positions", []),
            )
            if playing_teams and team_short in playing_teams:
                player.is_primary = True
                primary.append(player)
            else:
                secondary.append(player)

    confidence = "round" if round_data else ("partial" if round_num else "fallback")

    return RoundContext(
        round_num=round_num,
        teams_playing=sorted(playing_teams),
        bye_teams=bye_teams_list,
        primary_players=primary,
        secondary_players=secondary,
        confidence=confidence,
    )


def build_local_context(teams_data: dict | None = None) -> tuple[LocalContext, dict[str, str]]:
    """Create a LocalContext and team lookup for segment-level tracking."""
    if teams_data is None:
        teams_data = _load_teams()
    team_lookup = build_team_lookup(teams_data)
    return LocalContext(), team_lookup

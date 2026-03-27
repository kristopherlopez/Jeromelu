"""Layer 2: Phonetic + fuzzy matching against player/team registry.

Uses Double Metaphone for phonetic encoding and Jaro-Winkler for
character-level similarity. Scans segments with n-gram windows to
catch both single-word and multi-word garbles.

Supports topic-block-scoped matching: when topic blocks are provided,
the phonetic index is rebuilt per-block with a tighter player pool,
reducing false positives and enabling higher confidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import jellyfish

from .context import LocalContext, Player, RoundContext
from .segmentation import TopicBlock

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

# Load common words to exclude from candidate matching
def _load_common_words() -> set[str]:
    path = DATA_DIR / "common_words.txt"
    words: set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                words.add(line.lower())
    return words


@dataclass
class PhoneticEntry:
    name: str  # canonical full name
    surname: str  # last word of the name
    team: str
    positions: list[str]
    is_primary: bool
    # Metaphone codes for each word in the name
    word_codes: list[tuple[str | None, str | None]]
    # Full name as single string for Jaro-Winkler
    name_lower: str


@dataclass
class MatchResult:
    candidate: str  # the text that was matched
    matched_name: str  # the canonical name it matched to
    score: float
    team: str
    method: str  # "phonetic"


def _metaphone_pair(word: str) -> tuple[str | None, str | None]:
    """Get Double Metaphone codes for a word."""
    try:
        codes = jellyfish.metaphone(word)
        return (codes, None)
    except Exception:
        return (None, None)


def build_phonetic_index(context: RoundContext) -> list[PhoneticEntry]:
    """Build phonetic index from the scoped player pool."""
    entries: list[PhoneticEntry] = []

    for player in context.all_players:
        name = player.name
        words = name.replace("'", "").replace("-", " ").split()
        word_codes = [_metaphone_pair(w) for w in words]
        surname = words[-1] if words else name

        entries.append(PhoneticEntry(
            name=name,
            surname=surname,
            team=player.team,
            positions=player.positions,
            is_primary=player.is_primary,
            word_codes=word_codes,
            name_lower=name.lower(),
        ))

    return entries


def _compute_score(
    candidate: str,
    entry: PhoneticEntry,
    match_mode: str,  # "full" or "surname"
) -> float:
    """Compute similarity score between a candidate string and a phonetic entry.

    Weighted combination of:
    - Metaphone match (0.4)
    - Jaro-Winkler similarity (0.4)
    - Length ratio (0.2)
    """
    target = entry.name_lower if match_mode == "full" else entry.surname.lower()
    cand_lower = candidate.lower()

    # Jaro-Winkler similarity (0-1)
    jw = jellyfish.jaro_winkler_similarity(cand_lower, target)

    # Length ratio — reject if wildly different
    len_ratio = min(len(cand_lower), len(target)) / max(len(cand_lower), len(target), 1)
    if len_ratio < 0.5:
        return 0.0

    # Metaphone comparison
    cand_words = candidate.replace("'", "").replace("-", " ").split()
    target_codes = entry.word_codes if match_mode == "full" else entry.word_codes[-1:]
    cand_codes = [_metaphone_pair(w) for w in cand_words]

    metaphone_score = 0.0
    if cand_codes and target_codes:
        matches = 0
        comparisons = min(len(cand_codes), len(target_codes))
        for i in range(comparisons):
            cc = cand_codes[i][0]
            tc = target_codes[i][0]
            if cc and tc and cc == tc:
                matches += 1
            elif cc and tc:
                # Partial metaphone match via Jaro-Winkler on the codes
                code_sim = jellyfish.jaro_winkler_similarity(cc, tc)
                if code_sim > 0.8:
                    matches += 0.7
        metaphone_score = matches / max(comparisons, 1)

    return (0.4 * metaphone_score) + (0.4 * jw) + (0.2 * len_ratio)


# Contractions and short function words that should never be name candidates
_CONTRACTION_RE = re.compile(r"'[smdtvre]$|'ve$|'ll$|'re$|n't$", re.IGNORECASE)
_SENTENCE_STARTERS = {
    "i", "he", "she", "we", "they", "it", "you", "my", "his", "her",
    "our", "their", "its", "this", "that", "these", "those", "what",
    "who", "how", "when", "where", "why", "which", "there", "here",
    "so", "but", "and", "or", "if", "then", "now", "well", "yeah",
    "yes", "no", "not", "just", "also", "too", "very", "really",
    "okay", "ok", "sure", "right", "like", "super", "pretty",
}


_COMMON_FIRST_NAMES = {
    "chris", "ryan", "ben", "sam", "tom", "matt", "jack", "joe", "dan",
    "mark", "mike", "luke", "josh", "adam", "james", "john", "david",
    "paul", "nick", "alex", "will", "max", "jake", "cam", "pat", "daly",
    "harry", "casey", "blake", "jesse", "brad", "cooper", "liam",
    "ethan", "connor", "sean", "shane", "steve", "aaron", "kyle",
    "dale", "wade", "dean", "ray", "bailey", "beau", "braydon",
    "jayden", "dylan", "kalyn", "herbie", "spencer", "braden",
    "jackson", "daniel", "mitchell", "matthew", "brandon", "nathan",
    "reece", "isaac", "fletcher", "morgan", "trent", "keano",
    "jacob", "isaiah", "daine", "payne", "selwyn", "patrick",
    "stuart", "scott", "kevin", "peter", "andrew", "stephen",
    "martin", "wayne", "craig", "keith", "ricky", "tony",
    "tommy", "billy", "bobby", "johnny", "kenny", "terry",
}

# NRL nicknames and short forms that should NOT be corrected
_KNOWN_NICKNAMES = {
    "teddy", "turbo", "patty", "ponga", "munny", "munster", "latrell",
    "cody", "foggy", "herby", "timo", "walshie", "walshy",
    "cleary", "papi", "papz", "haasy", "hasler", "madge",
    "rabs", "blocker", "freddy", "joey", "gus", "brandy",
    "fletch", "hindy", "hodgo", "braith", "vonny", "lara",
    "papy", "kikau", "kiku", "robbo", "belly", "payney",
    "critter", "grub",
}


def _is_candidate(words: list[str], start: int, end: int, common_words: set[str]) -> bool:
    """Check if an n-gram is worth testing as a name candidate.

    Must have at least one capitalized word that:
    - Isn't a common English word or NRL term
    - Doesn't contain a contraction ('s, 'm, 're, etc.)
    - Isn't a sentence-start function word
    - Is at least 3 chars long (after stripping punctuation)
    - Any word in the span containing a contraction disqualifies the whole span
    """
    span = words[start:end]

    # If ANY word in the span has a contraction, reject the whole span
    for w in span:
        clean = re.sub(r"[^\w']", "", w)
        if _CONTRACTION_RE.search(clean):
            return False

    valid_name_words = 0
    total_words = 0

    for w in span:
        clean = re.sub(r"[^\w']", "", w)
        if not clean or len(clean) < 3:
            continue
        total_words += 1

        if clean.lower() in common_words:
            continue
        if clean.lower() in _SENTENCE_STARTERS:
            continue
        if len(span) == 1 and clean.lower() in _COMMON_FIRST_NAMES:
            continue
        if clean[0].islower():
            continue
        if clean.startswith(">>"):
            continue

        valid_name_words += 1

    if valid_name_words == 0:
        return False

    # For multi-word n-grams, require that at least half the words
    # look like name candidates (not just one name word buried in filler)
    if len(span) >= 2 and total_words >= 2:
        if valid_name_words / total_words < 0.5:
            return False

    return True


def _extract_known_names(context: RoundContext) -> set[str]:
    """Build a set of known player names (lowercase) to skip during matching.

    For PRIMARY players (block-scoped teams), adds all name parts
    (first name, surname, hyphenated parts) so the matcher won't
    try to "correct" a word that's already a real player name in
    this block's context. e.g. "Terrell" (Terrell May, Tigers) won't
    be matched to "Stanley-Traill" during a Cowboys vs Tigers block.

    For secondary players, only adds full name and surname (to avoid
    blocking legitimate corrections across different team contexts).
    """
    known: set[str] = set()
    for p in context.all_players:
        known.add(p.name.lower())
        parts = p.name.split()
        if p.is_primary:
            # Add every name part for primary players
            for part in parts:
                for sub in part.split("-"):
                    if len(sub) >= 3:
                        known.add(sub.lower())
        else:
            # Only add surname for secondary players
            if len(parts) > 1:
                known.add(parts[-1].lower())
    return known


def _clean_word(w: str) -> str:
    """Strip punctuation from word for matching purposes."""
    return re.sub(r"[,.\!?;:\"']+$", "", re.sub(r"^[\"']+", "", w))


def _is_name_word(w: str, common_words: set[str]) -> bool:
    """Check if a single word looks like it could be (part of) a name."""
    clean = _clean_word(w)
    if len(clean) < 3:
        return False
    if not clean[0].isupper():
        return False
    if _CONTRACTION_RE.search(clean):
        return False
    low = clean.lower()
    if low in common_words or low in _SENTENCE_STARTERS or low in _COMMON_FIRST_NAMES:
        return False
    return True


def scan_segment(
    seg_idx: int,
    text: str,
    index: list[PhoneticEntry],
    known_names: set[str],
    common_words: set[str],
    local_context: LocalContext,
    round_context: RoundContext,
    threshold: float = 0.85,
    flag_threshold: float = 0.78,
    min_word_len: int = 4,
    min_surname_len: int = 5,
) -> tuple[str, list[dict]]:
    """Scan a segment for potential name garbles and return corrected text + records.

    Strategy: find individual words that look like garbled names, then check
    if they pair with adjacent words to form a full-name match.

    min_word_len and min_surname_len can be lowered inside well-scoped
    game blocks where context provides the confidence that length
    normally provides.

    Returns (corrected_text, list_of_correction_records).
    """
    words = text.split()
    if not words:
        return text, []

    records: list[dict] = []
    replacements: list[tuple[str, str]] = []

    consumed: set[int] = set()

    # Short words (3-4 chars) in game blocks get extra scrutiny —
    # they must not look like common English words even if capitalised
    _SHORT_WORD_BLOCKLIST = {
        "yes", "yep", "yea", "nah", "nup", "hey", "lol", "wow", "hmm",
        "got", "get", "got", "put", "set", "let", "run", "ran", "hit",
        "cut", "sit", "sat", "bit", "lot", "end", "add", "did", "had",
        "has", "was", "are", "can", "may", "own", "use", "try", "say",
        "see", "new", "old", "big", "low", "top", "few", "bad", "far",
        "hard", "sure", "call", "take", "give", "make", "come", "keep",
        "find", "tell", "want", "feel", "mean", "play", "look", "help",
        "show", "talk", "turn", "move", "live", "long", "high", "last",
        "next", "same", "real", "full", "main", "base", "love", "drop",
        "pick", "hold", "rest", "miss", "lose", "lost", "win", "won",
        "role", "side", "done", "able", "goes", "type", "else", "best",
        "also", "only", "even", "more", "much", "many", "some", "most",
        "very", "than", "over", "into", "each", "from", "with", "they",
        "them", "that", "this", "what", "when", "will", "been", "have",
        "your", "were", "here", "just", "then", "than", "back", "down",
        "like", "well", "know", "good", "time", "way", "work",
        "him", "her", "his", "hid", "sim", "rob", "sup", "hub",
        "too", "half", "spot", "start", "easy", "tough", "weak",
    }

    for i, word in enumerate(words):
        if i in consumed:
            continue

        clean_w = _clean_word(word)
        if len(clean_w) < min_word_len:
            continue

        # Skip if it's a common/function word (even if capitalized)
        low = clean_w.lower()
        if low in common_words or low in _SENTENCE_STARTERS or low in _COMMON_FIRST_NAMES:
            continue
        if _CONTRACTION_RE.search(clean_w):
            continue

        # Extra filter for short words (3-4 chars) — block common English
        if len(clean_w) <= 4 and low in _SHORT_WORD_BLOCKLIST:
            continue

        # Skip if it's already a known correct name
        if low in known_names:
            continue

        # Skip known nicknames
        if low in _KNOWN_NICKNAMES:
            continue

        # Must be capitalized to be a name candidate
        if not clean_w[0].isupper():
            continue

        # Try 2-word match first (FirstName LastName), then 1-word (surname only)
        best_match: MatchResult | None = None
        best_score = 0.0
        best_span = 1  # how many words the match covers

        # --- Try 2-word candidate (i, i+1) ---
        skip_one_word = False
        if i + 1 < len(words) and i + 1 not in consumed:
            w2 = _clean_word(words[i + 1])
            two_word = f"{clean_w} {w2}"

            if len(w2) >= 3 and two_word.lower() not in known_names:
                for entry in index:
                    score = _compute_score(two_word, entry, "full")
                    score += _apply_boosts(entry, local_context, seg_idx)
                    if score > best_score:
                        best_score = score
                        best_match = MatchResult(
                            candidate=two_word,
                            matched_name=entry.name,
                            score=score,
                            team=entry.team,
                            method="phonetic",
                        )
                        best_span = 2
            elif two_word.lower() in known_names:
                # This word pairs with the next to form a known player name
                # (e.g. "Terrell May") — don't try to match it solo either
                skip_one_word = True

        # --- Try 1-word candidate (surname match) ---
        one_word_match: MatchResult | None = None
        one_word_score = 0.0

        if len(clean_w) >= min_surname_len and not skip_one_word:
            for entry in index:
                # Skip hyphenated surnames for single-word matches
                # (e.g., "Blake" should not match "Fonua-Blake")
                if "-" in entry.surname or "'" in entry.surname:
                    continue
                score = _compute_score(clean_w, entry, "surname")
                score += _apply_boosts(entry, local_context, seg_idx)
                if score > one_word_score:
                    one_word_score = score
                    one_word_match = MatchResult(
                        candidate=clean_w,
                        matched_name=entry.name,
                        score=score,
                        team=entry.team,
                        method="phonetic",
                    )

        # Pick the better of 2-word vs 1-word
        if one_word_score > best_score:
            best_score = one_word_score
            best_match = one_word_match
            best_span = 1

        if not best_match:
            continue

        # Short candidates (3-4 chars) need a higher score to auto-apply
        # because the phonetic/JW space is denser for short strings
        effective_threshold = threshold
        effective_flag = flag_threshold
        if len(best_match.candidate) <= 4 and best_span == 1:
            effective_threshold = max(threshold, 0.92)
            effective_flag = max(flag_threshold, 0.82)

        if best_score >= effective_threshold:
            if best_span == 1:
                # Surname-only: replace just the surname
                parts = best_match.matched_name.split()
                replacement = parts[-1] if parts else best_match.matched_name
                original = word  # preserve original punctuation context
                # But replace just the clean part
                replacement_in_context = word.replace(clean_w, replacement)
            else:
                replacement = best_match.matched_name
                original = " ".join(words[i:i + best_span])
                replacement_in_context = replacement

            replacements.append((original, replacement_in_context))
            for j in range(i, i + best_span):
                consumed.add(j)

            records.append({
                "segment_idx": seg_idx,
                "original": best_match.candidate,
                "corrected": replacement,
                "confidence": "MEDIUM",
                "score": round(best_score, 3),
                "method": "phonetic",
                "matched_full_name": best_match.matched_name,
                "team": best_match.team,
            })
        elif best_score >= effective_flag:
            records.append({
                "segment_idx": seg_idx,
                "original": best_match.candidate,
                "corrected": None,
                "confidence": "LOW",
                "score": round(best_score, 3),
                "method": "phonetic",
                "best_match": best_match.matched_name,
                "team": best_match.team,
            })

    # Apply replacements to text
    corrected = text
    for original, replacement in replacements:
        corrected = corrected.replace(original, replacement, 1)

    return corrected, records


def _apply_boosts(
    entry: PhoneticEntry,
    local_context: LocalContext,
    seg_idx: int,
) -> float:
    """Compute all contextual boosts for an entry."""
    boost = 0.0
    if entry.is_primary:
        boost += 0.03
    player = Player(
        name=entry.name,
        team=entry.team,
        positions=entry.positions,
    )
    boost += local_context.boost_score(player, seg_idx)
    return boost


def scan_all_segments(
    segments: list[dict],
    index: list[PhoneticEntry],
    round_context: RoundContext,
    local_context: LocalContext,
    team_lookup: dict[str, str],
    threshold: float = 0.85,
    flag_threshold: float = 0.70,
    topic_blocks: list[TopicBlock] | None = None,
) -> list[dict]:
    """Run phonetic matching across all segments with local context tracking.

    When topic_blocks are provided, rebuilds the phonetic index per-block
    using each block's scoped player pool. Within well-scoped blocks
    (game/position), the is_primary boost applies to block-relevant players.

    Modifies segments in-place and returns correction records.
    """
    common_words = _load_common_words()
    all_records: list[dict] = []

    if topic_blocks:
        for block in topic_blocks:
            # Build a block-scoped phonetic index and known names
            block_context = RoundContext(
                round_num=round_context.round_num,
                teams_playing=block.teams or round_context.teams_playing,
                bye_teams=round_context.bye_teams,
                primary_players=[p for p in block.player_pool if p.is_primary],
                secondary_players=[p for p in block.player_pool if not p.is_primary],
                confidence=round_context.confidence,
            )
            block_index = build_phonetic_index(block_context)
            # Known names are block-scoped: primary players' first+last
            # names are protected only within their block's teams
            block_known_names = _extract_known_names(block_context)

            # In well-scoped game blocks, lower the min word/surname
            # length — context provides the confidence that length
            # normally provides (e.g. "Ple" → "Pole" in a Tigers block)
            block_min_word = 3 if block.block_type == "game" else 4
            block_min_surname = 3 if block.block_type == "game" else 5

            for seg_idx in range(block.start_idx, block.end_idx):
                seg = segments[seg_idx]
                text = seg["text"]
                local_context.update(seg_idx, text, team_lookup)

                corrected, records = scan_segment(
                    seg_idx=seg_idx,
                    text=text,
                    index=block_index,
                    known_names=block_known_names,
                    common_words=common_words,
                    local_context=local_context,
                    round_context=block_context,
                    threshold=threshold,
                    flag_threshold=flag_threshold,
                    min_word_len=block_min_word,
                    min_surname_len=block_min_surname,
                )

                # Tag records with the block they came from
                for rec in records:
                    rec["block_label"] = block.label
                    rec["block_type"] = block.block_type

                seg["text"] = corrected
                all_records.extend(records)
    else:
        # Fallback: no segmentation, scan linearly (original behavior)
        known_names = _extract_known_names(round_context)
        for seg_idx, seg in enumerate(segments):
            text = seg["text"]
            local_context.update(seg_idx, text, team_lookup)

            corrected, records = scan_segment(
                seg_idx=seg_idx,
                text=text,
                index=index,
                known_names=known_names,
                common_words=common_words,
                local_context=local_context,
                round_context=round_context,
                threshold=threshold,
                flag_threshold=flag_threshold,
            )

            seg["text"] = corrected
            all_records.extend(records)

    return all_records

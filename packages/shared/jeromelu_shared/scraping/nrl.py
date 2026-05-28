"""NRL SuperCoach scraping utilities.

Shared team-code mapping, name normalization, and deterministic player ID
generation. Originally split out of the worker-scraper activities (which
were retired and deleted 2026-05-28); now used by the Scout pipelines
under ``services/api/app/scout/``.
"""

import hashlib
import re

# Map every known 3-letter team code to its canonical name.
TEAM_CODE_MAP = {
    "BRO": "Broncos", "BUL": "Bulldogs", "CBR": "Raiders",
    "DOL": "Dolphins", "DRA": "Dragons", "EEL": "Eels",
    "KNI": "Knights", "COW": "Cowboys", "MAN": "Sea Eagles",
    "MEL": "Storm", "PAN": "Panthers", "PAR": "Eels",
    "RAB": "Rabbitohs", "ROO": "Roosters", "SHA": "Sharks",
    "TIG": "Tigers", "TIT": "Titans", "WAR": "Warriors",
    "NQL": "Cowboys", "NEW": "Knights", "CRO": "Sharks",
    "SOU": "Rabbitohs", "SYD": "Roosters", "GLD": "Titans",
    "NZL": "Warriors", "WES": "Tigers", "CAN": "Raiders",
    "STG": "Dragons", "PEN": "Panthers", "BRI": "Broncos",
    "WST": "Tigers", "GCT": "Titans", "MNL": "Sea Eagles",
    "NQC": "Cowboys", "PTH": "Panthers", "STH": "Rabbitohs",
}


def normalize_team(team: str) -> str:
    """Resolve a 3-letter code or raw string to a canonical team name."""
    code = team.strip().upper()
    if code in TEAM_CODE_MAP:
        return TEAM_CODE_MAP[code]
    return team.strip()


def clean_name(name: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    clean = re.sub(r"<[^>]+>", "", name).strip()
    return re.sub(r"\s+", " ", clean)


def normalize_name(name: str) -> str:
    """Convert 'LastName, FirstName' to 'FirstName LastName'."""
    if "," in name:
        parts = name.split(",", 1)
        return f"{parts[1].strip()} {parts[0].strip()}"
    return name


def parse_int(value) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(re.sub(r"[,$]", "", str(value).strip()))
    except (ValueError, AttributeError):
        return 0


def parse_float(value) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(re.sub(r"[,$]", "", str(value).strip()))
    except (ValueError, AttributeError):
        return 0.0


# jqGrid key → (db_column, parser). Single source of truth for stat extraction.
# Values are SC points, not raw stat counts (e.g. TR=34 = 2 tries × 17pts).
JQGRID_COLUMN_MAP: dict[str, tuple[str, callable]] = {
    # SC Breakdown
    "Base": ("base", parse_int),
    "Attack": ("attack", parse_int),
    "Playmaking": ("playmaking", parse_int),
    "Power": ("power", parse_int),
    "Negative": ("negative", parse_int),
    # Scoring
    "TR": ("tries", parse_int),
    "TS": ("try_assists", parse_int),
    "GO": ("goals", parse_int),
    "MG": ("missed_goals", parse_int),
    "FG": ("field_goals", parse_int),
    "MF": ("missed_field_goals", parse_int),
    # Attack
    "LB": ("line_breaks", parse_int),
    "LA": ("line_break_assists", parse_int),
    "LT": ("last_touch", parse_int),
    "TB": ("tackle_busts", parse_int),
    "OL": ("offloads", parse_int),
    "IO": ("ineffective_offloads", parse_int),
    "H8": ("hitups_8m", parse_int),
    "HU": ("hitups_under_8m", parse_int),
    "KB": ("kick_metres", parse_int),
    # Defence
    "TA": ("tackles_made", parse_int),
    "MT": ("missed_tackles", parse_int),
    "IT": ("intercepts", parse_int),
    # Discipline
    "FD": ("forced_dropouts", parse_int),
    "FT": ("forty_twentys", parse_int),
    "KD": ("kicked_dead", parse_int),
    "PC": ("penalties", parse_int),
    "ER": ("errors", parse_int),
    "SS": ("sin_bins", parse_int),
    "HG": ("handover_given", parse_int),
    # Derived
    "PPM": ("ppm", parse_float),
    "BPPM": ("base_ppm", parse_float),
    "BasePower": ("base_power", parse_int),
    "BasePowerPPM": ("base_power_ppm", parse_float),
    # Averages
    "AvgScore": ("avg_score", parse_float),
    "TwoRdAvg": ("two_rd_avg", parse_float),
    "ThreeRdAvg": ("three_rd_avg", parse_float),
    "FiveRdAvg": ("five_rd_avg", parse_float),
    "SeasonAvg": ("season_avg", parse_float),
    # Percentages
    "H8percent": ("hitup_8m_pct", parse_float),
    "TBPERCENT": ("tackle_bust_pct", parse_float),
    "MTPERCENT": ("missed_tackle_pct", parse_float),
    "OLILPERCENT": ("offload_involvement_pct", parse_float),
    "BasePercent": ("base_pct", parse_float),
    # Price
    "StartPrice": ("start_price", parse_int),
    "EndPrice": ("end_price", parse_int),
    "RoundPriceChange": ("round_price_change", parse_int),
    "SeasonPriceChange": ("season_price_change", parse_int),
    "MagicNumber": ("magic_number", parse_int),
    # Context
    "vs": ("opposition", str),
    "Venue": ("venue", str),
    "weather": ("weather", str),
    "Surface": ("surface", str),
    "Jersey": ("jersey", parse_int),
    "ByeRd": ("bye_round", str),
}

# DB columns derived from the map, for use in persist logic.
STAT_DB_COLUMNS = [col for col, _ in JQGRID_COLUMN_MAP.values()]


def extract_all_stats(row: dict) -> dict:
    """Extract all mapped stats from a jqGrid row.

    Returns a dict keyed by DB column name with parsed values.
    Skips keys not present in the row; returns None for empty strings.
    """
    stats: dict = {}
    for jq_key, (db_col, parser) in JQGRID_COLUMN_MAP.items():
        val = row.get(jq_key)
        if val is None or (isinstance(val, str) and val.strip() == ""):
            stats[db_col] = None
            continue
        if parser is str:
            stats[db_col] = str(val).strip()
        else:
            parsed = parser(val)
            stats[db_col] = parsed if parsed != 0 else parsed  # keep explicit zeros
    return stats


def generate_player_id(name: str, team: str) -> int:
    """Deterministic 32-bit integer ID from player name + team.

    Uses MD5 truncated to 31 bits (positive signed int32).
    Will be replaced with real Supercoach IDs when API auth is available.
    """
    key = f"{name.strip().lower()}|{team.strip().lower()}"
    digest = hashlib.md5(key.encode()).hexdigest()
    return int(digest[:8], 16) & 0x7FFFFFFF

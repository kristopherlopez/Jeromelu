"""Validate scraped data before writing to the combined dataset."""

import logging

from temporalio import activity

logger = logging.getLogger(__name__)

EXPECTED_ROW_RANGE = (200, 700)

SCORE_RANGE = (0, 250)
PRICE_RANGE = (100_000, 900_000)
MINUTES_RANGE = (0, 80)
TRIES_RANGE = (0, 102)       # Max ~6 tries × 17pts
TACKLES_RANGE = (0, 150)     # High-tackling lock
LINE_BREAKS_RANGE = (0, 60)  # ~5 LBs × 12pts

REQUIRED_FIELDS = {
    "scores": ["player_id", "score"],
    "prices": ["player_id", "price"],
    "teamlists": ["player_id", "team"],
}


@activity.defn
async def validate_data(scrape_type: str, fetch_result: dict) -> dict:
    """Validate scraped data.

    Checks:
    - Row count within expected range
    - No nulls in required fields
    - Value ranges (scores, prices, minutes)
    - No duplicate player_ids

    Returns dict with keys: valid (bool), errors (list of str).
    """
    errors = []
    rows = fetch_result.get("rows", [])
    row_count = len(rows)

    # Row count check
    min_rows, max_rows = EXPECTED_ROW_RANGE
    if row_count < min_rows or row_count > max_rows:
        errors.append(f"Row count {row_count} outside expected range {EXPECTED_ROW_RANGE}")

    # Required fields null check
    required = REQUIRED_FIELDS.get(scrape_type, [])
    for field in required:
        nulls = sum(1 for r in rows if r.get(field) is None)
        if nulls > 0:
            errors.append(f"{nulls} null values in required field '{field}'")

    # Duplicate check
    player_ids = [r.get("player_id") for r in rows]
    dupes = len(player_ids) - len(set(pid for pid in player_ids if pid is not None))
    if dupes > 0:
        errors.append(f"{dupes} duplicate player_ids found")

    # Range checks
    for row in rows:
        if scrape_type == "scores" and row.get("score") is not None:
            if not (SCORE_RANGE[0] <= row["score"] <= SCORE_RANGE[1]):
                errors.append(f"Score {row['score']} out of range for player {row.get('player_id')}")

        if scrape_type == "prices" and row.get("price") is not None:
            if not (PRICE_RANGE[0] <= row["price"] <= PRICE_RANGE[1]):
                errors.append(f"Price {row['price']} out of range for player {row.get('player_id')}")

        if row.get("minutes") is not None:
            if not (MINUTES_RANGE[0] <= row["minutes"] <= MINUTES_RANGE[1]):
                errors.append(f"Minutes {row['minutes']} out of range for player {row.get('player_id')}")

        if row.get("tries") is not None:
            if not (TRIES_RANGE[0] <= row["tries"] <= TRIES_RANGE[1]):
                errors.append(f"Tries {row['tries']} out of range for player {row.get('player_id')}")

        if row.get("tackles_made") is not None:
            if not (TACKLES_RANGE[0] <= row["tackles_made"] <= TACKLES_RANGE[1]):
                errors.append(f"Tackles {row['tackles_made']} out of range for player {row.get('player_id')}")

        if row.get("line_breaks") is not None:
            if not (LINE_BREAKS_RANGE[0] <= row["line_breaks"] <= LINE_BREAKS_RANGE[1]):
                errors.append(f"Line breaks {row['line_breaks']} out of range for player {row.get('player_id')}")

    result = {"valid": len(errors) == 0, "errors": errors}

    if errors:
        logger.warning("Validation failed for %s: %s", scrape_type, errors)
    else:
        logger.info("Validation passed for %s (%d rows)", scrape_type, row_count)

    return result

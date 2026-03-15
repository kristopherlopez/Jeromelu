"""Persist scraped player data to the player_rounds table."""

import logging

from sqlalchemy.dialects.postgresql import insert
from temporalio import activity

from jeromelu_shared.db import SessionLocal
from jeromelu_shared.db.models import PlayerRound
from jeromelu_shared.scraping.nrl import STAT_DB_COLUMNS

logger = logging.getLogger(__name__)

# Identity + existing columns always present in upsert
_IDENTITY_COLUMNS = ["player_id", "player_name", "team", "position", "round", "season"]
_BASE_COLUMNS = ["score", "price", "breakeven", "minutes", "selected_pct"]
# All columns that get updated on conflict (everything except identity PK fields)
_UPDATE_COLUMNS = ["player_name", "team", "position", "score", "price",
                   "breakeven", "minutes", "selected_pct"] + STAT_DB_COLUMNS


@activity.defn
def persist_player_rounds(scrape_type: str, round: int, season: int, rows: list[dict]) -> dict:
    """Upsert rows into player_rounds.

    Uses INSERT ... ON CONFLICT (player_id, round, season) DO UPDATE
    so re-runs are idempotent. Column list derived from JQGRID_COLUMN_MAP.
    """
    if not rows:
        logger.warning("No rows to persist for %s round %d season %d", scrape_type, round, season)
        return {"upserted": 0}

    # Build values for bulk upsert
    values = []
    for row in rows:
        record = {
            "player_id": row["player_id"],
            "player_name": row["player_name"],
            "team": row["team"],
            "position": row.get("position", ""),
            "round": round,
            "season": season,
            "score": row.get("score"),
            "price": row.get("price"),
            "breakeven": row.get("breakeven"),
            "minutes": row.get("minutes"),
            "selected_pct": row.get("selected_pct"),
        }
        # Add all stat columns from the mapping
        for col in STAT_DB_COLUMNS:
            record[col] = row.get(col)
        values.append(record)

    stmt = insert(PlayerRound).values(values)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_player_round_season",
        set_={col: stmt.excluded[col] for col in _UPDATE_COLUMNS},
    )

    session = SessionLocal()
    try:
        session.execute(stmt)
        session.commit()
        logger.info("Upserted %d rows into player_rounds for %s round %d season %d",
                     len(values), scrape_type, round, season)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    return {"upserted": len(values)}

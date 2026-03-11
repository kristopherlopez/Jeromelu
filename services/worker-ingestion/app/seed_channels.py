"""Seed the channels table from sources.yaml. Safe to re-run (upserts)."""

import logging
import sys
from pathlib import Path

import yaml
from sqlalchemy import text

from jeromelu_shared.db import engine

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SOURCES_FILE = Path(__file__).resolve().parents[3] / "sources.yaml"

UPSERT_SQL = text("""
    INSERT INTO channels (slug, platform, external_id, name, url, description, quality_rating, tags, active)
    VALUES (:slug, :platform, :external_id, :name, :url, :description, :quality_rating, :tags, :active)
    ON CONFLICT (slug) DO NOTHING
""")


def seed():
    if not SOURCES_FILE.exists():
        logger.error("sources.yaml not found at %s", SOURCES_FILE)
        sys.exit(1)

    with open(SOURCES_FILE) as f:
        data = yaml.safe_load(f)

    sources = data.get("sources", [])
    inserted = 0
    skipped = 0

    with engine.begin() as conn:
        for src in sources:
            result = conn.execute(UPSERT_SQL, {
                "slug": src["id"],
                "platform": src["type"],
                "external_id": src.get("channel_id"),
                "name": src["name"],
                "url": src.get("url"),
                "description": src.get("description"),
                "quality_rating": src.get("quality_rating", 5),
                "tags": src.get("tags", []),
                "active": src.get("active", True),
            })
            if result.rowcount > 0:
                inserted += 1
            else:
                skipped += 1

    logger.info("Done: %d inserted, %d skipped (already exist)", inserted, skipped)


if __name__ == "__main__":
    seed()

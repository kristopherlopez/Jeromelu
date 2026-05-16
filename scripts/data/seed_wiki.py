"""Seed wiki pages from existing entities and knowledge base entries.

Idempotent: skips entities that already have slugs and pages that already exist.

Usage:
    cd services/api
    source .venv/Scripts/activate   # Windows
    python ../../scripts/data/seed_wiki.py
"""

import os
import re
import sys
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Ensure shared package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "shared"))

from jeromelu_shared.db.models import (
    Channel,
    Entity,
    KnowledgeBase,
    WikiPage,
    WikiRevision,
)


def get_db_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://jeromelu:jeromelu@localhost:5432/jeromelu",
    )


def slugify(name: str) -> str:
    """Convert a canonical name to a URL-safe slug."""
    s = name.lower().strip()
    s = re.sub(r"[''`]", "", s)        # remove apostrophes
    s = re.sub(r"[^a-z0-9]+", "-", s)  # non-alphanum → hyphens
    s = re.sub(r"-+", "-", s)          # collapse runs
    return s.strip("-")


def main():
    engine = create_engine(get_db_url())
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()

    try:
        # ------------------------------------------------------------------
        # 1. Generate slugs for entities that don't have one
        # ------------------------------------------------------------------
        entities = db.query(Entity).filter(Entity.slug.is_(None)).all()
        slug_count = 0
        existing_slugs: set[str] = set(
            r[0] for r in db.query(Entity.slug).filter(Entity.slug.isnot(None)).all()
        )

        for entity in entities:
            base = slugify(entity.canonical_name)
            slug = base
            counter = 2
            while slug in existing_slugs:
                slug = f"{base}-{counter}"
                counter += 1
            entity.slug = slug
            existing_slugs.add(slug)
            slug_count += 1

        if slug_count:
            db.flush()
            print(f"  Generated slugs for {slug_count} entities")

        # ------------------------------------------------------------------
        # 2. Create advisor entities from channels
        # ------------------------------------------------------------------
        channels = db.query(Channel).filter(Channel.active.is_(True)).all()
        advisor_count = 0

        for ch in channels:
            # Check if an advisor entity already exists for this channel
            existing = (
                db.query(Entity)
                .filter(Entity.entity_type == "advisor")
                .filter(Entity.canonical_name == ch.name)
                .first()
            )
            if existing:
                continue

            slug = slugify(ch.name)
            counter = 2
            while slug in existing_slugs:
                slug = f"{slugify(ch.name)}-{counter}"
                counter += 1

            advisor = Entity(
                entity_type="advisor",
                canonical_name=ch.name,
                aliases=[ch.slug] if ch.slug != slugify(ch.name) else [],
                slug=slug,
                metadata_json={"channel_id": str(ch.channel_id), "platform": ch.platform},
            )
            db.add(advisor)
            existing_slugs.add(slug)
            advisor_count += 1

        if advisor_count:
            db.flush()
            print(f"  Created {advisor_count} advisor entities from channels")

        # ------------------------------------------------------------------
        # 3. Create wiki pages for player, team, and advisor entities
        # ------------------------------------------------------------------
        page_types = ("player", "team", "advisor")
        wiki_entities = (
            db.query(Entity)
            .filter(Entity.entity_type.in_(page_types))
            .filter(Entity.slug.isnot(None))
            .all()
        )

        # Get existing wiki page slugs to skip
        existing_page_slugs: set[str] = set(
            r[0] for r in db.query(WikiPage.slug).all()
        )

        # Pre-load KB entries for seeding content
        kb_summaries: dict[str, str] = {}   # entity_id → content
        kb_opinions: dict[str, str] = {}    # entity_id → content

        for kb in db.query(KnowledgeBase).filter(
            KnowledgeBase.kb_type.in_(["player_summary", "opinion"])
        ).all():
            eid = str(kb.subject_entity_id)
            if kb.kb_type == "player_summary":
                kb_summaries[eid] = kb.content
            elif kb.kb_type == "opinion":
                kb_opinions[eid] = kb.content

        page_count = 0
        for entity in wiki_entities:
            if entity.slug in existing_page_slugs:
                continue

            eid = str(entity.entity_id)
            sections = []
            status = "stub"

            # Seed from KB entries
            if eid in kb_summaries:
                sections.append(f"## Overview\n\n{kb_summaries[eid]}")
                status = "draft"
            if eid in kb_opinions:
                sections.append(f"## Jerome's Take\n\n{kb_opinions[eid]}")
                status = "draft"

            content = "\n\n".join(sections)
            summary_text = kb_summaries.get(eid, "")[:200] if eid in kb_summaries else None

            page = WikiPage(
                entity_id=entity.entity_id,
                page_type=entity.entity_type,
                slug=entity.slug,
                title=entity.canonical_name,
                content=content,
                summary=summary_text,
                status=status,
            )
            db.add(page)
            db.flush()

            # Create initial revision
            rev = WikiRevision(
                page_id=page.page_id,
                summary="Initial page seeded from knowledge base" if content else "Stub page created",
                source_trigger="seed_wiki.py",
            )
            db.add(rev)
            page_count += 1

        db.commit()
        print(f"  Created {page_count} wiki pages")
        print("Done.")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

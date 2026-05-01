"""One-shot fix: resolve any youtube channels with external_id like '@handle'
to their canonical 'UC...' id, plus refresh url/logo_url and seed a
channel_metrics row if missing.

Background: refresh.py's _uploads_playlist_id derives the uploads playlist
from a UC id (UC... -> UU...) and refuses '@handle' ids. Anything filed
before validate_channel was added to handle_persist_candidate may have a
handle in external_id and would fail a single-channel refresh.

Run with the api venv active:
    cd services/api && python scripts/canonicalise_handles.py
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.scout.youtube_api import validate_channel
from jeromelu_shared.db import Channel, ChannelMetric, SessionLocal


def main() -> None:
    session = SessionLocal()
    try:
        non_uc = session.scalars(
            select(Channel).where(
                Channel.platform == "youtube",
                ~Channel.external_id.like("UC%"),
            )
        ).all()

        if not non_uc:
            print("No non-UC youtube channels — nothing to do.")
            return

        print(f"Found {len(non_uc)} channel(s) with non-UC external_id:")
        for ch in non_uc:
            print(f"  {ch.external_id}  {ch.name}")
        print()

        fixed = 0
        for ch in non_uc:
            handle = ch.external_id
            try:
                item = validate_channel(handle)
            except Exception as e:
                print(f"  ERR    {ch.name} ({handle}): {e}")
                continue

            if not item:
                print(f"  NOT-FOUND  {ch.name} ({handle}) — channel does not exist on YouTube")
                continue

            uc_id = item["id"]
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            thumbs = snippet.get("thumbnails", {})
            logo = (
                thumbs.get("high", {}).get("url")
                or thumbs.get("medium", {}).get("url")
                or thumbs.get("default", {}).get("url")
            )

            old_id = ch.external_id
            ch.external_id = uc_id
            ch.url = f"https://www.youtube.com/channel/{uc_id}"
            if logo and not ch.logo_url:
                ch.logo_url = logo

            existing_metric = session.scalars(
                select(ChannelMetric).where(ChannelMetric.channel_id == ch.channel_id)
            ).first()
            if not existing_metric:
                metrics_blob: dict = {}
                if stats.get("subscriberCount") is not None:
                    metrics_blob["subscribers"] = int(stats["subscriberCount"])
                if stats.get("viewCount") is not None:
                    metrics_blob["views"] = int(stats["viewCount"])
                if stats.get("videoCount") is not None:
                    metrics_blob["videos"] = int(stats["videoCount"])
                session.add(
                    ChannelMetric(
                        channel_id=ch.channel_id,
                        platform="youtube",
                        sampled_at=datetime.now(timezone.utc),
                        source="canonicalise_handles_backfill",
                        metrics=metrics_blob,
                    )
                )

            print(f"  FIXED  {ch.name}: {old_id} -> {uc_id}")
            fixed += 1

        session.commit()
        print()
        print(f"Done. {fixed}/{len(non_uc)} canonicalised.")
    finally:
        session.close()


if __name__ == "__main__":
    main()

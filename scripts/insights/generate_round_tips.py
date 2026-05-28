"""Generate SuperCoach Tips article for a given round.

Queries claim consensus and PlayerRound stats, then uses the LLM to write
an opinionated round preview in Jaromelu's voice.

Usage:
  python -m scripts.insights.generate_round_tips --round 5 --season 2026
  python -m scripts.insights.generate_round_tips --round 5 --season 2026 --temperature roast
"""

from __future__ import annotations

import argparse
import logging
import sys
import uuid

# Ensure packages are importable when running from repo root
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "packages" / "shared"))

from jeromelu_shared.db.session import SessionLocal
from jeromelu_shared.insights import (
    build_player_context,
    generate_article,
    get_current_round,
    query_claim_consensus,
    query_round_claims,
    query_top_players,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate SuperCoach Tips article")
    parser.add_argument("--round", type=int, default=None, help="Round number (default: latest)")
    parser.add_argument("--season", type=int, default=2026, help="Season year")
    parser.add_argument("--temperature", choices=["straight", "sharp", "roast"], default="sharp")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        round_num = args.round or get_current_round(db, args.season)
        if not round_num:
            logger.error("No claims found for season %d — cannot determine round", args.season)
            sys.exit(1)

        logger.info("Generating Round %d Tips (season=%d, temp=%s)", round_num, args.season, args.temperature)

        # 1. Gather data
        consensus = query_claim_consensus(db, round_num, args.season)
        claims = query_round_claims(db, round_num, args.season)
        players = query_top_players(db, round_num, args.season, top_n=30, order_by="season_avg")

        if not players and not consensus:
            logger.error("No player data or claims for Round %d — nothing to generate from", round_num)
            sys.exit(1)

        # 2. Build context
        player_context = build_player_context(players, consensus, claims)

        # 3. Collect all claim IDs for attribution
        all_claim_ids: list[uuid.UUID] = []
        for player_claims in claims.values():
            for c in player_claims:
                all_claim_ids.append(uuid.UUID(c["claim_id"]))

        # 4. Build metadata (structured data for frontend)
        metadata = {
            "article_type": "tips",
            "round": round_num,
            "season": args.season,
            "player_count": len(players),
            "claim_count": len(all_claim_ids),
            "players": [
                {
                    "entity_id": p["entity_id"],
                    "name": p["player_name"],
                    "team": p["team"],
                    "position": p["position"],
                    "price": p["price"],
                    "season_avg": p["season_avg"],
                    "consensus": consensus.get(p["entity_id"] or "", {}),
                }
                for p in players[:15]  # Top 15 for metadata
            ],
        }

        # 5. Generate and store
        entry = generate_article(
            db=db,
            kb_type="article_tips",
            round_num=round_num,
            season=args.season,
            player_context=player_context,
            metadata=metadata,
            claim_ids=all_claim_ids,
            temperature_mode=args.temperature,
        )

        logger.info("Done! kb_id=%s title=%s", entry.kb_id, entry.title)

    finally:
        db.close()


if __name__ == "__main__":
    main()

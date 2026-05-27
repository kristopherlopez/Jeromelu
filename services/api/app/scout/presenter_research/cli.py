"""CLI for Presenter Research. Run from services/api with venv active:

    python -m app.scout.presenter_research.cli --channel-id <uuid>
    python -m app.scout.presenter_research.cli --source-id <uuid>          # resolves to channel
    python -m app.scout.presenter_research.cli --channel-id <uuid> --dry-run
    python -m app.scout.presenter_research.cli --channel-id <uuid> --model claude-opus-4-7
"""

from __future__ import annotations

import argparse
import logging
import sys
from uuid import UUID

from jeromelu_shared.agent_audit import AgentBounds
from jeromelu_shared.db import SessionLocal

from .agent import (
    DEFAULT_BOUNDS,
    resolve_channel_from_source,
    run_presenter_research,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Presenter Research for one channel")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--channel-id", help="UUID of the channel to research")
    target.add_argument(
        "--source-id",
        help="UUID of a source — resolved to its channel_id server-side",
    )

    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Anthropic model id (default: claude-sonnet-4-6)",
    )
    parser.add_argument("--max-turns", type=int, default=DEFAULT_BOUNDS.max_turns)
    parser.add_argument("--max-tool-calls", type=int, default=DEFAULT_BOUNDS.max_tool_calls)
    parser.add_argument("--max-wall-seconds", type=int, default=DEFAULT_BOUNDS.max_wall_seconds)
    parser.add_argument(
        "--budget",
        type=float,
        default=DEFAULT_BOUNDS.max_budget_usd,
        help=f"USD budget cap (default: {DEFAULT_BOUNDS.max_budget_usd})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the agent and print everything but skip persist_presenter_candidate writes",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    bounds = AgentBounds(
        max_turns=args.max_turns,
        max_tool_calls=args.max_tool_calls,
        max_wall_seconds=args.max_wall_seconds,
        max_budget_usd=args.budget,
    )

    session = SessionLocal()
    try:
        if args.channel_id:
            channel_id = UUID(args.channel_id)
        else:
            channel_id = resolve_channel_from_source(session, UUID(args.source_id))
            print(f"Resolved source {args.source_id} → channel {channel_id}")

        result = run_presenter_research(
            session,
            channel_id,
            model=args.model,
            bounds=bounds,
            dry_run=args.dry_run,
        )
    finally:
        session.close()

    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())

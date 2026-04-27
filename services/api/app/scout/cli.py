"""Manual CLI for Scout. Usage from services/api with venv active:

    python -m app.scout.cli                       # default brief, sonnet 4.6
    python -m app.scout.cli --dry-run             # don't persist; just print
    python -m app.scout.cli --model claude-opus-4-7
    python -m app.scout.cli --max-turns 5 --budget 0.50
    python -m app.scout.cli --brief "Find injury-focused NRL podcasts only"
"""

from __future__ import annotations

import argparse
import logging
import sys

from jeromelu_shared.db import SessionLocal

from app.scout.loop import ScoutBounds, run_scout


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Scout source-discovery sweep")
    parser.add_argument("--brief", help="Override the default user brief")
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Anthropic model id (default: claude-sonnet-4-6)",
    )
    parser.add_argument("--max-turns", type=int, default=20)
    parser.add_argument("--max-tool-calls", type=int, default=60)
    parser.add_argument("--max-wall-seconds", type=int, default=900)
    parser.add_argument("--budget", type=float, default=3.00, help="USD budget cap per run")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the agent and print everything but do NOT write to discovered_sources",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    bounds = ScoutBounds(
        max_turns=args.max_turns,
        max_tool_calls=args.max_tool_calls,
        max_wall_seconds=args.max_wall_seconds,
        max_budget_usd=args.budget,
    )

    session = SessionLocal()
    try:
        result = run_scout(
            session,
            brief=args.brief,
            model=args.model,
            bounds=bounds,
            dry_run=args.dry_run,
        )
    finally:
        session.close()

    return 0 if result.status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())

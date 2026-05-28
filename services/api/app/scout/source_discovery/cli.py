"""Manual CLI for Source Discovery. Usage from services/api with venv active:

python -m app.scout.source_discovery.cli                       # default brief, sonnet 4.6
python -m app.scout.source_discovery.cli --dry-run             # don't persist; just print
python -m app.scout.source_discovery.cli --model claude-opus-4-7
python -m app.scout.source_discovery.cli --max-turns 5 --budget 0.50
python -m app.scout.source_discovery.cli --brief "Find injury-focused NRL podcasts only"
"""

from __future__ import annotations

import argparse
import logging
import sys

from jeromelu_shared.agent_audit import AgentBounds
from jeromelu_shared.db import SessionLocal

from .agent import run_source_discovery


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run a Source Discovery sweep")
    parser.add_argument("--brief", help="Override the default user brief")
    parser.add_argument(
        "--model",
        default="claude-sonnet-4-6",
        help="Anthropic model id (default: claude-sonnet-4-6)",
    )
    parser.add_argument("--max-turns", type=int, default=20)
    parser.add_argument("--max-tool-calls", type=int, default=60)
    parser.add_argument("--max-wall-seconds", type=int, default=900)
    parser.add_argument("--budget", type=float, default=1.00, help="USD budget cap per run")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run the agent and print everything but do NOT write to scout_candidates",
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
        result = run_source_discovery(
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

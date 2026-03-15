"""ScraperSweepWorkflow — orchestrates Supercoach data scraping.

Runs on a schedule:
- Monday 6AM AEST:    fetch scores
- Wednesday 6AM AEST: fetch prices + breakevens
- Thursday 6PM AEST:  fetch team lists

Each run: fetch data → validate → store (S3 + DB).
"""

import logging
from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.activities.scores import fetch_scores
    from app.activities.prices import fetch_prices
    from app.activities.teamlists import fetch_teamlists
    from app.activities.validation import validate_data
    from app.activities.persist import persist_player_rounds

logger = logging.getLogger(__name__)


@dataclass
class ScraperSweepInput:
    scrape_type: str  # "scores", "prices", "teamlists"
    round: int
    season: int


FETCH_ACTIVITIES = {
    "scores": fetch_scores,
    "prices": fetch_prices,
    "teamlists": fetch_teamlists,
}

RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_attempts=3,
    non_retryable_error_types=["AuthError"],
)


@workflow.defn
class ScraperSweepWorkflow:
    @workflow.run
    async def run(self, input: ScraperSweepInput) -> dict:
        """Execute a scrape for the given type and round."""

        activity = FETCH_ACTIVITIES.get(input.scrape_type)
        if not activity:
            raise ValueError(f"Unknown scrape_type: {input.scrape_type}")

        workflow.logger.info(
            "Starting %s scrape for round %d, season %d",
            input.scrape_type, input.round, input.season,
        )

        # Step 1: Fetch data
        fetch_result = await workflow.execute_activity(
            activity,
            args=[input.round, input.season],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RETRY_POLICY,
        )

        # Step 2: Validate
        validation = await workflow.execute_activity(
            validate_data,
            args=[input.scrape_type, fetch_result],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )

        # Step 3: Persist to DB (only if validation passed)
        persist_result = None
        if validation.get("valid"):
            persist_result = await workflow.execute_activity(
                persist_player_rounds,
                args=[input.scrape_type, input.round, input.season, fetch_result.get("rows", [])],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RETRY_POLICY,
            )
        else:
            workflow.logger.warning(
                "Skipping persist — validation failed: %s", validation.get("errors")
            )

        summary = {
            "scrape_type": input.scrape_type,
            "round": input.round,
            "season": input.season,
            "rows": fetch_result.get("row_count", 0),
            "validation": validation,
            "persist": persist_result,
        }
        workflow.logger.info("Scrape complete: %s", summary)
        return summary

"""FeedGenerationWorkflow — synthesise claims into feed events."""

import logging
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.activities.generate_events import (
        fetch_unprocessed_claims,
        generate_feed_events,
        persist_events,
    )
    from app.activities.generate_reviews import generate_review_data
    from app.activities.update_consensus import update_consensus_snapshots

logger = logging.getLogger(__name__)

RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_attempts=3,
)


@workflow.defn
class FeedGenerationWorkflow:
    @workflow.run
    async def run(self) -> dict:
        """Execute the full feed generation pipeline."""

        # 1. Fetch unprocessed claims
        claims_data = await workflow.execute_activity(
            fetch_unprocessed_claims,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RETRY,
        )

        # 2. Update consensus snapshots and detect sentiment flips
        consensus_shifts = await workflow.execute_activity(
            update_consensus_snapshots,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RETRY,
        )

        # 3. Generate review data from past predictions
        review_data = await workflow.execute_activity(
            generate_review_data,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RETRY,
        )

        # 4. Synthesise events via LLM
        claims = claims_data.get("claims", [])
        if not claims and not consensus_shifts and not review_data:
            workflow.logger.info("No new data to process — skipping LLM call")
            return {"generated": 0, "inserted": 0, "skipped": 0}

        events = await workflow.execute_activity(
            generate_feed_events,
            args=[claims_data, consensus_shifts, review_data],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RETRY,
        )

        if not events:
            return {"generated": 0, "inserted": 0, "skipped": 0}

        # 5. Persist events with dedup
        result = await workflow.execute_activity(
            persist_events,
            args=[events],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=RETRY,
        )

        summary = {
            "generated": len(events),
            "inserted": result.get("inserted", 0),
            "skipped": result.get("skipped", 0),
        }
        workflow.logger.info("Feed generation complete: %s", summary)
        return summary

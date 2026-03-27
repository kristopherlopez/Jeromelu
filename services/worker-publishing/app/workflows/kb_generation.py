"""KBGenerationWorkflow — distill claims and data into curated knowledge base entries."""

import logging
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.activities.generate_kb import (
        generate_player_summaries,
        generate_round_briefs,
        generate_decisions_log,
        generate_player_opinions,
        generate_source_digests,
        embed_kb_entries,
    )

logger = logging.getLogger(__name__)

RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_attempts=3,
)


@workflow.defn
class KBGenerationWorkflow:
    @workflow.run
    async def run(self) -> dict:
        """Execute the full KB generation pipeline."""

        # 1. Player summaries
        summaries = await workflow.execute_activity(
            generate_player_summaries,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RETRY,
        )

        # 2. Round briefs
        briefs = await workflow.execute_activity(
            generate_round_briefs,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RETRY,
        )

        # 3. Decisions log
        decisions = await workflow.execute_activity(
            generate_decisions_log,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RETRY,
        )

        # 4. Player opinions
        opinions = await workflow.execute_activity(
            generate_player_opinions,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RETRY,
        )

        # 5. Source digests
        digests = await workflow.execute_activity(
            generate_source_digests,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RETRY,
        )

        # 6. Embed all new/updated entries
        embedded = await workflow.execute_activity(
            embed_kb_entries,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RETRY,
        )

        result = {
            **summaries,
            **briefs,
            **decisions,
            **opinions,
            **digests,
            **embedded,
        }
        workflow.logger.info("KB generation complete: %s", result)
        return result

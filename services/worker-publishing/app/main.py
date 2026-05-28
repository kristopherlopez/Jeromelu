import asyncio
import logging

from jeromelu_shared.temporal import PUBLISHING_QUEUE, get_temporal_client
from temporalio.worker import Worker

from app.activities.generate_events import (
    fetch_unprocessed_claims,
    generate_feed_events,
    persist_events,
)
from app.activities.generate_kb import (
    embed_kb_entries,
    generate_decisions_log,
    generate_player_opinions,
    generate_player_summaries,
    generate_round_briefs,
    generate_source_digests,
)
from app.activities.generate_reviews import generate_review_data
from app.activities.update_consensus import update_consensus_snapshots
from app.workflows.feed_generation import FeedGenerationWorkflow
from app.workflows.kb_generation import KBGenerationWorkflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting worker-publishing...")

    client = await get_temporal_client()

    worker = Worker(
        client,
        task_queue=PUBLISHING_QUEUE,
        workflows=[FeedGenerationWorkflow, KBGenerationWorkflow],
        activities=[
            fetch_unprocessed_claims,
            generate_feed_events,
            persist_events,
            generate_review_data,
            update_consensus_snapshots,
            generate_player_summaries,
            generate_round_briefs,
            generate_decisions_log,
            generate_player_opinions,
            generate_source_digests,
            embed_kb_entries,
        ],
    )

    logger.info("Publishing worker listening on queue '%s'", PUBLISHING_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())

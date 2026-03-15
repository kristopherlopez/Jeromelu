import asyncio
import logging

from temporalio.worker import Worker

from jeromelu_shared.temporal import get_temporal_client, SCRAPER_QUEUE

from app.activities.scores import fetch_scores
from app.activities.prices import fetch_prices
from app.activities.teamlists import fetch_teamlists
from app.activities.validation import validate_data
from app.activities.persist import persist_player_rounds
from app.workflows.scraper_sweep import ScraperSweepWorkflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting worker-scraper...")

    client = await get_temporal_client()

    worker = Worker(
        client,
        task_queue=SCRAPER_QUEUE,
        workflows=[ScraperSweepWorkflow],
        activities=[
            fetch_scores,
            fetch_prices,
            fetch_teamlists,
            validate_data,
            persist_player_rounds,
        ],
    )

    logger.info("Scraper worker listening on queue '%s'", SCRAPER_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())

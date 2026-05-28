import asyncio
import logging

from jeromelu_shared.temporal import EXTRACTION_QUEUE, get_temporal_client
from temporalio.worker import Worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting worker-extraction...")

    client = await get_temporal_client()

    # Activity functions will be registered here as they are built
    activities: list = []

    worker = Worker(
        client,
        task_queue=EXTRACTION_QUEUE,
        activities=activities,
    )

    logger.info("Extraction worker listening on queue '%s'", EXTRACTION_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())

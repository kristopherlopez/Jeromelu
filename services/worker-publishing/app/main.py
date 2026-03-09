import asyncio
import logging

from temporalio.worker import Worker

from jeromelu_shared.temporal import get_temporal_client, PUBLISHING_QUEUE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting worker-publishing...")

    client = await get_temporal_client()

    # Activity functions will be registered here as they are built
    activities: list = []

    worker = Worker(
        client,
        task_queue=PUBLISHING_QUEUE,
        activities=activities,
    )

    logger.info("Publishing worker listening on queue '%s'", PUBLISHING_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())

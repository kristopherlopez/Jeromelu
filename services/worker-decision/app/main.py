import asyncio
import logging

from jeromelu_shared.temporal import DECISION_QUEUE, get_temporal_client
from temporalio.worker import Worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting worker-decision...")

    client = await get_temporal_client()

    # Activity functions will be registered here as they are built
    activities: list = []

    worker = Worker(
        client,
        task_queue=DECISION_QUEUE,
        activities=activities,
    )

    logger.info("Decision worker listening on queue '%s'", DECISION_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())

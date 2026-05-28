import asyncio
import logging

from jeromelu_shared.temporal import ORCHESTRATOR_QUEUE, get_temporal_client
from temporalio.worker import Worker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting worker-orchestrator...")

    client = await get_temporal_client()

    # Workflow classes will be registered here as they are built
    workflows: list = []

    worker = Worker(
        client,
        task_queue=ORCHESTRATOR_QUEUE,
        workflows=workflows,
    )

    logger.info("Orchestrator listening on queue '%s'", ORCHESTRATOR_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())

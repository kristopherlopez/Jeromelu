import asyncio
import logging

from jeromelu_shared.temporal import INGESTION_QUEUE, get_temporal_client
from temporalio.worker import Worker

from app.activities.collection import collect_transcript
from app.activities.discovery import discover_new_videos
from app.activities.indexing import index_document
from app.workflows.intel_sweep import IntelSweepWorkflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    logger.info("Starting worker-ingestion...")

    client = await get_temporal_client()

    worker = Worker(
        client,
        task_queue=INGESTION_QUEUE,
        workflows=[IntelSweepWorkflow],
        activities=[
            discover_new_videos,
            collect_transcript,
            index_document,
        ],
    )

    logger.info("Ingestion worker listening on queue '%s'", INGESTION_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())

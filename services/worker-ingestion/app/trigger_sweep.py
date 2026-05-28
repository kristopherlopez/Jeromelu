"""Manually trigger an IntelSweepWorkflow execution.

Usage: python -m app.trigger_sweep
"""

import asyncio
import logging
from datetime import UTC, datetime

from jeromelu_shared.temporal import INGESTION_QUEUE, get_temporal_client, workflow_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    client = await get_temporal_client()

    run_key = datetime.now(UTC).strftime("%Y-%m-%dT%H%M%S")
    wf_id = workflow_id("intel-sweep", run_key)

    handle = await client.start_workflow(
        "IntelSweepWorkflow",
        id=wf_id,
        task_queue=INGESTION_QUEUE,
    )

    logger.info("Started IntelSweepWorkflow: %s", wf_id)
    result = await handle.result()
    logger.info("Sweep result: %s", result)


if __name__ == "__main__":
    asyncio.run(main())

"""Create a Temporal schedule for daily IntelSweepWorkflow at 10PM AEST.

Note: All Temporal schedules use Australia/Sydney timezone.
The Temporal server runs in UTC but schedules specify their own timezone.

Usage: python -m app.create_schedule
"""

import asyncio
import logging
from datetime import timedelta

from temporalio.client import (
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleSpec,
    ScheduleCalendarSpec,
    ScheduleRange,
)

from jeromelu_shared.temporal import get_temporal_client, INGESTION_QUEUE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SCHEDULE_ID = "daily-intel-sweep"
TIMEZONE = "Australia/Sydney"


async def main():
    client = await get_temporal_client()

    await client.create_schedule(
        SCHEDULE_ID,
        Schedule(
            action=ScheduleActionStartWorkflow(
                "IntelSweepWorkflow",
                id="intel-sweep-scheduled",
                task_queue=INGESTION_QUEUE,
            ),
            spec=ScheduleSpec(
                calendars=[
                    ScheduleCalendarSpec(
                        hour=[ScheduleRange(start=22)],
                        minute=[ScheduleRange(start=0)],
                    )
                ],
                jitter=timedelta(minutes=5),
                time_zone_name=TIMEZONE,
            ),
        ),
    )

    logger.info("Created schedule '%s' — daily at 10:00 PM %s", SCHEDULE_ID, TIMEZONE)


if __name__ == "__main__":
    asyncio.run(main())

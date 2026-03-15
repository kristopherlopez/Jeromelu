"""IntelSweepWorkflow — orchestrates the ingestion pipeline.

Runs on a schedule (daily at 10 PM AEST):
1. Discovery — find new videos on whitelisted channels
2. Collection — fetch transcripts, store JSON in S3
3. Indexing — write Source + SourceDocument to DB

Processing activity is skipped for MVP (plain text extracted during collection).
"""

import logging
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from app.activities.collection import collect_transcript
    from app.activities.discovery import discover_new_videos
    from app.activities.indexing import index_document

logger = logging.getLogger(__name__)


@workflow.defn
class IntelSweepWorkflow:
    @workflow.run
    async def run(self) -> dict:
        """Execute the full ingestion sweep."""

        # Step 1: Discover new videos
        new_videos = await workflow.execute_activity(
            discover_new_videos,
            start_to_close_timeout=timedelta(minutes=5),
        )

        if not new_videos:
            workflow.logger.info("No new videos discovered — sweep complete")
            return {"discovered": 0, "collected": 0, "indexed": 0, "errors": []}

        workflow.logger.info("Discovered %d new videos", len(new_videos))

        collected = 0
        indexed = 0
        errors = []

        # Step 2 + 3: For each video, collect transcript then index
        for video in new_videos:
            video_id = video["video_id"]

            # Collection
            result = await workflow.execute_activity(
                collect_transcript,
                args=[video],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(
                    initial_interval=timedelta(seconds=5),
                    backoff_coefficient=2.0,
                    maximum_attempts=3,
                    non_retryable_error_types=["RateLimitError", "NoTranscriptFound", "TranscriptsDisabled"],
                ),
            )

            if not result["success"]:
                errors.append({"video_id": video_id, "stage": "collection", "error": result["error"]})
                continue

            collected += 1

            # Indexing
            try:
                index_result = await workflow.execute_activity(
                    index_document,
                    args=[video, result],
                    start_to_close_timeout=timedelta(minutes=1),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=2),
                        backoff_coefficient=2.0,
                        maximum_attempts=3,
                    ),
                )

                if index_result["success"] and not index_result.get("skipped"):
                    indexed += 1
            except Exception as e:
                errors.append({"video_id": video_id, "stage": "indexing", "error": str(e)})

        summary = {
            "discovered": len(new_videos),
            "collected": collected,
            "indexed": indexed,
            "errors": errors,
        }
        workflow.logger.info("Sweep complete: %s", summary)
        return summary

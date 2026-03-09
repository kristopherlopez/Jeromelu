import logging

from temporalio.client import Client

from jeromelu_shared.config import settings

logger = logging.getLogger(__name__)

# Task queue constants
ORCHESTRATOR_QUEUE = "orchestrator"
INGESTION_QUEUE = "ingestion"
EXTRACTION_QUEUE = "extraction"
DECISION_QUEUE = "decision"
PUBLISHING_QUEUE = "publishing"

_client: Client | None = None


async def get_temporal_client() -> Client:
    """Get or create a shared Temporal client connection."""
    global _client
    if _client is None:
        _client = await Client.connect(
            settings.temporal_host,
            namespace=settings.temporal_namespace,
        )
        logger.info(
            "Connected to Temporal at %s (namespace: %s)",
            settings.temporal_host,
            settings.temporal_namespace,
        )
    return _client


def workflow_id(name: str, key: str) -> str:
    """Build a deterministic workflow ID.

    Examples:
        workflow_id("daily-intel-sweep", "2026-03-09")
        workflow_id("match-review", "round-3")
    """
    return f"{name}-{key}"

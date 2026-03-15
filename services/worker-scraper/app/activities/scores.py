"""Fetch player scores from the Supercoach API."""

import logging

from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn
async def fetch_scores(round: int, season: int) -> dict:
    """Fetch player scores for a given round and season.

    Returns dict with keys: row_count, s3_key, rows (list of dicts).
    """
    # TODO: implement after API research is complete
    raise NotImplementedError("fetch_scores not yet implemented")

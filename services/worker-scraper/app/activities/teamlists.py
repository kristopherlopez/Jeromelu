"""Fetch team lists from the NRL API."""

import logging

from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn
async def fetch_teamlists(round: int, season: int) -> dict:
    """Fetch team lists for a given round and season from api.nrl.com.

    Returns dict with keys: row_count, s3_key, rows (list of dicts).
    """
    # TODO: implement after API research is complete
    raise NotImplementedError("fetch_teamlists not yet implemented")

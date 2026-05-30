"""Miner pipeline: nrl.com draw / fixtures.

Fetches /draw/data per (competition, season, round) and archives raw JSON
to S3. DB extraction (writing matches + rounds rows) is a separate
downstream job per D13.
"""

from .routes import router

__all__ = ["router"]

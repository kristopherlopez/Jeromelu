"""Miner pipeline: nrl.com casualty ward (injury list).

Pure capture — DB extraction (writing `injuries`) is downstream per D13.
"""

from .routes import router

__all__ = ["router"]

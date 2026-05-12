"""Top-level pytest fixtures shared across unit and integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    """Absolute path to the tests/fixtures/ directory.

    Use this instead of computing `Path(__file__).resolve().parents[N]`
    in individual test modules — N changes with directory depth and is
    a frequent source of off-by-one errors.
    """
    return Path(__file__).resolve().parent / "fixtures"

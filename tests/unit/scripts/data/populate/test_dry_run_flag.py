"""The `--dry-run` fix: every phase function the orchestrator calls must
accept a `commit` keyword (default True) so `--dry-run` can suppress writes.

Pure signature inspection — no S3, no DB. Guards against the META known-bug
("populate_db_from_s3 --dry-run silently writes") regressing: if a new phase
or a signature change drops the `commit` param, this fails.
"""

from __future__ import annotations

import inspect

import pytest

from scripts.data.populate.phase_attributes import populate_player_attributes
from scripts.data.populate.phase_aux import (
    populate_injuries,
    populate_stat_leaderboards,
    populate_team_standings,
)
from scripts.data.populate.phase_identity import backfill_identity
from scripts.data.populate.phase_matches import populate_matches
from scripts.data.populate.phase_people import (
    populate_people_history,
    reresolve_person_ids,
)
from scripts.data.populate.phase_player_rounds import populate_player_rounds
from scripts.data.populate.phase_rounds import populate_rounds
from scripts.data.populate.phase_stats import populate_player_match_stats
from scripts.data.populate.phase_team_lists import populate_team_lists
from scripts.data.populate.phase_timeline import populate_timeline_and_officials


_PHASE_FUNCS = [
    backfill_identity,
    populate_people_history,
    reresolve_person_ids,
    populate_player_attributes,
    populate_rounds,
    populate_matches,
    populate_team_lists,
    populate_player_match_stats,
    populate_timeline_and_officials,
    populate_team_standings,
    populate_stat_leaderboards,
    populate_injuries,
    populate_player_rounds,
]


@pytest.mark.parametrize("fn", _PHASE_FUNCS, ids=lambda f: f.__name__)
def test_phase_accepts_commit_flag(fn):
    """Every orchestrated phase function takes `commit` with default True."""
    params = inspect.signature(fn).parameters
    assert "commit" in params, f"{fn.__name__} is missing the `commit` parameter"
    assert params["commit"].default is True, f"{fn.__name__} `commit` default must be True"

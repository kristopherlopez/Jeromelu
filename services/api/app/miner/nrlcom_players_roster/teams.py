"""NRL.com internal team_id catalogue for the per-team /players/data walk.

The 17 NRL clubs' nrl.com internal team_id values, paired with the
`theme.key` short name. Used by the `refresh-all` endpoint to walk the
full top-grade roster server-side with polite 1 req/sec spacing.

**Source.** Derived from the canonical fixture
`tests/fixtures/miner/nrlcom_players_roster/canonical_response.json`
(`filterTeams[]`) captured live 2026-05-28 from
`https://www.nrl.com/players/data?competition=111&team=500011`. The
`/players/data` response itself carries the 17-team catalogue with the
internal team_id per team — so a single live fetch yields the full
walk-set without needing to read S3 ladder/draw archives. Worth knowing
when a new club joins (the next ladder/draw/players-roster response will
include them in `filterTeams`).

**Manual-update procedure.** When the NRL admits a new top-grade club:
1. Refresh the canonical fixture (rerun TASK-31's live-capture path).
2. Re-derive this list from `data["filterTeams"]` and update the
   tuples below, sorted by short_name for stable iteration.
3. The drift tests will catch any envelope/profile shape change at the
   same time.

**Note on the existing README example.** `services/api/app/miner/nrlcom_players_roster/README.md`
line 15 incorrectly labels `team=500011` as Storm — it's actually
**Broncos** (Storm is `500021`, as the list below shows). README
correction is folded into TASK-36 doc sweep.
"""

from __future__ import annotations

#: 17 NRL clubs' nrl.com internal team_id values + theme.key short name.
#: Sorted by short_name for stable iteration order (cron logs reproduce
#: deterministically).
NRL_TEAM_IDS: list[tuple[str, int]] = [
    ("broncos", 500011),
    ("bulldogs", 500010),
    ("cowboys", 500012),
    ("dolphins", 500723),
    ("dragons", 500022),
    ("eels", 500031),
    ("knights", 500003),
    ("panthers", 500014),
    ("rabbitohs", 500005),
    ("raiders", 500013),
    ("roosters", 500001),
    ("sea-eagles", 500002),
    ("sharks", 500028),
    ("storm", 500021),
    ("titans", 500004),
    ("warriors", 500032),
    ("wests-tigers", 500023),
]


__all__ = ["NRL_TEAM_IDS"]

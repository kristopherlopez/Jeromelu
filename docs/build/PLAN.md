# Jaromelu Build Plan

This document holds active and historical plan docs that drive the persistent task queue in [TASKS.md](./TASKS.md). Plans are written by the `planner` agent (or a planning session) and consumed by the `implementer`.

## What good looks like

A good plan doc is:

- **Self-contained** — readable cold by an implementer with no prior conversation context.
- **Interface-level** — names file paths, types, function signatures, table columns, API shapes, env vars. No "figure out the right shape".
- **End-to-end verifiable** — explicit "how do we know this is done" strategy, runnable from the outside (curl, CLI, screenshot, query).
- **Iterated to high quality** before any task is appended. A plan that ships fuzzy tasks burns implementer time on re-asking.

Plans link to the tasks they spawn. Tasks link back to the plan section they implement.

---

## Active plan

## 2026-05-27: Change-only storage for video_metrics + channel_metrics

**Goal:** Stop appending unchanged daily snapshots to the metrics time-series. Record a new `video_metrics` / `channel_metrics` row **only when the metrics payload differs from that entity's most recent recorded snapshot**, then one-time dedup the existing history and reclaim disk. Prod evidence (2026-05-27): 70.2% of the 2.13M `video_metrics` rows are byte-identical to the prior snapshot (1,498,053 droppable); 38% of videos never changed once in 3 weeks; steady-state only ~24% of daily snapshots change. Outcome: `video_metrics` ~641 MB / 2.13M rows → ~191 MB / ~637k rows, daily growth ~37 MB → ~9 MB (~4×). `channel_metrics` gets the identical treatment for symmetry (tiny payload, negligible savings, but one pattern everywhere).

**Why this is safe — the three design calls (ratified with the human 2026-05-27):**

1. **Scope = both tables.** `video_metrics` holds the bloat; `channel_metrics` is a structural twin and gets the same helper + dedup so the siblings don't diverge.
2. **Freshness derives from the refresh run, not a per-row timestamp.** Under change-only storage the latest row's `sampled_at` means "last *changed*", not "last *checked*". We deliberately do **not** add a per-row/per-source `last_checked_at` (that would trade `video_metrics` bloat for ~120k timestamp UPDATEs/day of `sources` bloat). Instead: a successful daily refresh means every video/channel was checked that day, so "is this metric current?" is answered by the last successful refresh run (observable via the daily `cron-report` and the refresh job's `agent_runs` row). This must be documented so a future reader doesn't misread a stale `sampled_at`.
3. **Reclaim = one-time `VACUUM (FULL, ANALYZE)` on prod**, run by the human as a documented runbook step (NOT a migration — `VACUUM` cannot run inside a transaction, and it's maintenance, not schema). The dedup `DELETE` ships as migration 070 and runs everywhere via `make migrate`; only the space-return-to-OS rewrite is the manual prod step.

**Constraints:**

- **Refactor landed:** the YouTube refresh code now lives at `services/api/app/scout/youtube/refresh.py` (627 lines). `services/api/app/scout/refresh.py` is a 4-line compatibility shim (`from .youtube.refresh import *`). **All new code edits target `scout/youtube/refresh.py`.** Existing tests import via the shim (`from app.scout.refresh import ...`) and still work; **new tests import from the canonical path** `from app.scout.youtube.refresh import _metrics_changed`.
- **Equality is pinned to the existing payload builders** — do not invent a new comparison. Videos already slice to `_METRIC_FIELDS = ("views", "likes", "comments")` before insert (`youtube/refresh.py` ~line 53); channels build `{subscribers, videos, views, country, channel_published_at}` in `refresh_all_channel_stats`. `_metrics_changed` compares those already-built dicts with plain `!=` (JSONB round-trips to a `dict` with the same int/str values; `dict` equality is key-order independent).
- **The only daily-append writers to change are `refresh_all_video_stats` and `refresh_all_channel_stats`.** Leave the first-snapshot writers untouched (they have no prior row, so skip-if-unchanged is a no-op there): `refresh_channel_videos` (`youtube/refresh.py` ~line 176, new-video discovery), `recon.py` ~line 306 (channel approval discovery snapshot), and `services/api/scripts/canonicalise_handles.py` ~line 83 (one-off backfill, already guarded by `if not existing_metric`). Name them in the docstring so a future reader knows they were considered.
- **The `video_latest_metrics` / `channel_latest_metrics` views are unchanged and must keep returning the current value.** `DISTINCT ON (...) ORDER BY ... sampled_at DESC` returns the last *change*, which under change-only storage **is** the current value. This is a verification target, not a code change.
- **Velocity/breakout reads are already change-only-safe — verify, don't rewrite.** `scripts/content_report.py` `fetch_channel_velocity` / `fetch_headline` use the `JOIN LATERAL (... WHERE sampled_at < now() - interval '6 days' ORDER BY sampled_at DESC LIMIT 1)` "most-recent-row-as-of-cutoff" pattern, which returns the true value as of the cutoff regardless of gaps. `fetch_top_new_videos` reads `video_latest_metrics` (current state). No consumer does consecutive-row `LAG` velocity that would assume a row exists at an exact prior date. The implementer **confirms this by reading the file** and records the confirmation; if any query is found to assume an exact-date prior row, STOP and file a new task rather than improvising.
- META: migrations only via `make migrate`; new migration is `070_dedup_metrics_snapshots.sql`. Session-scoped staging — stage only files this work creates/modifies; the Scout-refactor diff belongs to another session and must not be swept in (`git diff --cached --stat` before commit).

**Interface:**

### New pure helper — `services/api/app/scout/youtube/refresh.py`

```python
def _metrics_changed(previous: dict | None, current: dict) -> bool:
    """True when `current` should be recorded — i.e. there is no prior
    snapshot, or the payload differs from the most recent stored one.

    `current` is the already-sliced payload (videos: _METRIC_FIELDS;
    channels: the subscribers/videos/views/country/channel_published_at
    dict). Comparison is plain dict equality, so JSONB key order and
    int/str round-tripping don't matter."""
    return previous is None or previous != current
```

### New loaders — same file

```python
def _latest_video_metrics(session: Session) -> dict[UUID, dict]:
    """source_id → its most-recent recorded metrics payload (the set the
    `video_latest_metrics` view exposes). Loaded once per refresh so the
    write loop can skip re-recording an unchanged snapshot."""
    stmt = (
        select(VideoMetric.source_id, VideoMetric.metrics)
        .distinct(VideoMetric.source_id)
        .order_by(VideoMetric.source_id, VideoMetric.sampled_at.desc())
    )
    return {row.source_id: row.metrics for row in session.execute(stmt)}

def _latest_channel_metrics(session: Session) -> dict[UUID, dict]:
    """channel_id → most-recent recorded metrics payload. Twin of the above."""
    # identical shape over ChannelMetric.channel_id / .metrics
```

`metrics` is JSONB-typed on the ORM model, so rows come back as `dict` (no manual `json.loads`). `DISTINCT ON` is Postgres-native via SQLAlchemy `.distinct(col)` and is equivalent to the `*_latest_metrics` view.

### Wiring — `refresh_all_video_stats` (and symmetric in `refresh_all_channel_stats`)

Load latest once before the batch loop; gate the existing `session.add(...)`:

```python
latest = _latest_video_metrics(session)        # before the for-batch loop
...
metric_payload = {k: entry[k] for k in _METRIC_FIELDS if k in entry}
if metric_payload:
    if _metrics_changed(latest.get(source_id), metric_payload):
        session.add(VideoMetric(... metrics=metric_payload ...))
        refreshed += 1
    else:
        unchanged += 1
```

Return dicts gain one key each: `refresh_all_video_stats` → `"videos_unchanged": unchanged`; `refresh_all_channel_stats` → `"channels_unchanged": unchanged`. These keys flow through the `recon.py` admin-refresh endpoint response body (additive, backward-compatible). The identity-field sync onto `sources` / `channels` is **unchanged** — it always runs, independent of the metric skip.

### Migration — `packages/db/migrations/070_dedup_metrics_snapshots.sql`

House-style header comment (rationale + idempotency + "VACUUM is a separate manual step, see runbook"). Two LAG-based deletes — keep every entity's first snapshot and every change, drop runs of byte-identical consecutive rows:

```sql
WITH ordered AS (
    SELECT metric_id, metrics,
           lag(metrics) OVER (PARTITION BY source_id ORDER BY sampled_at) AS prev
    FROM video_metrics
)
DELETE FROM video_metrics vm
USING ordered o
WHERE vm.metric_id = o.metric_id
  AND o.prev IS NOT NULL
  AND o.metrics = o.prev;       -- jsonb '=' is semantic / key-order independent

-- then the identical statement over channel_metrics partitioned by channel_id
```

Idempotent: after one pass, consecutive rows always differ, so re-running deletes nothing. Safe on fresh/CI/local DBs (no-op or small). Contains **no** `VACUUM`.

### Reclaim runbook — `docs/operations/metrics-dedup-runbook.md` (new)

One-time prod step after migration 070 deploys, run by the human (brief `ACCESS EXCLUSIVE` lock; schedule off-hours; 40 GB free disk covers the rewrite):

```sql
VACUUM (FULL, ANALYZE) video_metrics;
VACUUM (FULL, ANALYZE) channel_metrics;
```

Plus before/after size query (`pg_total_relation_size`), expected `video_metrics` 641 MB → ~191 MB, and a "no rollback needed — VACUUM is non-destructive" note.

**Verification strategy:**

- **TASK-07 (gating):** `make test` green including a new `TestMetricsChanged` class in `tests/unit/api/scout/test_refresh_helpers.py` (cases: `previous is None` → record; equal payload → skip; one value changed → record; key-set differs, e.g. `comments` dropped → record; reordered keys equal → skip). Implementer records in proof the read-confirmation that `content_report.py` velocity queries use the as-of-cutoff / latest-view pattern. **Deferred (post-deploy):** the admin refresh endpoint (or `/var/log/jeromelu/scout-refresh.log`) reports `videos_unchanged` ≈ 75% of `videos_total` and `videos_refreshed` ≈ 29k (not ~119k) on the next daily run.
- **TASK-08 (gating, local):** `make migrate` applies 070 against local; assert (a) **latest-state preserved** — `SELECT md5(string_agg(source_id::text || metrics::text, '' ORDER BY source_id)) FROM video_latest_metrics` is **identical before and after** the migration (same check for `channel_latest_metrics`); (b) **idempotent** — re-running the embedded dedup `SELECT` (the `ordered` CTE filtered to `prev = metrics`) returns 0 rows post-migration; (c) total row count drops. Capture before/after counts.
- **TASK-09:** runbook file exists with the exact commands, lock warning, and before/after size query; data docs + cron comment updated. **Deferred (post-deploy):** human runs the `VACUUM (FULL, ANALYZE)`; observe `video_metrics` total relation size 641 MB → ~191 MB (mirror the TASK-06 deferred-verification pattern).
- **Tiers:** unit only (pure helper). DB-backed write-path behaviour is verified end-to-end via the post-deploy refresh response, consistent with the existing convention that DB-backed refresh logic lives outside the unit tier (see `test_refresh_helpers.py` header).

**Documentation updates:**

- `services/api/app/scout/youtube/refresh.py` — module docstring + `refresh_all_video_stats` / `refresh_all_channel_stats` docstrings: change "append a row" → "append a row only when the payload differs from the latest snapshot; unchanged samples are skipped." Note the first-snapshot writers that intentionally don't skip. (TASK-07, same changeset.)
- `docs/operations/data-catalogue/video_metrics.md` + `channel_metrics.md` — document change-only write semantics and the freshness-derives-from-the-refresh-run note. (TASK-07.)
- `docs/operations/data-lineage/video_metrics.md` + `channel_metrics.md` — Writer line: "INSERTs one row per video per sample" → "INSERTs a row only when views/likes/comments change vs the latest snapshot." Add the as-of read-pattern note for velocity consumers. (TASK-07.)
- `scripts/cron.d/jeromelu` — comment on the daily video refresh (line ~26-31): "snapshots video_metrics" → "snapshots video_metrics (only rows whose metrics changed)." (TASK-07.)
- `docs/operations/metrics-dedup-runbook.md` — new runbook (TASK-09).
- Do **not** edit migrations 023/024; document the behaviour change in 070's header and the data docs.

**Open assumptions (ratified 2026-05-27):**

1. Scope both tables — RESOLVED (human chose "Both").
2. Freshness from refresh run, no `last_checked_at` column — RESOLVED (human chose "Derive from refresh run").
3. `VACUUM FULL` one-time prod reclaim — RESOLVED (human chose "VACUUM FULL one-time").
4. Scout refactor complete; canonical path `scout/youtube/refresh.py` — RESOLVED (human confirmed 2026-05-27).

**Tasks:**

- TASK-07: Skip-if-unchanged in the refresh write path (both tables) + helper unit tests + behaviour docs
- TASK-08: Migration 070 — one-time dedup of existing `video_metrics` + `channel_metrics` snapshots
- TASK-09: Prod reclaim runbook + deferred `VACUUM FULL` size verification

---

## Completed work

Completed plans are **not** archived in this file. When a plan's tasks are all done, its durable record is a run report under [`docs/build/runs/`](./runs/) (see the [index](./runs/README.md)) and the plan is removed from "Active plan" above. This document holds only active/future plans; the run reports are the system of record for what shipped.

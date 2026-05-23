---
tags: [area/architecture, area/operations]
---

# API Surface

> Created 2026-05-12. Inventory of every endpoint the Jeromelu API exposes today, with a proposal to reorganise admin endpoints under per-agent URL prefixes. **The live OpenAPI spec at `/openapi.json` is the authoritative inventory**; this doc is the readable view + the migration target.

---

## How the surface is organised

There are three kinds of endpoints, each with a different organising principle:

| Kind | Examples | Organising principle |
|---|---|---|
| **Public** | `/api/feed`, `/api/wiki/pages`, `/api/ask` | Grouped by *user-facing feature*. Users don't know about crew agents. |
| **Admin (operator)** | `/api/admin/scout/refresh-videos`, `/api/admin/players/refresh` | Should be grouped by *crew agent owner* — the agent whose work the endpoint triggers, monitors, or corrects. |
| **System** | `/health` | Cross-cutting, no agent. |

The public surface is feature-aligned and largely fine where it is. The admin surface is where the reorganisation pays off — today admin endpoints are scattered across 8 routers with inconsistent grouping (`/api/admin/players/*` for SuperCoach roster, `/api/admin/scout/*` for media refresh, `/api/admin/recon/*` for Scout's approval queue, `/api/admin/presenters/*` for Analyst's presenter identification — all four are agent-owned but live under different prefixes).

---

## Inventory — public endpoints (29)

### Feed (`/api/feed/*`, `/api/jaromelu/*`)

Surfaces the crew's activity stream and Jaromelu's voice.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/feed` | Paginated feed events |
| POST | `/api/feed/ask` | Embedded chat within the feed |
| GET | `/api/jaromelu/status` | Live crew-status indicator ("Scout is scanning…") |

### Wiki (`/api/wiki/*`)

Read surface for entity pages and revision history.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/wiki/pages` | List wiki pages (filters: page_type, status, q) |
| GET | `/api/wiki/pages/{slug}` | Page detail + revisions + linked_pages map |
| GET | `/api/wiki/pages/{slug}/revisions` | Full revision history for a page |
| GET | `/api/wiki/recent-changes` | Recent revisions across all pages |
| GET | `/api/wiki/channels/{slug}/episodes` | Latest sources for a channel-backed page |

### Sources (`/api/sources/*` — read-side)

Source detail page reads (the source-review page).

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/sources` | List all sources with claim_count + voice |
| GET | `/api/sources/{source_id}` | Source detail (chunks, claims, speakers) |

### Ask Me (`/api/ask`)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/ask` | Direct Ask-Jaromelu chat |

### Insights / Analysis (`/api/insights/*`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/insights` | List articles |
| GET | `/api/insights/{kb_id}` | Article detail |

### Squad (`/api/squad/*`) — SuperCoach extension

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/squad` | Current squad |
| GET | `/api/squad/history` | Trade history, captain choices |

### Utility reads

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/people/search` | Player/person typeahead |
| GET | `/api/round/{round_num}` | Round overview |
| GET | `/api/stats` | Aggregate counts (homepage hero numbers) |

---

## Inventory — admin endpoints (29)

Today these live across 8 routers and are inconsistently namespaced. Each row's **proposed owner** column anticipates the reorganisation below.

### Currently in `routers/scout.py` *(none — Scout admin lives in `routers/recon.py`)*

### Currently in `routers/recon.py` (9)

| Method | Path | Purpose | Proposed owner |
|---|---|---|---|
| GET | `/api/admin/recon/candidates` | List Scout discovery candidates pending approval | **Scout** |
| GET | `/api/admin/recon/candidates/{candidate_id}` | Single candidate detail | **Scout** |
| POST | `/api/admin/recon/candidates/{candidate_id}/approve` | Approve a candidate | **Scout** |
| POST | `/api/admin/recon/candidates/{candidate_id}/reject` | Reject a candidate | **Scout** |
| GET | `/api/admin/recon/stats` | Discovery queue stats | **Scout** |
| GET | `/api/admin/scout/channel-coverage` | Per-channel funnel audit | **Scout** |
| POST | `/api/admin/scout/channels/{channel_ref}/refresh-videos` | Refresh one channel's videos | **Scout** |
| POST | `/api/admin/scout/refresh-channel-stats` | Daily channel stats sweep | **Scout** |
| POST | `/api/admin/scout/refresh-videos` | Daily video metadata refresh | **Scout** |

### Currently in `routers/players.py` (4)

| Method | Path | Purpose | Proposed owner |
|---|---|---|---|
| POST | `/api/admin/players/seed` | First-time roster seed from SuperCoach JSON | **Scout** |
| POST | `/api/admin/players/refresh` | Weekly SCD-2 roster refresh from JSON payload | **Scout** |
| POST | `/api/admin/players/fetch-and-refresh` | Server-side fetch + SCD-2 (one call) | **Scout** |
| POST | `/api/admin/players/refresh-nrlcom` | NRL.com roster cross-reference refresh | **Scout** |

### Currently in `routers/presenters.py` (5)

| Method | Path | Purpose | Proposed owner |
|---|---|---|---|
| GET | `/api/admin/presenters/by-channel/{channel_id}` | List presenter candidates per channel | **Analyst** |
| GET | `/api/admin/presenters/candidates` | List all presenter candidates | **Analyst** |
| POST | `/api/admin/presenters/candidates/{candidate_id}/confirm` | Confirm a presenter identification | **Analyst** |
| POST | `/api/admin/presenters/candidates/{candidate_id}/reject` | Reject a presenter identification | **Analyst** |
| POST | `/api/admin/presenters/scout/{channel_id}` | Trigger presenter scout for a channel | **Analyst** |

### Currently in `routers/admin.py` (8)

| Method | Path | Purpose | Proposed owner |
|---|---|---|---|
| POST | `/api/admin/ingest` | Transcript ingest | **Analyst** |
| POST | `/api/admin/ingest-raw` | Raw transcript ingest | **Analyst** |
| GET | `/api/admin/pipeline/items` | Cross-agent pipeline diagnostic view | **Cross-cutting (Ops)** |
| GET | `/api/admin/pipeline/summary` | Cross-agent pipeline summary | **Cross-cutting (Ops)** |
| GET | `/api/admin/sync-status` | System sync status | **Cross-cutting (Ops)** |
| GET | `/api/admin/transcript-test-files` | List transcript test fixtures | **Analyst (dev tool)** |
| GET | `/api/admin/transcript-diff/{filename}` | Show transcript diff for a fixture | **Analyst (dev tool)** |
| POST | `/api/admin/update-clean-text` | Operator override of cleaned transcript | **Analyst** |

### Currently in `routers/sources.py` — face / speaker admin (10 endpoints, public path)

These are operator tools on the source-review page, *not* public reads. The URL is currently `/api/sources/{source_id}/...` for both reads and writes.

| Method | Path | Purpose | Proposed owner |
|---|---|---|---|
| PATCH | `/api/sources/speakers/{segment_id}` | Rename a speaker segment | **Analyst** |
| POST | `/api/sources/{source_id}/speakers/{segment_id}/reassign` | Reassign a speaker segment | **Analyst** |
| GET | `/api/sources/{source_id}/face-runs` | List face runs for a source | **Analyst** |
| POST | `/api/sources/{source_id}/face-runs/assign` | Bulk-assign a face run | **Analyst** |
| POST | `/api/sources/{source_id}/face-runs/move-run` | Move a run between clusters | **Analyst** |
| POST | `/api/sources/{source_id}/face-clusters/recompute` | Recompute face clusters | **Analyst** |
| POST | `/api/sources/{source_id}/face-clusters/{cluster_id}` | Override a face cluster | **Analyst** |
| GET | `/api/sources/{source_id}/face-track` | Get face-track JSON for video overlay | **Analyst** |
| POST | `/api/sources/{source_id}/face-track/regenerate` | Regenerate face track | **Analyst** |
| GET | `/api/sources/{source_id}/face-crop` | Single face-crop image | **Analyst** |
| GET | `/api/sources/{source_id}/face-groups` | Face groups summary | **Analyst** |

### Currently in `routers/squad.py` (2 admin)

| Method | Path | Purpose | Proposed owner |
|---|---|---|---|
| POST | `/api/admin/squad/set` | Set current squad | **Operator (SuperCoach gameplay)** |
| POST | `/api/admin/squad/trade` | Record a trade | **Operator (SuperCoach gameplay)** |

### Currently in `routers/teams.py` (1 admin)

| Method | Path | Purpose | Proposed owner |
|---|---|---|---|
| POST | `/api/admin/teams/seed` | One-off seed of team identity rows | **Scout (identity acquisition)** |

---

## Inventory — system (1)

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness probe |

---

## Proposed reorganisation

Per-agent URL prefix for every admin endpoint. The shape:

```
/api/admin/<agent>/<resource-or-action>
```

### Target structure

| Prefix | Owner | What lives here | Today's analog |
|---|---|---|---|
| `/api/admin/scout/*` | Scout | All acquisition: media discovery, audio, SuperCoach roster + stats, NRL.com fetchers, recon approval queue, team-identity seed | Scattered across `/api/admin/scout/*`, `/api/admin/recon/*`, `/api/admin/players/*`, `/api/admin/teams/*` |
| `/api/admin/analyst/*` | Analyst | Transcript ingest, transcript cleaning, presenter identification, face cluster / face track / face run admin, speaker rename / reassign | Scattered across `/api/admin/ingest*`, `/api/admin/transcript-*`, `/api/admin/update-clean-text`, `/api/admin/presenters/*`, `/api/sources/{id}/face-*`, `/api/sources/{id}/speakers/*` |
| `/api/admin/archivist/*` | Archivist | Wiki update sessions (Phase 1+ of Archivist build) | Doesn't exist yet |
| `/api/admin/bookkeeper/*` | Bookkeeper | Math jobs — alignment indices, advisor accuracy, consensus snapshots | Doesn't exist yet (some math runs inside other endpoints today) |
| `/api/admin/ops/*` | Cross-cutting | Pipeline diagnostic view, sync status, system health | `/api/admin/pipeline/*`, `/api/admin/sync-status` |
| `/api/admin/squad/*` | Operator (SuperCoach gameplay) | Squad set, trades | `/api/admin/squad/*` (already correctly placed) |

### Full migration map (admin endpoints)

| Today | Proposed | Owner | Notes |
|---|---|---|---|
| `POST /api/admin/scout/refresh-videos` | `POST /api/admin/scout/refresh-videos` | Scout | ✓ already correct |
| `POST /api/admin/scout/refresh-channel-stats` | `POST /api/admin/scout/refresh-channel-stats` | Scout | ✓ already correct |
| `POST /api/admin/scout/channels/{channel_ref}/refresh-videos` | `POST /api/admin/scout/channels/{channel_ref}/refresh-videos` | Scout | ✓ already correct |
| `GET /api/admin/scout/channel-coverage` | `GET /api/admin/scout/channel-coverage` | Scout | ✓ already correct |
| `GET /api/admin/recon/candidates` | `GET /api/admin/scout/recon/candidates` | Scout | Move under scout |
| `GET /api/admin/recon/candidates/{id}` | `GET /api/admin/scout/recon/candidates/{id}` | Scout | Move under scout |
| `POST /api/admin/recon/candidates/{id}/approve` | `POST /api/admin/scout/recon/candidates/{id}/approve` | Scout | Move under scout |
| `POST /api/admin/recon/candidates/{id}/reject` | `POST /api/admin/scout/recon/candidates/{id}/reject` | Scout | Move under scout |
| `GET /api/admin/recon/stats` | `GET /api/admin/scout/recon/stats` | Scout | Move under scout |
| `POST /api/admin/players/seed` | `POST /api/admin/scout/supercoach-roster/seed` | Scout | Phase 1 of charter — supercoach_roster module |
| `POST /api/admin/players/refresh` | `POST /api/admin/scout/supercoach-roster/refresh` | Scout | Phase 1 of charter |
| `POST /api/admin/players/fetch-and-refresh` | `POST /api/admin/scout/supercoach-roster` | Scout | Phase 1 of charter; alias the legacy path |
| `POST /api/admin/players/refresh-nrlcom` | `POST /api/admin/scout/nrlcom-roster` | Scout | Phase 3 of charter — separate pipeline |
| `POST /api/admin/teams/seed` | `POST /api/admin/scout/teams/seed` | Scout | Identity acquisition |
| `POST /api/admin/ingest` | `POST /api/admin/analyst/ingest` | Analyst | Transcript ingest — Analyst territory (Q4 resolved) |
| `POST /api/admin/ingest-raw` | `POST /api/admin/analyst/ingest-raw` | Analyst | Raw transcript ingest — Analyst territory (Q4 resolved) |
| *(future)* | `POST /api/admin/scout/ingest` | Scout | Scout's audio-acquisition path (currently CLI-only via `make collect-audio`). HTTP-wraps when needed; namespace reserved alongside `analyst/ingest` per Q4 |
| `POST /api/admin/update-clean-text` | `POST /api/admin/analyst/cleaning/override` | Analyst | Operator override of cleaned chunk |
| `GET /api/admin/transcript-test-files` | `GET /api/admin/analyst/dev/transcript-fixtures` | Analyst | Dev tool, namespaced |
| `GET /api/admin/transcript-diff/{filename}` | `GET /api/admin/analyst/dev/transcript-fixtures/{filename}/diff` | Analyst | Dev tool, namespaced |
| `GET /api/admin/presenters/candidates` | `GET /api/admin/analyst/presenters/candidates` | Analyst | All presenter admin under analyst |
| `GET /api/admin/presenters/by-channel/{channel_id}` | `GET /api/admin/analyst/presenters/by-channel/{channel_id}` | Analyst | |
| `POST /api/admin/presenters/candidates/{id}/confirm` | `POST /api/admin/analyst/presenters/candidates/{id}/confirm` | Analyst | |
| `POST /api/admin/presenters/candidates/{id}/reject` | `POST /api/admin/analyst/presenters/candidates/{id}/reject` | Analyst | |
| `POST /api/admin/presenters/scout/{channel_id}` | `POST /api/admin/analyst/presenters/discover/{channel_id}` | Analyst | Verb renamed `scout` → `discover` to avoid collision with the Scout crew member (Q1 resolved) |
| `GET /api/sources/{source_id}/face-runs` | `GET /api/admin/analyst/sources/{source_id}/face-runs` | Analyst | Face admin moves out of the public /api/sources/* namespace |
| `POST /api/sources/{source_id}/face-runs/assign` | `POST /api/admin/analyst/sources/{source_id}/face-runs/assign` | Analyst | |
| `POST /api/sources/{source_id}/face-runs/move-run` | `POST /api/admin/analyst/sources/{source_id}/face-runs/move-run` | Analyst | |
| `POST /api/sources/{source_id}/face-clusters/recompute` | `POST /api/admin/analyst/sources/{source_id}/face-clusters/recompute` | Analyst | |
| `POST /api/sources/{source_id}/face-clusters/{cluster_id}` | `POST /api/admin/analyst/sources/{source_id}/face-clusters/{cluster_id}` | Analyst | |
| `GET /api/sources/{source_id}/face-track` | `GET /api/admin/analyst/sources/{source_id}/face-track` | Analyst | |
| `POST /api/sources/{source_id}/face-track/regenerate` | `POST /api/admin/analyst/sources/{source_id}/face-track/regenerate` | Analyst | |
| `GET /api/sources/{source_id}/face-crop` | `GET /api/admin/analyst/sources/{source_id}/face-crop` | Analyst | |
| `GET /api/sources/{source_id}/face-groups` | `GET /api/admin/analyst/sources/{source_id}/face-groups` | Analyst | |
| `PATCH /api/sources/speakers/{segment_id}` | `PATCH /api/admin/analyst/speakers/{segment_id}` | Analyst | |
| `POST /api/sources/{source_id}/speakers/{segment_id}/reassign` | `POST /api/admin/analyst/sources/{source_id}/speakers/{segment_id}/reassign` | Analyst | |
| `GET /api/admin/pipeline/items` | `GET /api/admin/ops/pipeline/items` | Ops | Cross-cutting diagnostic |
| `GET /api/admin/pipeline/summary` | `GET /api/admin/ops/pipeline/summary` | Ops | Cross-cutting diagnostic |
| `GET /api/admin/sync-status` | `GET /api/admin/ops/sync-status` | Ops | System health |
| `POST /api/admin/squad/set` | `POST /api/admin/squad/set` | Operator | ✓ stays |
| `POST /api/admin/squad/trade` | `POST /api/admin/squad/trade` | Operator | ✓ stays |

### What changes at the *file* layout level

Per [D9 of the Scout charter](../agents/crew/scout/charter.md), each Scout pipeline already has its own folder with a `routes.py`. Applying the same shape to admin endpoints across the API:

```
services/api/app/
├── routers/                          # legacy / cross-cutting only
│   ├── ops.py                        # NEW: pipeline + sync-status (was admin.py)
│   ├── squad.py                      # public squad reads
│   ├── ask.py                        # /api/ask
│   ├── feed.py                       # /api/feed/*
│   ├── crew.py                       # /api/jaromelu/status, /api/round/{n}
│   ├── insights.py                   # /api/insights/*
│   ├── wiki.py                       # /api/wiki/* (Archivist public reads)
│   ├── sources.py                    # /api/sources/* (read-only after migration)
│   ├── people.py                     # /api/people/search
│   └── stats.py                      # /api/stats
├── scout/                            # Scout's admin endpoints land here per D9
│   ├── loop.py · refresh.py · …      # legacy media flat files
│   ├── supercoach_roster/routes.py   # NEW
│   ├── supercoach_stats/routes.py    # NEW
│   ├── nrlcom_matches/routes.py      # NEW
│   ├── nrlcom_teamlists/routes.py    # NEW
│   ├── nrlcom_injuries/routes.py     # NEW
│   ├── nrlcom_rounds/routes.py       # NEW
│   ├── teams_seed/routes.py          # NEW (or stays in scout/data/)
│   └── recon/routes.py               # NEW (moves out of routers/recon.py)
├── analyst/                          # Analyst's admin endpoints land here
│   ├── transcribe.py · diarize.py · …  # existing
│   ├── ingest/routes.py              # NEW (moves out of routers/admin.py)
│   ├── cleaning/routes.py            # NEW (operator override)
│   ├── presenters/routes.py          # NEW (moves out of routers/presenters.py)
│   ├── faces/routes.py               # NEW (moves out of routers/sources.py)
│   ├── speakers/routes.py            # NEW (moves out of routers/sources.py)
│   └── dev/routes.py                 # NEW (transcript fixtures, dev tools)
├── archivist/                        # Phase 1+ of Archivist build (doesn't exist yet)
│   └── sessions/routes.py            # future
└── bookkeeper/                       # future
    └── derivations/routes.py         # future
```

The pattern: **each agent folder owns its admin endpoints**. `routers/` becomes the home for public surfaces (feed, wiki reads, ask, etc.) and cross-cutting ops.

---

## Migration phasing

This is a big reorganisation. Phase to minimise back-compat risk.

### Phase A — New endpoints land under the new pattern from day one (no migration cost)

Anything *not yet built* — Archivist endpoints, Bookkeeper endpoints, new Scout pipelines (supercoach-roster Phase 1 onwards) — ships directly under the proposed structure. Already locked in the Scout charter via D9.

### Phase B — Aliases for existing endpoints

For each legacy admin path: add the new path as an alias that calls into the same handler. Old path stays live, marked `@deprecated` in code. Caller-facing breaking change: none.

Example: `POST /api/admin/scout/supercoach-roster` is added (per Phase 1 of the Scout charter); `POST /api/admin/players/fetch-and-refresh` becomes an alias.

### Phase C — Move handlers to agent folders

Move the implementation out of `routers/<old>.py` into `services/api/app/<agent>/<resource>/routes.py`. The aliases stay live; the new path is now canonical.

### Phase D — Remove deprecated aliases

After a release cycle (or two) where the new paths have been live and all callers have migrated, remove the legacy aliases. Caller-facing breaking change: yes — needs an announcement.

### Sequence

- **Phase A** is automatic (only applies to net-new work).
- **Phase B + C can ship per-agent**, not all at once:
  1. Scout admin (already partially done — Phase 1 of Scout charter does this for SuperCoach roster)
  2. Analyst admin (the largest migration — 18 endpoints across 4 routers + sources.py)
  3. Ops (3 endpoints — small, can ship anytime)
- **Phase D** waits until every caller is on the new paths and metrics confirm no traffic on the legacy ones.

---

## What stays put (no migration)

These don't fit the agent-aligned model and stay where they are:

- All **public reads** — `/api/feed/*`, `/api/wiki/*`, `/api/ask`, `/api/insights/*`, `/api/sources` and `/api/sources/{source_id}` (the *read* form), `/api/squad/*` (the public reads), `/api/people/search`, `/api/round/{round_num}`, `/api/stats`, `/api/jaromelu/status`.
- **Health** — `/health`.
- **Squad admin** — `/api/admin/squad/*` is operator-only SuperCoach gameplay, not crew work.

### Explicit read/write split for `/api/sources/*` (Q5)

After migration, `/api/sources/*` is **read-only and public**; every administrative operation that mutates source data lives under `/api/admin/analyst/sources/*`. The frontend (source-review page) calls **both** namespaces:

| Frontend action | Endpoint | Namespace |
|---|---|---|
| Render the source page (video, transcript, claims) | `GET /api/sources/{source_id}` | Public |
| List all sources for the index | `GET /api/sources` | Public |
| Rename a speaker segment | `PATCH /api/admin/analyst/speakers/{segment_id}` | Admin (Analyst) |
| Reassign a speaker | `POST /api/admin/analyst/sources/{source_id}/speakers/{segment_id}/reassign` | Admin (Analyst) |
| Recompute face clusters | `POST /api/admin/analyst/sources/{source_id}/face-clusters/recompute` | Admin (Analyst) |
| Bulk-assign a face run | `POST /api/admin/analyst/sources/{source_id}/face-runs/assign` | Admin (Analyst) |
| Regenerate face track | `POST /api/admin/analyst/sources/{source_id}/face-track/regenerate` | Admin (Analyst) |
| ...etc. for every face/speaker mutation | `POST/PATCH /api/admin/analyst/sources/{source_id}/*` | Admin (Analyst) |

Frontend code that today bundles read + write under `/api/sources/{id}/*` will need a small refactor at Phase C of the migration to call the new admin paths. Read paths keep working unchanged.

---

## Resolved questions (2026-05-12)

1. **The "presenter scout" naming collision.**
   *Question:* `POST /api/admin/presenters/scout/{channel_id}` uses "scout" as a verb, but it's an Analyst operation — confusing alongside the Scout crew member's endpoints.
   **Resolution: rename the verb.** New path is `POST /api/admin/analyst/presenters/discover/{channel_id}`. Migration map updated accordingly.

2. **Public face/speaker endpoints.**
   *Question:* Today's face/speaker mutations sit under `/api/sources/{source_id}/*` mixed with public reads. Move to `/api/admin/analyst/sources/*`?
   **Resolution: yes, move to Analyst.** The full read/write split is now explicit (see §"Explicit read/write split for `/api/sources/*`" above). Public `/api/sources/*` stays; every mutation goes under `/api/admin/analyst/sources/*`. Frontend will need a small refactor at Phase C.

3. **`/api/admin/teams/seed` ownership.**
   *Question:* One-off seed of team identity rows — Scout or its own concern?
   **Resolution: Scout owns it.** New teams enter rarely (~once a season at most) so the pipeline is very slow-moving, but identity acquisition is a Scout responsibility per D1 of the charter regardless of cadence. Path becomes `POST /api/admin/scout/teams/seed`.

4. **`/api/admin/ingest` vs Scout's audio acquisition.**
   *Question:* The names overlap; both Scout and Analyst have "ingest"-shaped work.
   **Resolution: both namespaces are valid; they refer to different work.** `POST /api/admin/analyst/ingest` (and `/ingest-raw`) handle transcript persistence — Analyst's territory. `POST /api/admin/scout/ingest` is the future HTTP wrapper for Scout's audio acquisition (currently CLI-only via `make collect-audio`); namespace reserved for when that becomes an admin endpoint. Migration map carries both.

5. **`/api/sources` vs `/api/admin/analyst/sources/*` clarity.**
   *Question:* Mixed namespace risk after migration.
   **Resolution: be explicit.** Read-only public lives at `/api/sources/*`; every write goes to `/api/admin/analyst/sources/*`. Documented in §"Explicit read/write split for `/api/sources/*`" with a per-action mapping table.

6. **Bookkeeper public read surface.**
   *Question:* The Alignment Index / advisor accuracy / consensus shifts are user-facing. `/api/ledger/*` or `/api/bookkeeper/*`?
   **Resolution: move to the appropriate agent owner when built.** Today none of these endpoints exist. When they ship: admin operations (refresh alignment index, recompute consensus) at `/api/admin/bookkeeper/*`; the **public ledger surface** (what the Ledger page reads) lands under its own feature path — `/api/ledger/*` is the natural choice, consistent with `/api/wiki/*` and `/api/feed/*` being feature-aligned rather than agent-aligned. Users don't think in agents; readers do think in pages.

---

## Documentation maintenance

This doc has two failure modes:
1. **Endpoints get added or renamed and this doc isn't updated** — readers get a wrong picture.
2. **The doc gets stale as the implementation diverges from the proposal** — readers confuse target with current state.

Two mitigations:
- The **inventory section** could be auto-generated from OpenAPI at commit time (a `make api-doc` target that overwrites the inventory tables). Worth doing once the proposal stabilises.
- The **proposed reorganisation section** is point-in-time and frozen after migration completes; new endpoints land under the target structure directly and the migration map is preserved as historical reference.

For now, hand-maintained. Revisit auto-generation once the migration is underway.

---

## Related

- [Scout charter expansion (draft)](../agents/crew/scout/charter.md) — D9 establishes the folder-per-pipeline pattern this doc extends across all agents
- [Crew docs](../agents/crew/README.md) — who the agents are
- Live OpenAPI: `http://localhost:8000/openapi.json` (dev) — authoritative source of current shape

---
tags: [area/architecture, subarea/agents]
status: draft
---

# Scout Charter Expansion (Draft)

> Draft. Last reviewed: 2026-05-12. **Decisions D1–D7 locked 2026-05-12.** Ready for Phase 0 (doc reconciliation).
>
> Formalises the proposal in [`docs/pages/wiki/data-feeds.md`](../../pages/wiki/data-feeds.md) §"Scout's expanded charter": Scout's scope should grow from *media inventory* to *all external data acquisition*. This includes the SuperCoach scraper, NRL.com fetchers (matches, team lists, injuries, rounds), and any future external sources of truth. Cleaning, parsing, diarisation, and claim extraction stay with the Analyst.

---

## What this draft is for

The data-feeds doc surfaced that the input layers feeding the wiki are owned by **three different crew/system concepts**: Scout (media), the scraper (numeric NRL data — currently Bookkeeper-owned), and the player-roster pipeline (identity). The split is artificial — acquisition is one job regardless of source. This draft proposes consolidating that job under Scout, lays out the architectural pattern that makes it work, and stages the migration.

It does **not** propose changing what the Analyst, Bookkeeper, or Archivist do downstream — only changes where the data they consume comes from.

---

## Decisions to lock before any code is written

### D1. The boundary principle

**Recommendation: Scout owns every external source of truth.** If data comes from outside Jeromelu — a third-party API, a public JSON endpoint, a scraped HTML page, an RSS feed, an mp3 from a podcast host — Scout fetches it. Anything *derived* inside Jeromelu (claim extraction, embeddings, KB synthesis, voiceprint clustering, agreement-edges between advisors) stays downstream and is not Scout's.

This principle gives one answer to *"who fetches X?"* for every X, including future expansions (Twitter/X mentions, blog RSS, Reddit, league injury reports). Scout, always.

### D2. One agent or many?

**Recommendation: one Scout identity, multiple execution modules.** All acquisition runs under `agent_id='scout'` in the audit table, with `detail_json.pipeline` discriminating which module ran (`media-discovery`, `supercoach-roster`, `supercoach-stats`, `nrlcom-matches`, `nrlcom-teamlists`, `nrlcom-injuries`, `nrlcom-rounds`, `youtube-refresh`, etc.). Each pipeline is its own module under `services/api/app/scout/`; they share utilities (audit, idempotency, rate-limiting) but execute independently.

This mirrors how Scout's media work is already structured today — `scout/loop.py`, `scout/refresh.py`, `scout/audio.py` are already sibling modules under one agent identity. The expansion adds more siblings, not a new architecture.

### D3. Cron orchestration

**Recommendation: external cron hitting admin endpoints.** Each Scout pipeline exposes a `POST /api/admin/scout/<pipeline>` endpoint that returns a `run_id`. Cron (or the `scheduler` skill, or a `make` target) just hits the endpoint with the admin key. This matches the existing pattern — the daily YouTube refresh already works this way per [scout.md §3.4](../../agents/crew/scout.md) — and avoids introducing a new container or scheduler service for the prod footprint we already have.

A future Phase 5 could replace external cron with an in-process APScheduler if cadence management becomes painful, but that's not the V1 problem.

### D4. Disposition of `services/worker-scraper/`

**Recommendation: migrate the activities into per-pipeline folders under `services/api/app/scout/` per D9; retire the Temporal worker.** Per project memory, Temporal is not in production. The activities (`teamlists.py` and any siblings) become module-level functions inside the relevant pipeline folder (`scout/nrlcom_teamlists/fetcher.py`, etc.), called from admin endpoints under the unified Scout audit pattern. The `worker-scraper` directory stays in tree for a phase, with no new code, and is retired in Phase 4.

### D5. Skills disposition

**Decision (locked): no Claude Code skills for deterministic fetchers.** The endpoint + cron is the surface. Ad-hoc operator runs use the endpoint directly (curl, a `make` target, or the admin UI when one exists), not a skill. The existing `scrape-supercoach` Claude Code skill is retired as part of Phase 1 — operators move to hitting the endpoint.

The Claude Agent SDK remains the right tool for *agentic* work — Scout's existing media-discovery loop uses it, and any future build that needs a Claude agent to *orchestrate* a Scout fetch (e.g. as one tool call inside a larger reasoning loop) can call the same endpoint. The endpoint is the universal surface; skills are not on the critical path.

### D6. Audit granularity

Tied to D2 — single `agent_id='scout'`, pipeline discriminator in `detail_json`. This gives one dashboard ("is Scout healthy?") that breaks down by pipeline when needed.

### D7. Idempotency contract

**Every Scout pipeline writes idempotent upserts on natural keys.** Re-running the same fetch with no upstream change is a no-op. Existing media pipelines already mostly hold this property; spelling it out as a Scout-wide contract makes the property load-bearing for the cron orchestration in D3 (cron can hammer the endpoint without consequence).

| Pipeline | Natural key for upsert |
|---|---|
| `supercoach-roster` | `external_id` on `people` |
| `supercoach-stats` | `(player_id, season, round)` on `player_rounds` |
| `nrlcom-matches` | `(season, round, home_team_id, away_team_id)` on `matches` |
| `nrlcom-teamlists` | `(match_id, player_id)` on `match_team_lists` |
| `nrlcom-injuries` | `(person_id, reported_at)` on `injuries` |
| `nrlcom-rounds` | `(season, round_number)` on `rounds` |
| `youtube-discovery` | `(platform, kind, external_id)` on `scout_candidates` (existing) |

### D8. Upstream schema drift — test-fail, never silent-adapt

**Decision (locked 2026-05-12):** Every Scout scraper module ships with **endpoint-drift tests**. When the upstream source's response shape changes — new fields, removed fields, renamed fields, type changes, response-shape reorganisation — the test fails loudly and routes to the user. The agent does not auto-adapt or degrade to partial data.

**Why:** External sources (`nrl.com`, `supercoach.com.au`, `nrlsupercoachstats.com`, Zero Tackle) are out of our control. Silent degradation — e.g. a renamed field becoming null in every row — would propagate wrong/incomplete content downstream into the wiki. The user wants to be the one who decides the response: rewrite the parser, wait for the source to revert, accept the change, switch sources.

**Concrete contract** (applies to every pipeline folder under `services/api/app/scout/`):

1. **Fixture in repo.** Each module ships with `tests/fixtures/scout/<pipeline>/canonical_response.json` — a known-good sample of the upstream response.
2. **Strict Pydantic parsing.** Response models use `Config.extra = 'forbid'` so unknown fields raise rather than getting silently dropped.
3. **Drift test.** `tests/integration/scout/<pipeline>/test_response_shape.py` parses the fixture with the live model and asserts the shape; **and** has a "live mode" variant (env-flagged) that fetches the real endpoint and runs the same assertion.
4. **Actionable failure messages.** Test output names the endpoint and the specific drift — e.g. *"nrl.com /draw/data: unknown field `is_byzantine_round` on match object"* — so the fix is targeted.
5. **Drift surfaces to a human.** Either CI runs the live-mode drift tests on a schedule, or a separate cron pings the live endpoint and runs the parser. Failures go to the user, not into a silent log.

This decision tightens the mitigation language that was previously in Risk #4 ("logs unknown fields rather than crashing") into a hard requirement.

### D9. Code organisation — folder per pipeline

**Decision (locked 2026-05-12):** Each Scout pipeline lives in its own folder under `services/api/app/scout/<pipeline_name>/`. The folder contains every concern that pipeline owns: fetcher logic, Pydantic models, admin endpoint, per-pipeline README.

**Why:** Each pipeline has multiple concerns (fetch + parse + persist + endpoint + drift fixture + tests). Packing them into a single `.py` either bloats the file or scatters concerns across the tree. The test layout already uses folder-per-pipeline (`tests/fixtures/scout/<pipeline>/`, `tests/integration/scout/<pipeline>/`), so flat source files would create asymmetry. New module = `cp -r` an existing one and edit; the folder *is* the template.

**Naming convention:**

- Python paths (module folder, Python identifiers, test folder): **snake_case** — e.g. `supercoach_roster`.
- URL paths and pipeline labels (`detail_json.pipeline`, admin endpoint URL, `make` target): **kebab-case** — e.g. `supercoach-roster`.
- The two are 1:1 translations. Code that wants the pipeline label from the module name does `module.__name__.split('.')[-1].replace('_', '-')`.

**Source layout per pipeline:**

```
services/api/app/scout/supercoach_roster/
├── __init__.py          # public exports
├── fetcher.py           # the fetch function (HTTP, parsing)
├── models.py            # Pydantic strict models (Config.extra = 'forbid')
├── routes.py            # admin endpoint (POST /api/admin/scout/supercoach-roster)
└── README.md            # source, cadence, natural key, ownership
```

**Test layout mirrors source:**

```
tests/fixtures/scout/supercoach_roster/canonical_response.json
tests/unit/api/scout/supercoach_roster/test_fetcher.py
tests/unit/api/scout/supercoach_roster/test_models.py
tests/integration/scout/supercoach_roster/test_response_shape.py
tests/integration/scout/supercoach_roster/test_endpoint.py
```

**Out of scope for this charter:** Migrating the existing flat media-discovery files (`loop.py`, `refresh.py`, `audio.py`, `video.py`, `presenters.py`, `youtube_api.py`) into `scout/media/`. That refactor has no functional change; the new convention coexists with the legacy flat files until the media migration happens as separate work. The asymmetry is temporary and self-documenting — anything in a folder follows the new convention; anything flat at the top level is legacy media discovery on the migration roadmap.

---

## The expanded charter

### What Scout owns under the expansion

| Acquisition pipeline | Source of truth | Module location | Status |
|---|---|---|---|
| Media discovery (YouTube) | YouTube Data API + web | `services/api/app/scout/loop.py`, `refresh.py` | ✅ shipped |
| Audio acquisition | yt-dlp | `services/api/app/scout/audio.py` | ✅ shipped |
| Video metadata refresh | YouTube Data API | `services/api/app/scout/refresh.py` | ✅ shipped |
| **SuperCoach player roster** | SuperCoach API | move from `scripts/data/fetchers/fetch_supercoach_players.py` → `services/api/app/scout/supercoach_roster/` | 🟡 fetcher exists, not folder-organised, not audit-wrapped |
| **SuperCoach per-round stats** | SuperCoach API | move from `scripts/data/fetchers/fetch_player_stats.py` + `worker-scraper` → `services/api/app/scout/supercoach_stats/` | 🟡 fetcher exists, not folder-organised, not audit-wrapped |
| **NRL.com matches + draw** | nrl.com `/draw/data`, match-centre `/data` | move from `scripts/data/fetchers/fetch_match_stats.py` → `services/api/app/scout/nrlcom_matches/` | 🟡 fetcher exists, not folder-organised, not audit-wrapped |
| **NRL.com team lists** | nrl.com `/teamlists/data` | move from `scripts/data/fetchers/fetch_teamlists.py` + `worker-scraper/teamlists.py` → `services/api/app/scout/nrlcom_teamlists/` | 🟡 fetcher exists, not folder-organised, not audit-wrapped |
| **NRL.com casualty ward** | nrl.com `/casualty-ward/data` | new `services/api/app/scout/nrlcom_injuries/` | ❌ not built |
| **NRL.com round metadata** | nrl.com `/draw/data` (round-level) | new `services/api/app/scout/nrlcom_rounds/` | ❌ not built |
| Future: podcasts, Twitter/X, blogs, Reddit | RSS / API / web | backlog | ❌ scope only |

### What Scout still does NOT do (Extract-only rule, unchanged)

- **Cleaning, parsing, diarisation, embedding** — Analyst.
- **Speaker → Person attribution** — Analyst.
- **Claim / quote extraction** — Analyst.
- **Cross-source consensus / contradiction detection** — Analyst.
- **Numerical derivations** (advisor-accuracy index, alignment scores, breakeven trajectories beyond what the source itself reports) — Bookkeeper.
- **Wiki composition** — Archivist.
- **Voicing** — Jaromelu.

The Extract-only rule is the spine of the charter — Scout fetches raw, persists raw, sets `ingestion_status='collected'`, and stops. Every downstream agent reads from Scout's outputs; Scout never reads back from them.

---

## Architecture under the new charter

```
External world
       │
       ▼
┌──────────────────────────────────────────────────┐
│ Scout (one agent identity, many modules)         │
│                                                  │
│  Media (legacy flat files, scout/media/ later):  │
│    • discovery (loop.py + refresh.py)            │
│    • audio acquisition (audio.py)                │
│    • metadata refresh                            │
│                                                  │
│  Data (folder per pipeline, per D9):             │
│    • scout/supercoach_roster/    (NEW)           │
│    • scout/supercoach_stats/     (NEW)           │
│    • scout/nrlcom_matches/       (NEW)           │
│    • scout/nrlcom_teamlists/     (NEW)           │
│    • scout/nrlcom_injuries/      (NEW)           │
│    • scout/nrlcom_rounds/        (NEW)           │
└──────────────────────────────────────────────────┘
       │
       ▼
   Raw tables (sources, people, player_rounds, …)
       │
       ▼
┌──────────────────────────────────────────────┐
│ Analyst — cleaning, diarisation, extraction  │
│ Bookkeeper — math, derivations               │
│ Archivist — wiki prose composition           │
│ Jaromelu — voicing                           │
└──────────────────────────────────────────────┘
```

**Shared shape across all Scout modules:**

1. Each module exposes a single function (e.g. `refresh_supercoach_roster(session) -> RunResult`) that fetches, upserts idempotently, returns counts.
2. Each module gets an admin endpoint (`POST /api/admin/scout/<pipeline>`) that wraps the function in the `agent_runs` audit pattern (`record_agent_started/ended`).
3. Each module's wrapper writes one `agent_runs` row with `agent_id='scout'`, `detail_json.pipeline='<module>'`, plus per-run counts (rows fetched, rows upserted, rows skipped, errors).
4. Each module is independently cron-triggerable via the endpoint.
5. Each module emits unknown-field warnings to `agent_events` when the upstream source returns shapes the parser doesn't recognise — early-warning for source drift.

This is the pattern Scout's media side already follows; the expansion just instantiates it for more modules.

---

## Phasing

### Phase 0 — Scope reconciliation in docs (~half a day)

- Land this draft after review.
- Update [`scout.md`](../../agents/crew/scout.md): §"What Scout DOES cover" gains the new modules; §"What Scout DOES NOT cover" loses "Numeric NRL data" and "Player roster registry"; pipeline-position diagram updated.
- Reframe [`scraper.md`](../../agents/system/scraper.md) as a Scout component (specifically: the `worker-scraper` Temporal worker, marked for retirement) rather than a Bookkeeper subsystem.
- Update [`bookkeeper.md`](../../agents/crew/bookkeeper.md): consume-only over Scout-fetched data; Bookkeeper no longer acquires anything.
- Update [`crew/dynamics.md`](../../agents/crew/dynamics.md) Cadence row: Bookkeeper trigger becomes "Scout scrape complete" instead of "scraper sweep complete".
- Update [`crew/README.md`](../../agents/crew/README.md) Bookkeeper one-liner.

### Phase 1 — One pipeline migrated end-to-end (the proof slice)

Pick the smallest pipeline: **SuperCoach player roster**. It already has a working fetcher script and a skill (to be retired).

- Move `scripts/data/fetchers/fetch_supercoach_players.py` → `services/api/app/scout/supercoach_roster/` (folder per D9) as a callable function (no behavioural changes).
- **Add the D8 drift fixture and test:** `tests/fixtures/scout/supercoach_roster/canonical_response.json` + `tests/integration/scout/supercoach_roster/test_response_shape.py` (Pydantic-strict, live-mode env-flagged). This is the pattern every subsequent pipeline copies — getting it right on Phase 1 means it's cheap to apply for Phases 2-4.
- Add `POST /api/admin/scout/supercoach-roster` endpoint that wraps the function in the agent audit pattern.
- Add a `make scout-supercoach-roster` target for ad-hoc operator runs that hits the endpoint with admin auth.
- Retire the `scrape-supercoach` Claude Code skill — operators use the endpoint or the `make` target.
- Schedule via external cron — daily.
- Phase 1 done = the SuperCoach roster refreshes daily, an audit row lands per run, the drift test runs in CI (fixture-mode) and on a schedule (live-mode), the `make` target works for ad-hoc operator use, the skill is retired, and `people`/`people_attributes` row counts move when the upstream data does.

### Phase 2 — SuperCoach per-round stats (the high-leverage one)

Same pattern applied to `fetch_player_stats.py`. This is the **highest-leverage move on the entire roadmap** — it's what unblocks `player_rounds` from being empty and turns 600+ wiki stubs into pages with actual `## Current Form` and `## Price Analysis` content.

- Move into `services/api/app/scout/supercoach_stats/` (folder per D9).
- Admin endpoint + cron (post-round cadence, plus on-demand for re-pulls).
- The existing `services/worker-scraper/` Temporal worker can stop being touched after this; its activities are now sibling Scout modules.

### Phase 3 — NRL.com fetchers (matches + team lists)

Migrate `fetch_match_stats.py` and `fetch_teamlists.py` into `scout/nrlcom_matches/` and `scout/nrlcom_teamlists/` (folders per D9). Same endpoint/cron pattern.

This unblocks team pages (`## Recent Results`, `## Key Players`) and round pages (`## Team Lists`, `## Results`).

### Phase 4 — New NRL.com fetchers (injuries + rounds)

Build the two pipelines that don't exist yet: `nrlcom_injuries.py` and `nrlcom_rounds.py` against the public endpoints documented in `MEMORY.md`. These are net-new code, not migrations.

Retire `services/worker-scraper/` at the end of this phase — no Scout work runs through it anymore.

### Phase 5 — Unified Scout dashboard

A single operator view at `/admin/scout` showing health across every Scout pipeline (media + identity + stats + fixtures + injuries). Reads from `agent_runs` filtered by `agent_id='scout'`, groups by `detail_json.pipeline`. No new data — just the view.

This phase isn't blocked by anything earlier; could ship in parallel with Phase 2-4 to give visibility while migration happens.

### Phase 6 (future) — Multi-platform expansion

The roadmap items in [`scout.md` §4 "Multi-platform expansion"](../../agents/crew/scout.md) (podcasts, Twitter/X, blogs, Reddit) instantiate the same shape: each becomes a `scout/<platform>_<thing>/` folder with an admin endpoint. Out of scope for this draft; tracked for visibility.

---

## Architectural risks

1. **Endpoint is the only surface.** Per D5 there are no Claude Code skills for deterministic fetchers, so the duality risk doesn't exist. The remaining concern is that the `make` targets are kept in sync with the endpoint paths — handled by a single integration test that exercises the target → endpoint → DB path end-to-end.

2. **NRL.com rate limits / unauthenticated endpoint volatility.** Hammering nrl.com endpoints could get blocked or break when they restructure. Mitigation: per-pipeline rate limiter (e.g. one request per second, configurable per module); each module logs unknown response fields to `agent_events` so we get signal when the source shape changes; cron cadences are conservative (daily, not hourly).

3. **One-process overload.** All Scout pipelines running in the API process means a hung fetcher blocks API throughput. Mitigation: endpoints kick off the fetch as a FastAPI background task with hard wall-clock bounds (matching Scout's media pattern); endpoint returns the `run_id` immediately rather than waiting for completion.

4. **Schema drift in fetcher outputs.** SuperCoach API or NRL.com endpoint shapes can change silently — new fields, renamed fields, removed fields. Mitigation is locked in **D8**: strict Pydantic parsing + fixture-backed drift tests + live-mode scheduled runs that surface failures to the user. The agent does not auto-adapt.

5. **Bookkeeper-shaped hole in the crew docs.** Moving acquisition out of Bookkeeper's territory leaves [`bookkeeper.md`](../../agents/crew/bookkeeper.md) with a smaller, less-clearly-defined scope. Mitigation: Phase 0 doc updates explicitly redefine Bookkeeper as the *derivation/math* layer over Scout-fetched data — alignment indices, accuracy scores, trend extraction, breakeven-trajectory math. Not nothing, but narrower than today.

6. **Cron ownership ambiguity.** "External cron" per D3 is correct but vague — who actually maintains the crontab? Probably the same place Scout's media refresh cron lives today; needs to be documented.

7. **Phase 1 fetch reliability.** The SuperCoach roster fetch already runs as a skill — but if it fails on first endpoint-wrapped run because of an auth/permission issue we didn't see in skill mode, Phase 1 stalls. Mitigation: dry-run mode on every new endpoint that exercises the full fetch path but doesn't write.

---

## Cost, testing, rollout

### Cost

Effectively **zero** for the deterministic pipelines (no LLM calls). The agent_audit cost columns will all be `$0.00` for Scout modules other than the existing agentic media-discovery loop. Worth noting in the dashboard so it doesn't look broken — Scout's cost story is "media-discovery LLM runs cost something; everything else is free."

### Testing

| Tier | What it covers |
|---|---|
| Unit (`tests/unit/api/scout/<pipeline>/`) | Each module's response parser + upsert logic with a mocked HTTP client. Fast, deterministic. Mirrors the source folder per D9. |
| Integration (`tests/integration/scout/<pipeline>/`) | Round-trip against a fixture HTTP server that serves canned SuperCoach / NRL.com responses. Validates the endpoint wrapper, audit row creation, idempotency on re-run. |
| **Drift detection** (`tests/integration/scout/<pipeline>/test_response_shape.py`) | Per D8: fixture-backed shape assertion + env-flagged live-mode variant that fetches the real endpoint. Fails on any unknown field, missing field, or type change. Live-mode runs on a schedule so upstream drift surfaces to the user, not into a silent log. |
| Smoke (manual) | Operator runs each new endpoint once against the live source in staging; reviews the audit row and the upserted rows. |

No eval suite — these are deterministic fetchers. The eval suite belongs to the Analyst's claim-extraction and the Archivist's prose composition, not to Scout.

### Rollout

Each pipeline migration follows the same shape:

1. Land the pipeline folder under `scout/<pipeline_name>/` with the endpoint, dry-run-tested.
2. Run live once via the endpoint, review the audit row + upserted rows by hand.
3. Run live three more times manually, watch for unknown-field warnings.
4. Enable cron; observe for a week.
5. Decommission the old script path (skill keeps working via the endpoint).

Five steps × six pipelines is the bulk of the migration work — couple of weeks of focused work after Phase 0.

---

## Documentation Updates

The full list (matching [`data-feeds.md` §Documentation Updates](../../pages/wiki/data-feeds.md#documentation-updates)) plus this draft's own changes:

| Doc | Change |
|-----|--------|
| [`docs/agents/crew/scout.md`](../../agents/crew/scout.md) | Major rewrite of §scope, §pipeline position, §components. Adds all new modules. Removes "Numeric NRL data" and "Player roster registry" from §"What Scout DOES NOT cover". |
| [`docs/agents/system/scraper.md`](../../agents/system/scraper.md) | Reframe as a Scout component (the `worker-scraper` Temporal worker, marked for retirement). Cross-link to Scout instead of Bookkeeper. |
| [`docs/agents/crew/bookkeeper.md`](../../agents/crew/bookkeeper.md) | Scope clarification: derivation/math over Scout-fetched data; acquisition moved out. |
| [`docs/agents/crew/README.md`](../../agents/crew/README.md) | Update Bookkeeper one-liner. |
| [`docs/agents/crew/dynamics.md`](../../agents/crew/dynamics.md) | Cadence: Bookkeeper trigger row updates from "scraper sweep complete" to "Scout scrape complete". |
| [`docs/pages/wiki/data-feeds.md`](../../pages/wiki/data-feeds.md) | Replace "*proposed*" / "*tracked as a follow-up*" hedges with links to this draft and the implementing migrations as each phase ships. |
| New: `docs/agents/system/scout-data-acquisition.md` | Companion doc to `scout.md`; operational details for each new pipeline (CLI, endpoint, cron cadence, debugging). Splits the doc weight so `scout.md` stays readable. |
| New: `services/api/app/scout/README.md` | Top-level Scout README explaining the folder-per-pipeline convention (D9), how to add a new pipeline (cp -r template), and the legacy-flat-media-files exception. |

---

## Open questions

1. **Cron mechanics.** "External cron" is right architecturally but the prod box doesn't have a documented crontab pattern yet. Where do schedules actually land? Same place Scout's daily YouTube refresh runs today; needs to be documented as part of Phase 1.
2. **Auth on admin endpoints.** Today's pattern is `X-Admin-Key` (per `scout.md` §3.4). Reused for all the new Scout endpoints; rotating story unchanged.
3. **One module per data table, or one module per source?** E.g. is `nrlcom_matches.py` separate from `nrlcom_rounds.py` (both come from `/draw/data`)? Lean: one module per *upstream endpoint*, even if it writes multiple tables. Simpler to rate-limit and audit.
4. **Source-of-truth conflicts.** SuperCoach has player rosters; NRL.com has team lists. When they disagree (player listed at HOK in SuperCoach but FRF on the team list), who wins? Almost certainly: SuperCoach for "registered position", NRL.com for "this match's lineup". Worth documenting; not a blocker for the migration.
5. **Backfill strategy.** For historical `player_rounds`, do we backfill all of 2025 + 2026 on first run, or only refresh forward from now? Per-pipeline decision — for the wiki to have meaningful trend data, backfill is needed.
6. **Source-of-truth for advisor identity.** `people_roles` for advisors is currently empty (no advisors have been registered). Under the expansion, where do advisor entities get created? Probably manual today, becomes Analyst-derived once diarisation lands; not a Scout job either way. Worth a note.

---

## Drafting notes (delete before merge)

This draft formalises the data-feeds doc's §"Scout's expanded charter" without re-litigating the principle. The bulk of the new content is the **phasing**, the **architecture under the new charter** (one identity, many modules), and the **idempotency contract** in D7 — those are the implementation-shape decisions that need to be locked before any code moves.

The most consequential decision is D4 — retiring the Temporal worker. It's the right call given the project memory note that Temporal isn't in production, but it means `services/worker-scraper/` migrates *into* the API process. That's a footprint shift that should be obvious to anyone watching prod for the first time after the migration lands; flag it in the relevant operational docs.

The Bookkeeper scope shrinkage (Risk #5) is the second-most-consequential. Bookkeeper currently owns the scraper; after this, Bookkeeper owns *math over the scraped data*. Worth a separate, focused pass on the Bookkeeper docs once this draft is approved — the role isn't smaller, it's *clearer*, and saying that clearly is worth the doc work.

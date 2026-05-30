---
tags: [area/agents, subarea/crew]
---

# Scout — Status & Roadmap

> Last reviewed: 2026-05-24.

The forward plan for Scout, in three layers:

1. **Charter phasing (Phase 0–7)** — the staged migration of all external data acquisition under Scout, per [charter.md](charter.md). Phase 0–2 shipped; Phase 2.5 onward is the remaining work.
2. **YouTube depth + multi-platform** — the media-side roadmap (capabilities on the existing platform, then new platforms).
3. **Future improvements** — additive enhancements that layer on top of what's built.

Status labels:
- **Shipped** — live in production or dev
- **In design** — specced; implementation not started
- **Planned** — committed scope; no design yet
- **Backlog** — deferred or candidate; no commitment

---

## Charter phasing (Phase 0–7)

The expanded charter ([charter.md](charter.md)) stages the migration of all external data acquisition under Scout. Per-pipeline details (S3 paths, DB extraction targets, endpoints) live in the charter's pipeline-inventory tables.

### Phase 0 — Scope reconciliation in docs (~half a day) ✅

- Land the charter after review.
- Update Scout's crew docs: §"What Scout DOES cover" gains the new modules; §"What Scout DOES NOT cover" loses "Numeric NRL data" and "Player roster registry"; pipeline-position diagram updated.
- Reframe [`scraper.md`](../../system/scraper.md) as a Scout component (specifically: the `worker-scraper` Temporal worker, marked for retirement — **retired and deleted 2026-05-28** as part of Phase 4 / TASK-28) rather than a Bookkeeper subsystem.
- Update [`bookkeeper.md`](../bookkeeper/README.md): consume-only over Scout-fetched data; Bookkeeper no longer acquires anything.
- Update [`dynamics.md`](../dynamics.md) Cadence row: Bookkeeper trigger becomes "Scout scrape complete" instead of "scraper sweep complete".
- Update [crew `README.md`](../README.md) Bookkeeper one-liner.

### Phase 1 — One pipeline migrated end-to-end (the proof slice) ✅

Pick the smallest pipeline: **SuperCoach player roster**. The step-by-step record of this slice is the bullet list below.

> **Skill retired 2026-05-27.** The `scrape-supercoach` Claude Code skill was a thin wrapper around `make fetch-players` (which runs `fetch_supercoach_players.py` + `generate_players_yaml.js`) — it owned no logic, so deleting it removed no capability. Operators now run `make fetch-players` (local roster + `data/players.yaml` regen) or the `scout-supercoach-roster` endpoint/`make` target. The transcript-cleaning pipeline still reads `data/players.yaml`; rehoming that to read the roster from the DB is a **separate** open loop (it never actually gated this retirement — see [Analyst roadmap](../analyst/roadmap.md)).

- Move `scripts/data/fetchers/fetch_supercoach_players.py` → `services/api/app/scout/supercoach_roster/` (folder per D9) as a callable function (no behavioural changes).
- **Add the D8 drift fixture and test:** `tests/fixtures/scout/supercoach_roster/canonical_response.json` + `tests/integration/scout/supercoach_roster/test_response_shape.py` (Pydantic-strict, live-mode env-flagged). This is the pattern every subsequent pipeline copies — getting it right on Phase 1 means it's cheap to apply for Phases 2-4.
- Add `POST /api/admin/scout/supercoach-roster` endpoint that wraps the function in the agent audit pattern.
- Add a `make scout-supercoach-roster` target for ad-hoc operator runs that hits the endpoint with admin auth.
- ✅ Retire the `scrape-supercoach` Claude Code skill (done 2026-05-27) — operators use the endpoint or the `make` target.
- Schedule via external cron — daily.
- Phase 1 done = the SuperCoach roster refreshes daily, an audit row lands per run, the drift test runs in CI (fixture-mode) and on a schedule (live-mode), the `make` target works for ad-hoc operator use, the skill is retired, and `people`/`player_attributes` row counts move when the upstream data does.

### Phase 2 — SuperCoach per-round stats (the high-leverage one) ✅

Same pattern applied to `fetch_player_stats.py`. This is the **highest-leverage move on the entire roadmap** — it's what unblocks `player_rounds` from being empty and turns 600+ wiki stubs into pages with actual `## Current Form` and `## Price Analysis` content.

- Move into `services/api/app/scout/supercoach_stats/` (folder per D9).
- Admin endpoint + cron (post-round cadence, plus on-demand for re-pulls).
- The existing `services/worker-scraper/` Temporal worker stopped being touched after this; its activities are now sibling Scout modules. **(Worker retired and deleted 2026-05-28 as part of Phase 4 / TASK-28.)**

### Phase 2.5 — Bronze (S3-first) retrofit ✅ + lightweight SC siblings ✅ Shipped

The **bronze/S3-first retrofit is done** — `scout/supercoach_roster/` and `scout/supercoach_stats/` archive the raw response to S3 (D10) and strict-parse it (D8) before DB extraction (`_s3_archive.archive_response`; `s3_archive_key` recorded per run). The lightweight SC siblings **shipped 2026-05-24**:

- ✅ Shipped: `scout/supercoach_teams/` — tiny (17 rows, ~3KB), weekly cron (Mon 23:30 UTC), S3 archive at `scout/supercoach/classic/teams/{season}.json`, cross-references `teams.metadata_json.supercoach` (17/17 NRL clubs matched on the seed run). D8 fixture + unit + env-flagged live drift tests.
- ✅ Shipped: `scout/supercoach_settings/` — captures SC game rules (lockouts, scoring config, captains/emergencies/dual-position rules) per season; weekly cron (Mon 23:35 UTC, classic mode), S3 archive at `scout/supercoach/{mode}/settings/{season}/{YYYYMMDD}.json`, DB snapshots into `sc_settings`. Draft mode stays on-demand. D8 fixture + unit + live (classic + draft) drift tests.
- ✅ Done: one-time S3 seed for season 2026 (classic teams + classic/draft settings) — S3 archives and `sc_settings` rows verified 2026-05-24.

### Phase 3 — NRL.com draw + match-centre ingest ✅ Shipped (extractors → Phase 3.5)

The two capture pipelines that feed the wiki's match data. **Ingest shipped 2026-05-24** — D8-hardened, scheduled, seeded. The pre-existing fetch+archive code was retrofitted to charter discipline (the same pattern as Phase 2.5). The DB extractors that actually light up wiki pages are Phase 3.5.

- ✅ Shipped: `scout/nrlcom_draw/` — `/draw/data` per (competition, season, round) → S3; `NrlcomDraw`+`DrawFixture` D8 models, strict-parse wired into the route (drift → 500), daily cron (current round, 18:00 UTC). Discovers each match's `matchCentreUrl`.
- ✅ Shipped: `scout/nrlcom_match_centre/` — walks the round's fixtures, fetches `/.../{slug}/data/` per match → S3. **Highest-leverage capture** (lineups, per-player 58-field stats, 100+ timeline events, officials). D8 union envelope (FullTime/Upcoming state-dependent), non-aborting per-match validation, round-optional (resolves the current round), daily cron (18:15 UTC). Seeded R12/2026 — 5/5 matches, 0 validation failures.
- ⏳ Phase 3.5: DB extractors — `extract_matches` (writes `matches`, `match_team_lists`, `player_match_stats`, `match_timeline`, `match_officials`) + the `player_round_stats` extractor against nrlcom + nrlsupercoachstats with D11 trust-hierarchy merge.

Phase 3.5 unblocks: every team page's `## Recent Results`, every round page's `## Team Lists` + `## Results`, and every player page's per-match history including timeline events (try at 53', sin bin, etc.). Phase 3 (ingest) is the S3-archived, drift-protected foundation those extractors read.

### Phase 4 — NRL.com casualty ward + ladder ✅ Shipped (2026-05-28)

D8-hardened ingest (envelope **and** item/stats strict — deeper than draw/match-centre because the extractors are live), scheduled daily, seeded to prod, extractors unit-tested. NRL only (comp 111), season 2026, forward-only — historical backfill is Phase 5.

- ✅ Shipped: `scout/nrlcom_casualty_ward/` — `/casualty-ward/data?competition=111` → timestamped S3 key (`scout/nrlcom/casualty-ward/111/{YYYYMMDD}.json`); `NrlcomCasualtyWard` + `Casualty` D8 models (`extra="forbid"`); strict-parse wired into the route (drift → 500); daily cron 18:30 UTC. Live drift test under `SCOUT_DRIFT_LIVE=1`. Seeded 2026-05-28 (99 casualties; `validated:true` live).
- ✅ Shipped: `scout/nrlcom_ladder/` — `/ladder/data?competition=111&season=Y` → `scout/nrlcom/ladder/111/{season}/round-{NN}.json`; `NrlcomLadder` + `LadderPosition` + `LadderStats` D8 models (the 22 metrics use space-separated upstream keys mapped via `Field(alias=...)` with `populate_by_name=True`); strict-parse wired into the route; daily cron 18:45 UTC. Seeded 2026-05-28 (17 teams, round 12; `validated:true` live).
- ✅ Shipped: DB extractors `populate_injuries` (state-machine over daily snapshots → `injuries`) and `populate_team_standings` (UPSERT per `(team, comp, season, round)` → `team_standings`) in `scripts/data/populate/phase_aux.py`, with pure-function unit tests (`tests/unit/scripts/data/populate/test_phase_aux.py`). Latent `jsonb_build_object` parameter-typing bug in the injuries UPDATE branch fixed during seed verification (surfaced on the first real-archive run). Prod DB post-seed: `team_standings` 51 rows / 94% team_id resolution; `injuries` 130 rows / 99 open / 93% team_id resolution.
- ✅ Done: retired `services/worker-scraper/` — directory deleted + live doc references swept (Phase 4 closure, TASK-28, 2026-05-28). Per D4: it was orphaned (no code, compose, CI, or deploy-script refs); [`scraper.md`](../../system/scraper.md) remains as historical reference.

**Ops scheduling follow-up shipped (SCOUT-OPS-SCHED):** `scripts/scout-populate.sh`
now stages `scripts/` + `packages/` into the running `jeromelu-api` container and
executes `populate_db_from_s3` there. `scripts/cron.d/jeromelu` runs
`scout-populate.sh nrlcom-current` daily after the nrl.com archive jobs, so the
latest NRL.com captures project into DB tables without a manual operator run.
Season-aware phases receive the current season; identity/re-resolution phases may
inspect existing DB rows to keep links coherent. Historical S3 backfills remain
deliberate one-off runs.

### Phase 4.5 — NRL.com stats + players roster ✅ Shipped (2026-05-28)

Hardening replay of the existing (but unhardened) `scout/nrlcom_stats/` + `scout/nrlcom_players_roster/` ingest folders + the existing `populate_stat_leaderboards` extractor. Discovery (2026-05-28) found the fetchers/routes/`make` targets + migration 060 + the extractor already shipped pre-phase; the gap was the D8 contract, route ValidationError-aborts, extractor unit tests via pure-function refactor, cron scheduling, and prod seed verification. NRL only (comp 111), season 2026, forward-only — historical backfill stays Phase 5.

- ✅ Shipped: `scout/nrlcom_stats/` — D8 four-level strict (envelope + category + subgroup + leader, with single-model player-vs-team leader bifurcation per the `NrlcomDraw.videoProviders` precedent); route ValidationError → 500; live drift test under `SCOUT_DRIFT_LIVE=1`; daily cron 18:50 UTC; `_extract_leader_rows` pure-function refactor + 6 unit tests. **Seeded 2026-05-28** — 347 rows in `stat_leaderboards` for 2026/comp=111 (100% person_id resolution, 98.8% team_id resolution); 4,595 rows across all 14 seasons.
- ✅ Shipped: `scout/nrlcom_players_roster/` — D8 envelope + group + flat-`Profile` strict (live shape simpler than plan anticipated; no nested `ProfileBody` needed); route ValidationError → 500; live drift test under `SCOUT_DRIFT_LIVE=1`; new `POST /api/admin/scout/nrlcom-players-roster/refresh-all` endpoint walks 17 NRL teams server-side at 1 req/sec (~20s wall time); weekly Mon 23:40 UTC cron. **17-team catalogue** (`NRL_TEAM_IDS` constant) derived from the response's own `filterTeams[]` — no S3 ladder/draw read needed. **Seeded 2026-05-28** — 17/17 teams walked with `validated:true`, errors:[], 549 player profiles in S3. **No new DB extractor this phase** (S3-only) — the existing HTML-scrape `jeromelu_shared/players/nrlcom_refresh.py` enrichment is untouched.

**Deferred (out of scope, surfaced not self-queued):**
- SuperCoach Draft mode (`scout/supercoach_draft_*`) — parallel of classic, if Draft becomes a product concern.
- Folding `jeromelu_shared/players/nrlcom_refresh.py` (HTML profile scraper) into the `scout/nrlcom_players_roster/` folder per D9. The HTML-scrape and JSON-fetch are different upstream sources reaching different enrichment fields; the fold is a refactor concern, not a hardening one.
- Tightening `Profile` identity-field types from `str | None` to `str` non-null when a future `/players/data` extractor lands.

### Phase 5 — Historical backfill (one-time, ~4-5 hours operationally) — In design

Per D12. Each pipeline supports a `?season=Y[&round=N]` backfill mode that hits the same admin endpoint with explicit parameters. One-time operator-triggered job per pipeline:

1. `make scout-backfill SOURCE=nrlcom-draw SEASON_FROM=1908` → ~3,000 GETs over 1h
2. `make scout-backfill SOURCE=nrlcom-match-centre SEASON_FROM=2000` → ~5,200 GETs over 3-4h
3. `make scout-backfill SOURCE=nrlcom-ladder` → 30 GETs
4. `make scout-backfill SOURCE=nrlcom-stats` → 14 GETs
5. `make scout-backfill SOURCE=supercoach-stats SEASON_FROM=2018` → ~250 jqGrid sessions over 1-2h

Total: ~4-5 hours single-machine, rate-limited at 1 req/sec per origin. ~1-2GB S3.

Backfill produces the same S3 keys daily cron does — re-running future cron over the same range is a no-op.

### Phase 6 — Unified Scout dashboard — Shipped

Operator view at `/admin/scout` showing health across every pipeline (media + identity + stats + fixtures + injuries + ladder + leaderboards). Reads from `agent_runs` filtered by `agent_id='scout'`, groups by `detail_json.pipeline`. Per-pipeline: last run, status, row counts, cost. No new data — just the view.

API slice: `GET /api/admin/scout/dashboard` is read-only and groups recent
Scout `agent_runs` rows by `detail_json.pipeline`, returning last run status,
timestamps, summary, compact detail counts, recent failure count, and cost
rollups. The admin web surface now includes a Scout Dashboard tab that reads
that endpoint, supports refresh/window controls, and displays compact pipeline
rollups beside the existing admin operator panels.

### Phase 7 (future) — Multi-platform expansion — Backlog

The multi-platform roadmap items below (podcasts, radio, TV shows, Twitter/X, Instagram, blogs, Reddit) instantiate the same shape: each becomes a `scout/<platform>_<thing>/` folder with an admin endpoint. Out of scope for the charter proper; tracked for visibility.

---

## YouTube — depth on the existing platform

| Capability | Status | Notes |
|---|---|---|
| **Deterministic discovery surface (§3.1)** — `youtube_search` + `find_related_channels` with server-side `filter_known=True` | In design | Spec recorded in [architecture.md §3.1](architecture.md). Promotes the former "Tier 2" to a first-class architectural change. |
| Refocus agentic Scout brief on off-platform + long-tail (instead of competing with deterministic) | Planned | Tied to §3.1 landing |
| Admin review queue UI at `/admin/recon` | In design | Backend endpoints shipped; UI not started |
| Live Recon SSE stream in `/pulse` (theatric reasoning visible to users) | Planned | Drives the visible-reasoning UX |
| `Event` rows for the reasoning trace (Pulse feed integration) | Backlog | TBD when live stream lands |
| Scheduled Scout runs (cron / APScheduler) for the agentic surface | Planned | Manual CLI only today |
| **Weekly channel-metadata refresh** — periodic re-snapshot of subs/views/video count and active/inactive detection (extends §3.4) | Planned | Channel metadata only written at approval today |
| **Source health / liveness monitoring** — detect stalled channels, 404 sources, transcript fetch failures, caption regenerations | Backlog | Not built |
| Audio acquisition surface (Scout owns yt-dlp → S3) | Shipped (2026-05-03) | `make collect-audio SOURCE_ID=...`. Diarised transcription split out to Analyst. |
| Recurring drain job for `ingestion_status='pending'` sources | Backlog | Single-source CLI today; APScheduler / cron driver is the next slice. |
| Backfill of legacy `source_chunks_v1` (221k auto-caption chunks) | Backlog | Re-extract via Scout audio + Analyst transcribe on highest-leverage channels first; ~$50 for top-5. |
| Production ingestion off Temporal | Shipped | `IntelSweepWorkflow` superseded by Scout `audio.py` + Analyst `transcribe.py`. Worker code remains in tree for reference but is not invoked. |
| `agent_runs` rows for deterministic jobs (3.2, 3.3, 3.4) | Backlog | Currently logged as plain HTTP requests / cron output; standardising would unify cost/health dashboards across agentic + deterministic components |

---

## Multi-platform expansion

Schema (`platform` field on `scout_candidates` / `sources`) is already platform-agnostic. Each new platform instantiates the same shape: discovery surface (det + agentic) → approval → enumerate → refresh → extract. **All entries below are Backlog** until cross-platform identity (see Future improvements) is decided.

**Platform vs. format — and YouTube's gravity.** Scout acquires by *platform* (where it fetches); NRL media arrives in *formats* (what the content is — panel/podcast, radio show, TV show). The two are orthogonal, and the key fact is **YouTube's gravity**: most NRL podcasts publish there, many radio segments are re-uploaded there, and TV shows (NRL 360, the Matty Johns Show, panel shows) surface as clips and full episodes there. So the **shipped YouTube pipeline already reaches most of this content** — a re-uploaded radio show or TV episode is just a YouTube video with a format tag. The rows below are therefore the *off-YouTube residual*: native sources for content **not** re-uploaded (standalone podcast RSS, live-radio capture, paywalled broadcaster TV, social, web) — harder and rarer, hence Backlog. The schema piece that makes formats navigable independent of where they were acquired is a `format` / `content_type` tag on `sources` (podcast / radio / tv / panel / written) — not built yet.

| Platform / format | Discovery surface | Content extraction | Notes |
|---|---|---|---|
| **Podcasts** (YouTube / Apple / Spotify) | Most NRL podcasts are on YouTube (shipped pipeline); RSS catalogue search only for feeds not re-uploaded | Already captured as a YouTube video, *or* RSS enumerate → mp3 → transcribe | Mostly reachable via YouTube already; standalone RSS is the residual. |
| **Radio** (Triple M, SEN, ABC Grandstand) | Re-uploads caught by the YouTube pipeline; native live-radio capture (scheduled stream recording) is the residual | Audio → transcribe | Prefer YouTube re-uploads / show podcast feeds; native live capture is low-priority. |
| **TV shows** (NRL 360, Matty Johns Show, panel shows) | Clips + full episodes mostly on YouTube (shipped); native broadcaster (Fox League / Nine) is paywalled | YouTube video → transcribe | Re-uploads cover most of it; native broadcaster capture is paywalled and hard — defer. |
| **Twitter / X** (NRL personalities) | Manual seed list + agentic for adjacent accounts | API or scrape; tweets become `source_chunks` directly (no transcription) | Quote-extraction value high, signal-to-noise low. API now paid/restricted; scraping is ToS-fraught. |
| **Instagram** (clubs / players / NRL accounts) | Manual seed list + agentic for adjacent accounts | Captions → `source_chunks`; Reels audio → transcribe (like YouTube) | **Hardest acquisition** — auth-gated, anti-scraping, ToS-restrictive. Official club / injury news but brittle; lowest priority. |
| **Blogs / news** (Roar, NRL.com features, club sites) | RSS where available + agentic web search for new outlets | RSS enumerate → article HTML → readability extract | Off-platform discovery already works for these via §3.2; missing piece is structured ingestion. |
| **Reddit** (r/nrl, club subs) | API search for high-engagement threads, weekly | Thread + top comments to `source_chunks` | Community signal; complements expert-driven sources. |

---

## Future improvements

Additive — they layer on top of Tier 1 (already built: known-set injection + bulk dedupe) without replacing it.

> **Note:** The former "Tier 2 — YouTube-aware tools" entry has been promoted to a first-class architectural change — see [architecture.md §3.1](architecture.md) (in design) and the YouTube roadmap above.

**Tier 3 — Coverage-gap biasing (agentic surface)**
- Pre-run, count `scout_candidates.content_categories` (and, post multi-platform, `platform`) to find underrepresented dimensions
- Inject "Coverage gaps:" paragraph into the user brief to bias the run
- Most useful once §3.1 lands and the agentic surface is dedicated to long-tail work. Becomes especially valuable when multi-platform lands and "underrepresented" is multi-axis (category × platform).

**Quality scoring on §3.1 candidates**
- Deterministic discovery has no semantic filter — it persists everything novel
- Options: lightweight heuristic scorer (sub count, upload frequency, channel age), or a small batch LLM pass that reads About pages for raw candidates and assigns score + content_categories
- Becomes important if §3.1 floods `scout_candidates` with low-signal results

**Cross-platform deduplication**
- Once multi-platform lands, the same person/show may appear on YouTube + podcast feed + Twitter. The `scout_candidates.platform` axis avoids accidental re-onboarding on the same platform but doesn't link them across platforms.
- Add a `source_identity` concept (or use `channels.canonical_handle` consistently) so an Analyst querying "what has Pat Souness said this week" pulls across all platforms a single creator publishes on.

---

## Related

- [README.md](README.md) — Scout's identity, scope, and voice
- [architecture.md](architecture.md) — pipeline position, flow, component internals
- [charter.md](charter.md) — locked design decisions D1–D13

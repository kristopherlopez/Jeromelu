---
tags: [area/architecture, subarea/agents]
status: draft
---

# Scout Charter Expansion (Draft)

> Draft. Last reviewed: 2026-05-12. **Decisions D1–D13 locked 2026-05-12.** Phase 0 doc reconciliation shipped; Phase 1 (SuperCoach roster) shipped; Phase 2 (SuperCoach stats) shipped.
>
> Formalises the proposal in [`docs/pages/wiki/data-feeds.md`](../../pages/wiki/data-feeds.md) §"Scout's expanded charter": Scout's scope grows from *media inventory* to *all external data acquisition*. The full surface area — verified by direct endpoint exploration on 2026-05-12 — spans **nrl.com** (6 endpoints, history back to 1908 for fixtures and 2000 for full match-centre detail), **supercoach.com.au** (6 endpoints across classic + draft modes, current + prior season only), and **nrlsupercoachstats.com** (1 jqGrid endpoint, 9 seasons of history). Cleaning, parsing, diarisation, and claim extraction stay with the Analyst.

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

### D10. Storage — JSON-first to S3, DB derivative

**Decision (locked 2026-05-12):** Every Scout fetch writes the **raw upstream response to S3 first**. The DB layer is downstream: extractors read S3 snapshots and project them into structured tables. The pipeline owns S3; DB extraction is a separate concern that can be re-run independently.

**Why:** We don't yet know the full schema we want for every endpoint, and we want every endpoint's history captured before we lock decisions. JSON-first means: (a) **re-extractable** — adding a new field to the DB schema replays against S3, no re-fetch needed; (b) **drift-detectable** — the saved raw object is the artifact you diff when the D8 test fires; (c) **historical-once** — backfill writes to S3 once and the DB extractor can be re-run forever; (d) **cheap** — ~1-2GB of S3 covers years of NRL data; (e) **decoupled** — schema changes don't require touching the fetcher.

**Bucket convention:** `s3://jeromelu-clean-documents/scout/{source}/{pipeline}/{...identity path}.json`

```
s3://jeromelu-clean-documents/scout/
├── nrlcom/
│   ├── draw/{competition}/{season}/round-{NN}.json
│   ├── match-centre/{competition}/{season}/round-{NN}/{slug}.json
│   ├── casualty-ward/{competition}/{YYYYMMDD}.json
│   ├── stats/{competition}/{season}.json
│   ├── ladder/{competition}/{season}/round-{NN}.json
│   └── players-roster/{competition}/{team_slug}.json
├── supercoach/
│   ├── classic/players-cf/{season}/{YYYYMMDD}.json
│   ├── classic/teams/{season}.json
│   ├── classic/settings/{season}/{YYYYMMDD}.json
│   ├── draft/players-cf/{season}/{YYYYMMDD}.json
│   ├── draft/teams/{season}.json
│   └── draft/settings/{season}/{YYYYMMDD}.json
└── nrlsupercoachstats/
    └── stats/{season}/round-{NN}.json   (NN = '00' for Totals)
```

**Path rules:**
- **Path = idempotency.** Same (source, identity) → same S3 key → overwrite. No accidental duplication.
- **No timestamp in path for "current state" snapshots** that overwrite daily (roster, ladder, draw). S3 versioning preserves yesterday's snapshot if needed.
- **Timestamp in path** for time-series data where every day's snapshot matters (casualty ward, SC players-cf because notes drop continuously).
- **Round-keyed** for immutable per-match data (match-centre post-FullTime).

**Drift fixtures** under `tests/fixtures/scout/{pipeline}/canonical_response.json` are **subsets** of the same S3 objects — trimmed for size and committed for CI.

### D11. Trust hierarchy — which source wins per field

**Decision (locked 2026-05-12):** Where multiple sources expose the same field, the higher-trust source is canonical:

**`nrl.com` > `supercoach.com.au` > `nrlsupercoachstats.com`**

Rationale: nrl.com is the league's own publication of structural truth (fixtures, results, lineups, officials, injuries). SuperCoach is the official second-degree source (their own product reflecting NRL data + their fantasy overlay). `nrlsupercoachstats.com` is a third-party aggregator — useful precisely because it exposes derivations SC doesn't publish (the SC scoring breakdown: base/attack/playmaking/power/negative).

**Field-resolution matrix (the rules the DB extractor follows):**

| Concern | Primary | Fallback | Reason |
|---|---|---|---|
| Player identity (canonical name, DOB, image) | nrl.com profile + match-centre | SC `players-cf` | League canonical |
| Jersey number, position-this-round, on-field flag | nrl.com match-centre `players[]` | — | Only nrl.com has actual lineup |
| Per-match raw stats (tries, tackles, run metres, ...) | nrl.com match-centre `stats.players[]` (58 fields) | nrlsupercoachstats jqGrid | nrl.com cleaner + more granular |
| Match timeline (try at 53', sin bin, etc.) | nrl.com match-centre `timeline` | — | Only nrl.com |
| Officials, venue, weather, attendance | nrl.com match-centre | — | Only nrl.com |
| Coaches, captains | nrl.com match-centre | — | Only nrl.com |
| Injuries (current league-wide) | nrl.com `/casualty-ward` | SC `injury_suspension_status` | Official league injury roll |
| Ladder + team form | nrl.com `/ladder` | — | Only nrl.com |
| Roster (eligible SC players) | SC `players-cf` | nrl.com `/players` | SC has the dense fantasy-eligible list |
| SC price + breakeven + trajectory | nrlsupercoachstats jqGrid | SC `player_stats[].price` (less detail) | nrlsupercoachstats has full price history |
| **SC scoring breakdown (base/attack/playmaking/power/negative)** | **nrlsupercoachstats jqGrid** | — | Only source |
| SC magic number, consistency (CV, StdDev) | nrlsupercoachstats jqGrid | — | Only source |
| Ownership %, projections, next opponents | SC `player_stats[]` | — | Only SC has forward-looking data |
| Editorial commentary on player | SC `notes[]` | — | Only SC; feeds `claims`/`quotes` |
| SC game rules (lockouts, scoring config, captains, emergencies, dual-position) | SC `/settings` | — | Only source for fantasy mechanics |
| Statistical leaderboards (Most Tries, Most Tackles, etc.) | nrl.com `/stats` | nrlsupercoachstats derives equivalents from jqGrid | nrl.com is pre-computed canonical |

D11 applies at **DB extraction time**, not at S3 capture time. We capture *everything* from every source; the extractor picks the winner when projecting to DB rows.

### D12. Backfill — harvest history once

**Decision (locked 2026-05-12):** Each pipeline supports a `?season=Y[&round=N]` backfill mode, identical code path to daily cron. One-time historical sweep writes every reachable snapshot to S3.

**Reachable history per source (verified 2026-05-12):**

| Source / endpoint | Earliest year | Quality |
|---|---|---|
| nrl.com `/draw/data` | **1908** | Real fixtures; 119 seasons in filter |
| nrl.com match-centre | **1990** (partial) / **2000** (full) | 1990 returns thin payload (timeline only). 2000+ has stats + timeline + lineups (60-91KB/match) |
| nrl.com `/ladder` | 1990s | 29 seasons in filter |
| nrl.com `/stats` (leaderboards) | ~2013 | 14 seasons in filter |
| nrl.com `/casualty-ward` | **current only** | No season param works |
| nrl.com `/players/data` | current only (per-team roster) | — |
| supercoach.com.au `/players-cf` etc. | **2025** | 2024 → 500, 2023 ← redirects to HTML; effective 2-season window |
| nrlsupercoachstats.com `/stats.php` | **2018** | 9 seasons of jqGrid history |

**Backfill order (cheapest first, highest leverage first):**

1. `nrlcom_draw`: 1908..2026 × ~25 rounds avg ≈ **~3,000 GETs**, ~100MB S3, **~1h**
2. `nrlcom_match_centre`: 2000..2026 × ~200 matches/season ≈ **~5,200 GETs**, ~400MB S3, **~3-4h**
3. `nrlcom_ladder`: ~30 seasons × end-of-season round ≈ **30 GETs**, minutes
4. `nrlcom_stats`: ~14 seasons × 1 ≈ **14 GETs**, minutes
5. `nrlcom_players_roster`: 17 teams × current ≈ **17 GETs**, seconds
6. `supercoach_roster` + `supercoach_teams` + `supercoach_settings`: 2 seasons × 3 endpoints ≈ **6 GETs**, seconds
7. `nrlsupercoachstats_stats`: 9 seasons × ~28 rounds incl. Totals ≈ **~250 jqGrid sessions** (~3 pages each), ~1-2h

**Total: ~4-5 hours of one-time harvesting** at 1 req/sec rate-limit per origin. **~1-2GB S3.** Single-machine, single operator-triggered job per pipeline (`make scout-backfill SOURCE=nrlcom-draw SEASON_FROM=1908`).

After backfill: future cron only writes new (current-season, current-round) snapshots. The history layer is immutable in S3.

### D13. DB extraction is downstream of S3

**Decision (locked 2026-05-12):** Each Scout pipeline does **two writes** — raw JSON to S3 (the durable layer) and structured rows to DB (the queryable projection). The two writes are decoupled:

- **S3 write** is the canonical capture. It happens **always**, even for fields we don't yet extract.
- **DB write** is the projection. It applies the strict Pydantic models (D8), the idempotency keys (D7), and the trust-hierarchy resolution (D11).

**Implication:** if we add a new DB field later (e.g. `attendance` from match-centre, or `notes[]` claims from SC), we ship just the extractor — no re-fetch. The S3 archive replays.

**Implication for tests:** Drift tests (D8) run against the S3 snapshot in CI — the canonical fixture path under `tests/fixtures/scout/{pipeline}/` is just a trimmed copy of a real S3 object.

**Extractor inventory** (DB-writing jobs, downstream of S3):

| Extractor | Reads | Writes to DB |
|---|---|---|
| `extract_matches` | `scout/nrlcom/draw/*` + `scout/nrlcom/match-centre/*` | `matches`, `match_team_lists`, `player_match_stats` (new), `match_timeline` (new), `match_officials` (new) |
| `extract_injuries` | `scout/nrlcom/casualty-ward/*` | `injuries` |
| `extract_ladder` | `scout/nrlcom/ladder/*` | `team_standings` (new) |
| `extract_stat_leaderboards` | `scout/nrlcom/stats/*` | `stat_leaderboards` (new) |
| `extract_roster_identity` | `scout/supercoach/classic/players-cf/*` | `people`, `people_attributes`, `people_roles` (current Phase 1 path — moves to read-from-S3 instead of read-from-upstream) |
| `extract_editorial_claims` | `scout/supercoach/classic/players-cf/*` (the `notes[]` slice) | `claims`, `quotes`, `claim_associations` |
| `extract_player_round_stats` | `scout/nrlsupercoachstats/stats/*` ⊕ `scout/nrlcom/match-centre/*` | `player_rounds` (with the D11 trust-hierarchy merge) |
| `extract_sc_settings` | `scout/supercoach/classic/settings/*` | `sc_settings` (new — game rules per season) |

Extractors are agent-audited (`agent_id='scout'` works for them too, with `detail_json.role='extractor'`) and idempotent (same S3 → same DB rows on re-run).

---

## The expanded charter

### What Scout owns under the expansion

Pipeline inventory after full source enumeration (2026-05-12). Each row is a folder under `services/api/app/scout/` per D9, with S3-first capture per D10.

**Media (legacy flat-file layout — to be folded into `scout/media/` later):**

| Pipeline | Source | Status |
|---|---|---|
| Media discovery (YouTube) | YouTube Data API + web | ✅ shipped (`loop.py`, `refresh.py`) |
| Audio acquisition | yt-dlp | ✅ shipped (`audio.py`) |
| Video / channel metadata refresh | YouTube Data API | ✅ shipped (`refresh.py`) |

**Data — supercoach.com.au:**

| Pipeline folder | Endpoint | S3 path | DB extraction target | Status |
|---|---|---|---|---|
| `scout/supercoach_roster/` | `/api/nrl/classic/v1/players-cf` | `supercoach/classic/players-cf/{season}/{YYYYMMDD}.json` | `people`, `people_attributes`, `people_roles` (+ `claims`/`quotes` from `notes[]`) | ✅ shipped (Phase 1) — needs S3-first retrofit per D10 |
| `scout/supercoach_teams/` | `/api/nrl/classic/v1/teams` | `supercoach/classic/teams/{season}.json` | Cross-reference into `teams.metadata_json.supercoach` | 🟡 not built — Phase 1.5 |
| `scout/supercoach_settings/` | `/api/nrl/classic/v1/settings` | `supercoach/classic/settings/{season}/{YYYYMMDD}.json` | `sc_settings` (new table — SC game rules per season) | 🟡 not built |
| `scout/supercoach_draft_roster/` | `/api/nrl/draft/v1/players-cf` | `supercoach/draft/players-cf/{season}/{YYYYMMDD}.json` | Draft-mode parallel of `people_attributes` (or `people_attributes.metadata_json.draft`) | 🟡 optional — Phase deferred |
| `scout/supercoach_draft_teams/` | `/api/nrl/draft/v1/teams` | `supercoach/draft/teams/{season}.json` | Same cross-reference | 🟡 optional |
| `scout/supercoach_draft_settings/` | `/api/nrl/draft/v1/settings` | `supercoach/draft/settings/{season}/{YYYYMMDD}.json` | Draft-mode rules | 🟡 optional |

**Data — nrl.com (the league-canonical source — highest trust per D11):**

| Pipeline folder | Endpoint | S3 path | DB extraction target | Status |
|---|---|---|---|---|
| `scout/nrlcom_draw/` | `/draw/data?competition={N}&season={Y}&round={N}` | `nrlcom/draw/{comp}/{season}/round-{NN}.json` | `matches` (fixtures), `rounds` (round metadata derived) | 🟡 not built — Phase 3 |
| `scout/nrlcom_match_centre/` | `/draw/{league}/{season}/round-{N}/{slug}/data/` per match | `nrlcom/match-centre/{comp}/{season}/round-{NN}/{slug}.json` | `match_team_lists`, `player_match_stats` (new), `match_timeline` (new), `match_officials` (new), augments `matches` | 🟡 not built — Phase 3 (high leverage) |
| `scout/nrlcom_casualty_ward/` | `/casualty-ward/data?season={Y}` | `nrlcom/casualty-ward/{comp}/{YYYYMMDD}.json` | `injuries` | 🟡 not built — Phase 4 |
| `scout/nrlcom_ladder/` | `/ladder/data?competition={N}&season={Y}[&round={N}]` | `nrlcom/ladder/{comp}/{season}/round-{NN}.json` | `team_standings` (new) | 🟡 not built — Phase 4 |
| `scout/nrlcom_stats/` | `/stats/data?competition={N}&season={Y}` | `nrlcom/stats/{comp}/{season}.json` | `stat_leaderboards` (new) | 🟡 not built — Phase 4.5 |
| `scout/nrlcom_players_roster/` | `/players/data?competition={N}&team={team_id}` | `nrlcom/players-roster/{comp}/{team_slug}.json` | Enriches `people` with NRL.com profile fields | 🟡 partially exists in `jeromelu_shared/players/nrlcom_refresh.py`; needs folder-organise + S3-first |

**Data — nrlsupercoachstats.com (third-tier, fills SC scoring breakdown gap):**

| Pipeline folder | Endpoint | S3 path | DB extraction target | Status |
|---|---|---|---|---|
| `scout/supercoach_stats/` | `nrlsupercoachstats.com/stats.php` (jqGrid) | `nrlsupercoachstats/stats/{season}/round-{NN}.json` | `player_rounds` (SC scoring breakdown columns) | ✅ shipped (Phase 2) — needs S3-first retrofit per D10 |

**Future (multi-platform expansion):** podcasts (RSS), Twitter/X, blogs/news, Reddit — same pattern, each gets a folder per D9.

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
┌─────────────────────────────────────────────────────────┐
│ Scout (one agent identity, many modules)                │
│                                                         │
│  Media (legacy flat files, scout/media/ later):         │
│    • discovery (loop.py + refresh.py)                   │
│    • audio acquisition (audio.py)                       │
│    • metadata refresh                                   │
│                                                         │
│  Data — supercoach.com.au (folder per pipeline, D9):    │
│    • scout/supercoach_roster/                  shipped  │
│    • scout/supercoach_teams/                   new      │
│    • scout/supercoach_settings/                new      │
│    • scout/supercoach_draft_*/                 optional │
│                                                         │
│  Data — nrl.com (canonical per D11):                    │
│    • scout/nrlcom_draw/                        new      │
│    • scout/nrlcom_match_centre/                new ★    │
│    • scout/nrlcom_casualty_ward/               new      │
│    • scout/nrlcom_ladder/                      new      │
│    • scout/nrlcom_stats/                       new      │
│    • scout/nrlcom_players_roster/              partial  │
│                                                         │
│  Data — nrlsupercoachstats.com:                         │
│    • scout/supercoach_stats/                   shipped  │
└─────────────────────────────────────────────────────────┘
       │
       ▼ (S3-first per D10)
┌─────────────────────────────────────────────────────────┐
│ s3://jeromelu-clean-documents/scout/{source}/{pipeline} │
│        — raw JSON snapshots, durable, replayable        │
└─────────────────────────────────────────────────────────┘
       │
       ▼ (extractors per D13)
┌─────────────────────────────────────────────────────────┐
│ DB tables — projection of S3 with trust-hierarchy (D11) │
│   people, matches, match_team_lists, player_rounds,     │
│   injuries, team_standings, claims/quotes from notes,…  │
└─────────────────────────────────────────────────────────┘
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

### Phase 2.5 — S3-first retrofit + lightweight SC siblings (~1 day)

Bring shipped pipelines into compliance with D10 (S3-first), and add the small SC siblings:

- Retrofit `scout/supercoach_roster/` and `scout/supercoach_stats/` to write the raw response to S3 before any DB extraction. Existing DB writes continue unchanged; S3 becomes an additional write.
- New `scout/supercoach_teams/` — tiny (17 rows, ~3KB), weekly cadence, cross-references `teams.metadata_json.supercoach`.
- New `scout/supercoach_settings/` — captures SC game rules (lockouts, scoring config, captains/emergencies/dual-position rules) per season; weekly.
- Run once with current season → S3 archive is complete for the SC surface.

### Phase 3 — NRL.com draw + match-centre (the big unlock)

The two pipelines that turn the wiki from "stubs" to "rich" for every player who's ever played a match in the last 25 years.

- New `scout/nrlcom_draw/` — fetches `/draw/data` per (competition, season, round); writes S3. Discovers the list of matches with their `matchCentreUrl` slugs.
- New `scout/nrlcom_match_centre/` — fetches `/draw/.../{slug}/data/` per match; writes S3. **Highest-leverage single pipeline** — one call per match yields lineups, per-player 58-field stat lines, timeline of 100+ typed events, officials, scoring narrative.
- DB extractors (Phase 3.5 or concurrent): `extract_matches` (writes `matches`, `match_team_lists`, `player_match_stats`, `match_timeline`, `match_officials`). The `player_round_stats` extractor that runs against both nrlcom + nrlsupercoachstats with D11 trust-hierarchy merge.

This phase unblocks: every team page's `## Recent Results`, every round page's `## Team Lists` + `## Results`, and every player page's per-match history including timeline events (try at 53', sin bin, etc.).

### Phase 4 — NRL.com casualty ward + ladder (~half a day each)

- New `scout/nrlcom_casualty_ward/` — daily snapshot of the official league injury roll. Writes S3 with timestamped key (state changes daily). DB extractor populates `injuries`.
- New `scout/nrlcom_ladder/` — per-round team standings + the 22 per-team metrics (form, streak, points-for/against, home/away/day/night records, average margins). DB extractor populates `team_standings` (new table).

Retire `services/worker-scraper/` at the end of this phase — no Scout work runs through it anymore.

### Phase 4.5 — NRL.com stats + players roster + Draft mode (optional)

- New `scout/nrlcom_stats/` — pre-computed leaderboards (top-25 per category) for the wiki's `## Key Players` and Bookkeeper's leaderboard queries.
- New `scout/nrlcom_players_roster/` — fold the existing `jeromelu_shared/players/nrlcom_refresh.py` enrichment into a proper folder per D9.
- Optional: SuperCoach Draft mode (`scout/supercoach_draft_*`) — parallel of classic, if Draft becomes a product concern.

### Phase 5 — Historical backfill (one-time, ~4-5 hours operationally)

Per D12. Each pipeline supports a `?season=Y[&round=N]` backfill mode that hits the same admin endpoint with explicit parameters. One-time operator-triggered job per pipeline:

1. `make scout-backfill SOURCE=nrlcom-draw SEASON_FROM=1908` → ~3,000 GETs over 1h
2. `make scout-backfill SOURCE=nrlcom-match-centre SEASON_FROM=2000` → ~5,200 GETs over 3-4h
3. `make scout-backfill SOURCE=nrlcom-ladder` → 30 GETs
4. `make scout-backfill SOURCE=nrlcom-stats` → 14 GETs
5. `make scout-backfill SOURCE=supercoach-stats SEASON_FROM=2018` → ~250 jqGrid sessions over 1-2h

Total: ~4-5 hours single-machine, rate-limited at 1 req/sec per origin. ~1-2GB S3.

Backfill produces the same S3 keys daily cron does — re-running future cron over the same range is a no-op.

### Phase 6 — Unified Scout dashboard

Operator view at `/admin/scout` showing health across every pipeline (media + identity + stats + fixtures + injuries + ladder + leaderboards). Reads from `agent_runs` filtered by `agent_id='scout'`, groups by `detail_json.pipeline`. Per-pipeline: last run, status, row counts, cost. No new data — just the view.

This phase isn't blocked by anything earlier; could ship in parallel with Phases 3-4 to give visibility while migration happens.

### Phase 7 (future) — Multi-platform expansion

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

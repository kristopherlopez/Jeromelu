---
tags: [area/architecture, subarea/agents]
---
	
# Scout Charter

> Last reviewed: 2026-05-24. **Decisions D8–D13 locked 2026-05-12; D1–D7 locked 2026-05-24.** Phase 0 doc reconciliation shipped; Phase 1 (SuperCoach roster) shipped; Phase 2 (SuperCoach stats) shipped. See [roadmap.md](roadmap.md) for the full phasing and status.
>
> The decision record for Scout's scope. Formalises the proposal in [`docs/pages/wiki/data-feeds.md`](../../../pages/wiki/data-feeds.md) §"Scout's expanded charter": Scout's scope grows from *media inventory* to *all external data acquisition* — making Scout the project's **bronze layer** (raw capture for every external source). The full surface area — verified by direct endpoint exploration on 2026-05-12 — spans **nrl.com** (6 endpoints, history back to 1908 for fixtures and 2000 for full match-centre detail), **supercoach.com.au** (6 endpoints across classic + draft modes, current + prior season only), **nrlsupercoachstats.com** (1 jqGrid endpoint, 9 seasons of history), and — added 2026-05-24 — **rugbyleagueproject.org** (HTML pages, no API: 130+ years of match-by-match lineups, scorers, results, and player/coach/referee/venue histories back to 1908; era-dependent trust, see [D11](#d11-trust-hierarchy--which-source-wins-per-field)). Cleaning, parsing, diarisation, and claim extraction stay with the Analyst.

---

## Charter rationale

The data-feeds doc surfaced that the input layers feeding the wiki are owned by **three different crew/system concepts**: Scout (media), the scraper (numeric NRL data — currently Bookkeeper-owned), and the player-roster pipeline (identity). The split is artificial — acquisition is one job regardless of source. This charter consolidates that job under Scout, lays out the architectural pattern that makes it work, and stages the migration.

It does **not** change what the Analyst, Bookkeeper, or Archivist do downstream — only where the data they consume comes from.

---

## Decisions to lock before any code is written

### D1. The boundary principle — Scout owns the bronze layer

**Decision (locked): Scout owns every external source of truth — it is the project's bronze layer.** If data comes from outside Jeromelu — a third-party API, a public JSON endpoint, a scraped HTML page, an RSS feed, an mp3 from a podcast host — Scout fetches it and lands it **raw, as-ingested, never interpreted**.

In medallion terms:

- **Bronze — Scout.** Raw external data landed faithfully (the S3 JSON-first capture, [D10](#d10-storage--json-first-to-s3-db-derivative)) — no interpretation. Scout's remit extends one *mechanical* step further for **structured** feeds: the deterministic projection of its own raw JSON into typed DB rows (the [D13](#d13-db-extraction-is-downstream-of-s3) extractors, trust-resolved per [D11](#d11-trust-hierarchy--which-source-wins-per-field)). That projection is **deserialization, not judgement**, so it stays Scout's.
- **Silver — downstream (Analyst).** The *interpretive* transform: cleaning, diarisation, speaker→Person attribution, and claim/quote extraction from unstructured sources.
- **Gold — downstream (Bookkeeper + Archivist).** Curated and derived: alignment indices, accuracy scores, consensus snapshots, the wiki.

This gives one answer to *"who fetches X?"* for every X, including future expansions (Twitter/X mentions, blog RSS, Reddit, league injury reports): **Scout, always.** And one answer to *"is this Scout's job?"* — only if it's raw acquisition. Anything *derived* inside Jeromelu (claim extraction, embeddings, KB synthesis, voiceprint clustering, agreement-edges between advisors) is silver or gold, lives downstream, and is not Scout's.

### D2. One agent or many?

**Decision (locked): one Scout identity, multiple execution modules.** All acquisition runs under `agent_id='scout'` in the audit table, with `detail_json.pipeline` discriminating which module ran (`media-discovery`, `supercoach-roster`, `supercoach-stats`, `nrlcom-matches`, `nrlcom-teamlists`, `nrlcom-injuries`, `nrlcom-rounds`, `youtube-refresh`, etc.). Each pipeline is its own module under `services/api/app/scout/`; they share utilities (audit, idempotency, rate-limiting) but execute independently.

This mirrors how Scout's media work is already structured today — `scout/loop.py`, `scout/refresh.py`, `scout/audio.py` are already sibling modules under one agent identity. The expansion adds more siblings, not a new architecture.

### D3. Cron orchestration

**Decision (locked): external cron hitting admin endpoints.** Each Scout pipeline exposes a `POST /api/admin/scout/<pipeline>` endpoint that returns a `run_id`. Cron (or the `scheduler` skill, or a `make` target) just hits the endpoint with the admin key. This matches the existing pattern — the daily YouTube refresh already works this way per [architecture.md §3.4](architecture.md) — and avoids introducing a new container or scheduler service for the prod footprint we already have.

A future Phase 5 could replace external cron with an in-process APScheduler if cadence management becomes painful, but that's not the V1 problem.

### D4. Disposition of `services/worker-scraper/`

**Decision (locked): migrate the activities into per-pipeline folders under `services/api/app/scout/` per D9; retire the Temporal worker.** Per project memory, Temporal is not in production. The activities (`teamlists.py` and any siblings) become module-level functions inside the relevant pipeline folder (`scout/nrlcom_teamlists/fetcher.py`, etc.), called from admin endpoints under the unified Scout audit pattern. The `worker-scraper` directory stays in tree for a phase, with no new code, and is retired in Phase 4.

### D5. Skills disposition

**Decision (locked): no Claude Code skills for deterministic fetchers.** The endpoint + cron is the surface. Ad-hoc operator runs use the endpoint directly (curl, a `make` target, or the admin UI when one exists), not a skill. The existing `scrape-supercoach` Claude Code skill is retired as part of Phase 1 — operators move to hitting the endpoint.

**If agentic behaviour is genuinely required, build it on the Claude Agent SDK — never a Claude Code skill.** Scout's existing media-discovery loop already uses the SDK, and any future build that needs a Claude agent to *orchestrate* a Scout fetch (e.g. as one tool call inside a larger reasoning loop) calls the same admin endpoint. The endpoint is the universal surface; Claude Code skills are off the critical path entirely.

### D6. Audit granularity

**Decision (locked): as per D2** — single `agent_id='scout'`, pipeline discriminator in `detail_json`. This gives one dashboard ("is Scout healthy?") that breaks down by pipeline when needed.

### D7. Idempotency contract

**Decision (locked): every Scout pipeline writes idempotent upserts on natural keys.** Re-running the same fetch with no upstream change is a no-op. Existing media pipelines already mostly hold this property; spelling it out as a Scout-wide contract makes the property load-bearing for the cron orchestration in D3 (cron can hammer the endpoint without consequence).

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

**Why:** External sources (`nrl.com`, `supercoach.com.au`, `nrlsupercoachstats.com`) are out of our control. Silent degradation — e.g. a renamed field becoming null in every row — would propagate wrong/incomplete content downstream into the wiki. The user wants to be the one who decides the response: rewrite the parser, wait for the source to revert, accept the change, switch sources.

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
- **S3 path segments** (D10) mirror the *upstream endpoint's* own naming, hyphenated where the source uses it — e.g. `nrlcom/match-centre/`, `casualty-ward/`, `players-cf/`. They name the source artefact, not the module, so they don't follow the snake_case folder name.
- The first two are 1:1 translations. Code that wants the pipeline label from the module name does `module.__name__.split('.')[-1].replace('_', '-')`.

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

> Note: the `jeromelu-clean-documents` bucket name predates the bronze framing — Scout's captures under `scout/` are **raw/bronze**, not cleaned. Renaming the bucket is deferred infra churn; treat the path, not the bucket name, as authoritative.

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

`rugbyleagueproject.org` is a community historical aggregator: third-party, so it sits **below** nrl.com for anything nrl.com publishes — but it is the **primary (often only) source for pre-2000 history** (match-by-match lineups, scorers, results, and player/coach/referee careers nrl.com's match-centre doesn't reach). Trust here is therefore **era-dependent**: nrl.com canonical from 2000 on; rugbyleagueproject primary before that.

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
| **Historical lineups / results / scorers (pre-2000)** | **rugbyleagueproject.org** | — | nrl.com match-centre is thin/absent before 2000 |
| Player career history (debut, clubs, rep span, appearances) | rugbyleagueproject.org | nrl.com profile (current only) | only consolidated long-career source |
| Referees / coaches / venues as historical entities | rugbyleagueproject.org | nrl.com match-centre (current matches only) | historical depth + cross-competition |

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
| `extract_roster_identity` | `scout/supercoach/classic/players-cf/*` | `people`, `player_attributes`, `people_roles` (current Phase 1 path — moves to read-from-S3 instead of read-from-upstream) |
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
| `scout/supercoach_roster/` | `/api/nrl/classic/v1/players-cf` | `supercoach/classic/players-cf/{season}/{YYYYMMDD}.json` | `people`, `player_attributes`, `people_roles` (+ `claims`/`quotes` from `notes[]`) | ✅ shipped (Phase 1) — now S3-first per D10 |
| `scout/supercoach_teams/` | `/api/nrl/classic/v1/teams` | `supercoach/classic/teams/{season}.json` | Cross-reference into `teams.metadata_json.supercoach` | 🟡 not built — Phase 2.5 |
| `scout/supercoach_settings/` | `/api/nrl/classic/v1/settings` | `supercoach/classic/settings/{season}/{YYYYMMDD}.json` | `sc_settings` (new table — SC game rules per season) | 🟡 not built |
| `scout/supercoach_draft_roster/` | `/api/nrl/draft/v1/players-cf` | `supercoach/draft/players-cf/{season}/{YYYYMMDD}.json` | Draft-mode parallel of `player_attributes` (or `player_attributes.metadata_json.draft`) | 🟡 optional — Phase deferred |
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
| `scout/supercoach_stats/` | `nrlsupercoachstats.com/stats.php` (jqGrid) | `nrlsupercoachstats/stats/{season}/round-{NN}.json` | `player_rounds` (SC scoring breakdown columns) | ✅ shipped (Phase 2) — now S3-first per D10 |

**Data — rugbyleagueproject.org (community historical archive — HTML, no API; added 2026-05-24):**

The deep-history source. HTML pages, not JSON, so the fetch shape differs from the feeds above: fetch HTML → archive the raw page to S3 (still bronze, D10) → parse to typed rows. The projection stays strict (D8), but the parser reads HTML structure and the drift fixture is a saved HTML page, not a JSON sample. Be a polite client — it's a volunteer-run community site: conservative rate-limit (≤1 req/sec), cache-friendly, no hammering.

| Pipeline folder | Source | S3 path | DB extraction target | Status |
|---|---|---|---|---|
| `scout/rugbyleagueproject_matches/` | season + match pages | `rugbyleagueproject/matches/{comp}/{season}/{slug}.html` | Pre-2000 `matches` + `match_team_lists` (historical lineups, scorers, results) | 🟡 future — HTML scrape; fills the pre-2000 gap nrl.com can't |
| `scout/rugbyleagueproject_players/` | player career pages | `rugbyleagueproject/players/{slug}.html` | Player career history → enriches `people` / `people_roles` (debut, clubs, rep span) | 🟡 future |

**Why it's worth it / the trade-off:** match-by-match lineups, scorers, and results back to **1908** (plus coach/referee/venue histories and cross-competition coverage) — the data that turns historical wiki pages from stubs into real careers, which no JSON source can supply. But HTML scraping is more brittle than the JSON feeds, so these are **future/optional** pipelines — sequence them after the nrl.com pipelines (Phases 3–4) land.

**Future (multi-platform expansion):** podcasts (RSS), Twitter/X, blogs/news, Reddit — same pattern, each gets a folder per D9.

### What Scout still does NOT do (the bronze boundary)

The bronze boundary is the spine of the charter — Scout fetches raw, persists raw, sets `ingestion_status='collected'`, and (for structured feeds) projects the JSON into typed rows; then it stops. Every downstream agent reads from Scout's outputs; Scout never reads back from them. The *interpretive* transform — cleaning, diarisation, embedding, speaker→Person attribution, claim/quote extraction, and cross-source consensus — stays with the Analyst; numerical derivations with the Bookkeeper; wiki composition with the Archivist; voicing with Jaromelu. The canonical prose breakdown lives in [README § What Scout DOES NOT cover](README.md#what-scout-does-not-cover).

---

## Architecture under the new charter

The S3-first architecture diagram (one identity, many modules → S3 → DB extractors) and the shared-module shape live in [architecture.md § Architecture under the expanded charter](architecture.md#architecture-under-the-expanded-charter). In brief: every module exposes a single idempotent fetch function, wraps it in an admin endpoint with the `agent_runs` audit pattern (`agent_id='scout'`, `detail_json.pipeline='<module>'`), captures raw JSON to S3 first (D10), and projects to DB via downstream extractors (D13).

---

## Phasing

The full phasing (Phase 0–7) lives in [roadmap.md § Charter phasing](roadmap.md#charter-phasing-phase-07). Phase 0–2 shipped (doc reconciliation + SuperCoach roster + stats); Phase 2.5 onward is the remaining migration work.

---

## Architectural risks

1. **Endpoint is the only surface.** Per D5 there are no Claude Code skills for deterministic fetchers, so the duality risk doesn't exist. The remaining concern is that the `make` targets are kept in sync with the endpoint paths — handled by a single integration test that exercises the target → endpoint → DB path end-to-end.

2. **NRL.com rate limits / unauthenticated endpoint volatility.** Hammering nrl.com endpoints could get blocked or break when they restructure. Mitigation: per-pipeline rate limiter (e.g. one request per second, configurable per module); each module logs unknown response fields to `agent_events` so we get signal when the source shape changes; cron cadences are conservative (daily, not hourly).

3. **One-process overload.** All Scout pipelines running in the API process means a hung fetcher blocks API throughput. Mitigation: endpoints kick off the fetch as a FastAPI background task with hard wall-clock bounds (matching Scout's media pattern); endpoint returns the `run_id` immediately rather than waiting for completion.

4. **Schema drift in fetcher outputs.** SuperCoach API or NRL.com endpoint shapes can change silently — new fields, renamed fields, removed fields. Mitigation is locked in **D8**: strict Pydantic parsing + fixture-backed drift tests + live-mode scheduled runs that surface failures to the user. The agent does not auto-adapt.

5. **Bookkeeper-shaped hole in the crew docs.** Moving acquisition out of Bookkeeper's territory leaves [`bookkeeper.md`](../bookkeeper/README.md) with a smaller, less-clearly-defined scope. Mitigation: Phase 0 doc updates explicitly redefine Bookkeeper as the *derivation/math* layer over Scout-fetched data — alignment indices, accuracy scores, trend extraction, breakeven-trajectory math. Not nothing, but narrower than today.

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

## Open questions

1. **Cron mechanics.** "External cron" is right architecturally but the prod box doesn't have a documented crontab pattern yet. Where do schedules actually land? Same place Scout's daily YouTube refresh runs today; needs to be documented as part of Phase 1.
2. **Auth on admin endpoints.** Today's pattern is `X-Admin-Key` (per [architecture.md §3.4](architecture.md)). Reused for all the new Scout endpoints; rotating story unchanged.
3. **One module per data table, or one module per source?** E.g. is `nrlcom_matches.py` separate from `nrlcom_rounds.py` (both come from `/draw/data`)? Lean: one module per *upstream endpoint*, even if it writes multiple tables. Simpler to rate-limit and audit.
4. **Source-of-truth conflicts.** SuperCoach has player rosters; NRL.com has team lists. When they disagree (player listed at HOK in SuperCoach but FRF on the team list), who wins? Almost certainly: SuperCoach for "registered position", NRL.com for "this match's lineup". Worth documenting; not a blocker for the migration.
5. **Backfill strategy.** For historical `player_rounds`, do we backfill all of 2025 + 2026 on first run, or only refresh forward from now? Per-pipeline decision — for the wiki to have meaningful trend data, backfill is needed.
6. **Source-of-truth for advisor identity.** `people_roles` for advisors is currently empty (no advisors have been registered). Under the expansion, where do advisor entities get created? Probably manual today, becomes Analyst-derived once diarisation lands; not a Scout job either way. Worth a note.

---

## Related

- [README.md](README.md) — Scout's identity, scope, and voice
- [architecture.md](architecture.md) — pipeline position, flow, component internals, S3-first architecture
- [roadmap.md](roadmap.md) — status and the full Phase 0–7 phasing
- [plans/phase-1-supercoach-roster.md](plans/phase-1-supercoach-roster.md) — the Phase 1 implementation plan
- [Data lineage](../../../architecture/data-lineage.md) — locked D1–D13 govern the lineage

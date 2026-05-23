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
- Reframe [`scraper.md`](../../system/scraper.md) as a Scout component (specifically: the `worker-scraper` Temporal worker, marked for retirement) rather than a Bookkeeper subsystem.
- Update [`bookkeeper.md`](../bookkeeper.md): consume-only over Scout-fetched data; Bookkeeper no longer acquires anything.
- Update [`dynamics.md`](../dynamics.md) Cadence row: Bookkeeper trigger becomes "Scout scrape complete" instead of "scraper sweep complete".
- Update [crew `README.md`](../README.md) Bookkeeper one-liner.

### Phase 1 — One pipeline migrated end-to-end (the proof slice) ✅

Pick the smallest pipeline: **SuperCoach player roster**. It already has a working fetcher script and a skill (to be retired). Full step-by-step plan in [plans/phase-1-supercoach-roster.md](plans/phase-1-supercoach-roster.md).

- Move `scripts/data/fetchers/fetch_supercoach_players.py` → `services/api/app/scout/supercoach_roster/` (folder per D9) as a callable function (no behavioural changes).
- **Add the D8 drift fixture and test:** `tests/fixtures/scout/supercoach_roster/canonical_response.json` + `tests/integration/scout/supercoach_roster/test_response_shape.py` (Pydantic-strict, live-mode env-flagged). This is the pattern every subsequent pipeline copies — getting it right on Phase 1 means it's cheap to apply for Phases 2-4.
- Add `POST /api/admin/scout/supercoach-roster` endpoint that wraps the function in the agent audit pattern.
- Add a `make scout-supercoach-roster` target for ad-hoc operator runs that hits the endpoint with admin auth.
- Retire the `scrape-supercoach` Claude Code skill — operators use the endpoint or the `make` target.
- Schedule via external cron — daily.
- Phase 1 done = the SuperCoach roster refreshes daily, an audit row lands per run, the drift test runs in CI (fixture-mode) and on a schedule (live-mode), the `make` target works for ad-hoc operator use, the skill is retired, and `people`/`player_attributes` row counts move when the upstream data does.

### Phase 2 — SuperCoach per-round stats (the high-leverage one) ✅

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

The multi-platform roadmap items below (podcasts, Twitter/X, blogs, Reddit) instantiate the same shape: each becomes a `scout/<platform>_<thing>/` folder with an admin endpoint. Out of scope for the charter proper; tracked for visibility.

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

| Platform | Discovery surface | Content extraction | Notes |
|---|---|---|---|
| **Podcasts** (Apple Podcasts / Spotify) | RSS catalogue search + `find_related` from tracked feeds | RSS feed enumeration → episode mp3 → transcribe (Deepgram?) | Closest analogue to YouTube. RSS makes `filter_known` trivial. |
| **Twitter / X** (NRL personalities) | Manual seed list + agentic for adjacent accounts | API or scrape; tweets become `source_chunks` directly (no transcription) | Quote-extraction value high, signal-to-noise low. |
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
- [plans/phase-1-supercoach-roster.md](plans/phase-1-supercoach-roster.md) — the Phase 1 implementation plan

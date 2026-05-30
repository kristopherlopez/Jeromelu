---
tags: [area/agents, subarea/crew]
---

# Miner — Status & Roadmap

> Last reviewed: 2026-05-30.

The forward plan for Miner, in three layers:

1. **Charter phasing (Phase 0–7)** — the staged migration of all external data acquisition under Miner, per [charter.md](charter.md). Phases 0–4.5 and 6 shipped; Phase 5 is the remaining one-time historical backfill; Phase 7 is future multi-platform expansion.
2. **YouTube depth + multi-platform** — the media-side roadmap (capabilities on the existing platform, then new platforms).
3. **Future improvements** — additive enhancements that layer on top of what's built.

Status labels:
- **Shipped** — live in production or dev
- **In design** — specced; implementation not started
- **Planned** — committed scope; no design yet
- **Backlog** — deferred or candidate; no commitment

---

## Charter phasing (Phase 0–7)

The expanded charter ([charter.md](charter.md)) stages the migration of all external data acquisition under Miner. Per-pipeline details (S3 paths, DB extraction targets, endpoints) live in the charter's pipeline-inventory tables.

### Phase 0 — Scope reconciliation in docs (~half a day) ✅

- Land the charter after review.
- Update Miner's crew docs: §"What Miner DOES cover" gains the new modules; §"What Miner DOES NOT cover" loses "Numeric NRL data" and "Player roster registry"; pipeline-position diagram updated.
- Reframe [`scraper.md`](../../system/scraper.md) as a Miner component (specifically: the `worker-scraper` Temporal worker, marked for retirement — **retired and deleted 2026-05-28** as part of Phase 4 / TASK-28) rather than a Bookkeeper subsystem.
- Update [`bookkeeper.md`](../bookkeeper/README.md): consume-only over Miner-fetched data; Bookkeeper no longer acquires anything.
- Update [`dynamics.md`](../dynamics.md) Cadence row: Bookkeeper trigger becomes "Miner scrape complete" instead of "scraper sweep complete".
- Update [crew `README.md`](../README.md) Bookkeeper one-liner.

### Phase 1 — One pipeline migrated end-to-end (the proof slice) ✅

Pick the smallest pipeline: **SuperCoach player roster**. The step-by-step record of this slice is the bullet list below.

> **Skill retired 2026-05-27.** The `scrape-supercoach` Claude Code skill was a thin wrapper around `make fetch-players` (which runs `fetch_supercoach_players.py` + `generate_players_yaml.js`) — it owned no logic, so deleting it removed no capability. Operators now run `make fetch-players` (local roster + `data/players.yaml` regen) or the `miner-supercoach-roster` endpoint/`make` target. The transcript-cleaning pipeline still reads `data/players.yaml`; rehoming that to read the roster from the DB is a **separate** open loop (it never actually gated this retirement — see [Analyst roadmap](../analyst/roadmap.md)).

- Move `scripts/data/fetchers/fetch_supercoach_players.py` → `services/api/app/miner/supercoach_roster/` (folder per D9) as a callable function (no behavioural changes).
- **Add the D8 drift fixture and test:** `tests/fixtures/miner/supercoach_roster/canonical_response.json` + `tests/integration/miner/supercoach_roster/test_response_shape.py` (Pydantic-strict, live-mode env-flagged). This is the pattern every subsequent pipeline copies — getting it right on Phase 1 means it's cheap to apply for Phases 2-4.
- Add `POST /api/admin/miner/supercoach-roster` endpoint that wraps the function in the agent audit pattern.
- Add a `make miner-supercoach-roster` target for ad-hoc operator runs that hits the endpoint with admin auth.
- ✅ Retire the `scrape-supercoach` Claude Code skill (done 2026-05-27) — operators use the endpoint or the `make` target.
- Schedule via external cron — daily.
- Phase 1 done = the SuperCoach roster refreshes daily, an audit row lands per run, the drift test runs in CI (fixture-mode) and on a schedule (live-mode), the `make` target works for ad-hoc operator use, the skill is retired, and `people`/`player_attributes` row counts move when the upstream data does.

### Phase 2 — SuperCoach per-round stats (the high-leverage one) ✅

Same pattern applied to `fetch_player_stats.py`. This is the **highest-leverage move on the entire roadmap** — it's what unblocks `player_rounds` from being empty and turns 600+ wiki stubs into pages with actual `## Current Form` and `## Price Analysis` content.

- Move into `services/api/app/miner/supercoach_stats/` (folder per D9).
- Admin endpoint + cron (post-round cadence, plus on-demand for re-pulls).
- The existing `services/worker-scraper/` Temporal worker stopped being touched after this; its activities are now sibling Miner modules. **(Worker retired and deleted 2026-05-28 as part of Phase 4 / TASK-28.)**

### Phase 2.5 — Bronze (S3-first) retrofit ✅ + lightweight SC siblings ✅ Shipped

The **bronze/S3-first retrofit is done** — `miner/supercoach_roster/` and `miner/supercoach_stats/` archive the raw response to S3 (D10) and strict-parse it (D8) before DB extraction (`_s3_archive.archive_response`; `s3_archive_key` recorded per run). The lightweight SC siblings **shipped 2026-05-24**:

- ✅ Shipped: `miner/supercoach_teams/` — tiny (17 rows, ~3KB), weekly cron (Mon 23:30 UTC), S3 archive at `miner/supercoach/classic/teams/{season}.json`, cross-references `teams.metadata_json.supercoach` (17/17 NRL clubs matched on the seed run). D8 fixture + unit + env-flagged live drift tests.
- ✅ Shipped: `miner/supercoach_settings/` — captures SC game rules (lockouts, scoring config, captains/emergencies/dual-position rules) per season; weekly cron (Mon 23:35 UTC, classic mode), S3 archive at `miner/supercoach/{mode}/settings/{season}/{YYYYMMDD}.json`, DB snapshots into `sc_settings`. Draft mode stays on-demand. D8 fixture + unit + live (classic + draft) drift tests.
- ✅ Done: one-time S3 seed for season 2026 (classic teams + classic/draft settings) — S3 archives and `sc_settings` rows verified 2026-05-24.

### Phase 3 — NRL.com draw + match-centre ingest ✅ Shipped

The two capture pipelines that feed the wiki's match data. **Ingest shipped 2026-05-24** — D8-hardened, scheduled, seeded. The pre-existing fetch+archive code was retrofitted to charter discipline (the same pattern as Phase 2.5). The DB extractors that light up wiki pages shipped under `scripts/data/populate/` and now run through the scheduled `miner-populate.sh nrlcom-current` projection.

- ✅ Shipped: `miner/nrlcom_draw/` — `/draw/data` per (competition, season, round) → S3; `NrlcomDraw`+`DrawFixture` D8 models, strict-parse wired into the route (drift → 500), daily cron (current round, 18:00 UTC). Discovers each match's `matchCentreUrl`.
- ✅ Shipped: `miner/nrlcom_match_centre/` — walks the round's fixtures, fetches `/.../{slug}/data/` per match → S3. **Highest-leverage capture** (lineups, per-player 58-field stats, 100+ timeline events, officials). D8 union envelope (FullTime/Upcoming state-dependent), non-aborting per-match validation, round-optional (resolves the current round), daily cron (18:15 UTC). Seeded R12/2026 — 5/5 matches, 0 validation failures.
- ✅ Shipped: DB extractors in `scripts/data/populate/` — `populate_rounds`, `populate_matches`, `populate_match_team_lists`, `populate_player_match_stats`, `populate_match_timeline`, and `populate_player_rounds` read the S3 archives and project them into canonical tables. The scheduled populate wrapper runs current-season projections after daily capture; historical seasons remain a deliberate Phase 5 backfill run.

### Phase 4 — NRL.com casualty ward + ladder ✅ Shipped (2026-05-28)

D8-hardened ingest (envelope **and** item/stats strict — deeper than draw/match-centre because the extractors are live), scheduled daily, seeded to prod, extractors unit-tested. NRL only (comp 111), season 2026, forward-only — historical backfill is Phase 5.

- ✅ Shipped: `miner/nrlcom_casualty_ward/` — `/casualty-ward/data?competition=111` → timestamped S3 key (`miner/nrlcom/casualty-ward/111/{YYYYMMDD}.json`); `NrlcomCasualtyWard` + `Casualty` D8 models (`extra="forbid"`); strict-parse wired into the route (drift → 500); daily cron 18:30 UTC. Live drift test under `MINER_DRIFT_LIVE=1`. Seeded 2026-05-28 (99 casualties; `validated:true` live).
- ✅ Shipped: `miner/nrlcom_ladder/` — `/ladder/data?competition=111&season=Y` → `miner/nrlcom/ladder/111/{season}/round-{NN}.json`; `NrlcomLadder` + `LadderPosition` + `LadderStats` D8 models (the 22 metrics use space-separated upstream keys mapped via `Field(alias=...)` with `populate_by_name=True`); strict-parse wired into the route; daily cron 18:45 UTC. Seeded 2026-05-28 (17 teams, round 12; `validated:true` live).
- ✅ Shipped: DB extractors `populate_injuries` (state-machine over daily snapshots → `injuries`) and `populate_team_standings` (UPSERT per `(team, comp, season, round)` → `team_standings`) in `scripts/data/populate/phase_aux.py`, with pure-function unit tests (`tests/unit/scripts/data/populate/test_phase_aux.py`). Latent `jsonb_build_object` parameter-typing bug in the injuries UPDATE branch fixed during seed verification (surfaced on the first real-archive run). Prod DB post-seed: `team_standings` 51 rows / 94% team_id resolution; `injuries` 130 rows / 99 open / 93% team_id resolution.
- ✅ Done: retired `services/worker-scraper/` — directory deleted + live doc references swept (Phase 4 closure, TASK-28, 2026-05-28). Per D4: it was orphaned (no code, compose, CI, or deploy-script refs); [`scraper.md`](../../system/scraper.md) remains as historical reference.

**Ops scheduling follow-up shipped (MINER-OPS-SCHED):** `scripts/miner-populate.sh`
now stages `scripts/` + `packages/` into the running `jeromelu-api` container and
executes `populate_db_from_s3` there. `scripts/cron.d/jeromelu` runs
`miner-populate.sh nrlcom-current` daily after the nrl.com archive jobs, so the
latest NRL.com captures project into DB tables without a manual operator run.
Season-aware phases receive the current season; identity/re-resolution phases may
inspect existing DB rows to keep links coherent. Historical S3 backfills remain
deliberate one-off runs.

### Phase 4.5 — NRL.com stats + players roster ✅ Shipped (2026-05-28)

Hardening replay of the existing (but unhardened) `miner/nrlcom_stats/` + `miner/nrlcom_players_roster/` ingest folders + the existing `populate_stat_leaderboards` extractor. Discovery (2026-05-28) found the fetchers/routes/`make` targets + migration 060 + the extractor already shipped pre-phase; the gap was the D8 contract, route ValidationError-aborts, extractor unit tests via pure-function refactor, cron scheduling, and prod seed verification. NRL only (comp 111), season 2026, forward-only — historical backfill stays Phase 5.

- ✅ Shipped: `miner/nrlcom_stats/` — D8 four-level strict (envelope + category + subgroup + leader, with single-model player-vs-team leader bifurcation per the `NrlcomDraw.videoProviders` precedent); route ValidationError → 500; live drift test under `MINER_DRIFT_LIVE=1`; daily cron 18:50 UTC; `_extract_leader_rows` pure-function refactor + 6 unit tests. **Seeded 2026-05-28** — 347 rows in `stat_leaderboards` for 2026/comp=111 (100% person_id resolution, 98.8% team_id resolution); 4,595 rows across all 14 seasons.
- ✅ Shipped: `miner/nrlcom_players_roster/` — D8 envelope + group + flat-`Profile` strict (live shape simpler than plan anticipated; no nested `ProfileBody` needed); route ValidationError → 500; live drift test under `MINER_DRIFT_LIVE=1`; new `POST /api/admin/miner/nrlcom-players-roster/refresh-all` endpoint walks 17 NRL teams server-side at 1 req/sec (~20s wall time); weekly Mon 23:40 UTC cron. **17-team catalogue** (`NRL_TEAM_IDS` constant) derived from the response's own `filterTeams[]` — no S3 ladder/draw read needed. **Seeded 2026-05-28** — 17/17 teams walked with `validated:true`, errors:[], 549 player profiles in S3. **No new DB extractor this phase** (S3-only) — the existing HTML-scrape `jeromelu_shared/players/nrlcom_refresh.py` enrichment is untouched.

**Deferred (out of scope, surfaced not self-queued):**
- SuperCoach Draft mode (`miner/supercoach_draft_*`) — parallel of classic, if Draft becomes a product concern.
- Folding `jeromelu_shared/players/nrlcom_refresh.py` (HTML profile scraper) into the `miner/nrlcom_players_roster/` folder per D9. The HTML-scrape and JSON-fetch are different upstream sources reaching different enrichment fields; the fold is a refactor concern, not a hardening one.
- Tightening `Profile` identity-field types from `str | None` to `str` non-null when a future `/players/data` extractor lands.

### Phase 5 — Historical backfill (one-time, ~4-5 hours operationally) — Ready for operator run

Per D12. Each pipeline supports a `?season=Y[&round=N]` backfill mode that hits the same admin endpoint with explicit parameters. `scripts/data/miner_backfill.py` adds resume support and `archive_only=true` for older seasons whose shapes may drift from current D8 models. One-time operator-triggered job per pipeline:

1. `make miner-backfill SOURCE=nrlcom-draw SEASON_FROM=1908` → ~3,000 GETs over 1h
2. `make miner-backfill SOURCE=nrlcom-match-centre SEASON_FROM=2000` → ~5,200 GETs over 3-4h
3. `make miner-backfill SOURCE=nrlcom-ladder` → 30 GETs
4. `make miner-backfill SOURCE=nrlcom-stats` → 14 GETs
5. `make miner-backfill SOURCE=supercoach-stats SEASON_FROM=2018` → ~250 jqGrid sessions over 1-2h

Total: ~4-5 hours single-machine, rate-limited at 1 req/sec per origin. ~1-2GB S3.

Backfill produces the same S3 keys daily cron does — re-running future cron over the same range is a no-op.

### Phase 6 — Unified Miner dashboard — Shipped

Operator view at `/admin/miner` showing health across every pipeline (media + identity + stats + fixtures + injuries + ladder + leaderboards). Reads from `agent_runs` filtered by `agent_id='miner'`, groups by `detail_json.pipeline`. Per-pipeline: last run, status, row counts, cost. No new data — just the view.

API slice: `GET /api/admin/miner/dashboard` is read-only and groups recent
Miner `agent_runs` rows by `detail_json.pipeline`, returning last run status,
timestamps, summary, compact detail counts, recent failure count, and cost
rollups. The admin web surface now includes a Miner Dashboard tab that reads
that endpoint, supports refresh/window controls, and displays compact pipeline
rollups beside the existing admin operator panels.

### Phase 7 (future) — Multi-platform expansion — Backlog

The multi-platform roadmap items below (podcasts, radio, TV shows, Twitter/X, Instagram, blogs, Reddit) instantiate the same shape: each becomes a `miner/<platform>_<thing>/` folder with an admin endpoint. Out of scope for the charter proper; tracked for visibility.

---

## YouTube — depth on the existing platform

| Capability | Status | Notes |
|---|---|---|
| **Deterministic discovery surface (§3.1)** — `youtube_search` + `find_related_channels` with server-side `filter_known=True` | Shipped | Admin endpoint and CLI file novel YouTube candidates into `miner_candidates` with server-side dedupe and `agent_runs` audit rows. |
| Refocus agentic Miner brief on off-platform + long-tail (instead of competing with deterministic) | Planned | Tied to §3.1 landing |
| Admin review queue UI at `/admin/recon` | Shipped (2026-05-30) | Admin tab lists candidates, supports details, approval/rejection, filters, admin-key storage, and stats. |
| Live Recon SSE stream in `/pulse` (theatric reasoning visible to users) | Planned | Drives the visible-reasoning UX |
| `Event` rows for the reasoning trace (Pulse feed integration) | Backlog | TBD when live stream lands |
| Scheduled deterministic YouTube discovery | Shipped (2026-05-30) | Weekly Lightsail cron invokes `miner-refresh.sh source-discovery-youtube` at Monday 06:30 AEST; operator `--dry-run` is static/no-op. Agentic off-platform discovery remains manual. |
| **Channel-metadata refresh** — periodic re-snapshot of subs/views/video count and active/inactive detection (extends §3.4) | Shipped | Daily cron invokes `/api/admin/miner/refresh-channel-stats`; the job writes `agent_runs` and channel metric snapshots independently of the heavier video refresh. |
| **Source health / liveness monitoring** — detect stalled channels, failed refresh/backfill runs, pending/failed audio or transcription work, caption-regeneration risk | Shipped (internal classifier) | `app.miner.source_health` returns route-free structured summaries from DB metadata. Dashboard surfacing can layer on later if operators need it. |
| Audio acquisition surface (Miner owns yt-dlp → S3) | Shipped (2026-05-03) | `make collect-audio SOURCE_ID=...`. Diarised transcription split out to Analyst. |
| Recurring drain job for `ingestion_status='pending'` sources | Partially shipped | Bounded drain helpers + `make collect-audio-drain` exist. Cron/APScheduler scheduling is still open. |
| Backfill of legacy `source_chunks_v1` (221k auto-caption chunks) | Backlog | Re-extract via Miner audio + Analyst transcribe on highest-leverage channels first; ~$50 for top-5. |
| Production ingestion off Temporal | Shipped | `IntelSweepWorkflow` superseded by Miner `audio.py` + Analyst `transcribe.py`. Worker code remains in tree for reference but is not invoked. |
| `agent_runs` rows for deterministic jobs (3.2, 3.3, 3.4) | Shipped (2026-05-30) | YouTube refresh, per-channel refresh, channel-stats refresh, and deterministic discovery write standard Miner audit rows. |

---

## Multi-platform expansion

Schema (`platform` field on `miner_candidates` / `sources`) is already
platform-agnostic, but multi-platform should not mean "add every possible
scraper." Each platform must earn its place by adding coverage the shipped
YouTube pipeline cannot already reach.

**Platform vs. format — and YouTube's gravity.** Miner acquires by *platform*
(where it fetches); NRL media arrives in *formats* (what the content is:
podcast, panel show, radio segment, TV clip, article, social post). The two are
orthogonal. Most NRL podcasts publish to YouTube, many radio segments are
re-uploaded there, and TV shows surface as clips or full episodes there. The
shipped YouTube pipeline therefore already reaches much of the "podcast/radio/TV"
surface. Multi-platform work should target the off-YouTube residual:
standalone RSS feeds, article pages, Reddit threads, social posts, and native
audio/video that is not re-uploaded.

### Foundation slice: MP0 — platform identity and content taxonomy

Do this before adding new acquisition modules. Without it, new platforms will
produce duplicate shows, ambiguous source types, and hard-to-query wiki inputs.

**Schema / metadata**
- Add a stable `source_identity` concept for a show/person/outlet that can span
  platforms. A single show may have a YouTube channel, podcast RSS feed, website,
  Twitter/X account, Instagram account, and Reddit presence.
- Add `sources.content_format` or equivalent metadata with a small controlled
  vocabulary: `video`, `podcast_audio`, `radio_audio`, `tv_clip`, `article`,
  `social_post`, `forum_thread`.
- Add platform-specific external IDs in `metadata_json`, but keep the common
  columns (`platform`, `external_id`, `canonical_url`, `published_at`, title)
  consistent across platforms.
- Extend candidate scoring to include `platform`, `content_format`,
  `source_identity_hint`, `publisher`, and `rights_risk`.

**Storage convention**
- Keep bronze raw captures under `s3://{clean_bucket}/miner/{platform}/...`.
- Store raw platform payloads before any parsing: RSS XML, article HTML, API JSON,
  Reddit JSON, tweet JSON, captions, or media metadata.
- Store downloaded audio/video under the existing media buckets only after the
  row is approved and enumerated as a source.

**Operational rules**
- Every new platform folder follows D9: `fetcher.py`, `models.py`, `routes.py`,
  fixtures, unit tests, and env-flagged live drift tests where live access is
  practical.
- Every endpoint writes `agent_runs` under `agent_id='miner'` with
  `detail_json.pipeline='<platform>-<thing>'`.
- Every platform has an explicit rate limit, retry policy, and robots/ToS note
  in its README before it is scheduled.

### Recommended sequence

| Phase | Platform | Why this order | Output |
|---|---|---|---|
| MP0 | Identity + format taxonomy | Prevents duplicate ingestion before adding more sources | Schema/docs/tests only |
| MP1 | Blogs/news/RSS articles | Highest value-to-risk ratio; public HTML/RSS; no media pipeline needed | Article sources + raw HTML/text |
| MP2 | Podcast RSS | High signal and usually open; captures shows not on YouTube | Episode sources + audio hand-off |
| MP3 | Reddit | Good community signal; official API path exists; lower authority than media | Thread sources + comment trees |
| MP4 | Twitter/X | High quote value but paid/restricted API and high noise | Social-post sources |
| MP5 | Instagram | Injury/team-news value but brittle and auth-gated | Captions/Reels only if policy-safe |
| MP6 | Native radio/TV | Most already re-uploaded; native capture is rights/paywall heavy | Defer unless a specific source is critical |

### Platform slices

#### MP1 — Blogs / news / article pages

**Priority:** First non-YouTube platform.

**Why:** This fills a real gap without introducing audio/video complexity. It
captures written analysis, injury updates, team news, club announcements, and
long-form opinion that never appears as video.

**Candidate sources**
- NRL.com features and club news pages.
- The Roar, Zero Tackle, ESPN NRL, ABC sport NRL articles.
- Club websites and official press releases.
- Independent fantasy/analysis blogs where RSS or stable indexes exist.

**Implementation shape**
- Folder: `services/api/app/miner/articles/`.
- Candidate kind: `article_feed` or `article_site`.
- Source rows: `platform='web'`, `content_format='article'`.
- Bronze keys:
  - `miner/web/feed/{publisher}/{YYYYMMDD}.xml`
  - `miner/web/articles/{publisher}/{YYYY}/{MM}/{slug}.html`
  - optional extracted text snapshot:
    `miner/web/articles/{publisher}/{YYYY}/{MM}/{slug}.txt`
- Extraction: readability-style article text extraction into `source_documents`
  or equivalent raw text document rows. Analyst still owns claim extraction and
  interpretation.

**Done definition**
- One seeded source list with 5-10 publishers.
- Deterministic feed/page enumerator with dedupe on canonical URL.
- Fixture tests for RSS, sitemap/listing page, article page, and paywall/blocked
  fallback.
- Admin review queue can approve article feeds/sites and enumerate article
  sources.

#### MP2 — Podcast RSS

**Priority:** Second.

**Why:** Podcast RSS is open, structured, and high signal. It covers shows that
publish audio feeds but do not reliably upload every episode to YouTube.

**Candidate sources**
- Podcast RSS feeds from Apple Podcasts / Spotify pages where the canonical RSS
  URL is discoverable.
- Publisher-hosted feeds from club/fantasy/news sites.

**Implementation shape**
- Folder: `services/api/app/miner/podcast_rss/`.
- Candidate kind: `podcast_feed`.
- Source rows: `platform='podcast_rss'`, `content_format='podcast_audio'`.
- Bronze keys:
  - `miner/podcast_rss/feeds/{feed_hash}/{YYYYMMDD}.xml`
  - `miner/podcast_rss/episodes/{feed_hash}/{episode_guid}.json`
- Media hand-off: approved episode rows keep `ingestion_status='pending'`; the
  existing Miner audio drain downloads the episode enclosure to raw audio S3,
  then Analyst transcribes.

**Done definition**
- RSS parser handles GUID, enclosure URL, duration, title, description,
  published date, and episode URL.
- Dedupe on `(platform, external_id)` where `external_id` is stable feed GUID +
  episode GUID hash.
- At least one feed fixture, one changed-feed fixture, and one missing-enclosure
  fixture.

#### MP3 — Reddit

**Priority:** Third, if community signal becomes useful.

**Why:** Reddit is not authoritative, but it captures fan consensus, rumours,
sentiment, and early reactions. It should complement expert sources, not drive
truth by itself.

**Candidate sources**
- `r/nrl`, club subreddits, SuperCoach/fantasy subs if signal is sufficient.
- High-engagement threads around team lists, injuries, trades, judiciary, and
  game reactions.

**Implementation shape**
- Folder: `services/api/app/miner/reddit/`.
- Candidate kind: `subreddit` or `reddit_thread_query`.
- Source rows: `platform='reddit'`, `content_format='forum_thread'`.
- Bronze keys:
  - `miner/reddit/subreddits/{subreddit}/{YYYYMMDD}.json`
  - `miner/reddit/threads/{thread_id}.json`
- Extraction: raw thread title/body/top comments into source documents/chunks
  with comment IDs preserved. Analyst owns summarisation, claim extraction, and
  credibility treatment.

**Done definition**
- Uses an official API path where available.
- Configurable score threshold using upvotes, comments, recency, and keyword
  match.
- Explicit filters for low-signal meme/banter posts.
- No automatic wiki facts from Reddit without downstream corroboration.

#### MP4 — Twitter / X

**Priority:** Fourth, only if API/access economics make sense.

**Why:** High quote value for players, journalists, clubs, and insiders, but
high noise and high acquisition risk.

**Candidate sources**
- Manual seed list of NRL journalists, clubs, players, SuperCoach analysts,
  and official league accounts.
- Agentic discovery can suggest adjacent accounts, but approval should stay
  manual.

**Implementation shape**
- Folder: `services/api/app/miner/twitter/`.
- Candidate kind: `twitter_account`.
- Source rows: `platform='twitter'`, `content_format='social_post'`.
- Bronze keys:
  - `miner/twitter/accounts/{handle}/{YYYYMMDD}.json`
  - `miner/twitter/posts/{post_id}.json`
- Extraction: post text, author, timestamp, URL, conversation/repost metadata.
  Media attachments are metadata-only unless explicit download is policy-safe.

**Done definition**
- API cost and access model documented before implementation.
- Strict allowlist for accounts; no broad scraping.
- Quote extraction downstream can distinguish first-party posts from reports
  about someone else's comments.

#### MP5 — Instagram

**Priority:** Fifth / lowest among social platforms.

**Why:** Clubs and players often break training, injury, and selection hints
through Instagram, but acquisition is brittle, auth-gated, and policy-sensitive.

**Implementation shape**
- Folder only if a policy-safe API or export path exists:
  `services/api/app/miner/instagram/`.
- Candidate kind: `instagram_account`.
- Source rows: `platform='instagram'`, `content_format='social_post'` or
  `video` for Reels only when media download is permitted.
- Bronze keys:
  - `miner/instagram/accounts/{handle}/{YYYYMMDD}.json`
  - `miner/instagram/posts/{post_id}.json`

**Done definition**
- No credential scraping.
- Captions and public metadata only unless a compliant API grants more.
- Reels audio/video enters the normal media pipeline only when rights and access
  are explicit.

#### MP6 — Native radio / TV / paywalled broadcasters

**Priority:** Defer unless a specific source is strategically critical.

**Why:** Most usable clips are already on YouTube or podcast RSS. Native capture
adds legal, operational, and engineering complexity: schedules, stream recording,
paywalls, DRM, missed-airing retries, and rights policy.

**Potential shape**
- Radio: prefer official podcast RSS feeds first. Native live stream recording
  only for a named show with clear access rights.
- TV: prefer official YouTube clips and public video pages. Do not build around
  paywalled/DRM sources.
- Source rows remain audio/video sources and flow through the existing Miner
  media + Analyst transcription path.

### Platform readiness checklist

A new platform is ready to implement when all are true:

- It adds material coverage not already available through YouTube.
- There is a stable public/API acquisition path.
- S3 bronze keys and DB source/candidate shapes are specified.
- Dedupe keys are stable and documented.
- Rate limits, auth requirements, and policy risks are explicit.
- At least one fixture can be checked into `tests/fixtures/miner/<platform>/`.
- A minimal operator path exists: admin endpoint, dry-run, and run audit.

Until MP0 lands, treat platform-specific work as exploratory only. The most
practical first execution thread is MP1 Blogs/news/RSS, because it avoids media
download, is easy to fixture-test, and gives downstream agents written text that
YouTube will never provide.

---

## Future improvements

Additive — they layer on top of Tier 1 (already built: known-set injection + bulk dedupe) without replacing it.

> **Note:** The former "Tier 2 — YouTube-aware tools" entry has been promoted to a shipped first-class architectural change — see [architecture.md §3.1](architecture.md) and the YouTube roadmap above.

**Tier 3 — Coverage-gap biasing (agentic surface)**
- Pre-run, count `miner_candidates.content_categories` (and, post multi-platform, `platform`) to find underrepresented dimensions
- Inject "Coverage gaps:" paragraph into the user brief to bias the run
- Most useful once §3.1 lands and the agentic surface is dedicated to long-tail work. Becomes especially valuable when multi-platform lands and "underrepresented" is multi-axis (category × platform).

**Quality scoring on §3.1 candidates**
- Deterministic discovery has no semantic filter — it persists everything novel
- Options: lightweight heuristic scorer (sub count, upload frequency, channel age), or a small batch LLM pass that reads About pages for raw candidates and assigns score + content_categories
- Becomes important if §3.1 floods `miner_candidates` with low-signal results

**Cross-platform deduplication**
- Once multi-platform lands, the same person/show may appear on YouTube + podcast feed + Twitter. The `miner_candidates.platform` axis avoids accidental re-onboarding on the same platform but doesn't link them across platforms.
- Add a `source_identity` concept (or use `channels.canonical_handle` consistently) so an Analyst querying "what has Pat Souness said this week" pulls across all platforms a single creator publishes on.

---

## Related

- [README.md](README.md) — Miner's identity, scope, and voice
- [architecture.md](architecture.md) — pipeline position, flow, component internals
- [charter.md](charter.md) — locked design decisions D1–D13

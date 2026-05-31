---
tags: [area/agents, subarea/crew]
---

# Miner Roadmap

> Last reviewed: 2026-05-31.

This page is the execution roadmap for Miner. It is intentionally organised by
what an operator or implementer should do next, not by the order the system was
originally built.

For stable architecture and ownership rules, use:

- [README.md](README.md) - Miner's identity, scope, and boundary.
- [architecture.md](architecture.md) - flow diagrams and component internals.
- [charter.md](charter.md) - locked decisions D1-D13 and pipeline inventory.

Status labels:

- **Live** - shipped and deployed.
- **Ready** - implementation exists; needs an operator run or rollout action.
- **Next** - highest-priority unshipped work.
- **Later** - useful, but not blocking the current product surface.
- **Parked** - explicitly deferred.

---

## Current State

| Area | State | What this means |
|---|---|---|
| Miner identity | Live | The Scout-to-Miner rename is merged and deployed. Migration `072_rename_scout_to_miner.sql` is applied in prod. Historical S3 archives were copied from `scout/` to `miner/`. |
| YouTube media acquisition | Live | Discovery, recon approval, channel/video enumeration, daily refresh, channel stats, audio acquisition, and Miner audit rows are in place. |
| Structured data acquisition | Live | SuperCoach and NRL.com current-season pipelines are S3-first and project current data into DB tables. |
| Miner dashboard | Live | `/admin/miner` reads Miner `agent_runs` and shows pipeline health. |
| Historical data | Ready | Phase 5 archive backfill still needs the long-running operator run, then historical S3-to-DB projection. |
| Multi-platform acquisition | Next | The plan is defined, but MP0 platform identity/taxonomy should land before adding more scrapers. |

---

## What Is Left

These are the remaining roadmap items that matter. Everything else below is
supporting detail or shipped history.

### 1. Phase 5 - Historical Backfill

**State:** Ready for operator run.

**Goal:** Fill historical `miner/*` S3 archives, then project those archives into
canonical DB tables so wiki/player/team/history surfaces can read more than the
current season.

**Prerequisites already done:**

- Prod deploy is on the Miner code path.
- Migration `072_rename_scout_to_miner.sql` is applied in prod.
- Old `scout/` S3 archives were copied to `miner/`.
- Backfill driver supports `--archive-only`, `--resume`, and `--force`.
- `scripts/miner-populate.sh` can stage populate code into the prod API
  container and run S3-to-DB projection phases.

**Capture runs:**

| Source | Range | Mode | Expected cost/time |
|---|---:|---|---|
| `nrlcom-draw` | 1908-current | `--archive-only --resume` | About 3,000 GETs, roughly 1 hour |
| `nrlcom-match-centre` | 2000-current | `--archive-only --resume` | About 5,200 round/match walks, roughly 3-4 hours |
| `nrlcom-ladder` | available seasons | `--archive-only --resume` | Small |
| `nrlcom-stats` | available seasons | `--archive-only --resume` | Small |
| `supercoach-stats` | 2018-current | `--archive-only --resume` | About 250 jqGrid sessions, roughly 1-2 hours |

**Projection runs after capture:**

- Run `scripts/miner-populate.sh phase rounds --seasons ...`
- Run `scripts/miner-populate.sh phase matches --seasons ...`
- Run `scripts/miner-populate.sh phase team_lists --seasons ...`
- Run `scripts/miner-populate.sh phase stats --seasons ...`
- Run `scripts/miner-populate.sh phase timeline --seasons ...`
- Run `scripts/miner-populate.sh phase standings --seasons ...`
- Run `scripts/miner-populate.sh phase leaderboards --seasons ...`
- Run `scripts/miner-populate.sh phase player_rounds --seasons ...`
- Finish with identity/re-resolution phases where needed.

**Done when:**

- S3 counts exist for each expected historical prefix.
- Projection runs are resumable and have recorded row deltas.
- Spot checks pass for old seasons, recent seasons, finals rounds, and missing
  upstream data.
- Any shape drift is documented as either accepted archive-only data or queued
  extractor work.

### 2. Multi-Platform Foundation

**State:** Next.

Do this before adding podcast, article, Reddit, Twitter/X, Instagram, radio, or
TV acquisition modules. The problem is not "can Miner fetch more things"; the
problem is avoiding duplicate identities and inconsistent source metadata once
the same show/person/outlet appears on several platforms.

**MP0 deliverables:**

- Add a stable source identity concept for a show, outlet, person, or feed that
  can span multiple platforms.
- Add or standardise `content_format` metadata with values such as `video`,
  `podcast_audio`, `article`, `social_post`, and `forum_thread`.
- Document platform-specific external IDs in `metadata_json` while keeping
  common fields consistent: `platform`, `external_id`, `canonical_url`,
  `published_at`, and title.
- Extend candidate scoring metadata with `platform`, `content_format`,
  `source_identity_hint`, `publisher`, and `rights_risk`.
- Lock S3 bronze conventions under `s3://{clean_bucket}/miner/{platform}/...`.

**Done when:**

- New platform candidates can be reviewed without duplicating an existing
  YouTube channel, podcast feed, or article source identity.
- Tests cover identity matching and candidate/source metadata round-trips.
- The admin/recon shape is ready for non-YouTube candidates.

### 3. First New Platform: Articles / News / RSS

**State:** Next after MP0.

This should be the first non-YouTube platform because it avoids media download,
is easy to fixture-test, and supplies downstream agents with written text that
YouTube will never provide.

**Scope:**

- Folder: `services/api/app/miner/articles/`.
- Candidate kind: `article_feed` or `article_site`.
- Source rows: `platform='web'`, `content_format='article'`.
- Bronze keys:
  - `miner/web/feed/{publisher}/{YYYYMMDD}.xml`
  - `miner/web/articles/{publisher}/{YYYY}/{MM}/{slug}.html`
  - optional text snapshot:
    `miner/web/articles/{publisher}/{YYYY}/{MM}/{slug}.txt`

**Seed targets:**

- NRL.com features and club news pages.
- Club websites and official press releases.
- ABC Sport, ESPN NRL, The Roar, Zero Tackle, and similar stable publishers.
- Independent fantasy/analysis blogs only where the source is stable and
  policy-safe.

**Done when:**

- A seeded source list covers 5-10 publishers.
- RSS/listing enumeration dedupes on canonical URL.
- Fixtures cover RSS, sitemap/listing, article page, blocked/paywalled page,
  and changed feed.
- Approved article sources hand raw text to downstream Analyst surfaces without
  Miner interpreting claims.

### 4. Operations Hardening

**State:** Later.

These are useful, but they should not displace Phase 5 or MP0/MP1.

| Item | Why it matters | Current state |
|---|---|---|
| Recurring audio drain scheduling | Keeps `ingestion_status='pending'` from building up. | Bounded drain helpers and `make collect-audio-drain` exist; cron/APScheduler still open. |
| Source-health dashboard surfacing | Operators can see stale runs, stalled channels, failed audio/transcription, and caption risk in the UI. | Classifier exists in `app.miner.source_health`; richer dashboard surfacing can layer later. |
| Cron alerting for partial failures | Some scheduled jobs may return HTTP 200 while recording failed/partial `agent_runs`. | Audit data exists; alerting semantics still need tightening. |
| Legacy `source_chunks_v1` backfill | Rebuilds old auto-caption chunks through modern Miner audio + Analyst transcription. | Parked; cost/risk should be scoped by highest-leverage channels first. |

---

## Execution Lanes

Use these lanes when splitting the roadmap across separate threads/worktrees.
Only run lanes in parallel when their touched files are disjoint.

| Lane | Can run now? | Touches | Depends on | Output |
|---|---|---|---|---|
| Phase 5 capture operator run | Yes | Prod S3/admin API only | Migration 072, prod `ADMIN_KEY`, AWS access | Historical `miner/*` archives |
| Phase 5 projection operator run | After capture | Prod DB/S3, `scripts/data/populate/**` only if fixes are needed | Phase 5 capture | Historical DB rows |
| MP0 identity/taxonomy | Yes | DB migrations, shared models, recon/admin API, docs/tests | None | Cross-platform source identity contract |
| MP1 articles/RSS | After MP0 contract is clear | `services/api/app/miner/articles/**`, tests, docs | MP0 | Article feed/site discovery and enumeration |
| Audio drain scheduling | Yes | `scripts/cron.d/**`, `scripts/miner-refresh.sh` or new wrapper, docs/tests | None | Scheduled pending-audio drain |
| Source-health UI surfacing | Yes | `services/web/**`, maybe API dashboard response | Existing source-health classifier | Operator-visible source-health panels |

---

<a id="charter-phasing-phase-07"></a>

## Shipped Baseline

This section is intentionally compact. Detailed implementation history belongs
in build run reports under `docs/build/runs/`, not in the active roadmap.

### Media Acquisition

| Capability | State | Notes |
|---|---|---|
| Deterministic YouTube discovery | Live | Admin endpoint and CLI write novel candidates into `miner_candidates` with server-side dedupe and `agent_runs` audit rows. |
| Agentic source discovery | Live | Web-hunting loop remains best for off-platform mentions and long-tail discovery. |
| Recon review queue | Live | `/admin/recon` lists candidates and supports detail, approval, rejection, filters, admin-key storage, and stats. |
| Channel/video enumeration | Live | Approval triggers uploads-playlist walk; daily refresh finds new uploads and snapshots video metrics. |
| Channel metadata refresh | Live | Daily channel-stats refresh writes `channel_metrics` independently of the heavier video refresh. |
| Audio acquisition | Live | Miner owns yt-dlp to S3. Analyst owns transcription, diarisation, and interpretation. |
| Miner dashboard | Live | `/admin/miner` groups `agent_runs` by `detail_json.pipeline`. |

### Structured Data Acquisition

| Phase | Capability | State |
|---|---|---|
| 1 | SuperCoach roster | Live |
| 2 | SuperCoach per-round stats | Live |
| 2.5 | SuperCoach teams/settings and S3-first retrofit | Live |
| 3 | NRL.com draw and match-centre capture | Live |
| 3.5 | NRL.com S3-to-DB extractors | Live |
| 4 | NRL.com casualty ward and ladder | Live |
| 4.5 | NRL.com stats and players roster | Live |
| 5 | Historical backfill | Ready |
| 6 | Unified dashboard | Live |
| 7 | Multi-platform expansion | Next |

### Retired / Reframed

| Item | State | Notes |
|---|---|---|
| `services/worker-scraper/` | Retired | Deleted 2026-05-28; Temporal scraper path was not part of prod. |
| `scrape-supercoach` skill | Retired | Operators use the Miner endpoint or `make` target. |
| Old Scout naming | Retired | Code/docs/schema use Miner; historical migrations keep old names until migration 072 moves the live schema forward. |

---

<a id="multi-platform-expansion"></a>

## Multi-Platform Expansion

The platform plan is deliberately ordered by value-to-risk ratio. YouTube already
captures many podcasts, radio segments, and TV clips because creators re-upload
to YouTube. New platform work should target content YouTube does not reach.

| Step | Platform | Why this order | Output |
|---|---|---|---|
| MP0 | Identity + format taxonomy | Prevents duplicate ingestion before adding more sources. | Schema/docs/tests |
| MP1 | Blogs/news/RSS articles | High value, low operational risk, no media download. | Article sources and raw HTML/text |
| MP2 | Podcast RSS | Open and structured; covers shows not reliably uploaded to YouTube. | Episode sources and audio hand-off |
| MP3 | Reddit | Useful community signal, but lower authority. | Thread sources and comment trees |
| MP4 | Twitter/X | High quote value, but paid/restricted API and noisy. | Social-post sources |
| MP5 | Instagram | Potential injury/team-news signal, but brittle and auth-gated. | Captions/Reels only if policy-safe |
| MP6 | Native radio/TV | Rights/paywall/scheduling complexity; most useful clips are elsewhere. | Defer unless a named source is critical |

### MP2 - Podcast RSS

Podcast RSS should reuse the existing media pipeline after enumeration.

- Folder: `services/api/app/miner/podcast_rss/`.
- Candidate kind: `podcast_feed`.
- Source rows: `platform='podcast_rss'`, `content_format='podcast_audio'`.
- Bronze keys:
  - `miner/podcast_rss/feeds/{feed_hash}/{YYYYMMDD}.xml`
  - `miner/podcast_rss/episodes/{feed_hash}/{episode_guid}.json`
- Done when RSS parser handles GUID, enclosure URL, duration, title,
  description, publish date, and canonical episode URL.

### MP3 - Reddit

Reddit is useful for reaction and rumour tracking, not canonical facts.

- Folder: `services/api/app/miner/reddit/`.
- Candidate kind: `subreddit` or `reddit_thread_query`.
- Source rows: `platform='reddit'`, `content_format='forum_thread'`.
- Bronze keys:
  - `miner/reddit/subreddits/{subreddit}/{YYYYMMDD}.json`
  - `miner/reddit/threads/{thread_id}.json`
- Done when score thresholds, comment limits, low-signal filters, and
  downstream credibility treatment are explicit.

### MP4 - Twitter / X

Implement only if API access and cost are acceptable.

- Folder: `services/api/app/miner/twitter/`.
- Candidate kind: `twitter_account`.
- Source rows: `platform='twitter'`, `content_format='social_post'`.
- Bronze keys:
  - `miner/twitter/accounts/{handle}/{YYYYMMDD}.json`
  - `miner/twitter/posts/{post_id}.json`
- Done when accounts are allowlisted, API costs are documented, and downstream
  extraction distinguishes first-party posts from reports about someone else.

### MP5 - Instagram

Instagram should stay parked until there is a policy-safe API/export path.

- No credential scraping.
- Captions and public metadata only unless a compliant API grants more.
- Reels audio/video enters the normal media pipeline only when rights and access
  are explicit.

### MP6 - Native Radio / TV

Prefer official YouTube uploads and podcast RSS first. Native live capture should
only happen for a named show/source with clear access rights and enough value to
justify scheduling, retry, and rights complexity.

---

## Decision Gates

Use these gates before promoting any roadmap item into implementation.

1. **Bronze boundary:** Miner fetches and stores raw external data. Analyst and
   downstream agents interpret it.
2. **S3 first:** New acquisition writes raw payloads to S3 before parsing or DB
   projection.
3. **D8 drift guard:** New scrapers need fixture-backed strict-shape tests and,
   where practical, env-flagged live drift tests.
4. **Audit:** New runs write `agent_runs` under `agent_id='miner'` with
   `detail_json.pipeline`.
5. **Dedupe:** New platforms must define stable external IDs and cross-platform
   identity behaviour before scheduling.
6. **Policy:** Rate limits, auth requirements, robots/ToS constraints, and media
   rights must be documented before automation.

---

## Parking Lot

These are intentionally not part of the next execution lane.

- SuperCoach Draft mode (`miner/supercoach_draft_*`) unless Draft becomes a
  product concern.
- Folding the NRL.com HTML profile scraper into `miner/nrlcom_players_roster/`;
  the HTML scrape and JSON fetch enrich different fields and can stay separate
  until there is a real maintenance reason.
- Tightening NRL.com player profile identity fields from nullable strings after
  a future extractor consumes the JSON roster.
- Live Recon SSE stream in `/pulse`.
- Event rows for visible reasoning traces.
- Broad native TV/radio capture.

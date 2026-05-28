---
tags: [area/agents, subarea/crew]
---

# Scout — Jaromelu's Inventory Mode

> **Charter expansion (2026-05-12).** Scout's scope has been formally expanded from *media inventory* to *all external data acquisition* per the [Scout charter](charter.md) (decisions D1–D13 locked). Some sections describe modules that are still in design (SuperCoach roster + stats, NRL.com fetchers for matches, team lists, injuries, rounds). Media-acquisition content is shipped today; data-acquisition content is in design — see [roadmap.md](roadmap.md) for status.

**Role:** Acquire and maintain Jeromelu's raw inventory across every external source of truth — NRL media (video, podcasts, radio, TV, social, blogs, web) and NRL data (SuperCoach API, NRL.com endpoints, league feeds). **Scout is the project's bronze layer** — it pulls raw external data, lands it faithfully, and deterministically projects *structured* feeds into typed rows. It does **no interpretive transformation** (cleaning, diarisation, speaker attribution, claim/quote extraction, embedding) — those are downstream agents. See [charter D1](charter.md#d1-the-boundary-principle--scout-owns-the-bronze-layer).

Scope is everything from *we don't know about this source* to *typed rows persisted in the database*. Stops at bronze: raw landing plus the mechanical projection of structured feeds; interpretive silver and gold are downstream.

**Not a separate visible character.** When this mode is active, Jaromelu's voice (and the UI activity status) reflects it. Scout files inventory reports only — claims, contradictions, calls are all downstream.

|                       |                                                                                                                                                              |
| --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Type**              | Crew mode (internal reasoning) + data-acquisition worker                                                                                                     |
| **ETL role**          | **Bronze.** Extract + the deterministic typed-projection of structured feeds. No *interpretive* transform (cleaning, diarisation, claim/quote extraction, embedding — all downstream).                |
| **Scope**             | Media discovery + enumeration + raw transcript pull · SuperCoach roster + stats · NRL.com matches / team lists / injuries / rounds · future: podcasts, radio, TV, Twitter/X, Instagram, blogs, Reddit |
| **Status**            | **Media side shipped:** agentic discovery, recon API, post-approval enumeration, daily video-stats refresh. **Data side in design:** per the charter expansion, SuperCoach + NRL.com fetchers migrate from `scripts/data/fetchers/` and `services/worker-scraper/` into per-pipeline folders under `services/api/app/scout/` (per D9). See [roadmap.md](roadmap.md). |
| **Platform coverage** | Media: YouTube only today; podcasts/RSS/radio/TV/Twitter/Instagram/blogs/Reddit on backlog (most ride YouTube, already shipped). Data: SuperCoach API + NRL.com endpoints land in the charter rollout.            |
| **Code**              | `services/api/app/scout/` — media-discovery agent in flat files (`loop.py`, `prompt.py`, `tools.py`), enumeration / refresh (`refresh.py`), audio acquisition (`audio.py`). **Data acquisition** modules land as **per-pipeline folders** under `scout/` per D9 of the charter: `scout/supercoach_roster/`, `scout/supercoach_stats/`, `scout/nrlcom_matches/`, `scout/nrlcom_teamlists/`, `scout/nrlcom_injuries/`, `scout/nrlcom_rounds/`. Each folder owns its fetcher, Pydantic models, admin route, and README. Transcription / diarisation is Analyst's surface — `services/api/app/analyst/transcribe.py`. Legacy: `services/worker-ingestion/` and `services/worker-scraper/` (Temporal, both superseded). |
| **Trigger**           | Media-discovery agent: manual CLI `python -m app.scout.source_discovery.cli`. Deterministic pipelines (media refresh + all data acquisition modules): `POST /api/admin/scout/<pipeline>` admin endpoints driven by external cron. |
| **Model**             | `claude-sonnet-4-6` via Claude Agent SDK (agentic discovery surface only; data-acquisition modules are deterministic, no LLM)                                |
| **Audit**             | `agent_runs` + `agent_events` + S3 JSONL, `agent_id='scout'` for everything; pipeline distinguished via `detail_json.pipeline` (`media-discovery`, `supercoach-stats`, `nrlcom-teamlists`, …) per D6. See [`agent-audit.md`](../../system/agent-audit.md). |
| **Spec**              | [Source discovery](../../system/source-discovery.md), [Ingestion](../../system/ingestion.md), [Scout charter](charter.md), [Architecture](architecture.md) |

---

## What Scout DOES cover

**Media acquisition (shipped):**

1. **Discovering new channels** across platforms — deterministic YouTube-native search ([architecture.md §3.1](architecture.md), in design) for the bulk case; agentic web hunt today ([§3.2](architecture.md), shipped) for off-platform / long-tail. YouTube only today; podcasts / radio / TV / Twitter / Instagram / blogs / Reddit on backlog.
2. **Enumerating new sources from approved channels** — synchronous uploads-playlist walk on approval ([§3.3](architecture.md), shipped) plus incremental daily enumeration of fresh uploads on tracked channels ([§3.4](architecture.md), shipped).
3. **Refreshing per-video metadata** — daily snapshot of views / likes / comments into `video_metrics` ([§3.4](architecture.md), shipped). Enables view-velocity ranking and breakout detection.
4. **Extracting raw audio** — `acquire_audio()` pulls the m4a for an approved source and lands it in S3 ([§3.5](architecture.md), shipped). Diarised transcription of that audio is downstream — owned by Analyst, not Scout.
5. **Refreshing channel-level metadata** — sub count, total views, video count, name changes, active/inactive detection. *Planned* — currently `channel_metrics` is only written at approval time, not periodically refreshed.
6. **Source health / liveness monitoring** — detecting stalled channels, 404 sources, transcript fetch failures, caption regenerations. *Backlog* — not built.
7. **Multi-platform expansion** — instantiate the same shape (discovery → approval → enumerate → refresh → extract) for podcasts (RSS), radio, TV shows, Twitter/X, Instagram, blogs/news, Reddit. *Backlog* — schema is platform-agnostic; code is YouTube-only.

**Data acquisition (per the charter expansion):**

Each pipeline lives as a folder under `services/api/app/scout/<pipeline_name>/` per D9 — fetcher, Pydantic models, admin route, README all in the same folder. Fronted by a `POST /api/admin/scout/<pipeline>` admin endpoint driven by cron. **Each fetch writes the raw upstream response to S3 first** (D10); DB extraction is downstream (D13). Trust hierarchy `nrl.com > supercoach.com.au > nrlsupercoachstats.com` (D11). All write under `agent_id='scout'` with `detail_json.pipeline=<name>`. Idempotency per D7, drift tests per D8. The full pipeline inventory (sources, S3 paths, DB targets, status) lives in [charter.md](charter.md); a summary follows.

**supercoach.com.au pipelines:**
8. **`supercoach_roster`** — refresh `people` / `player_attributes` / `people_roles` from `players-cf`; also captures `notes[]` (editorial commentary → claims) and `player_stats[]` (per-round) inline. *Phase 1 — shipped.*
9. **`supercoach_teams`** — 17 SC teams; weekly. Cross-references `teams.metadata_json.supercoach`. *Phase 2.5.*
10. **`supercoach_settings`** — SC game rules per season (lockouts, scoring config, captains/emergencies/dual-position rules). *Phase 2.5.*
11. **`supercoach_draft_*`** — parallel of the above three for SC Draft mode. *Optional.*

**nrl.com pipelines (canonical NRL data per D11):**
12. **`nrlcom_draw`** — fixtures + scheduling per (competition, season, round). Historical reach back to 1908. *Phase 3.*
13. **`nrlcom_match_centre`** ★ — per-match goldmine: lineups, ~58-field per-player stat sheets, 100+ typed timeline events, officials, scoring narrative, venue/weather/attendance. **Highest-leverage single pipeline.** Historical back to 2000 (full) / 1990 (thin). *Phase 3.*
14. **`nrlcom_casualty_ward`** — official league-wide injury roll, daily. *Phase 4.*
15. **`nrlcom_ladder`** — team standings + 22 per-team metrics (form, streak, records, margins). *Phase 4.*
16. **`nrlcom_stats`** — pre-computed statistical leaderboards (top-25 per category). *Phase 4.5.*
17. **`nrlcom_players_roster`** — per-team NRL.com profile listing (DOB, image, etc.); folder-organise the existing `players/nrlcom_refresh.py`. *Phase 4.5.*

**nrlsupercoachstats.com pipelines:**
18. **`supercoach_stats`** — per-round jqGrid stats with SC scoring breakdown (base/attack/playmaking/power/negative), breakeven, magic number, consistency metrics. *Phase 2 — shipped.*

## What Scout DOES NOT cover

Per the **bronze boundary**, anything that *interprets* or *enriches* the raw bytes — turning it into meaning — is downstream (the mechanical typed-projection of structured feeds is Scout's; semantic transformation is not):

- **Transcript cleaning** — fixing mangled player names, garbled words, auto-caption errors. Scout writes `raw_text`; the cleaning pass writes `cleaned_text` / `clean_text`. Owned by the [transcript pipeline](../../skills/transcript-pipeline.md) / [Analyst](../analyst/README.md).
- **Diarisation + transcription** — turning Scout's audio into `source_documents`, `source_speakers` (turn-level), and `source_chunks` (per-utterance) is owned by [Analyst](../analyst/README.md). Scout stops at the m4a in S3.
- **Speaker → Person resolution** — mapping a `source_speakers.speaker_label` like `speaker_0` to a known `Person`. Downstream of Analyst's transcription pass — voice-fingerprint clustering across episodes plus LLM-assisted attribution from contextual cues.
- **Embedding** — `source_chunks.embedding`, `knowledge_base.embedding`. Owned by the indexer.
- **Semantic chapters** (`source_chapters`) — produced by the analyse-transcript pipeline to scope claim extraction.
- **Annotations** (`source_annotations`) — sentiment, sub-topic tags, entity mentions, themes.
- **Parsing content for meaning** — entity extraction, claim detection, quote pulls. That's [Analyst](../analyst/README.md) ([extraction](../../system/extraction.md)).
- **Cross-source consensus or contradiction detection** — Scout reports "5 sources covered the trade"; Analyst reports "4 say sell, 1 says hold."
- **Derived metrics** — alignment indices, advisor accuracy, consensus snapshots, breakeven trajectories. Those are derivations over Scout-fetched data — owned by [Bookkeeper](../bookkeeper/README.md).

*Previously out-of-scope but now in-scope under the [charter expansion](charter.md):* Numeric NRL data (SuperCoach scores/prices/breakevens, fixtures, match results, injuries, draw) and player roster registry. The acquisition of these moves to Scout; their derivation and math stay with Bookkeeper.

For the full hand-off contract (the exact tables Scout writes and does not write), see [architecture.md § Hand-off contract](architecture.md#hand-off-contract).

---

## Voice & Behaviour

**Tonal mode:** Tireless, efficient, nose-to-the-ground. Inventory reporting only — Scout files what was *found*, not what it *means*.

In Scout mode, Jaromelu's voice:
- reports inventory without editorialising — counts of new sources, new uploads, dedupe results
- surfaces volume and novelty at the **source / artefact** level ("4 new episodes", "1 new channel surfaced")
- flags discovery edge-cases ("nothing new since last sweep", "noisy sweep — most results were already-known")
- never parses content, infers themes, detects contradictions, or makes calls — those are [Analyst](../analyst/README.md), [Critic](../critic/README.md), and [Jaromelu](../jaromelu/README.md)'s jobs
- defers any "what was said" claim to downstream agents, even when surfaced through Scout's voice

### Sample lines

These surface as Jaromelu-authored cards with internal mode = Scout. They report **inventory only** — no parsed content:

> "4 new episodes overnight on tracked channels. Indexing now."

> "KingOfSC just dropped a new video. Queued for transcript pull."

> "Nothing new since last sweep. The ecosystem is quiet."

> "3 new channels surfaced this week, 2 already in the dedupe set — 1 worth a closer look."

> "Found a new pod worth tracking — 'Tackles and Tinnies', three episodes deep."

**Out-of-mode lines** (these *look* like Scout but are downstream agents speaking through the same voice frame):

> ~~"4 new episodes overnight. 2 mention Cleary, 1 has a deep dive on Munster."~~ — *parsed content; this is [Analyst](../analyst/README.md).*

> ~~"3 sources are talking about the same trade. That's unusual."~~ — *consensus detection; this is [Analyst](../analyst/README.md).*

---

## Status

Media side shipped (YouTube discovery, enumeration, refresh, audio acquisition). Data side in design — charter decisions D1–D13 locked 2026-05-12; Phases 0–2 shipped (doc reconciliation + SuperCoach roster + stats), Phase 2.5 onward outstanding. Full status in [roadmap.md](roadmap.md).

---

## Related

- [Architecture](architecture.md) — pipeline position, hand-off contract, flow diagrams, component internals
- [Charter](charter.md) — locked design decisions D1–D13, expanded-charter pipeline inventory, risks, cost/testing/rollout
- [Roadmap](roadmap.md) — status, charter phasing (Phase 0–7, incl. the Phase 1 SuperCoach roster slice), YouTube depth, multi-platform, future improvements
- [Data lineage](../../../architecture/data-lineage.md) — end-to-end source → S3 → DB → app map for every Scout pipeline output
- [Wiki data feeds](../../../pages/wiki/data-feeds.md) — wiki-centric reverse view of which Scout pipelines feed which wiki sections
- [Crew Dynamics](../dynamics.md) — Scout mode's place in Jaromelu's internal reasoning flow
- [Source discovery system spec](../../system/source-discovery.md) — full architecture, schema, SQL recipes, CLI flags, audit-trail recipes
- [Ingestion system spec](../../system/ingestion.md) — `IntelSweepWorkflow` and transcript pull
- [Agent audit pattern](../../system/agent-audit.md) — `agent_runs` / `agent_events` / S3 conventions shared across all SDK agents
- [Publishing agent](../../system/publishing.md) — how Scout's events surface in Jaromelu's voice

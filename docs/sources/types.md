---
tags: [area/sources]
---

# Source Types

Each type has different ingestion, cleaning, and attribution concerns.

---

## 1. YouTube Transcripts → Claims

| Property | Value |
|----------|-------|
| **Origin** | Whitelisted YouTube channels (defined in `data/sources.yaml`) |
| **Cadence** | Daily automated sweep ([`IntelSweepWorkflow`](../agents/system/ingestion.md), 10 PM AEST) |
| **Raw format** | Timestamped transcript segments (JSON in S3) |
| **Cleaning** | `/clean-transcript` skill → deterministic NLP + LLM review. See [cleaning.md](cleaning.md). |
| **Extraction** | `/analyse-transcript` or `/process-transcript` — see [extraction agent](../agents/system/extraction.md) |
| **Verification** | `/verify-claims` → Haiku agents cross-check each claim against transcript |
| **Storage** | Claims linked to `source_documents` and `entities` |
| **Access** | Public — deep-link with timestamp |
| **Wiki impact** | Player pages (Expert Opinions, Current Form), Advisor pages (Track Record), Round pages (Key Talking Points) |

**Pipeline:**
```
discovery → collection (S3) → indexing (DB)
  → clean → extract claims → verify → upload to DB
```

Discovery, collection, and indexing are automated. Cleaning through upload is currently skill-driven (manual trigger, interactive review).

---

## 2. Articles (public and paywalled)

| Property | Value |
|----------|-------|
| **Origin** | URL + trafilatura/similar (public) or manual paste (paywalled) |
| **Cadence** | Ad-hoc |
| **Raw format** | HTML → cleaned markdown |
| **Cleaning** | Strip chrome, preserve structure, resolve player/team names |
| **Extraction** | Same extraction path as YouTube (claims) |
| **Storage** | Claims linked to `source_documents` |
| **Access** | Public (deep-link) or paywalled (citation without link) |
| **Wiki impact** | Player pages (Expert Opinions), Advisor pages (Recent Calls), Round pages |

**Paywalled handling:** Still cite by name ("NRL.com · Trbojevic injury update"), but the attribution badge links to the site root rather than the deep URL. No scraped content is hosted publicly.

---

## 3. Podcast Transcripts → Claims

| Property | Value |
|----------|-------|
| **Origin** | RSS feeds (post-MVP) |
| **Cadence** | Per-episode |
| **Raw format** | Audio → Deepgram transcript with diarised speakers (Phase 2) |
| **Cleaning** | Same as YouTube — garble fixes, name resolution, plus speaker attribution |
| **Extraction** | Same extraction path — but claims are attributed to the speaker entity, not just the episode |
| **Storage** | Claims with `speaker_entity_id` populated |
| **Access** | Public — deep-link to episode + timestamp |
| **Wiki impact** | Same as YouTube |

**Phase 2 concern:** Speaker diarisation and identification. Today we ingest episodes as single-speaker. Post-Phase-2, we distinguish which expert said what within a multi-host podcast.

---

## 4. Radio Transcripts → Claims

| Property | Value |
|----------|-------|
| **Origin** | Local recordings (manual capture) |
| **Cadence** | Ad-hoc |
| **Raw format** | Audio → transcript |
| **Cleaning** | Same as podcast (plus potentially noisier audio) |
| **Extraction** | Same path |
| **Access** | Usually private — citation only, no deep link |
| **Wiki impact** | Advisor pages, Round pages — lower volume than YouTube |

---

## 5. Player Statistics

| Property | Value |
|----------|-------|
| **Origin** | nrlsupercoachstats.com |
| **Cadence** | Post-round, on-demand (`scripts/data/fetchers/fetch_player_stats.py --round N`) |
| **Raw format** | Per-player stat lines: score, price, breakeven, PPM, minutes, tries, tackles, errors, etc. |
| **Cleaning** | Minimal — structured data, validated against `data/players.yaml` registry |
| **Storage** | `data/player_stats/round_NN.yaml` → `PlayerRound` records in DB |
| **Access** | Attributed to `nrlsupercoachstats.com` |
| **Wiki impact** | Player pages (Stats, Price Analysis), Round pages (Scoring Summary) |

Stats feed the [Bookkeeper](../agents/crew/bookkeeper/README.md) domain.

---

## 6. Match Statistics

| Property | Value |
|----------|-------|
| **Origin** | Derived from player stats (`scripts/data/fetchers/fetch_match_stats.py`) |
| **Cadence** | Post-round, on-demand |
| **Raw format** | Team-level aggregates: total SC points, try scorers, top 5 scorers per team |
| **Cleaning** | None — derived from already-clean player stats |
| **Storage** | `data/match_stats/round_NN.yaml` |
| **Wiki impact** | Team pages (Recent Results), Round pages (Match Summaries) |

---

## 7. Team Lists

| Property | Value |
|----------|-------|
| **Origin** | NRL game data (`scripts/data/fetchers/fetch_teamlists.py`) |
| **Cadence** | Weekly, pre-round (typically Tuesday) |
| **Raw format** | Per-match squad: jerseys 1–13 starters, 14–17 interchange, 18–22 reserves |
| **Cleaning** | Player name resolution against `data/players.yaml` |
| **Storage** | `data/teamlists/round_NN.yaml` |
| **Wiki impact** | Player pages (Selection Status), Team pages (Current Lineup), Round pages (Team Lists) |

---

## 8. SuperCoach Player Registry

| Property | Value |
|----------|-------|
| **Origin** | supercoach.com.au (scraped via Playwright) |
| **Cadence** | On-demand (`/scrape-supercoach`), typically pre-season and after trade periods |
| **Raw format** | Player names, teams, SuperCoach positions, IDs |
| **Cleaning** | None — authoritative source |
| **Storage** | `data/players.yaml` → `entities` table |
| **Wiki impact** | Player pages (metadata: position, team), Team pages (squad list) |

---

## Access Categories

| Category | Deep-link? | Content hosted? | Examples |
|----------|-----------|----------------|----------|
| Public | Yes | No — link to original | YouTube, public articles |
| Paywalled | No | No | Subscription articles |
| Private | No | No | Radio recordings, private recordings |

Cleaning and storage treat all three identically — the difference is surfacing.

---
tags: [area/pages, subarea/wiki]
---

# Wiki Data Feeds

> Status: **Reference doc** (created 2026-05-12).
>
> Single-page view of every upstream data input the wiki depends on, the pipeline that owns each input, current population state, and which wiki sections each input unblocks. Doubles as a **charter document for Scout** — Scout's eventual scope is *all* data acquisition, not just media inventory. This doc maps that expanded territory.

---

## Why this exists

Two questions kept coming up that no single doc could answer:

1. *"What has to be populated for a wiki page to be more than a stub?"*
2. *"Which acquisition pipeline produces each input the wiki needs?"*

Pieces of the answer were scattered across [`content-pipeline.md`](content-pipeline.md), [`scout.md`](../../agents/crew/scout.md), [`scraper.md`](../../agents/system/scraper.md), [`sources/README.md`](../../sources/README.md), and [`04-information-architecture.md`](../../architecture/04-information-architecture.md). This doc consolidates that view in one place and uses it to define **Scout's expanded charter** — the user-stated intent that Scout should eventually own all data gathering, not just transcripts and media.

This is the doc to read when:
- Asking "why is Wests Tigers still a stub?"
- Asking "what would the Archivist actually have to write from?"
- Planning Scout work, including pipelines outside the current media-only scope.
- Onboarding to the data layer.

---

## The four input layers

Every wiki page is composed from inputs in these four layers. Each layer feeds specific page sections; missing layers → missing sections.

```
┌─────────────────────────────────────────────────────────────────────┐
│ LAYER 1: IDENTITY            people, people_attributes,             │
│                              people_roles, teams, venues, channels  │
│   → ## Overview              (name, position, team, height, role)   │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 2: PERFORMANCE         player_rounds, matches,                │
│                              match_team_lists, injuries, rounds     │
│   → ## Current Form          (recent scores, minutes, form trend)   │
│   → ## Price Analysis        (price, breakeven, ownership)          │
│   → ## Selection History     (jersey, starts vs bench)              │
│   → ## Recent Results        (team-page match outcomes)             │
│   → ## Key Players           (team-page top SC scorers)             │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 3: SOURCE MATERIAL     sources, source_documents,             │
│                              source_chunks, source_speakers         │
│   (no direct page section — feeds Layer 4)                          │
│   Also feeds: ## Recent Sources (channel pages)                     │
├─────────────────────────────────────────────────────────────────────┤
│ LAYER 4: ATTRIBUTED CLAIMS   quotes (with speaker_person_id),       │
│                              claims (with claim_associations)       │
│   → ## Expert Opinions       (who said what, when, polarity)        │
│   → ## Recent Calls          (advisor pages roll these up)          │
│   → ## Key Talking Points    (round pages)                          │
└─────────────────────────────────────────────────────────────────────┘
```

Layers 1-2 are **structural** — they describe what *is*. Layers 3-4 are **commentary** — they describe what's been *said*. The wiki's distinctive value lies in Layer 4 (attributed opinion); Layer 2 is what makes it useful day-to-day.

---

## Per-page data dependencies

For each page type, the table below shows which sections depend on which input layers, and the **minimum data** required for the section to be more than a placeholder.

### Player pages (`/wiki/player/[slug]`)

| Section | Inputs | Minimum to render meaningfully |
|---------|--------|-------------------------------|
| `## Overview` | L1: `people`, `people_attributes`, `people_roles` | 1 row in each (have today) |
| `## Current Form` | L2: `player_rounds` | ≥3 recent rounds with scores |
| `## Price Analysis` | L2: `player_rounds` (price, breakeven over time) | ≥3 rounds for a trend |
| `## Selection History` | L2: `match_team_lists` | ≥3 match lineups |
| `## Injuries` | L2: `injuries` | At least one injury row (or be empty by design) |
| `## Expert Opinions` | L4: `claims`, `quotes` joined to person via `claim_associations` | ≥3 attributed claims |

**Today's reality for Apisai Koroisau:** L1 ✅ (1 row each), L2 ❌ (`player_rounds`/`injuries`/`match_team_lists` all empty), L3-L4 ❌ (no source material mentions him, no claims). The page can only render `## Overview` from a thin scaffold; everything else is a placeholder.

### Team pages (`/wiki/team/[slug]`)

| Section | Inputs | Minimum to render meaningfully |
|---------|--------|-------------------------------|
| `## Overview` | L1: `teams` | 1 row (have today) |
| `## Current Squad` | L2: `match_team_lists` (latest round per team) | A current round's lineup |
| `## Recent Results` | L2: `matches` (team's recent match rows) | ≥3 recent matches |
| `## Key Players` | L2: `player_rounds` aggregated by team | A current round of stats |

### Channel pages (`/wiki/channel/[slug]`)

| Section | Inputs | Minimum to render meaningfully |
|---------|--------|-------------------------------|
| `## About` | L1: `channels.description` | Channel row (have today) |
| `## Recent Sources` | L3: `sources` filtered by `channel_id` | ≥1 source ingested for this channel |
| `## Coverage` | L1: `channels.tags` | Tags populated (have today for most) |
| `## Hosts` | L1: `people_roles` filtered to `advisor`, joined via `channel_hosts` | Speaker diarisation + person resolution (deferred) |

### Round pages (`/wiki/round/[season]/[round]`)

| Section | Inputs | Minimum to render meaningfully |
|---------|--------|-------------------------------|
| `## Overview` | L2: `rounds`, `matches` | Round row + scheduled fixtures |
| `## Team Lists` | L2: `match_team_lists` | Lineups for each match in the round |
| `## Key Talking Points` | L4: `claims` filtered by round | ≥5 attributed claims for the round |
| `## Results` | L2: `matches` (post-game), `player_rounds` | Match results + player rounds |

### Advisor pages (`/wiki/advisor/[slug]`) — deferred

Advisor pages are blocked on **speaker diarisation + person attribution** (Layer 3.5). Until `quotes.speaker_person_id` reliably resolves to advisor entities, `## Recent Calls` cannot be written.

---

## Per-table feed pipelines

This is the inventory: every input table the wiki depends on, what populates it, current state, where the code lives, and the proposed Scout-scope future.

| Layer | Table | Populated by | Current state | Code | Proposed Scout scope |
|---|---|---|---|---|---|
| **L1** | `people` | SuperCoach roster fetch | ✅ 557 rows | `scripts/data/fetchers/fetch_supercoach_players.py` | **Yes** — roster acquisition |
| **L1** | `people_attributes` | SuperCoach roster fetch | ✅ 550 rows | Same as above | **Yes** — roster attributes |
| **L1** | `people_roles` | SuperCoach roster fetch + manual | ✅ 550 rows | Same as above | **Yes** — role assignment derives from roster |
| **L1** | `teams` | Seed scripts | ✅ 58 rows | `scripts/data/seed_teams.py` | **Yes** — seed → ongoing refresh |
| **L1** | `venues` | Seed scripts | ✅ 27 rows | `scripts/data/seed_venues.py` | **Yes** — seed → ongoing |
| **L1** | `channels` | Scout discovery + recon approval | ✅ 14 rows | `services/api/app/scout/`, `routers/recon.py` | **Yes** — already in scope |
| **L2** | `player_rounds` | SuperCoach scraper (per-round stats) | ❌ 0 rows | `scripts/data/fetchers/fetch_player_stats.py`, `services/worker-scraper/` | **Yes** (currently Bookkeeper/scraper) |
| **L2** | `matches` | NRL.com fetcher | ❌ 0 rows | `scripts/data/fetchers/fetch_match_stats.py` | **Yes** (currently scraper) |
| **L2** | `match_team_lists` | NRL.com team list fetcher | ❌ 0 rows | `scripts/data/fetchers/fetch_teamlists.py`, `services/worker-scraper/app/activities/teamlists.py` | **Yes** (currently scraper) |
| **L2** | `injuries` | NRL.com casualty ward fetcher | ❌ 0 rows | *Code does not exist yet* | **Yes** (new pipeline to build) |
| **L2** | `rounds` | NRL.com draw fetcher | ❌ 0 rows | *Code does not exist yet* | **Yes** (new pipeline to build) |
| **L3** | `sources` | Scout discovery | ✅ 2,235 rows | `services/api/app/scout/loop.py`, `refresh.py` | **Yes** — already in scope |
| **L3** | `source_documents` | Scout audio acquisition + Analyst transcription | ⚠️ 88 rows; only 4 have chunk text | `services/api/app/scout/audio.py`, `services/api/app/analyst/transcribe.py` | Acquisition: yes (Scout). Transcription: no (Analyst). |
| **L3** | `source_chunks` | Analyst transcription | ⚠️ 2,470 rows; **0 cleaned** | `services/api/app/analyst/transcribe.py` + cleaning skill | Analyst |
| **L3** | `source_speakers` | Analyst diarisation | ✅ 4,401 rows; person attribution unknown | `services/api/app/analyst/transcribe.py` (pyannote) | Analyst |
| **L4** | `quotes` | Analyst extraction | ❌ 0 rows | `clean-transcript` + `process-transcript` skills | Analyst |
| **L4** | `claims` | Analyst extraction | ❌ 0 rows | `process-transcript` + `verify-claims` + `upload-transcript` skills | Analyst |
| **L4** | `claim_associations` | Analyst extraction (sets person/team subjects) | ❌ 0 rows | `upload-transcript` skill | Analyst |

**Quick read of where things stand:**
- L1 is fully populated.
- L2 is **completely empty** despite fetcher code existing for 3 of 5 tables. The blocker is orchestration (the fetchers aren't run), not engineering.
- L3 has source rows but transcription has only run on 4 of 88 documents, and **the cleaning pass has not run on any chunk**.
- L4 has never run.

---

## Scout's expanded charter

### What Scout owns today

Per [`docs/agents/crew/scout.md`](../../agents/crew/scout.md): **media inventory only** — Extract for podcasts/video. Numeric NRL data and player rosters are explicitly *out* of Scout's current scope; they're owned by the [scraper](../../agents/system/scraper.md) (Bookkeeper) and `player-roster` systems.

### What Scout should own (proposed)

**All external data acquisition.** Acquisition is one job: find an external source of truth, fetch it, persist it raw, do not interpret. The Analyst owns interpretation downstream. Splitting acquisition into "Scout for media" + "scraper for SuperCoach" + "player-roster for identity" creates artificial seams that make it impossible to ask "which feeds are healthy?" in one place.

The proposal:

| Acquisition pipeline | Source of truth | Current home | Proposed home |
|---|---|---|---|
| YouTube video discovery + audio | YouTube Data API + yt-dlp | `services/api/app/scout/` | **Scout** (no change) |
| Podcast / RSS / blog / Twitter (future) | RSS feeds, web | Backlog | **Scout** (no change) |
| SuperCoach player roster | SuperCoach API | `scripts/data/fetchers/fetch_supercoach_players.py` (cron-runnable via `scrape-supercoach` skill) | **Scout** (move) |
| SuperCoach per-round stats | SuperCoach API | `scripts/data/fetchers/fetch_player_stats.py`, `services/worker-scraper/` | **Scout** (move) |
| NRL.com fixtures + matches | nrl.com `/draw/data`, match-centre `/data` | `scripts/data/fetchers/fetch_match_stats.py` | **Scout** (move) |
| NRL.com team lists | nrl.com `/teamlists/data` | `scripts/data/fetchers/fetch_teamlists.py`, `services/worker-scraper/app/activities/teamlists.py` | **Scout** (move) |
| NRL.com casualty ward (injuries) | nrl.com `/casualty-ward/data` | *Not built* | **Scout** (new) |
| NRL.com round metadata | nrl.com `/draw/data` | *Not built* | **Scout** (new) |

### What Scout still does NOT do (after the expansion)

The Extract-only rule still applies — Scout fetches raw, Analyst transforms:

- **Cleaning, parsing, diarisation, embedding** — Analyst.
- **Speaker → Person attribution** — Analyst.
- **Claim / quote extraction** — Analyst.
- **Cross-source consensus / contradiction detection** — Analyst.
- **Deriving `agrees_with` / `contradicts` edges from claims** — Analyst (per [entity-connections draft](../../architecture/drafts/wiki-entity-connections.draft.md)).

### Implications of the expansion

- [`scout.md`](../../agents/crew/scout.md) needs a scope rewrite: §"What Scout DOES NOT cover" currently lists "Numeric NRL data" and "Player roster registry" as out-of-scope; both move into scope.
- [`scraper.md`](../../agents/system/scraper.md) becomes a *system component* under Scout (the `services/worker-scraper/` Temporal worker) rather than a Bookkeeper-owned subsystem. Bookkeeper consumes the data; Scout produces it.
- The [Bookkeeper crew doc](../../agents/crew/bookkeeper.md) needs a corresponding scope clarification — it becomes a *consumer* and *math-runner*, not a fetcher.
- The fetcher scripts under `scripts/data/fetchers/` should migrate into `services/api/app/scout/` (or a new `services/api/app/scout/data/` subdirectory) to live alongside the existing media-inventory code.
- Audit pattern (`agent_runs` with `agent_id='scout'`) extends to all acquisition pipelines, giving us one dashboard for "is data acquisition healthy?"

This scope expansion is formalised in [`scout-charter-expansion.draft.md`](../../architecture/drafts/scout-charter-expansion.draft.md), with decisions D1–D7 locked 2026-05-12. Phase 0 (the doc reconciliation across `scout.md`, `scraper.md`, `bookkeeper.md`, `crew/README.md`, `dynamics.md`) lands alongside this update; the migration phases follow.

---

## Minimum to publish

For a page to leave `status='stub'` and become a meaningfully readable `status='draft'`, the inputs below must be populated. These are also the thresholds an automated `stub → draft` promotion would gate on.

| Page type | Minimum L1 | Minimum L2 | Minimum L4 | Notes |
|---|---|---|---|---|
| Player | identity row + role row | ≥3 recent `player_rounds` | ≥3 attributed claims | L4 optional for `draft` if L2 is rich; required for `published` |
| Team | identity row | ≥3 recent matches + current squad lineup | n/a (team-level claims are sparse) | |
| Round | round row | full match list + team lists for the round | n/a | |
| Channel | channel row | n/a | ≥1 source ingested via channel | |
| Advisor | identity row + advisor role | n/a | ≥5 attributed claims with diarised speaker | Deferred until diarisation lands |

**Applied to the current state:** every player page can *theoretically* leave stub today (L1 is populated), but the resulting `draft` would be ~50 words of identity prose with no form, no opinions, no selection history. That's not actually useful, which is why the thresholds in the table reference L2/L4 minimums — anything less and the page is a stub with extra steps.

---

## Critical path

The unblock order, ranked by leverage (most pages affected per unit of work):

1. **L2 — SuperCoach scraper.** Run `fetch_supercoach_players.py` + `fetch_player_stats.py` on a regular cadence (the `scrape-supercoach` skill already does the player roster part). Unblocks `## Current Form` and `## Price Analysis` for every player page in one go. **Highest leverage.**
2. **L2 — NRL.com fetchers.** `fetch_match_stats.py` + `fetch_teamlists.py` need to be run; injury and round fetchers need to be built. Unblocks every team page's `## Recent Results` / `## Key Players` and every round page's `## Team Lists` / `## Results`.
3. **L3 cleanup — get the existing 88 transcripts cleaned.** None of the 2,470 chunks have `clean_text`. The cleaning pass is one skill (`clean-transcript`) per document. Unblocks Layer 4 for whichever players the existing transcripts discuss.
4. **L4 — claim extraction over the cleaned chunks.** `process-transcript` → `verify-claims` → `upload-transcript`. Unblocks `## Expert Opinions` for the players that come up in the corpus. *Note: Apisai Koroisau is not in the current corpus.*
5. **L3.5 — speaker diarisation + person attribution.** Required for `quotes.speaker_person_id` to resolve to actual advisor entities. Without this, claims are anonymous. Unblocks advisor pages entirely.
6. **L2 — wider transcript ingestion.** Of the 2,235 sources Scout has discovered, 88 have been transcribed. Working through the rest is the long-tail content unlock.

**Concretely for the user's "populate Api Koroisau" question:** none of the above unblocks it directly, because Api isn't mentioned in the current source corpus. To make Api's page non-trivial, the path is: (a) get L2 running so his stats appear, and (b) ingest fresh Tigers-focused content via Scout that actually mentions him.

---

## Open questions

These need answers before Scout's charter expansion ships, and most influence the Archivist build downstream.

1. **Where exactly does the scraper code live after the move?** `services/api/app/scout/data/` is the cleanest home structurally, but `services/worker-scraper/` already exists as its own service. Probably keep `worker-scraper` as the *runner* (cron / scheduler) and import shared logic from `scout/data/`.
2. **Cron orchestration — who runs the L2 fetchers, and how often?** Today they're skill-runnable but not on a schedule. Options: (a) APScheduler in the API process, (b) the `scheduler` skill, (c) external cron on the prod box, (d) the `worker-scraper` service runs a schedule loop. Pick one and standardise.
3. **Should fetchers populate via the same `agent_runs` audit pattern as Scout's media-discovery loops?** Yes if Scout's expanded charter is real — gives one dashboard. Means the deterministic fetcher runs need a `record_agent_started/ended` wrapper.
4. **Does Bookkeeper become consume-only after this move?** Yes — Bookkeeper becomes a math/derivation layer over the data Scout fetches. Bookkeeper docs need updating.
5. **NRL.com endpoint stability.** The casualty ward and round-metadata endpoints (per memory note) are public JSON but undocumented. Building the injury and round fetchers means committing to maintaining them when NRL.com changes shape.
6. **Source-of-truth for `people_roles`.** Today it's seeded from SuperCoach. Once advisor diarisation lands, role assignments for advisors come from Analyst's attribution — that's an Analyst write, not a Scout write. The doc needs a clarifying note when that lands.

---

## Documentation Updates

If the Scout-charter expansion is approved, the following docs need updating as part of the implementing changeset:

| Doc | Change |
|-----|--------|
| [`docs/agents/crew/scout.md`](../../agents/crew/scout.md) | §"What Scout DOES cover" gains all L2 acquisition pipelines. §"What Scout DOES NOT cover" loses "Numeric NRL data" and "Player roster registry". §"Pipeline position" diagram updated. |
| [`docs/agents/system/scraper.md`](../../agents/system/scraper.md) | Reframed as a Scout component (the `worker-scraper` service), not a Bookkeeper subsystem. Cross-link to Scout. |
| [`docs/agents/crew/bookkeeper.md`](../../agents/crew/bookkeeper.md) | Scope clarification: Bookkeeper is consume-only over the data Scout fetches. |
| [`docs/agents/crew/README.md`](../../agents/crew/README.md) | Update the Bookkeeper one-liner to reflect consume-only scope. |
| [`docs/agents/crew/dynamics.md`](../../agents/crew/dynamics.md) | Cadence table — Bookkeeper trigger becomes "Scout scrape complete" instead of "scraper sweep complete". |
| [`docs/architecture/drafts/scout-charter-expansion.draft.md`](../../architecture/drafts/scout-charter-expansion.draft.md) | ✅ Created 2026-05-12; decisions locked. Phase 0 reconciliation lands alongside this row. |
| Eventually: `docs/agents/crew/archivist.md` "Hand-off contract" reads | The `claims`/`player_rounds`/`teamlists` rows the Archivist consumes will all be Scout-produced under the new model. Footnote the source. |

---

## Related

- [Wiki overview](overview.md) — page types and routes
- [Wiki content pipeline](content-pipeline.md) — Archivist runtime that consumes these feeds
- [Archivist (role spec)](../../agents/crew/archivist.md) — primary downstream consumer
- [Scout (current scope)](../../agents/crew/scout.md) — to be reframed per the charter expansion above
- [Scraper system](../../agents/system/scraper.md) — currently Bookkeeper-owned; moves under Scout
- [Source pipeline](../../sources/README.md) — Scout → Analyst → wiki end-to-end stages
- [NRL.com endpoints (memory)](../../../README.md) — `/draw/data`, match-centre `/data`, `/casualty-ward/data` (referenced in `MEMORY.md`)

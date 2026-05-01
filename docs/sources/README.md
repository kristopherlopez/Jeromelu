---
tags: [area/sources]
---

# Sources

The source system is a first-class concern. Every claim Jaromelu makes traces back to a source; every wiki page and every Ask Me answer surfaces source attribution. This folder owns the concept end-to-end — from original → cleaned → to the point where structured outputs leave for downstream pipelines.

---

## Pipeline

```
 Original             Cleaned              Structured              Consumed
 ────────             ───────              ──────────              ────────

 YouTube video   →    clean transcript  →  claims + entities   →   Wiki references
 Article URL     →    clean markdown    →  KB entries          →   Ask Me answers
 Podcast audio   →    diarised text     →  player summaries    →   Feed events
 Radio recording →    transcript        →  opinion digests     →   Analysis articles
```

| Stage | Owner | Status |
|-------|-------|--------|
| **Ingestion** (fetch the original) | [`agents/system/ingestion.md`](../agents/system/ingestion.md) | Live |
| **Cleaning** (fix garbles, preserve claims) | [cleaning.md](cleaning.md) | Skill-driven, iterating |
| **Extraction** (claims, entities, knowledge) | [`agents/system/extraction.md`](../agents/system/extraction.md) | Local experimentation |
| **Consumption** (wiki, Ask Me, Feed, Analysis) | [`pages/`](../pages/) | Live |

This folder focuses on **ingestion through cleaning** plus the **attribution surface**. The extraction stage and downstream consumers are owned elsewhere but referenced throughout.

---

## Attribution Philosophy

Every public surface that uses source-derived content must surface attribution. The form varies by surface.

| Surface | Attribution style |
|---------|-------------------|
| [Wiki page § Expert Opinions](../pages/wiki/overview.md) | Per-claim pill: `[SC Playbook · Round 7 · 14:32]` → deep-link where public |
| [Feed Remark](../concepts/02-remarks.md) | Evidence trail (expandable): list of source chunks per claim |
| [Ask Me answer](../pages/ask-me/overview.md) | Inline citations with source name; deep-link footer |
| [Analysis article](../pages/analysis/overview.md) | Sources section at article end; per-claim inline refs |

### Originals vs cleaned

Readers see **originals** (link to YouTube, article URL, podcast episode). The LLM sees **cleaned** text. This separation is intentional:

- **Originals** establish trust and let readers verify. Deep-link where timestamp + public.
- **Cleaned** text is what context feeds to models — auto-caption garbles fixed, claims preserved, timestamps intact.

### Paywalled / private sources

Some sources can't be deep-linked (paywalled articles, radio, private recordings). Attribution still surfaces — **citation without link**:

> "Triple M · Round 7 (radio)"

The claim is attributed, but the user can't click through. This is honest attribution, not hidden sourcing.

---

## Why This Folder Exists

Three problems this system needs to solve:

1. **Cleaning is non-trivial.** Auto-captions garble NRL player names, teams, and slang. Getting cleaning wrong poisons every downstream stage. [cleaning.md](cleaning.md) is the workbench.
2. **Corrections compound.** What we learn cleaning one transcript helps every future one. [patterns.md](patterns.md) accumulates the catalogue.
3. **Attribution has to be right.** A claim attributed to the wrong source is worse than no citation — it destroys trust. Attribution rules live here, not scattered across page specs.

---

## Docs in this folder

| Doc | Covers |
|-----|--------|
| [types.md](types.md) | Source types (YouTube, article, podcast, radio, stats), fields per type, access categories |
| [cleaning.md](cleaning.md) | The cleaning workbench: current pipeline, quality evaluation, iteration loop |
| [patterns.md](patterns.md) | The correction catalogue — player-name garbles, protected slang, etc. |

---

## Roster ingestion (non-claim source)

Not every source produces claims. The **player roster** ingestion pipeline
populates `entities` + `player_attributes` (the SCD-2 of slow-changing
player facts) directly from the SuperCoach `players-cf` API, and is
refreshed weekly during season to pick up team / position changes. It
runs alongside the claim pipeline above but doesn't go through cleaning
or extraction — the JSON is structured already.

See [`agents/system/player-roster.md`](../agents/system/player-roster.md)
for the regime split (lifetime constants → `entities.metadata_json`,
slow-changing → `player_attributes`, per-round → `player_rounds`), the
SCD-2 transition pattern, and the v2 expansion to NRL.com / NSWRL / QRL
as additional sources.

---

## Related

- [Wiki content pipeline](../pages/wiki/content-pipeline.md) — how wiki pages consume sources (downstream of this folder)
- [`data/sources.yaml`](../../data/sources.yaml) — whitelisted YouTube channels (operational registry)
- [`data/players.yaml`](../../data/players.yaml) — player registry used for name resolution during cleaning
- Memory: `reference_transcript_corrections.md`, `reference_nrl_slang.md` (cross-conversation recall of cleaning patterns)

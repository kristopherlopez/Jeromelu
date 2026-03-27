# Analyse Transcript — Hierarchical Multi-Agent Pipeline

The analyse-transcript pipeline replaces the flat clean+process approach with progressive context building. Instead of one context window holding the entire transcript, it detects semantic chapters and spawns specialist agents per chapter — each with a fresh context and scoped enrichment data.

```
Raw Transcript (3000+ segments)
    |
    v
Phase 1: Deterministic Pre-Clean (scripts/clean_transcript.py)
    |  corrections.yaml exact-match + phonetic matching
    |  Output: clean transcript + cleaning report with keyword blocks
    v
Phase 2: Chapter Detection (Sonnet agent)
    |  Reads stitched text + keyword blocks as hints
    |  Produces chapter manifest with semantic boundaries
    v
Phase 3: Specialist Agents (parallel Opus agents, one per chapter)
    |  Each agent gets ONLY its chapter's segments + scoped enrichment
    |  game_review → both teams' player lists + fixture data
    |  position_analysis → all players at those positions
    |  strategy → full round fixtures + full player pool
    |  Output per agent: sub-topics + name corrections + claims
    v
Phase 4: Merge & Verify
    |  Merge all specialist outputs
    |  Deduplicate claims (same player + type + overlapping timestamps)
    |  Haiku verification agents (one per claim)
    v
Output: data/transcripts/analysed/
    ├── {filename}.clean.json     (clean transcript, same format as data/transcripts/clean/)
    ├── {filename}.topics.json    (chapters → sub-topics → segment index mapping)
    ├── {filename}.claims.json    (verified claims with chapter/sub-topic traceability)
    ├── {filename}.json           (full enriched transcript + embedded chapter structure)
    └── {filename}.manifest.json  (debug stats per phase)
```

---

## Why This Architecture

### Problem: Flat Context

The previous pipeline processes transcripts in two disconnected passes:
1. **Clean** — deterministic + phonetic name correction without semantic understanding
2. **Process** — single LLM pass over 30KB+ stitched text for claim extraction

This means:
- The cleaner doesn't know what's being *said* (can't use discussion context to resolve names)
- The extractor holds the entire transcript in one context window (quality degrades for long podcasts)
- Topic segmentation is keyword-based, producing duplicate blocks and undifferentiated "General discussion" catch-alls

### Solution: Progressive Context

The hierarchical approach solves each limitation:

| Problem | Solution |
|---------|----------|
| Weak topic boundaries | LLM refines keyword blocks into semantic chapters |
| No enrichment data | Each specialist gets scoped player pools + fixture data |
| Single overloaded context | Each specialist gets 2-5KB of text (not 30KB+) |
| Cleaning disconnected from extraction | Specialists do both name correction AND claim extraction with full domain context |

---

## Chapter Types

| Type | Description | Enrichment Data |
|------|-------------|-----------------|
| `game_review` | Discussion of a specific match between 2 teams | Both teams' players + fixture details |
| `position_analysis` | Breakdown by position group (CTW, forwards, halves) | All players at those positions across all teams |
| `strategy` | Trade advice, captaincy, ownership, budget management | Full round fixtures + full player pool |
| `qa_segment` | Answering viewer/chat questions | Full player pool + fixtures |
| `intro_outro` | Opening/closing banter | Minimal (name resolution only) |
| `tangent` | Off-topic discussion | Minimal (name resolution only) |

---

## Sub-Topic Granularity

Within each chapter, specialist agents decompose the discussion into sub-topics. Each sub-topic represents a discrete discussion about 1-3 players with:
- Clear timestamp boundaries (start_ts, end_ts)
- Player and team identification
- A summary of the speaker's opinion
- Traceability to extracted claims

This granularity enables:
- Precise claim-to-source mapping
- Better timestamp accuracy on claims
- Structured navigation of long podcasts (chapter → sub-topic → claim)

---

## Model Selection

| Phase | Model | Reasoning |
|-------|-------|-----------|
| Phase 1 | Python (no LLM) | Deterministic corrections — free, reliable, cleans ~90% of name errors |
| Phase 2 | Sonnet | Structured classification task with keyword hints — good cost/quality balance |
| Phase 3 | Opus | Deep extraction + name resolution + sub-topic decomposition — benefits from highest reasoning quality |
| Phase 4 | Haiku | Bounded single-claim verification — cost-efficient for embarrassingly parallel tasks |

---

## Comparison with Flat Pipeline

To compare results, run both pipelines on the same transcript:

```
/analyse-transcript data/transcripts/raw/<filename>.json
/process-transcript data/transcripts/clean/<filename>.json
```

Then compare:
- `data/transcripts/analysed/<filename>.claims.json` (hierarchical)
- `data/transcripts/processed/<filename>.json` (flat)

Key metrics to compare:
- Total claim count (hierarchical should find more due to sub-topic granularity)
- Verification pass rate (hierarchical should be higher due to better context)
- Name correction count (hierarchical specialists may catch errors the deterministic pipeline missed)
- Timestamp accuracy (sub-topic boundaries should produce tighter timestamp ranges)

---

## Invocation

```
/analyse-transcript <path>
```

Accepts raw or clean transcript paths. Supports batch processing (multiple paths space-separated).

Output files are written to `data/transcripts/analysed/` — separate from the existing pipeline's `data/transcripts/processed/` and `data/transcripts/clean/` directories.

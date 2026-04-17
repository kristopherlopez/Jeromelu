# Transcript Analysis Pipeline

Full workflow doc: [`analyse-transcript.md`](analyse-transcript.md).

A hierarchical multi-agent pipeline for extracting NRL SuperCoach claims from YouTube podcast transcripts. Uses progressive context building — each phase feeds the next.

## Phases

| Phase | Agent | Model | Parallelism | Purpose |
|---|---|---|---|---|
| 1 | Pre-clean | Python (no LLM) | Single pass | Fix auto-caption garbles: mangled names, teams, NRL terms |
| 2 | Chapter Detection | Claude Sonnet | Single agent | Detect semantic chapter boundaries, types, team associations, sub-topic hints |
| 3 | Specialist Agents | Claude Opus | 1 per chapter (parallel) | Deep claim extraction with scoped enrichment data per chapter type |
| 4 | Verification Agents | Claude Haiku | 1 per claim (parallel) | Cross-check each claim against transcript (PASS / FLAG / FAIL) |

## Chapter Types and Specialist Scoping

| Chapter Type | Enrichment Data Provided |
|---|---|
| `game_review` | Both teams' player lists + fixture data |
| `position_analysis` | All players at target positions |
| `strategy` | Full player pool + all fixtures |
| `qa_segment` | Full player pool + fixtures |
| `intro_outro` | Player name registry only |
| `tangent` | Player name registry only |

## Verification

Verification checks: `claim_type`, `claim_text`, `strength`, `polarity`, `start_ts`, `end_ts`.

## Related Skills

- `/clean-transcript` — Phase 1 standalone
- `/process-transcript` — flat single-pass extraction alternative
- `/verify-claims` — Phase 4 standalone
- `/fetch-transcripts` — download raw transcripts from S3
- `/upload-transcript` — persist claims to DB

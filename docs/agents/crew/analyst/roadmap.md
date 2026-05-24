---
tags: [area/agents, subarea/crew]
---

# Analyst — Status & Roadmap

> Last reviewed: 2026-05-24.

The forward plan for Analyst runs on **two tracks at once**:

1. **Lineup externalisation** — moving transcript materialisation + speaker identification out of this repo into a service ([charter A2](charter.md#a2-lineup-is-a-service-boundary-not-a-sub-module)). The in-repo code is held as legacy until the external API lands.
2. **The interpretive-pass buildout** — promoting cleaning, chapter detection, annotation, embedding, extraction, and consensus from Claude Code skill experiments to production passes ([charter A4](charter.md#a4-cleaning--skill-validated-then-workerised)–[A6](charter.md#a6-consensus--contradiction-detection-is-semantic-not-numeric)).

Status labels:
- **Shipped** — live in production or dev
- **Skill-driven** — validated and usable today via a Claude Code skill; production worker not built
- **In design** — specced; implementation not started
- **Planned** — committed scope; no design yet
- **Backlog** — deferred or candidate; no commitment

---

## Pass status at a glance

| Pass | Surface today | Status | Charter |
|---|---|---|---|
| Transcript materialisation (Lineup) | `transcribe.py` + GPU stack, in-repo | **Shipped but legacy** | [A2](charter.md#a2-lineup-is-a-service-boundary-not-a-sub-module) · [A8](charter.md#a8-disposition-of-the-in-repo-lineup-code--legacy-not-deleted) |
| Speaker identification (Lineup) | voice + face + fusion, in-repo | **Shipped but legacy** | [A2](charter.md#a2-lineup-is-a-service-boundary-not-a-sub-module) · [A8](charter.md#a8-disposition-of-the-in-repo-lineup-code--legacy-not-deleted) |
| Cleaning | `/clean-transcript`; `update-clean-text` backfill endpoint | Skill-driven | [A4](charter.md#a4-cleaning--skill-validated-then-workerised) |
| Chapter detection | `/analyse-transcript` | Skill-driven | — |
| Annotation | — | Not built | — |
| Embedding | — | Not built | [Open Q2](charter.md#open-questions) |
| Entity / quote / claim extraction | `/process-transcript` → `/verify-claims` → `/upload-transcript` | Skill-driven | [A5](charter.md#a5-extraction--skill-validated-then-workerised-llm-graded) |
| Cross-reference / consensus | — | Not built | [A6](charter.md#a6-consensus--contradiction-detection-is-semantic-not-numeric) |

---

## Track 1 — Lineup externalisation

The carve-out of transcript materialisation + speaker ID into an external service. **Directional decision, not a completed migration** ([charter A2](charter.md#a2-lineup-is-a-service-boundary-not-a-sub-module)); the in-repo path remains the only transcript producer until the API exists.

### L0 — Decision + contract pinned ✅

- Decision locked 2026-05-23. LEGACY notices on [transcription-pipeline.md](../../system/transcription-pipeline.md), [speaker-identification.md](../../system/speaker-identification.md), and the `app.analyst` package docstring.
- The transcript contract Analyst designs against is pinned ([charter A3](charter.md#a3-the-input-contract--a-speaker-attributed-transcript)); `source_speakers.cluster_label` stays in schema as the column the external API writes into.

### L1 — Hold the in-repo path as legacy ✅ *(ongoing)*

- Per [charter A8](charter.md#a8-disposition-of-the-in-repo-lineup-code--legacy-not-deleted): **fixes only, no new features** in `diarize.py`, `identify_voice.py`, `visual_id.py`, `fusion.py`, `remote.py`, the voice/face cluster modules, `identity_alignment.py`, `services/gpu/`, the `LINEUP_REMOTE` pathway, and the review-UI overlays.
- The live single-source CLI (`make transcribe`) keeps producing transcripts; this is load-bearing until L2.

### L2 — External Lineup API + producer swap — In design

- Analyst calls the Lineup API with an audio (+video) source and receives the [transcript contract](charter.md#a3-the-input-contract--a-speaker-attributed-transcript) back.
- Producer of `source_documents` / `source_speakers` / `source_chunks` / `speaker_person_id` becomes the service; Analyst becomes a pure reader of those rows.
- In-repo Lineup code can then be deleted (or archived) — the contract makes the swap transparent to every downstream pass.
- **Blocked on:** the external project existing. No date — see [charter Open Q1](charter.md#open-questions).

> **Lineup phase ledger** (the in-repo build that is now legacy) lives in [README § Lineup status](README.md#lineup-status): Phases 1–4b shipped, Phase 5.5 remote GPU shipped, cross-modal compounding (Phase 5) was the only pending item and is now out-of-scope under externalisation. The detailed per-phase plan is in [speaker-identification-plan.md](../../../todo/speaker-identification-plan.md).

---

## Track 2 — Interpretive-pass buildout

Promoting Analyst's durable scope from skill experiments to production. Every pass follows the [charter rollout shape](charter.md#rollout): skill-validate → lock an eval → shared module → workerise + audit → drain on a schedule. All passes are designed against the L0 contract, so they are indifferent to whether Track 1 has cut over.

### T1 — Cleaning worker — Planned

- Encode the [`/clean-transcript`](../../skills/transcript-pipeline.md) skill as a shared pure module + a worker pass.
- Lock a cleaning-fidelity eval (does it fix garbles without "correcting" legitimate NRL slang like *PVL*?).
- **Open loop:** the cleaning pass shares `data/players.yaml` with SuperCoach roster regeneration. Rehoming it (read the roster from the DB) unblocks retirement of the legacy `scrape-supercoach` skill — see [Scout Phase 1 plan](../scout/plans/phase-1-supercoach-roster.md). ([charter A4](charter.md#a4-cleaning--skill-validated-then-workerised))

### T2 — Extraction worker — Planned

- Encode the [`/process-transcript`](../../skills/transcript-pipeline.md) → [`/verify-claims`](../../system/extraction.md) → [`/upload-transcript`](../../skills/transcript-pipeline.md) chain into `services/worker-extraction/` (skeleton today).
- **Gated by a DeepEval suite** locking acceptable claim precision/recall on a graded corpus ([charter A5](charter.md#a5-extraction--skill-validated-then-workerised-llm-graded)). No worker ships ahead of its eval.
- Audited per [charter A7](charter.md#a7-audit--agent_idanalyst-pass-discriminator-in-detail_json) (`agent_id='analyst'`, `detail_json.pass='extract'`). See [extraction-worker](../../../todo/extraction-worker.md).

### T3 — Embedding pass — In design

- Text embeddings on `source_chunks.embedding` for retrieval/similarity (≠ Lineup's voice/face embeddings).
- Decide model (OpenAI vs Voyage) and index location (pgvector in-repo vs external) — [charter Open Q2](charter.md#open-questions).

### T4 — Annotation pass — Backlog

- Sentiment, sub-topic tags, entity mentions, themes → `source_annotations`. Layers on top of chapter detection.

### T5 — Consensus engine — In design

- The cross-source semantic consensus + contradiction pass → `consensus_snapshots` ([charter A6](charter.md#a6-consensus--contradiction-detection-is-semantic-not-numeric)).
- Carries `match_confidence` through from attribution so low-confidence "who said what" is surfaced, not silently counted.
- This is the pass that produces the Analyst voice lines ("3 sources turned bearish since Tuesday"). See [consensus-engine](../../../todo/consensus-engine.md).

### T6 — Recurring drain jobs — Backlog

- Today every pass is operator-run per source. The target is a drain job per pass over the predecessor's completion state (e.g. clean over `transcription_status='transcribed' AND cleaned_text IS NULL`). Whether this lives in-repo or against the Lineup API depends on Track 1 ([charter Open Q1](charter.md#open-questions)).

---

## Backlog

Additive items that layer on the tracks above, pulled from the [transcription-pipeline backlog](../../system/transcription-pipeline.md#backlog) and the extraction/consensus surfaces:

| Item | Track | Notes |
|---|---|---|
| `agent_runs` rows for the transcription path | — | Not retrofitted — the path is legacy ([charter A8](charter.md#a8-disposition-of-the-in-repo-lineup-code--legacy-not-deleted)). New passes adopt audit from day one ([A7](charter.md#a7-audit--agent_idanalyst-pass-discriminator-in-detail_json)). |
| Player alias backfill (`people.aliases`) | T1/T2 | Empty today; populating improves keyterm coverage for nicknames and cleaning accuracy — the biggest single keyterm-pool win. |
| Topic-targeted keyterms | (Lineup) | Per-source keyterms from title/description/channel focus instead of the global roster pool. Lives with the transcription producer — moves out with Lineup. |
| Backfill legacy `source_chunks_v1` (221k auto-caption chunks) | T1/T2 | Re-clean + re-extract highest-leverage channels first. |
| "Analyst health" admin panel | T-all | Per-pass run counts, cost, latency from `agent_runs` filtered by `agent_id='analyst'`. Parallels the Scout dashboard. |
| Chapter detection as a first-class pass | T2 | Currently bundled into `/analyse-transcript`; may split out so annotation + extraction both depend on it ([charter Open Q3](charter.md#open-questions)). |

---

## Related

- [README.md](README.md) — Analyst's identity, scope, and voice
- [architecture.md](architecture.md) — pipeline position, hand-off contract, pass chain, current-vs-target
- [charter.md](charter.md) — locked design decisions A1–A8
- [Lineup status](README.md#lineup-status) — the in-repo (now legacy) speaker-ID phase ledger
- [Speaker identification plan](../../../todo/speaker-identification-plan.md) — full Lineup phase ledger and tuning notes
- [Extraction worker](../../../todo/extraction-worker.md) — claim-extraction worker tasks and local experimentation plan
- [Consensus engine](../../../todo/consensus-engine.md) — cross-source consensus design
- [Scout roadmap](../scout/roadmap.md) — the bronze-stage roadmap feeding Analyst's input

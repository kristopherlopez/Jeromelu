---
tags: [area/architecture, subarea/agents]
---

# Analyst Charter

> Last reviewed: 2026-05-24. **Decisions A1–A11 below; A2 (Lineup is a service boundary) locked 2026-05-23.**
>
> The decision record for Analyst's scope. Where the [Scout charter](../scout/charter.md) *expands* one agent to own all external acquisition, this charter does the opposite: it **draws a boundary that sheds work**. Analyst's largest current surface — *Lineup* (transcript materialisation + speaker identification: pyannote, Deepgram, voice/face/fusion, the GPU stack) — is being moved **out of this repo** into an external service. What remains, and what this charter formalises, is Analyst's durable identity: **the interpretive layer** — the agent that turns a speaker-attributed transcript into *meaning* (cleaning, embedding, entity/quote/claim extraction, cross-source consensus and contradiction detection).

---

## Why this charter exists

The Analyst README accreted around the surface that got built first and hardest — Lineup. As of 2026-05-23 that surface is leaving (see `memory/project_lineup_external.md` and the LEGACY notices on [transcription-pipeline.md](../../system/transcription-pipeline.md) and [speaker-identification.md](../../system/speaker-identification.md)). That decision inverts what Analyst *is*: not "the diarization-and-faces agent," but "the agent that makes meaning from a transcript."

This charter exists to record that inversion before it confuses anyone:

- It names the **medallion seam** Analyst sits on, and where Lineup now sits relative to it.
- It pins the **input contract** Analyst designs against — a speaker-attributed transcript — so the externalisation of Lineup is a swap of *producer*, not a rewrite of Analyst.
- It declares the in-repo Lineup code **legacy** (kept alive, not extended) and says what that means in practice.
- It stages the **forward build** — cleaning, embedding, extraction, consensus — the work that was always Analyst's but has so far lived only as local Claude Code skill prototypes, never production code ([A11](#a11-production-runs-in-workers-not-claude-code-skills)).

It does **not** change what Scout, Bookkeeper, Critic, or the Archivist do. It only redraws the line between Analyst and the structural transcript-materialisation that used to be lumped in with it.

---

## What Analyst owns

> Analyst owns the **interpretive transform** — every step that turns a transcript into structured, cross-referenced *knowledge*. In medallion terms, Analyst is the **silver** layer (and the producer of much of what feeds gold). The full principle is locked in [A1](#a1-the-boundary-principle--analyst-owns-the-interpretive-layer); what it means in practice:

| Pass | What it produces | Production status | Local prototype (not production — [A11](#a11-production-runs-in-workers-not-claude-code-skills)) |
|---|---|---|---|
| **Cleaning** | `source_documents.cleaned_text`, `source_chunks.clean_text` — garbles fixed, names/nicknames + SC jargon + numbers normalised, restarts merged, filler stripped ([A4](#a4-cleaning--skill-validated-then-workerised)) | Not built | [`/clean-transcript`](../../skills/transcript-pipeline.md); `update-clean-text` admin endpoint backfills from S3 |
| **Referential resolution** | coreference, claim-source attribution, entity disambiguation (brothers / positional / time-dependent) — resolves what the words *point to* before meaning is extracted ([A9](#a9-referential-resolution--attribution-is-claim-level-not-turn-level)) | Not built | implicit in the local `/process-transcript` prototype |
| **Chapter detection** | `source_chapters` — semantic chapters that scope claim extraction | Not built | [`/analyse-transcript`](../../skills/analyse-transcript.md) |
| **Annotation** | `source_annotations` — sentiment, sub-topic tags, entity mentions, themes | Not built | — |
| **Embedding** | `source_chunks.embedding` — text embeddings for retrieval (distinct from the voice/face embeddings Lineup writes) | Not built | — |
| **Entity / quote / claim extraction** | `quotes`, `claims`, `claim_chunks`, `claim_associations` — multi-pass LLM extraction with stance/strength shaping, dedup, falsifiability + resolution capture ([A10](#a10-claims-carry-falsifiability--resolution-criteria)), and automated verification | Not built | [`/process-transcript`](../../skills/transcript-pipeline.md), [`/verify-claims`](../../system/extraction.md), [`/upload-transcript`](../../skills/transcript-pipeline.md) |
| **Cross-reference / consensus** | `consensus_snapshots` — *semantic* consensus shifts and contradictions across sources ("4 say sell, 1 says hold") | Not built | [consensus-engine](../../../todo/consensus-engine.md) |

Every one of these reads a transcript and writes a *derivative of meaning*. None of them acquires raw bytes (Scout/bronze), and none of them does the structural audio→attributed-transcript transform (Lineup, externalising — see [A2](#a2-lineup-is-a-service-boundary-not-a-sub-module)). **No interpretive pass is in production yet** — the rightmost column lists *local prototypes* (Claude Code skills, plus one backfill endpoint) used to validate the approach. Production runs in workers, never skills ([A11](#a11-production-runs-in-workers-not-claude-code-skills)).

## What Analyst does NOT own

- **Raw acquisition** — discovery, enumeration, audio/video pull, structured-feed fetching. That's [Scout](../scout/README.md) (bronze). Analyst never reaches outside Jeromelu for source bytes.
- **Transcript materialisation + speaker identification (Lineup)** — pyannote diarization, Deepgram ASR, the merge, voice/face/fusion, enrollment, clustering, the review-UI overlays, the SageMaker GPU path. **Going forward this is an external service** ([A2](#a2-lineup-is-a-service-boundary-not-a-sub-module)); the in-repo code is legacy ([A8](#a8-disposition-of-the-in-repo-lineup-code--legacy-not-deleted)).
- **Numeric derivations** — alignment indices, advisor-accuracy scores, breakeven trajectories, consensus *math*. Those are derivations over fetched/extracted data — owned by [Bookkeeper](../bookkeeper/README.md). Analyst detects that two sources *disagree*; Bookkeeper computes *by how much, weighted by historical accuracy*.
- **The final call** — committing to a position and voicing it is [Jaromelu](../jaromelu/README.md)'s integrated voice. Analyst presents both sides; it does not resolve them.
- **Wiki composition** — turning structured knowledge into browsable encyclopedic prose is the [Archivist](../archivist/README.md).

For the exact tables Analyst reads and writes per pass, see [architecture.md § Hand-off contract](architecture.md#hand-off-contract).

---

## How it works

The pass chain (receive attributed transcript → clean → resolve references → chapter/annotate → embed → extract & shape claims/quotes → verify → cross-reference) and the current-vs-target architecture (in-repo legacy Lineup + Claude Code skills today; external Lineup API + workerised passes tomorrow) live in [architecture.md](architecture.md). In brief: each pass is an idempotent transform over the previous pass's output, validated first as a Claude Code skill and then workerised, with LLM passes gated by eval suites ([A5](#a5-extraction--skill-validated-then-workerised-llm-graded)) rather than the drift tests Scout's deterministic fetchers use.

---

## Phasing

The full forward plan lives in [roadmap.md](roadmap.md). Two tracks run in parallel: **(1) Lineup externalisation** — the carve-out of transcript materialisation + speaker ID into a service, with the in-repo code held as legacy until the API lands; and **(2) the interpretive-pass buildout** — promoting cleaning, embedding, extraction, and consensus from local skill prototypes to production worker passes ([A11](#a11-production-runs-in-workers-not-claude-code-skills)).

---

## Decisions register (A1–A11)

> The Analyst decision record. Prefixed **A** to disambiguate from Scout's **D**-series (a bare "per D8" always means Scout). Cited by number across the repo (`per A2`, `per A5`, …).

### A1. The boundary principle — Analyst owns the interpretive layer

**Decision: Analyst owns every transform that turns a transcript into *meaning*.** Cleaning, chapter detection, annotation, embedding, entity/quote/claim extraction, and cross-source consensus/contradiction detection are Analyst's. In medallion terms:

- **Bronze — [Scout](../scout/README.md).** Raw external data landed faithfully, plus the mechanical typed-projection of structured feeds. No interpretation.
- **Structural transform — Lineup (externalising).** Audio (+video) → a speaker-attributed transcript. Mechanical/ML, but it makes *structure*, not *meaning* — it says "Person X spoke these words from 45.2–51.8s," not "Person X is bullish on Cleary." Moving to a service ([A2](#a2-lineup-is-a-service-boundary-not-a-sub-module)).
- **Interpretive transform (silver) — Analyst.** Transcript → cleaned text, embeddings, entities, quotes, claims, consensus. This is where *meaning* is made.
- **Gold — [Bookkeeper](../bookkeeper/README.md) + [Archivist](../archivist/README.md).** Numeric derivations and the curated wiki.

The dividing question between Lineup and Analyst: **does the step decide *who said what* (structural) or *what it means* (interpretive)?** Structural is Lineup; interpretive is Analyst. This is why speaker identification — for all its ML — is *not* Analyst's durable scope: it answers "who," not "what it means."

### A2. Lineup is a service boundary, not a sub-module

**Decision (locked 2026-05-23): transcript materialisation + speaker identification move out of this repo into an external "Lineup" service.** End state: Analyst hands an audio (and optionally video) source to a Lineup API and receives a speaker-attributed transcript back. The merge, identification, and fusion stages stop being concerns of this repo.

**Why:** Treating Lineup as a service boundary lets the speaker-ID stack iterate independently — its own models, GPU infra, and fusion heuristics — without dragging Jaromelu's release cadence or container size along with it. It also aligns with the *API-container-lean* principle: heavy/GPU dependencies (pyannote, torch, InsightFace, SageMaker plumbing) should not live in the API image. See `memory/project_lineup_external.md`.

**Scope of the move** (stages 2–5 of the [transcription pipeline](../../system/transcription-pipeline.md)): pyannote diarization, Deepgram ASR, the merge, voice match, visual match, fusion, voice/face enrollment, per-source face clustering, identity alignment, the review-UI overlays, and the SageMaker `LINEUP_REMOTE` pathway (`services/gpu/`). **Stage 1 (audio acquisition) stays with Scout; everything downstream of the transcript (clean, extract, consensus, wiki, ledger) stays with Analyst and the other crew.**

This is a **directional decision, not yet a completed migration** — the external API does not exist yet. Until it does, the in-repo path still produces transcripts (see [A8](#a8-disposition-of-the-in-repo-lineup-code--legacy-not-deleted)).

### A3. The input contract — a speaker-attributed transcript

**Decision: Analyst designs against a transcript contract, not against diarization internals.** Whatever produces the transcript — the legacy in-repo path today, the external Lineup API tomorrow — hands Analyst the same shape:

| Table | What the contract guarantees |
|---|---|
| `source_documents` | `raw_text`, `language`, `checksum`, `chunk_count`, S3 pointer |
| `source_speakers` | one row per turn: `speaker_label`, `start_ts`, `end_ts`, and the attribution — `speaker_person_id` (+ `match_method`, `match_confidence`) where identified; `cluster_label` as the stable label layer |
| `source_chunks` | one row per utterance: `raw_text`, `chunk_index`, `start_ts`/`end_ts`, char offsets, `speaker_segment_id` (FK to the turn), `paragraph_break` |
| `sources` | `transcription_status='transcribed'` |

Because Analyst consumes the *contract* and not the producer, the Lineup externalisation ([A2](#a2-lineup-is-a-service-boundary-not-a-sub-module)) is a swap of who writes these rows — not a change to any Analyst pass. The `source_speakers.cluster_label` layer (reads use `coalesce(cluster_label, speaker_label)`) is the column the external API writes into; it **stays in Jaromelu's schema** as the contract surface even though the producing logic leaves.

### A4. Cleaning — skill-validated, then workerised

**Decision: cleaning ships as a production worker pass; the Claude Code skill is a local prototype only ([A11](#a11-production-runs-in-workers-not-claude-code-skills)).** Cleaning normalises the *surface* of the transcript — the ASR + NRL-domain mess — so every later pass reads clean text. It reads the canonical player registry and NRL domain knowledge, and writes `source_documents.cleaned_text` and `source_chunks.clean_text`. The skill is used locally to stabilise the prompt and generate eval fixtures — it never runs in production.

**What the cleaning pass must contend with** — each is a recurring normalisation rule, not a one-off fix:

- **Garbled player names** — auto-caption mangles Polynesian / Māori names especially (Tuipulotu, Fonua-Blake, Nofoaluma, Papali'i, To'o, Suaalii). Highest-frequency error class.
- **Nicknames + initials** — "DCE", "RTS", "JWH", "Nicho" (Hynes), "Turbo", "Teddy", "Foxx". Resolved against a **managed alias table** (`people.aliases` — empty today; populating it is the single biggest accuracy win, see [roadmap backlog](roadmap.md#backlog)).
- **SuperCoach jargon → canonical concept** — BE (breakeven), POD (point of difference), donut (zero score), ton (100+), loophole / captain's loophole, ceiling/floor, rage trade, the bye; team slang (cows, chooks, green machine). A **domain lexicon** parallel to the player registry.
- **Number typing** — the same digits mean different things: SuperCoach score vs price ($) vs breakeven vs minutes vs real-life stat (tries/tackles). ASR also renders "fifty-eight" / "58" inconsistently.
- **Filler, false starts, self-corrections** — strip disfluency ("like, you know") and merge retractions ("I'd start, no — I'd bench him") without losing meaning.
- **Protect legitimate slang** — do *not* "correct" real NRL terms (e.g. *PVL*) into dictionary words.

Today **only a local prototype exists** — the [`/clean-transcript`](../../skills/transcript-pipeline.md) skill (plus the `POST /api/admin/update-clean-text` endpoint, which backfills `clean_text` onto existing chunks from a cleaned S3 document). There is **no production cleaning pass yet.** The prototype's job is to settle the prompt and pass structure — that settled form *is* the spec the worker encodes.

> **Coupling to leave intact:** the cleaning pass and the SuperCoach roster regeneration currently share the `data/players.yaml` registry. Rehoming that (cleaning reads the roster from the DB instead of yaml) is the open loop blocking retirement of the legacy `scrape-supercoach` skill — tracked in the [Scout Phase 1 plan](../scout/plans/phase-1-supercoach-roster.md), surfaced here because it touches Analyst's input.

### A5. Extraction — skill-validated, then workerised; LLM-graded

**Decision: claim/quote/entity extraction ships as a production worker pass, gated by eval suites (not drift tests); any Claude Code skill is local prototyping only ([A11](#a11-production-runs-in-workers-not-claude-code-skills)).** This is the defining testing contrast with Scout: Scout's deterministic fetchers need *endpoint-drift tests* (the upstream shape is the only thing that can change); Analyst's extraction passes are *LLM-graded* (the model's judgement is what can regress), so they need [DeepEval suites under `tests/evals/`](../../../../tests/README.md).

**Shaping a claim is more than finding it.** Over (cleaned, reference-resolved — [A9](#a9-referential-resolution--attribution-is-claim-level-not-turn-level)) chunks, the extraction pass must also:

- **Filter signal from banter** — pods are mates joking. "I'd sell my house on Cleary" is hyperbole, not a trade call; sponsor reads and tangents aren't claims.
- **Own the stance** — distinguish the host's *own* view from devil's-advocate / hypothetical / audience-question framing ("a lot of people are asking should they sell Cleary" is *not* the host's claim).
- **Type + structure** — `claim_type` (buy/sell/hold/start/bench/captain/trade/injury/price/role/match-result), subject entity, polarity, strength. Map hedging / conditionals / negation to strength: "lock him in" (strong), "you could start him I guess" (weak), "I'm *not* selling Cleary" (a HOLD via negation).
- **Anchor in time** — stamp the round/window the claim *pertains to* ("this week", "after Origin"), not just when it was said. Predictions need a horizon ([A10](#a10-claims-carry-falsifiability--resolution-criteria)).
- **Deduplicate** — a host repeating "Cleary's a buy" four times is one claim, within and across chapters.
- **Link to canonical entities** — so claims aggregate across sources and can later be grounded against Scout's actual price/breakeven data.

Today **only local prototypes exist**, multi-pass: [`/process-transcript`](../../skills/transcript-pipeline.md) (multi-pass extraction), [`/verify-claims`](../../system/extraction.md) (per-claim Haiku cross-check), [`/analyse-transcript`](../../skills/analyse-transcript.md) (chapter-scoped enrichment), [`/upload-transcript`](../../skills/transcript-pipeline.md) (persist). The production surface — the `services/worker-extraction/` worker — is a skeleton; it is built only once the eval suite locks acceptable precision/recall on a graded corpus. See [extraction-worker](../../../todo/extraction-worker.md).

### A6. Consensus / contradiction detection is *semantic*, not numeric

**Decision: Analyst owns the semantic cross-reference; Bookkeeper owns the numeric derivation.** Analyst detects *that* sources agree or contradict and *which way* ("3 sources turned bearish on Cleary since Tuesday"). It writes `consensus_snapshots`. It does **not** compute the alignment index, the advisor-accuracy weighting, or the breakeven math behind the call — those are Bookkeeper derivations over the same data.

The seam matters because both are tempting to call "consensus." The rule: if the output is a *count or a direction over claims*, it's Analyst; if it's a *score, index, or weighted metric*, it's Bookkeeper. The write target is the publishing surface's `update_consensus_snapshots`. See [consensus-engine](../../../todo/consensus-engine.md).

### A7. Audit — `agent_id='analyst'`, pass discriminator in `detail_json`

**Decision: every Analyst pass lands on the shared audit tables**, mirroring Scout's pattern ([agent-audit.md](../../system/agent-audit.md)): one `agent_runs` row per pass with `agent_id='analyst'` and `detail_json.pass` discriminating which pass ran (`transcribe`, `clean`, `embed`, `extract`, `verify`, `consensus`). This gives one "is Analyst healthy?" dashboard that breaks down by pass and unifies cost/latency reporting with Scout's agentic surface.

**Today this is unmet for the transcription path** — the in-repo transcription pipeline writes no canonical `agent_runs` row (it predates the convention, and it's legacy per [A8](#a8-disposition-of-the-in-repo-lineup-code--legacy-not-deleted), so it won't be retrofitted). The *new* passes (clean, embed, extract, consensus) adopt it from day one.

### A8. Disposition of the in-repo Lineup code — legacy, not deleted

**Decision: the in-repo Lineup code is frozen as legacy — kept working, not extended, not deleted.** Until the external Lineup API exists ([A2](#a2-lineup-is-a-service-boundary-not-a-sub-module)), the in-repo path is the *only* producer of transcripts, so it is load-bearing. The policy:

- **No feature work, refactors, or "improvements"** inside `app.analyst.diarize`, `identify_voice`, `visual_id`, `fusion`, `remote`, the voice/face cluster modules, `identity_alignment`, `services/gpu/`, the `LINEUP_REMOTE` pathway, or the review-UI Lineup overlays. **Fixes only, and only when something is actively breaking the live pipeline.**
- **New transcription work in this repo** is designed around the eventual API call ([A3](#a3-the-input-contract--a-speaker-attributed-transcript)), not around extending the current in-repo Lineup.
- **The `source_speakers.cluster_label` column stays** ([A3](#a3-the-input-contract--a-speaker-attributed-transcript)) — it's the contract the external API writes into. Don't propose dropping it.
- When "Lineup" is mentioned without qualifier, assume the **external project**, not this repo's code.

The legacy file inventory and per-phase Lineup status live in [README § Lineup status](README.md#lineup-status) and [roadmap.md § Lineup externalisation](roadmap.md#track-1--lineup-externalisation).

### A9. Referential resolution — attribution is claim-level, not turn-level

**Decision: Analyst resolves what the words *point to* before extracting meaning — and this is a distinct concern from Lineup's turn attribution.** Lineup ([A2](#a2-lineup-is-a-service-boundary-not-a-sub-module)) answers "*which Person spoke this turn*." Necessary, but not sufficient: the *claim* inside a turn can point elsewhere. The referential problems that **stay in-repo after Lineup leaves**:

- **Coreference / anaphora** — "he's a great buy", "trade him", "this guy". Claim attribution silently depends on resolving these to an entity. The hidden hard problem: if it's wrong, every claim downstream is mis-subjected.
- **Claim-source ≠ speaker** — the speaker may be quoting ("Gus reckons Cleary's a sell"), reading a tweet, or reciting a stat. The *claim's* source is not always the turn's speaker. This residual attribution work is Analyst's, not Lineup's.
- **Same-surname disambiguation** — the Trbojevic brothers (Tom vs Jake), the Fifitas. "Turbo" disambiguates; "Trbojevic" alone does not — needs context.
- **Positional / role reference** — "the fullback", "their halfback", "the captain". Resolvable only with team + round context.
- **Time-dependent entity resolution** — "Pearce at the Roosters" in a 2023 clip resolves relative to the *source date*, not now. Entities and the player↔team mapping are resolved as-of the source.

**Why it's its own decision:** these are not cleaning (the surface is already fine) and not extraction (no claim has been shaped yet) — they are the *linking* step in between. Getting them wrong produces confidently-attributed garbage the eval suite ([A5](#a5-extraction--skill-validated-then-workerised-llm-graded)) can't catch, because the claim *text* reads fine; only the subject/source is wrong. **Coreference and claim-source resolution are the two I'd hold to the highest bar** — they are what make attribution real rather than nominal.

### A10. Claims carry falsifiability + resolution criteria

**Decision: when a claim is a prediction, Analyst captures *how it resolves* — not just what it says.** This is the keystone for the **ledger** (advisor-accuracy tracking — [Bookkeeper](../bookkeeper/README.md)): a claim is only worth tracking if it can be scored against reality later. "Cleary scores 60+ this round" is resolvable; "Cleary's a gun" is a vibe.

Per claim, Analyst marks:
- **Is it falsifiable?** — a resolvable prediction vs an unfalsifiable opinion.
- **Resolution criterion** — what observable outcome settles it (a SuperCoach score threshold, a selection/role, a price move, a match result).
- **Horizon** — the round/window by which it resolves (from the temporal anchor in [A5](#a5-extraction--skill-validated-then-workerised-llm-graded)).

**Boundary with Bookkeeper:** *identifying* that a claim is a falsifiable prediction and *capturing its resolution rule* is interpretive — Analyst's. *Scoring* it against the outcome and rolling it into an accuracy index is numeric derivation — Bookkeeper's. Analyst makes the claim **gradeable**; Bookkeeper **grades** it. This is the decision that makes the silver layer worth building: grading advisors is the reason claims are extracted at all.

### A11. Production runs in workers, not Claude Code skills

**Decision: every Analyst pass ships as a worker/service; Claude Code skills are local developer tools only and are never on the production path.** Production cannot depend on a skill — skills run in a developer's local Claude Code session, not in the deployed API/worker fleet. This mirrors [Scout D5](../scout/charter.md#d5-skills-disposition) ("the endpoint is the universal surface; skills are off the critical path entirely").

**What skills are for:** prototyping a pass's prompt, exploring an extraction approach, and generating eval fixtures against real transcripts. **What they are not:** a deployable surface, a cron target, or a dependency of any production pass.

Consequences:
- The honest production status of every interpretive pass today is **not built** — a working *local prototype* (a skill) is not production. The docs say "not built (production)" and list the skill separately as a prototype.
- The shippable artefact is a worker module — audited per [A7](#a7-audit--agent_idanalyst-pass-discriminator-in-detail_json), eval-gated per [A5](#a5-extraction--skill-validated-then-workerised-llm-graded), drained on a schedule.
- A skill and its worker should share one pure module so a settled prototype doesn't rot into a divergent second implementation — but if forced to choose, the worker is canonical and the skill is disposable.

---

## Architectural risks

1. **Legacy Lineup rot.** The in-repo Lineup is "kept working, not invested in" ([A8](#a8-disposition-of-the-in-repo-lineup-code--legacy-not-deleted)) but is the only transcript producer until the API lands. Risk: dependency drift (pyannote/torch/InsightFace upgrades, HF token expiry, SageMaker config rot) breaks the live pipeline with no one actively maintaining it. Mitigation: fixes-only policy keeps the surface area small; the GPU stack is already isolated from the API container, so its breakage is contained.

2. **The external Lineup API doesn't exist yet.** [A2](#a2-lineup-is-a-service-boundary-not-a-sub-module) is directional. Sequencing risk: workerising the interpretive passes (Track 2) assumes a transcript producer, and for now that's the legacy path. Mitigation: design every new pass against the [A3](#a3-the-input-contract--a-speaker-attributed-transcript) contract so the producer swap is transparent.

3. **LLM extraction quality regresses silently.** Claims/quotes extraction is LLM-graded; without eval coverage, a prompt or model change degrades precision invisibly and propagates wrong claims into the wiki and ledger. Mitigation: [A5](#a5-extraction--skill-validated-then-workerised-llm-graded) — DeepEval suites gate workerisation; no worker ships ahead of its eval.

4. **Skills mistaken for production.** A local prototype skill is convenient enough that ops starts leaning on it — and now production depends on a developer's laptop. Mitigation: [A11](#a11-production-runs-in-workers-not-claude-code-skills) — prod is workers, skills are local-only (prototype + eval-fixture generation). Where a skill and its worker coexist, they share one pure module so the prototype can't rot into a divergent second implementation; the worker is canonical.

5. **Consensus inherits Lineup's attribution quality.** "Who said what" is only as good as speaker identification. If attribution is wrong, consensus detection ([A6](#a6-consensus--contradiction-detection-is-semantic-not-numeric)) confidently reports the wrong host's position. Mitigation: consensus carries `match_confidence` through from `source_speakers`; low-confidence attributions are surfaced, not silently counted.

6. **Embedding ownership ambiguity.** `source_chunks.embedding` is described as "the indexer's" in some docs and as an Analyst pass here. It is a transform over chunks, so it belongs to Analyst by [A1](#a1-the-boundary-principle--analyst-owns-the-interpretive-layer). Mitigation: this charter claims it explicitly; the "indexer" language elsewhere refers to this pass. Tracked in Open Questions.

---

## Cost, testing, rollout

### Cost

The expensive part of Analyst's *current* footprint — Deepgram (~$0.30/source) plus GPU inference (~$0.13/source) ≈ **~$0.43/source** — is **Lineup's, and it leaves with Lineup** ([A2](#a2-lineup-is-a-service-boundary-not-a-sub-module)). Analyst's *residual* cost is the interpretive passes: LLM claim/quote extraction (per-source, scales with transcript length) and text embeddings (cheap, batched). Eval runs cost $$ per run and are the other recurring spend — run on demand, not per-commit.

### Testing

| Tier | What it covers |
|---|---|
| Unit (`tests/unit/api/analyst/`) | Pure helpers — chunk/turn merge logic, char-offset math, claim-shape validation. No IO, no LLM. |
| **Evals** (`tests/evals/`) | The distinguishing tier. DeepEval LLM-graded suites over a fixed corpus — claim extraction precision/recall, verification accuracy, cleaning fidelity. Gates workerisation per [A5](#a5-extraction--skill-validated-then-workerised-llm-graded). Costs $$ per run. |
| Integration (`tests/integration/api/analyst/`) | Round-trip a fixture transcript through a pass; assert DB writes + `agent_runs` row + idempotency on re-run. |

No drift tests — Analyst doesn't fetch from upstream sources (that's Scout's concern). The thing that can change underneath Analyst is *model behaviour*, which is what the eval tier guards.

### Rollout

Each interpretive pass follows the same shape — the **worker is the deliverable**; any skill is an optional, local prototyping aid ([A11](#a11-production-runs-in-workers-not-claude-code-skills)):

1. Prototype the prompt locally against real transcripts (optionally via a Claude Code skill); iterate.
2. Lock an eval suite that encodes "good enough" (precision/recall thresholds on a graded corpus); capture eval fixtures from the prototype runs.
3. Build the production pass as a worker module (a shared pure function is the implementation).
4. Wire the [A7](#a7-audit--agent_idanalyst-pass-discriminator-in-detail_json) audit pattern + a recurring drain job.
5. Run the worker against the eval corpus and a live sample; diff; cut over. The prototype skill, if any, is now disposable.

---

## Open questions

1. **When does the external Lineup API land?** Until it does, the legacy in-repo path is load-bearing ([A8](#a8-disposition-of-the-in-repo-lineup-code--legacy-not-deleted)). The contract ([A3](#a3-the-input-contract--a-speaker-attributed-transcript)) is the hedge, but the cutover date is unknown — and gates whether the recurring drain job is built in-repo or against the API.
2. **Embedding ownership** — text-chunk embedding is claimed for Analyst here ([risk #6](#architectural-risks)); the "indexer" framing elsewhere needs reconciling. Which model (OpenAI vs Voyage) and where the index lives (pgvector in-repo vs external) is undecided.
3. **Chapter detection placement** — `source_chapters` is produced by the [`/analyse-transcript`](../../skills/analyse-transcript.md) pipeline. Is it a first-class Analyst pass in its own right, or a sub-step of extraction? Leaning: its own pass, because annotation and claim-scoping both depend on it.
4. **Advisor / Person identity creation.** `people_roles` for advisors (podcast hosts) is largely empty. Under the externalised Lineup, where do advisor entities get created — manually, or derived by the Lineup service and written back? Shared open question with [Scout charter Q6](../scout/charter.md#open-questions).
5. **Where `consensus_snapshots` is written** — the publishing surface (`update_consensus_snapshots`) or an Analyst consensus worker? [A6](#a6-consensus--contradiction-detection-is-semantic-not-numeric) names the table; the owning process is open.

---

## Related

- [README.md](README.md) — Analyst's identity, scope, and voice
- [architecture.md](architecture.md) — pipeline position, hand-off contract, pass chain, current-vs-target architecture
- [roadmap.md](roadmap.md) — status and the two-track forward plan
- [Scout charter](../scout/charter.md) — the bronze-layer charter Analyst's silver boundary abuts (decisions D1–D13)
- [Transcription pipeline](../../system/transcription-pipeline.md) — the in-repo Lineup surface (legacy), stages 1–5
- [Speaker identification](../../system/speaker-identification.md) — voice + face + fusion (legacy Lineup detail)
- [Extraction](../../system/extraction.md) — claim/entity/quote extraction surface (local prototype today; production worker not built)
- [Crew Dynamics](../dynamics.md) — Analyst mode's place in Jaromelu's internal reasoning flow

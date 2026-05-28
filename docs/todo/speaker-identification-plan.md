---
tags: [area/todo, status/in-progress]
---

# Speaker Identification — Voice + Visual Fusion

> **Status:** Phase 1 ✅ + Phase 2 ✅ + Phase 3 ✅ + Phase 4a ✅ + Phase 4-asd ✅ + Phase 4b-display ✅ + Phase 4b-display-v2 (ephemeral video + YouTube overlay) ✅ + Phase 4b-action (click-to-reassign) ✅ + Phase 5.5 (remote GPU) ✅ + **Voices tab (cluster-level voice assign) ✅** + **Identity alignment (face × voice matrix, read-only) ✅** + **Pyannote community-1 upgrade ✅** + **Face-driven re-segmentation Phase 1 (diagnostic) ✅** shipped. Voice + face fusion + face overlay live. Lineup runs on a SageMaker Async endpoint in `us-east-1` when `LINEUP_REMOTE=1`; full fresh-source pipeline drops from ~50 min CPU → **~3 min** wall time (pyannote 91 s, visual ID 75 s, Deepgram + DB writes ~30 s). Per-source video files are no longer persisted — overlay draws on the YouTube iframe; visual ID yt-dlps into a 24h-lifecycle staging key and deletes after. **Phase 5 (cross-modal compounding) remains.**

**Phase:** Analyst quality / identification
**Priority:** Unlocks per-speaker quote attribution, ledger weighting by host, host-specific consensus.
**Service:** `services/api/app/analyst/` (extends existing `transcribe.py`)

## Summary

Replace Deepgram's bundled diarizer with an open-source diarizer (pyannote.audio), then add two identification modalities — **voice embeddings** (ECAPA-TDNN) and **visual embeddings + active speaker detection** (InsightFace + Light-ASD) — fused per turn to populate `source_speakers.speaker_person_id`. The review UI gains a video pane with a clickable face overlay, which doubles as the manual-override surface.

Deepgram remains the words+timestamps source. We only stop using its `diarize` flag.

## Goals

- Recurring podcast hosts auto-resolve to known `Person` rows on the first run, ≥80% of turns.
- Manual corrections in the review UI write back to both registries (voice + face), so accuracy compounds across episodes.
- Single audit surface that lets an operator watch the video and see who the system thinks each face/voice is, in real time.

## Non-goals

- Replacing Deepgram for ASR — we keep `nova-3` + keyterm biasing.
- Production GPU compute. Phases 1–4 run on the dev box via the existing CLI pattern. Prod compute (Modal / RunPod / dedicated EC2) is a separate decision tracked outside this plan.
- Real-time / live identification. Batch-only, same as today.
- Backfilling player face embeddings from `nrl.com` headshots — not used for this work.

## Architecture (target)

```
Scout audio (m4a)  ──┐
                     │
Scout video (240p) ──┤
                     │
                     ▼
   ┌─────────────────────────────────────────────────────────┐
   │  Deepgram nova-3   →  words + utterances + paragraphs   │
   │  pyannote.audio    →  diarization turns + ECAPA emb     │
   │  InsightFace+ASD   →  per-frame faces + speaking face   │
   └─────────────────────────────────────────────────────────┘
                     │
                     ▼
          Fusion (per pyannote turn)
            voice match  ──┐
            face match   ──┼──> source_speakers.speaker_person_id
            ocr (opt.)   ──┘    + match_method + confidence
                     │
                     ▼
   Review UI: video with clickable face overlay, transcript with
   per-turn modality scores. Click a face → reassign Person →
   write a new face/voice embedding → next episode is better.
```

Provenance kept in `source_speakers` columns: `audio_match_*`, `visual_match_*`, `match_method`, `match_confidence`. The final `speaker_person_id` is the fused decision.

## Phasing

### Phase 1 — pyannote side-by-side (1–2 days, no schema change) — **SCAFFOLDED**

- ✅ `pyannote.audio>=3.1,<4` added to `services/api/requirements.txt` (lazy-imported — torch not pulled at module import time).
- ✅ `huggingface_token`, `pyannote_model` added to `packages/shared/jeromelu_shared/config.py`. Default model: `pyannote/speaker-diarization-3.1`.
- ✅ `services/api/app/analyst/diarize.py` — `diarize(audio_s3_key, *, force) -> DiarizeResult`. Downloads audio from S3, converts to 16 kHz mono WAV via ffmpeg, runs pyannote, persists JSON to `s3://jeromelu-raw-transcripts/.../pyannote.json`. Idempotent.
- ✅ `services/api/app/analyst/diarize_cli.py` — `make diarize SOURCE_ID=<uuid> [FORCE=1]`.
- ✅ `services/api/app/analyst/diarize_compare.py` — read-only diff tool: summary stats, confusion matrix, greedy label alignment, agreement %, disagreement listing. `make diarize-compare SOURCE_ID=<uuid>`.
- ⏳ **Decision gate (next):** run on source `e276d3fc-d3bc-4703-9b45-b0552ff94762`. If pyannote 3.1 agreement against Deepgram is broadly aligned **and** spot-checks favour pyannote turn boundaries, proceed to Phase 2. If marginal, A/B against pyannote 4.0 community-1 and NeMo Sortformer before continuing.

#### Phase 1 result (2026-05-03)

Run: `make diarize SOURCE_ID=e276d3fc-d3bc-4703-9b45-b0552ff94762`. CPU runtime 39m 54s for a 2710s audio file (~0.88× real-time). Source: NRL podcast, "Who will be the ORIGIN fullbacks?…".

Comparison summary (sampled every 2.0s, 1272 samples with both diarizers active):

```
                   Deepgram       pyannote
speakers                  3              4
turns                   126            678
duration             2709.5s

Confusion matrix (seconds of co-occurrence):
                    | speaker_0 | speaker_1 | speaker_2
SPEAKER_00          |        52 |        62 |       296
SPEAKER_01          |       814 |       166 |        28
SPEAKER_02          |        46 |      1016 |        62
SPEAKER_03          |         2 |         0 |         0

Greedy alignment:
  SPEAKER_00 -> speaker_2
  SPEAKER_01 -> speaker_0
  SPEAKER_02 -> speaker_1
  SPEAKER_03 -> speaker_0  (only 2s of co-occurrence — noise)

Agreement after alignment: 1064/1272 samples = 83.6%
```

**Decision: proceed to Phase 2 with pyannote 3.1.**

Reasoning:
- Speaker counts align (3 vs 4); the 4th pyannote speaker has only 2s of co-occurrence with any Deepgram label, so it's almost certainly an interlude / jingle / ad voice that pyannote catches and Deepgram folds into a host. That's a feature, not a bug — quality gates in Phase 3 will filter sub-3s speakers.
- 83.6% agreement at 2s sampling is well within the band where disagreements are likely genuine information rather than label instability.
- Three pyannote speakers map cleanly to three Deepgram speakers with strong dominance (SPEAKER_01→speaker_0 = 814s, SPEAKER_02→speaker_1 = 1016s, SPEAKER_00→speaker_2 = 296s). The matrix is diagonal-ish with no ambiguous splits.
- 678 turns vs Deepgram's 126 — pyannote is finer-grained. That matches its known behaviour and is what we want; Phase 2 will merge utterances into pyannote's turn boundaries via overlap.
- Real-time factor on CPU is acceptable for batch processing today. Production GPU is a Phase-2-prerequisite tracked in Open Decisions #7.

Open question before Phase 2 kickoff: should we A/B against pyannote 4.0 community-1 and NeMo Sortformer first? **Recommend deferring** — 83.6% agreement on 3.1 plus a meaningful 4th-speaker signal is enough to commit to the architecture; community-1 can be a drop-in upgrade in a Phase 1.5 sprint if Phase 3 voice-ID accuracy underperforms.

User actions required before the decision-gate run:

1. Accept the gated-model licence at **all three** Hugging Face pages — pyannote/speaker-diarization-3.1 pulls in two sub-models, and the load fails opaquely if any one is unaccepted:
   - <https://huggingface.co/pyannote/speaker-diarization-3.1>
   - <https://huggingface.co/pyannote/segmentation-3.0>
   - <https://huggingface.co/pyannote/wespeaker-voxceleb-resnet34-LM>

   Get a token at <https://huggingface.co/settings/tokens>.
2. Add `HUGGINGFACE_API_KEY=hf_...` to project-root `.env`.
3. Install heavy deps: `cd services/api && source .venv/Scripts/activate && pip install -r requirements.txt`. Pulls torch (~2 GB).
4. Run: `make diarize SOURCE_ID=e276d3fc-d3bc-4703-9b45-b0552ff94762`. Expect 30–60 min on CPU for a 90-min podcast; ~2–5 min on GPU if CUDA is available.
5. Inspect: `make diarize-compare SOURCE_ID=e276d3fc-d3bc-4703-9b45-b0552ff94762`.

Result of step 5 is the input to the Phase 2 go/no-go.

### Phase 2 — pyannote becomes the diarization source of truth — **SHIPPED 2026-05-03**

- ✅ Migration `047_pyannote_diarization.sql`: `source_speakers.embedding vector(256)`, `source_speakers.embedding_model TEXT`, `sources.diarization_method TEXT`. Embedding dim is 256 (wespeaker bundled with pyannote 3.1) not 192 (ECAPA) — the bundled model is one less dep, and the 192 vs 256 difference is irrelevant for cosine k-NN.
- ✅ `transcribe.py` orchestrates pyannote-then-Deepgram. Deepgram runs with `diarize=False`. pyannote turns are the source of truth for `source_speakers`; each Deepgram utterance gets `speaker_segment_id` by max-overlap.
- ✅ `diarize.py` extended with sliding-window embedding extraction (2s window, 0.5s hop, medoid representative). Pyannote JSON bumped to `json_version=2` carrying both diarization and per-turn embeddings (medoid + full window list).
- ✅ Quality gates baked in: turns shorter than `MIN_TURN_DURATION` (0.3s) get NULL embeddings — wespeaker can't produce a stable vector from <300ms of audio. NaN embeddings filtered defensively at both diarize-write time and transcribe-read time.
- ✅ Force semantics split: `make transcribe FORCE=1` only re-runs Deepgram + DB; pyannote artefact is reused. To re-diarize, run `make diarize FORCE=1` first.
- ✅ New `extraction_method='deepgram_words+pyannote_v1'`. Old `'deepgram_v1'` rows stay put.

End-to-end run on `e276d3fc-d3bc-4703-9b45-b0552ff94762`:

```
speakers_recorded:  4      ← SPEAKER_00/01/02/03
turns_recorded:     678
chunks_recorded:    331
chunks_unassigned:  0
embeddings populated: 548/678 (80.8%)
embeddings NULL:    130/678 (sub-300ms turns)
extraction_method:  deepgram_words+pyannote_v1
diarization_method: pyannote-3.1
embedding dim:      256
```

### Phase 3 — Voice enrollment + voice-only identification — **SHIPPED 2026-05-03**

- ✅ Migration `048_person_voiceprints.sql`: table + HNSW index on `embedding vector_cosine_ops`. `created_by` constraint enforces `'manual' | 'auto-confirmed'`.
- ✅ `services/api/app/analyst/identify_voice.py` — `enroll()` (sliding-window per-window voiceprint rows), `identify_turn_in_memory()` (numpy matrix-multiply k-NN + majority vote), `identify_pyannote_turns()` (per-source convenience wrapper).
- ✅ `enroll_voice_cli.py` + `make enroll-voice PERSON_ID=… SOURCE_ID=… START_TS=… END_TS=…`.
- ✅ Wired into `transcribe.py`: after `source_speakers` rows are created, voiceprint matrix is loaded once, every turn's `embedding_windows` runs through the matcher, `speaker_person_id` + `confidence` are written for matches that clear thresholds.
- ✅ NaN-safe at all layers: filter at extract (`diarize.py`), pre-write (`transcribe._safe_embedding`), pre-match (`identify_voice.identify_pyannote_turns`), and inside the matcher itself (`math.isfinite` before threshold check, since `NaN < 0.75` is False and would otherwise let bad windows vote).

End-to-end test on `e276d3fc…` with one 75 s enrollment of SPEAKER_01:

```
turns_recorded:     678
turns_identified:    14    (13 SPEAKER_01 + 1 borderline SPEAKER_00 at conf=0.762)
precision:           92.9 %
recall (by airtime): 25.4 % of SPEAKER_01's 1078 s
confidence range:    0.756 – 0.992
```

The lone false positive was a 1.3 s turn at exactly the cosine threshold — the kind of single-window fluke that bumping `DEFAULT_MIN_WINDOWS` from 1 to 2 (or `DEFAULT_AGREEMENT_THRESHOLD` from 0.6 to 0.7) would eliminate. Recall improves automatically as more enrollment spans are added (per-host coverage of acoustic variation) and once Phase 5 cross-modal compounding lands.

### Phase 3 — Voice enrollment + voice-only identification — original plan (kept for reference)

- Migration `048_person_voiceprints.sql`:
  ```sql
  CREATE TABLE person_voiceprints (
      voiceprint_id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
      person_id       UUID NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
      source_id       UUID REFERENCES sources(source_id) ON DELETE SET NULL,
      start_ts        FLOAT NOT NULL,
      end_ts          FLOAT NOT NULL,
      embedding       VECTOR(192) NOT NULL,
      embedding_model TEXT NOT NULL,
      created_by      TEXT,    -- 'manual' | 'auto-confirmed'
      created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
  );
  CREATE INDEX person_voiceprints_embedding_idx ON person_voiceprints
      USING hnsw (embedding vector_cosine_ops);
  ```
- New module `services/api/app/analyst/identify_voice.py`:
  - `enroll(person_id, source_id, start_ts, end_ts)` — extract clip, run sliding-window embeddings, write **one voiceprint row per window** (each tagged with the same enrolment session). Reject the enrolment if pyannote flags the span as overlapping speech, or if a music/speech VAD scores it below threshold.
  - `identify_turn(window_embeddings) -> (person_id, similarity) | None` — for each window in the turn, k-NN against `person_voiceprints`. Majority-vote across windows; return the winning Person and the fraction of windows that agreed (used as confidence). Cosine threshold ~0.75 per-window; ≥60% window agreement to commit the turn.
  - Quality gates baked in: skip turns shorter than 2s; skip turns where pyannote `overlap_probability > 0.3`; skip windows where speech-vs-music VAD prefers music.
- Wire into `transcribe.py`: after `source_speakers` rows exist, call `identify_turn` per row, set `audio_match_person_id` + `audio_match_score`. (Final `speaker_person_id` written in Phase 4 fusion; in Phase 3 we just promote the voice match to it as a single-modality interim.)
- **Score normalization (S-norm).** Maintain a small impostor cohort (10–20 random speaker embeddings from VoxCeleb or unenrolled hosts). Normalize each match score against the cohort distribution so the threshold is meaningful across episodes recorded in different rooms / mics.
- Bootstrap: enroll 5–10 known recurring hosts manually using existing transcripts. Pick clean monologue spans of ≥10s each, 2–3 non-contiguous spans per host. The cleanest 30s beats five noisy minutes — curate, don't dump.

### Phase 4a — Visual ID (no ASD) + Fusion — **SHIPPED 2026-05-03**

- ✅ Migrations `049_person_face_embeddings.sql` + `050_speaker_match_provenance.sql`. Face registry table mirrors voiceprints; `source_speakers` gains `audio_match_*`, `visual_match_*`, `match_method`, `match_confidence`. `sources` gains `video_s3_key`, `video_format`.
- ✅ Scout video acquisition (`make collect-video`): single-stream low-res mp4 (default 360p) to S3. `youtube_utils.download_video`'s post-merge filename detection was broken; bypassed with an inline yt-dlp call selecting a combined-stream format.
- ✅ `services/api/app/analyst/visual_id.py`: ffmpeg + cv2 frame sampling at 1 fps, InsightFace `buffalo_l` face detection + 512-dim ArcFace embeddings, in-memory k-NN match against `person_face_embeddings`, face-track JSON to S3, format heuristic (multi_cam vs single_cam).
- ✅ `services/api/app/analyst/enroll_face_cli.py` + `make enroll-face` (image file or video frame at TS).
- ✅ `services/api/app/analyst/fusion.py`: voice + face vote per turn. Both agree → `voice+face`. One fires → that modality. Disagree → NULL (flagged for review).
- ✅ Wired into `transcribe.py`: voice ID → visual ID (when `video_s3_key` set) → fusion → write all provenance columns.

End-to-end test on `e276d3fc…` (single-cam podcast, one host enrolled):

```
turns_recorded:     678
turns_identified:   157   (up from 14 voice-only)
  voice_match:       14
  visual_match:     157
  voice+face:        14   (both modalities agreed — high confidence)
  face_only:        143   (face fired alone, voice didn't clear threshold)
  disagreements:      0
video_format:       single_cam
```

By pyannote speaker:
| label | total | voice✓ | visual✓ | identified seconds / total |
|---|---|---|---|---|
| SPEAKER_01 (correct) | 194 | 13 | 87 | 1022 / 1078 (94.8 %) |
| SPEAKER_02 (wrong) | 279 | 0 | 42 | 294 (false positives) |
| SPEAKER_00 (wrong) | 179 | 1 | 26 | 153 (false positives) |
| SPEAKER_03 (noise) | 26 | 0 | 2 | 1 |

**Visual modality has high recall but low precision in single-cam** — it identifies "is this face on screen", not "is this face speaking". In single-cam podcasts (everyone always in frame), face fires for every enrolled host on every turn. Without ASD this is the expected ceiling; the cross-modal `voice+face` row (14/14) is the trustworthy subset.

### Phase 4-asd — Active Speaker Detection (mouth-opening heuristic) — **SHIPPED 2026-05-04**

Light-ASD / TalkNet / LoCoNet aren't pip-packaged — vendoring them inflates the budget. Phase 4-asd uses a landmark-based ASD heuristic instead, with the same precision-floor goal.

- ✅ `_mouth_opening` extracts ratio = inner-lip distance / face-bbox-height from InsightFace `landmark_3d_68` indices 62 (top) and 66 (bottom). Already provided by `buffalo_l`, no new deps. Earlier attempt with `landmark_2d_106[100/103]` produced a stable ~0.13 regardless of mouth state — wrong indices for that layout.
- ✅ `_select_active_face` per frame: candidate must have mouth-opening ≥ `MIN_ACTIVE_MOUTH_OPENING` (0.045, just above the closed-mouth baseline ~0.040) AND beat the runner-up by `ACTIVE_FACE_MARGIN` (0.005). For frames with one face, the threshold is what gates.
- ✅ `_per_turn_vote` no longer falls back to face-presence voting. Active-face-only voting + `MIN_ACTIVE_FRACTION` (0.30) density gate per turn — listener mouth-open events (chewing, smiling, brief reactions) sit at 10–25 %; the actual speaker is at 30–45 %.
- ✅ `visual_id.visual_identify` reuses an existing face-track JSON when at the current `FACE_TRACK_JSON_VERSION` (skips the ~30 min frame-extraction pass). To force re-extraction, delete the JSON or bump the version.
- ✅ `mouth_opening` persisted in face-track JSON v3 alongside `bbox` / `det_score` / `person_id` / `similarity`.

End-to-end test on `e276d3fc…` (single-host enrolled, single-cam podcast):

| | Phase 4a (face-presence) | Phase 4-asd (this) |
|---|---|---|
| total identified | 157 | 90 |
| true positives (SPEAKER_01) | 87 | 69 |
| false positives | 70 | 21 |
| **precision** | **55.4 %** | **76.7 %** |
| recall on correct speaker | 44.8 % | 35.6 % |
| voice+face (highest-trust) | 14 | 9 |

The 21 remaining false positives are turns where Test Host A's mouth happens to be open ≥ 30 % of frames during someone else's monologue (laugh reactions, backchannels). Genuinely hard for landmark-based ASD; would need a real audio-sync ASD model to filter further. Acceptable precision floor — `voice+face` (9 turns) is the trustworthy subset for downstream consumers.

Tuning:
- `MIN_ACTIVE_MOUTH_OPENING=0.045`, `MIN_ACTIVE_FRACTION=0.30` — empirically tuned on the audited source. Sweet spot in the threshold sweep.
- Higher thresholds (0.050+ or density 0.40+) collapsed precision because too many true-positive frames fell below the bar.
- Lower thresholds reverted to Phase 4a behavior (face-presence with single-host noise).

### Phase 5.5 — Remote GPU inference via SageMaker Async — **SHIPPED 2026-05-05**

Lineup's GPU-bound steps run on a SageMaker Async endpoint in `us-east-1` (Sydney g4dn / g5 capacity was exhausted at deploy time). End-to-end ~50 min CPU → **~3 min** wall time on `ml.g5.xlarge` (A10G).

Measured on the audited 45-min source, fresh full run:

| Stage | GPU time | CPU baseline | Speedup |
|---|---|---|---|
| Pyannote diarize + embeddings | 91 s | ~40 min | ~26× |
| Deepgram + Voice ID + DB writes | ~25 s | same | — |
| Visual ID (frame extraction + InsightFace + ASD) | 75 s | ~7 min | ~5× |
| **Total wall time** | **3 min 16 s** | ~50 min | **~15×** |

- ✅ `services/gpu/Dockerfile` — multi-stage build on AWS DLC PyTorch base image. Stage 1 downloads pyannote + InsightFace model weights using HF token via Buildkit secret; stage 2 grafts deps + caches + project source onto the runtime image. Token never lands in image layers.
- ✅ `services/gpu/inference.py` — SageMaker BYOC handler. `model_fn` pre-warms pyannote pipeline + embedding model + InsightFace; `predict_fn` dispatches on `task` (`diarize` / `visual_identify`).
- ✅ `services/gpu/deploy.py` — boto3 idempotent deploy: model + endpoint-config + endpoint. `make lineup-deploy` re-deploys with rolling update.
- ✅ `services/gpu/build_and_push.sh` — `make lineup-build` builds + pushes to ECR.
- ✅ `services/api/app/analyst/remote.py` — local-side wrappers (`diarize_remote`, `visual_identify_remote`) that submit to the endpoint, poll the SageMaker output S3 location, reconstruct the local result types from the persisted artefacts.
- ✅ `diarize.py` and `visual_id.py` short-circuit to the remote wrappers when `settings.lineup_remote` is true. Default off so local-only dev still works.
- ✅ Module-level caches for pyannote pipeline + embedding model (mirrors visual_id's `_face_app` pattern) so the long-lived inference server amortises the ~30 s load across calls.
- ✅ InsightFace provider list auto-detected — picks `CUDAExecutionProvider` when available (GPU container), CPU fallback for local dev. Earlier hardcoded CPU was leaving the T4 idle.
- ✅ Visual ID accepts `registry=(matrix, person_ids)` directly — local-side preloads from Postgres and ships in the SageMaker request, so the GPU container has no DB credentials.
- ✅ Cross-region split: artefact buckets in Sydney; SageMaker async I/O staging bucket `jeromelu-sagemaker-async` in `us-east-1`. Per-source cross-region transfer is ~$0.001 — rounding error.
- ✅ One-time AWS setup runbook at `services/gpu/SETUP.md` (ECR repo, IAM role, staging bucket, `.env` config).

Confirmed architectural decisions: one endpoint with task dispatch · `ml.g5.xlarge` (A10G; switched from `g4dn.xlarge` after capacity issues) · models baked at build · `us-east-1` region · single-concurrent invocation. Cost: ~$0.43/source (≈$0.13 GPU + $0.30 Deepgram + ~$0.001 cross-region) + ECR ~$0.30/month.

#### Bugs fixed during deploy (kept here for archaeology)

| # | Symptom | Root cause | Fix |
|---|---|---|---|
| 1 | `pip install -e jeromelu_shared` failed: requires py3.12, base is py3.11 | DLC base image is py3.11 | Loosened `requires-python` to `>=3.11` |
| 2 | First invoke: HTTP 413 from primary | TorchServe default 6 MB request limit | `TS_MAX_REQUEST_SIZE` + `SAGEMAKER_TS_MAX_REQUEST_SIZE` env on model |
| 3 | Container hit MinIO `localhost:9000` | SageMaker silently dropped empty-string `S3_ENDPOINT` env, default kicked in | Flipped `s3_endpoint` default in `config.py` from `"http://localhost:9000"` to `""` |
| 4 | Visual ID returned in 20 min on T4 (no speedup) | `_get_face_app` hardcoded `["CPUExecutionProvider"]` | Auto-detect via `onnxruntime.get_available_providers()` |
| 5 | `ml.g4dn.xlarge` and `ml.g5.xlarge` `InsufficientInstanceCapacity` | Sydney region capacity exhausted | Migrated endpoint to `us-east-1` |
| 6 | SageMaker create-endpoint failed: "Please check the specified bucket's configurations" | AsyncInferenceConfig validates same-region S3 paths | Created `jeromelu-sagemaker-async` bucket in `us-east-1` for SageMaker's internal I/O staging |

### Phase 4b-display — Read-only review-UI overlay — **SHIPPED 2026-05-04**

- ✅ HTML5 `<video>` + absolutely-positioned `<canvas>` over the locally-stored 360p video.
- ✅ Face boxes drawn on `timeupdate` from a face-track JSON proxied through the API (`/api/sources/{id}/face-track`) — bypasses S3 CORS.
- ✅ Box colour by `match_method`: green = `voice+face`, amber = `face`-only, blue = on-screen-but-not-speaker, grey = unknown.
- ✅ `services/web/src/app/components/VideoOverlay.tsx` wired into `SourceReviewClient.tsx`. Falls back to the YouTube embed when `video_url` / `face_track_url` aren't set.

### Phase 4b-display-v2 — Ephemeral video + canvas-on-iframe overlay — **SHIPPED 2026-05-05**

Driver: at 100K+ catalogue scale, persisting a 360p mp4 per source is wasted hot storage — the only consumer that needed durable video was the review UI's overlay, and the overlay can read the same face-track JSON over the YouTube iframe just as well.

- ✅ `services/api/app/analyst/video_staging.py` — `acquire_video_temp` / `staged_video` (yt-dlp + upload to `staging/video/<uuid>.mp4`, delete on context exit) and `staged_video_local` (yt-dlp into a `tempfile.TemporaryDirectory` for in-process consumers like the reassign endpoint).
- ✅ `transcribe.py` wraps `visual_identify` in `staged_video(...)` — three regimes (legacy persistent key, ephemeral staging, no-video voice-only) handled by one context manager. `sources.video_s3_key` is no longer written for new sources.
- ✅ Reassign endpoint (`POST /api/sources/{source_id}/speakers/{segment_id}/reassign`) drops the hard-fail-on-missing-video; falls back to `staged_video_local` when the row has no persistent video. ~10–30 s extra latency per reassign, paid only when an operator clicks a face.
- ✅ Face-track JSON v4 carries `frame_width` + `frame_height` so overlays can scale bboxes to whatever surface they're drawing over (HTML5 video used `videoWidth/Height` intrinsics; the iframe doesn't expose those).
- ✅ `services/web/src/app/components/YouTubeFaceOverlay.tsx` — canvas + click targets layered over a `YT.Player` iframe. `pointer-events: none` on the canvas; per-face buttons re-enable pointer-events for their bboxes so YouTube's native controls remain clickable elsewhere.
- ✅ `SourceReviewClient.tsx` priority order: `YouTubeFaceOverlay` (default for any YouTube source with a face-track JSON) → legacy `VideoOverlay` (only for sources where stored video still exists) → `YouTubePlayer` (no overlay).
- ⏳ S3 lifecycle rule on `staging/video/` prefix (24h expiration) — set in Terraform.
- ⏳ Manual cleanup of the one persisted video remaining (`e276d3fc…`).

### Phase 4b-action — Click-to-reassign — **SHIPPED 2026-05-05**

Shipped alongside Phase 4b-display-v2 (canvas-on-iframe overlay) in commit `87b14f0`.

- Click a face on `YouTubeFaceOverlay` → `ReassignFaceModal` opens with prefilled `segment_id`, `frame_ts`, `bbox`.
- Person picker (`PersonPicker`, fuzzy search over `people`) → POST `/api/sources/{source_id}/speakers/{segment_id}/reassign`.
- Backend (`services/api/app/routers/sources.py::reassign_speaker`): acquires video (persisted S3 mp4 OR ephemeral yt-dlp), extracts frame via ffmpeg, enrols face via InsightFace + voice via wespeaker over the turn's audio span, both with `created_by='manual'`. Updates `source_speakers.speaker_person_id`, `match_method='manual'`, `match_confidence=1.0`. Single transaction; idempotent on the speaker update; embeddings are append-only.
- Match-method colour-coding: shipped via the overlay component.
- Full sequence: see [`speaker-identification.md` § Manual reassign](../agents/system/speaker-identification.md#manual-reassign).

### Phase 4 — Visual ID + ASD + Fusion + Video-overlay Review UI — original plan (kept for reference)

The big one. Lands the visual modality, the fusion logic, and the review/override surface together so they're tested as a system.

**Acquisition.** Scout downloads a low-res video stream alongside the audio:
- `yt-dlp -f "worst[height>=240]"` → `s3://jeromelu-raw-audio/.../{video_id}.video.mp4`.
- 30-day S3 lifecycle rule discards after processing window.
- New columns: `sources.video_s3_key TEXT`, `sources.video_format TEXT`.

**Visual processing.** New module `services/api/app/analyst/visual_id.py`:
- ffmpeg frame sample at 1fps (configurable via `frame_sample_rate`).
- **InsightFace `buffalo_l`** for multi-face detection + 512-dim ArcFace embeddings per frame. Returns `[(bbox, embedding, det_score), …]` per frame.
- **Light-ASD** for active speaker detection: per detected face, predict speaking probability using a 1s audio window centered on the frame.
- Persist a face-track JSON to S3:
  ```
  s3://jeromelu-raw-transcripts/.../*.face_track.json
  [
    { "ts": 0.0, "faces": [
        { "bbox": [x,y,w,h], "embedding_id": "...",
          "person_id": "...", "confidence": 0.94, "asd_score": 0.81 }
    ]},
    ...
  ]
  ```
  (Embeddings themselves go to the DB as needed; the JSON keeps just the resolved match for replay.)

**Format heuristic.** Stored as `sources.video_format`:
- `face_change_rate` = frames where dominant face identity changes / total frames.
- High → `'multi_cam'` (face presence ≈ active speaker; ASD optional).
- Low → `'single_cam'` (ASD required to disambiguate).
- No video → `'audio_only'`.

**Face registry.** Migration `049_person_face_embeddings.sql` — mirrors voiceprints:
```sql
CREATE TABLE person_face_embeddings (
    face_embedding_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    person_id         UUID NOT NULL REFERENCES people(person_id) ON DELETE CASCADE,
    source_id         UUID REFERENCES sources(source_id) ON DELETE SET NULL,
    frame_ts          FLOAT,
    embedding         VECTOR(512) NOT NULL,
    embedding_model   TEXT NOT NULL,         -- 'insightface/buffalo_l'
    created_by        TEXT,                  -- 'manual' | 'auto-confirmed'
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX person_face_embeddings_idx ON person_face_embeddings
    USING hnsw (embedding vector_cosine_ops);
```

**Fusion.** Migration `050_speaker_match_provenance.sql`:
```sql
ALTER TABLE source_speakers
    ADD COLUMN audio_match_person_id  UUID REFERENCES people(person_id),
    ADD COLUMN audio_match_score      FLOAT,
    ADD COLUMN visual_match_person_id UUID REFERENCES people(person_id),
    ADD COLUMN visual_match_score     FLOAT,
    ADD COLUMN match_method           TEXT,   -- 'voice'|'face'|'voice+face'|'ocr'|'manual'
    ADD COLUMN match_confidence       FLOAT;
```

New module `services/api/app/analyst/fusion.py`:
- For each turn, compute average visual identity vector from frames where `asd_score > 0.5` (multi-cam) or all detected faces (single-cam).
- k-NN match against `person_face_embeddings`.
- Combine with voice match per the fusion table:

| Voice match | Face match | Result |
|---|---|---|
| Person X | Person X | `voice+face`, high confidence, auto-assign |
| Person X | NULL | `voice`, medium confidence, auto-assign |
| NULL | Person X | `face`, medium confidence, auto-assign |
| Person X | Person Y | NULL, flagged for review |
| NULL | NULL | NULL, flagged as unknown |

**Review UI.** `services/web/src/app/stream/[sourceId]/`:
- New `<VideoOverlay />` component: HTML5 `<video>` element streaming the locally-stored `video.mp4`, with an absolutely positioned `<canvas>` on top.
- On `timeupdate`, look up the nearest face-track entry, draw boxes scaled to canvas dimensions, label each with the matched Person name (or "?" if unknown).
- Click a box → modal: pick a Person from the roster (or create new). Persists:
  1. `source_speakers.speaker_person_id` for the corresponding turn.
  2. New row in `person_face_embeddings` with `created_by='manual'`.
  3. New row in `person_voiceprints` with `created_by='manual'` (using the audio span of that turn).
- Transcript pane next to it shows the per-turn `audio_match_score` / `visual_match_score` for inspection.

### Voices tab — cluster-level voice assign — **SHIPPED 2026-05-12**

The voice-focused workflow the face-runs/assign endpoint explicitly deferred. Pyannote already tags every `source_speakers` row with a per-source `SPEAKER_NN` cluster label, so no clustering pass is needed — the Voices tab is pure aggregation, mirroring the Faces tab's cluster-level ergonomic.

- ✅ `services/api/app/analyst/voice_clusters.py` — `aggregate_clusters(rows, preview_by_segment)` (pure) + `compute_voice_clusters(session, source_id)` (DB wrapper). Returns per-cluster turn_count, total_seconds, embedding_eligible_count, dominant_person, match_method_breakdown, plus the 5 longest sample turns with preview text.
- ✅ `GET /api/sources/{source_id}/voice-clusters` — read endpoint; resolves dominant_person_name in one Person query.
- ✅ `POST /api/sources/{source_id}/voice-clusters/{speaker_label}/assign` — NDJSON-streaming SQL-only bulk assign. Phases: `person` → `voice_enrol` (copy up to 10 medoid embeddings from `source_speakers.embedding` into `person_voiceprints` with `created_by='manual'`, `skip` event when no eligible turns) → `attribute` (one UPDATE on `source_speakers` matching `document_id` + `speaker_label`, sets `speaker_person_id` + `match_method='manual'`) → `commit`.
- ✅ Voiceprint promotion uses the per-turn medoid wespeaker vector pyannote wrote at diarisation — same model the matcher uses, no audio re-fetch, instant. Voice analogue of the face side's "copy top-N detections into person_face_embeddings".
- ✅ `services/web/src/app/components/VoicesPanel.tsx` + `AssignVoiceModal.tsx`. Tab wired into `SourceReviewClient.tsx` alongside Faces and Claims. Sample turns click-to-seek the YouTube player.
- ✅ `tests/unit/api/analyst/test_voice_clusters.py` — 13 pure-function tests over `aggregate_clusters` covering grouping, ordering, dominant-person mode, match-method breakdown, sample selection, NULL-embedding handling, preview-text truncation.

This converts the in-app voice enrolment story from "operator finds a clean monologue span and runs `make enroll-voice` from the CLI" to "operator clicks `Assign` on a pyannote cluster". `make enroll-voice` still exists for the bootstrap case where a specific span is wanted; the Voices tab is the cluster-level path for everything else.

### Identity alignment — face × voice cluster matrix — **SHIPPED 2026-05-12**

Read-only diagnostic over the two independent clusterings of the same conversation. Cross-modal cluster fusion is the bridge between per-turn `fuse_per_turn` and Phase 5 compounding — alignment at *identity* granularity is stronger evidence than agreement on a single frame.

- ✅ `services/api/app/analyst/identity_alignment.py` — pure `compute_alignment(detections, speakers)` over `DetectionRow` / `TurnRow` projections + `fetch_alignment(session, source_id)` DB wrapper. Builds the (face_cluster_id, speaker_label) overlap matrix, derives per-modality shares + confidence, runs greedy 1:1 dominant pairings, and produces a per-turn disagreement worklist (capped at 50, sorted by duration desc).
- ✅ `GET /api/sources/{source_id}/identity-alignment` — resolves Person names for every face cluster, voice cluster, and disagreement-list row in one Person query.
- ✅ `services/web/src/app/components/AlignmentPanel.tsx` — three sections: dominant pairings list with consistency-coloured borders, overlap matrix capped at 8×8 with confidence-coloured cells, disagreement worklist with click-to-seek. New `Alignment` tab in `SourceReviewClient.tsx`, gated on `face_track_url`.
- ✅ `tests/unit/api/analyst/test_identity_alignment.py` — 17 tests covering overlap counting, active-vs-passive split, share computation, NULL handling, greedy pairing 1:1 invariant, disagreement detection + sorting + cap.

Today the tab is read-only. The next layer — one-shot dual assign and asymmetric-error backfill — is action on top of this same matrix.

### Pyannote diarization upgrade 3.1 → community-1 — **SHIPPED 2026-05-13**

Drop-in pipeline swap; embedding model (wespeaker, 256-dim) unchanged so `person_voiceprints` stays schema-compatible.

- ✅ `pyannote_model` default in `packages/shared/jeromelu_shared/config.py` flipped to `pyannote/speaker-diarization-community-1`.
- ✅ Error-message URLs in `diarize.py` switched from hardcoded `3.1` to f-string against `settings.pyannote_model` so the operator gets the right HF page to license-accept regardless of which model the env points at.
- ✅ Docs note: user must accept the new model's license at `https://huggingface.co/pyannote/speaker-diarization-community-1` before the next `make diarize`.

The motivation is the over-merging behaviour 3.1 shows on similar-voice speakers — same accent, same mic, same room produces conflated SPEAKER_NN labels. community-1 is reported to segment more cleanly on this class. Re-diarize a known-conflated source post-upgrade to measure the delta before deciding whether the deeper Phase 2 (face-driven re-segmentation) is needed.

### Face-driven re-segmentation Phase 1 — diagnostic view — **SHIPPED 2026-05-13**

The visibility layer for the over-merging problem. Builds on already-stored data only — no schema changes, no audio re-fetch.

- ✅ `compute_alignment` extended with `face_transcript` (Deepgram chunks grouped into consecutive runs of the same dominant on-screen face cluster) + `conflated_turn_ids` (pyannote turn ids whose chunks attribute to more than one face cluster). Pure helper `_compute_face_transcript`; conflation detection uses chunk-midpoint inside turn for strict semantics (touching-boundary overlap caused false positives on adjacent turns).
- ✅ `fetch_alignment` now pulls `SourceChunk` rows for the document and passes them through.
- ✅ Router resolves `face_cluster_person_name` for each face_run.
- ✅ `AlignmentPanel` gains a "Words by face cluster" section at the top with a CONFLATED badge on runs overlapping conflated pyannote turns. Conflation count headline summarises pyannote's over-merging rate.
- ✅ 9 new unit tests cover: empty inputs, chunks with no overlapping detections, consecutive same-cluster merging, face cluster change → new run, conflation detection when one pyannote turn covers multiple face_runs, no conflation when face_runs match turns 1:1, no conflation from None-cluster runs (silence), pyannote_turn_ids reflects overlapping turns, deterministic tiebreak on cluster_id asc.

**Phase 2 decision gate:** measure `conflated_turn_ids` count on a known-conflated source after the community-1 upgrade. If conflation drops to single-digit per source, skip the Phase 2 invasive build (sub-segment table + audio re-fetch). If conflation remains high, proceed with Phase 2.

### Phase 5 — Cross-modal compounding (3 days)

**The strategic mechanism**, not a periodic-job afterthought. This is what turns the system from "85% on day one" into "95%+ over six months without any human work" — the visual modality auto-curates the audio registry, and vice versa.

The asymmetry that makes this work: face ID + ASD is *easier to bootstrap* (few headshots, threshold-clean signal, multi-modal sync of mouth-movement and audio). Voice ID is *harder to bootstrap* (need clean monologue spans, mic/room variance, no obvious sync signal) but generalises further across episodes once enrolled. Letting the easy modality label the hard one is the leverage point.

**Auto-enrolment loop:**

1. **Visual → voice.** When `match_method='voice+face'` AND `match_confidence > 0.9` for a turn, OR when `match_method='face'` (visual only, voice was NULL) with face confidence > 0.95 AND the turn passes voice quality gates (clean, no overlap, ≥3s), promote the turn's sliding-window embeddings into `person_voiceprints` with `created_by='auto-confirmed'`. **This is the killer move** — it's how unknown-voice but known-face hosts (e.g. a guest who's been visually enrolled but never voice-enrolled) get a voiceprint automatically on first appearance.
2. **Voice → visual.** Symmetric: high-confidence voice match + clean face detection → promote face embedding. Less common because voice generalises better than face, but useful for cases where the host's appearance has drifted.
3. **Cap per-person embeddings.** 50 per modality. Prefer recency and per-source diversity (don't let one episode dominate the registry).
4. **Quality gates on auto-enrolment** are *stricter* than for matching — false positives here corrupt the registry permanently. SNR threshold, no overlapping speech, no music VAD flag, ≥3s duration, single confident face in frame.

**Periodic backfill job.** Walk all `source_speakers` rows where the auto-enrolment criteria hold but a row hasn't been promoted yet. Cheap idempotent sweep.

**Manual corrections compound the same way.** When an operator reassigns a turn in the overlay UI (Phase 4), both modalities' embeddings from that turn get written as `created_by='manual'` — same path, just a different `created_by` tag.

**Admin dashboard surfaces:**
- Embeddings per host per modality over time (growth curve).
- First-pass hit rate per episode (auto-resolved / total turns).
- Auto-enrolment count per episode (how much the registry grew).
- "Drift watch" — hosts whose match scores are trending down across recent episodes (sign their voiceprint registry is going stale).

## Data model deltas (consolidated)

| Migration | What |
|---|---|
| 047 | `source_speakers.embedding`, `source_speakers.embedding_model`, `sources.diarization_method` |
| 048 | `person_voiceprints` table + HNSW index |
| 049 | `person_face_embeddings` table + HNSW index, `sources.video_s3_key`, `sources.video_format` |
| 050 | `source_speakers` provenance columns (audio/visual match person+score, method, confidence) |

## New files

| Path | Purpose |
|---|---|
| `services/api/app/scout/media/persistent_video.py` | Legacy/debug low-res persistent video acquisition |
| `services/api/app/scout/media/cli/persistent_video.py` | `make collect-video SOURCE_ID=…` |
| `services/api/app/analyst/diarize.py` | pyannote pipeline wrapper |
| `services/api/app/analyst/diarize_cli.py` | `make diarize SOURCE_ID=…` |
| `services/api/app/analyst/identify_voice.py` | ECAPA enroll + match |
| `services/api/app/analyst/visual_id.py` | InsightFace + Light-ASD + face-track JSON |
| `services/api/app/analyst/fusion.py` | Combine voice + visual per turn |
| `services/api/app/routers/voiceprints.py` | Enroll / list / delete voiceprints |
| `services/api/app/routers/face_embeddings.py` | Enroll / list / delete face embeddings |
| `packages/db/migrations/047_pyannote_diarization.sql` | |
| `packages/db/migrations/048_person_voiceprints.sql` | |
| `packages/db/migrations/049_person_face_embeddings.sql` | |
| `packages/db/migrations/050_speaker_match_provenance.sql` | |
| `services/web/src/app/admin/VoiceprintsPanel.tsx` | Voice enrolment + roster |
| `services/web/src/app/admin/FaceEnrollmentPanel.tsx` | Face enrolment + roster |
| `services/web/src/app/stream/[sourceId]/VideoOverlay.tsx` | Clickable face overlay over local video |

## Modified files

| Path | Change |
|---|---|
| `services/api/app/analyst/transcribe.py` | Disable Deepgram diarize. Call diarize → identify_voice → visual_id → fusion. |
| `services/api/requirements.txt` | `pyannote.audio`, `insightface`, `onnxruntime-gpu`, `Light-ASD` (vendored or pip), `torch` |
| `Makefile` | `diarize`, `collect-video`, `identify-visual`, `enroll-voice`, `enroll-face` targets |
| `packages/shared/jeromelu_shared/config.py` | `huggingface_token`, `pyannote_model`, `voice_embedding_model`, `face_model='insightface/buffalo_l'`, `asd_model='light-asd'`, `frame_sample_rate=1` |
| `services/api/app/routers/sources.py` | Surface match scores + face-track JSON URL on the stream review payload. |
| `services/web/src/app/stream/[sourceId]/SourceReviewClient.tsx` | Render `<VideoOverlay />` alongside transcript; show per-turn modality scores. |

## New dependencies

- `pyannote.audio` (diarization + ECAPA embeddings)
- `insightface` (face detection + ArcFace embeddings)
- `onnxruntime-gpu` (or CPU build for dev)
- `Light-ASD` (active speaker detection)
- `torch` (already implicit via pyannote)
- `ffmpeg` (already required for audio)

## Open decisions (call before kickoff)

1. **pyannote 3.1 vs 4.0 community-1 vs NeMo Sortformer.** Default to 3.1 (most stable). Re-evaluate after Phase 1 A/B.
2. **Voice embedding model.** Default to ECAPA-TDNN (pyannote-bundled — one dep) for Phase 3. Upgrade options if eval falls short on YouTube-compressed audio: **WavLM-large** (foundation-model-derived, more robust to mic/room variance, MIT-licensed), **NVIDIA TitaNet** (production-grade, NeMo), **3D-Speaker / CAM++** (current SOTA on VoxCeleb, Alibaba). The embedding column is sized for ECAPA (192-dim) — switching to WavLM (256-dim) or larger means a migration; budget accordingly.
3. **HuggingFace gated-model access.** pyannote requires accepting the license + a HF token. Confirm token can live in `.env` and prod secrets store.
4. **Backfill scope at Phase 2.** Re-run pyannote on every existing `extraction_method='deepgram_v1'` source, or only new ones going forward? Recommend: only new ones; re-run on demand via `force=True`.
5. **Video storage policy.** Keep low-res videos with 30-day S3 lifecycle, or always re-download at processing time? Default: keep + lifecycle. The review UI needs the local file for the overlay.
6. **OCR pass for lower-third name graphics.** Defer past Phase 5 unless an episode is found where it would unblock identification cheaply.
7. **Production compute.** Required before Phase 2 ships to prod. Out of scope here but linked.

## Future work (post-Phase 5)

- **Lexical / stylistic fingerprint as a third modality.** Audio-derived but text-grounded: TF-IDF over each host's known utterances (catchphrases, slang, references), speech-rate distribution, pause patterns, exact-match short-phrase detection. Fails on short or generic turns, but nearly free since the transcripts already exist. Useful tiebreaker when voice and face disagree.
- **Speaker-overlap-aware embedding.** For turns flagged as overlapping by pyannote, use overlap-aware embedding extractors (e.g. pyannote's overlap-aware speaker embedding head) rather than skipping them entirely.
- **Per-source mic/room calibration.** Extract a "channel signature" from a known-clean span at the start of each episode; subtract it from per-turn embeddings before matching. Reduces false negatives when the same host moves studios.

## Autonomous bootstrap and annotation

Phase 5 (cross-modal compounding) is the autonomous loop, but it depends on at least one bootstrap signal in either registry to start. This section enumerates the bootstrap and annotation paths that don't require a human at annotation time. They're complementary — building any combination further reduces the human-in-the-loop role from "label every misattribution" to "audit the system and correct residual edge cases".

### Layer 1 — Phase 5 compounding (planned, captured above)

Once *anything* is in either registry, voice + face cross-modal agreement promotes itself. See [Phase 5](#phase-5--cross-modal-compounding-3-days) above. This is the autonomous loop; layers 2–5 below are non-human ways to seed it.

### Layer 2 — Headshot scraping (cheap, high leverage)

`person_face_embeddings.created_by` already supports `'headshot'`; the scraper is unbuilt. Concept: take a Person's name, find a public photo (channel banner, news article, public profile), run it through `enroll_face_from_image`, persist with `created_by='headshot'`. One-time per host, no human at annotation time.

Combined with Phase 5: the scraped headshot identifies the host on first appearance, and voice embeddings auto-promote from the high-confidence visual matches. This converts "first episode is unattributed" into "first episode is attributed in the visual-only / voice-bootstrapped state".

Open: which sources are licensable for scraping; how to handle stale photos (host changed appearance — covered partially by append-only growth, but a strict-newest-N policy may be wanted).

### Layer 3 — Channel presenters as priors (presenter-scout Phase 3, planned)

[presenter-scout.md](../agents/system/presenter-scout.md) curates `(channel_id, person_id)` confirmations agentically. Presenter-scout's own Phase 3 (planned) feeds those into Lineup as the channel's expected roster — lowering match thresholds for in-roster Persons and short-circuiting first-appearance enrollment when a headshot exists.

This is the obvious cross-link between two surfaces; both half-done. Wiring is the only blocker.

### Layer 4 — LLM-driven transcript annotation (unbuilt)

The Deepgram transcript already names hosts during intros and outros — *"What's up everyone, this is Denan from Bloke In A Bar."* / *"Joined today by Tyson Jackson and Blake Austin."* / *"That was Denan's take, what do you reckon Tyson?"*

A small-LLM pass over the first/last 60 seconds of each transcript could:

1. Detect self-identification or peer-naming patterns.
2. Match each name to the channel's known presenter list (from presenter-scout) or the `people` registry — high precision because the candidate set is tiny.
3. Identify which `SPEAKER_NN` was speaking or being addressed by joining Deepgram word timestamps to pyannote turn boundaries.
4. Insert voice embeddings (and optionally face embeddings from corresponding video frames) with `created_by='auto-llm'` (a new provenance value to add).

Cost: one LLM call per episode, scoped to ~120 s of audio. Probably <$0.01 per source.

Strong candidate for the next built phase after Phase 5 — the LLM is reading data already produced, the candidate set is naturally constrained, and the failure mode (a wrong name → bad embedding) is voted down by the registry-side robustness machinery rather than poisoning future matches.

Schema impact: extend the `created_by` enum to include `'auto-llm'` so post-hoc auditing can distinguish human-confirmed from LLM-confirmed.

### Layer 5 — Cross-source clustering (unbuilt)

When N episodes of a channel are processed without enrollments, pyannote produces N independent SPEAKER_NN labels per source. Across episodes, the same actual host appears repeatedly. Cosine-clustering the per-turn embeddings across all episodes of one channel agglomerates them — the largest clusters are regular hosts, smaller clusters are guests, singletons are noise.

Match the largest clusters against the channel's known presenters (from presenter-scout, or LLM annotations from Layer 4) and auto-enroll each cluster as a Person.

Cost: bigger lift than Layer 4 (a clustering pipeline + cluster-to-Person matching logic), but it bootstraps an entire channel from a folder of audio + a list of host names with zero human annotation.

### What humans still own

Even with all five layers:

- **Curation of `people`.** Name canonicalisation, identity disambiguation across podcasts. Ontology problem, not annotation.
- **Edge-case correction.** Guests, side conversations, audio cameos. Phase 4b-action handles these. Active-learning surfacing (lowest-confidence turns first) would compound the savings.
- **Auditing auto-enrolled embeddings.** `created_by` provenance enables retroactive cleanup if a layer turns out noisy. Append-only registries mean pruning bad rows is a separate operator workflow — useful for layers with imperfect precision.

### Recommended sequencing

If the goal is fastest path to "human-in-the-loop is just an audit, not a labelling job":

1. **Headshot scraper (Layer 2)** — cheapest, most leveraged. One-time per host.
2. **Wire presenter-scout Phase 3 priors into Lineup (Layer 3)** — already designed, needs hooking up.
3. **LLM transcript annotator (Layer 4)** — one new model integration; high signal-to-noise.
4. **Phase 5 compounding** (already in plan) — closes the loop with all the above feeding it.
5. **Cross-source clustering (Layer 5)** — bigger lift, lower marginal value once 1–4 are in.

## Risks

- **Pyannote turns won't perfectly align with Deepgram utterances.** Edge case: an utterance straddling a turn boundary. Mitigation: max-overlap assignment; track unassigned chunks in a metric.
- **Voice embedding drift.** Same person in different rooms / mics / hat. Mitigation: multiple voiceprints per person; nearest-of-many match.
- **Face embedding drift.** Hairstyle / lighting / age. Same mitigation.
- **B-roll false positives.** A highlight reel will visually-identify a player not present. Mitigation: ASD threshold; B-roll fails because audio-face sync is broken.
- **YouTube ToS.** Storing video isn't ideal. The 240p + 30-day lifecycle policy keeps the footprint conservative; the alternative is on-demand re-download at view time.
- **YouTube compression artifacts at 240p.** May degrade face match for guests viewed from the side. Mitigation: bump to 360p if eval shows it.

## Success criteria

- The transcript at `localhost:3000/stream/e276d3fc-d3bc-4703-9b45-b0552ff94762` shows ≥3 distinct speakers, each turn labelled with the actual host name, ≥80% auto-resolved on first run.
- The video overlay correctly labels the speaking face ≥85% of frames during clear single-speaker turns.
- Manual reassignment in the overlay UI measurably improves the next episode's hit rate.

## Documentation Updates

- **NEW `docs/agents/system/speaker-identification.md`** — full surface doc: voice + visual + fusion, hand-off contract, running, backlog. Mirrors the shape of `transcription-pipeline.md`.
- **NEW `docs/operations/identification-runbook.md`** — operator runbook: how to enroll a host (face + voice), how to clean up bad embeddings, threshold tuning, format heuristic interpretation.
- **`docs/agents/system/transcription-pipeline.md`** — rewrite "What it does" steps 3–5 to reflect Deepgram-without-diarize. Move "Speaker → Person resolution" out of Backlog into the active pipeline. Reference migrations 047–050.
- **`docs/agents/crew/analyst.md`** — add Identification surface alongside Transform.
- **`docs/agents/system/ingestion.md`** — Scout now acquires video alongside audio; document the new path and S3 lifecycle rule.
- **`docs/sources/extraction-method.md`** — extraction method labels evolve: `deepgram_words+pyannote_v1` → `…+visual_v1` after Phase 4.
- **`docs/vision/02-the-show.md`** — update data-flow diagram if it references Deepgram diarize.
- **`docs/operations/data-catalogue/`** — add `person_voiceprints.md` and `person_face_embeddings.md`; update `source_speakers.md` provenance columns and `sources.md` (`video_s3_key`, `video_format`); link them from `README.md`.
- **`README.md`** — bump deps note (HF token, ffmpeg, onnxruntime). Add `make diarize`, `make collect-video`, `make enroll-voice`, `make enroll-face` to dev cheatsheet.

## Related

- [Transcription (Analyst's first Transform)](../agents/system/transcription-pipeline.md) — predecessor surface this plan extends.
- [Analyst (crew)](../agents/crew/analyst/README.md)
- [Ingestion (Scout)](../agents/system/ingestion.md) — gains the video acquisition step.
- [Migration 044](../../packages/db/migrations/044_audio_first_extract.sql), [045](../../packages/db/migrations/045_split_ingestion_transcription.sql), [046](../../packages/db/migrations/046_chunk_paragraph_break.sql) — current schema.

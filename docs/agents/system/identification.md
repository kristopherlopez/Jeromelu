---
tags: [area/agents, subarea/system, status/live]
---

# Speaker Identification (Voice + Visual Fusion)

| | |
|---|---|
| **Modules** | `services/api/app/analyst/identify_voice.py` (voice enroll + match), `services/api/app/analyst/visual_id.py` (face detect + match), `services/api/app/analyst/fusion.py` (cross-modal vote), CLIs in `enroll_voice_cli.py` / `enroll_face_cli.py` |
| **Driver** | Enrollment via `make enroll-voice` / `make enroll-face`. Identification + fusion run inline inside `make transcribe`. |
| **ETL role** | **Transform.** Populates `source_speakers.speaker_person_id`, `match_method`, `match_confidence` plus the per-modality provenance columns (`audio_match_*`, `visual_match_*`). |
| **Cost** | Voice: ~10 s of CPU per enrollment span; matching is sub-second per source (in-memory). Visual: ~7 min CPU per 45-min video at 1 fps (face detection on every frame). With Phase 5.5 remote GPU enabled, both pyannote diarization and visual ID move to a SageMaker Async endpoint — ~$0.13/source compute, scale-to-zero idle, ~10–15 min total wall time. |
| **Status** | Phase 3 (voice) live; Phase 4a (visual + fusion) live; Phase 4-asd (mouth-opening ASD) live; Phase 4b-display (review UI overlay) live; Phase 5.5 (remote GPU on SageMaker Async) live. Click-to-reassign (Phase 4b-action) and cross-modal compounding (Phase 5) remain. |

> **Single-cam caveat:** mouth-opening ASD is the current precision-floor (76.7 % vs 55.4 % without it on the test source) but not a substitute for a real audio-sync ASD model. Reaction-shot false positives (smiling at someone else's joke, laughing during their monologue) survive — `voice+face` is still the most trustworthy subset.

---

## What it does

The module is two parallel matchers + a fuser:

```
voice embeddings (Phase 2)  ──┐
                              │
                              ├─> identify_voice  ──┐
                              │                    │
                              │                    ├─> fusion ──> source_speakers
                              │                    │              .speaker_person_id
video frames @ 1 fps        ──┤                    │              .match_method
                              │                    │              .match_confidence
                              ├─> visual_id     ───┘              + audio_match_* / visual_match_*
                              │   (face detect +
                              │    arcface + k-NN)
                              │
                              └─> face_track JSON ──> S3 (Phase 4b UI consumes)
```

### Voice enrollment — `enroll(person_id, source_id, start_ts, end_ts, created_by)`

1. Validate the span (must be ≥ `MIN_TURN_DURATION` 0.3 s, recommended ≥ `SOFT_MIN_ENROLLMENT_DURATION` 10 s).
2. Download the source audio from S3, ffmpeg-convert to 16 kHz mono WAV.
3. Generate sliding windows (2 s window, 0.5 s hop) over the span.
4. Embed each window with `pyannote/wespeaker-voxceleb-resnet34-LM` (256-dim).
5. Reject NaN/inf windows.
6. Insert one `person_voiceprints` row per valid window. `created_by='manual'` for operator enrollment, `'auto-confirmed'` for Phase 5 cross-modal compounding.

### Voice identification — `identify_pyannote_turns(session, pyannote_doc)`

1. Load the entire voiceprint matrix into memory once (typically <1 MB while the registry is small; switch to pgvector HNSW server-side k-NN at Phase 5+ scale).
2. For each pyannote turn's `embedding_windows` list:
   - Drop windows that are non-finite or wrong-dimensional.
   - Cosine-similarity-match each remaining window against the full voiceprint matrix in one matrix multiply.
   - For each window, take its single nearest voiceprint. Tally votes per Person, gated by `cosine_threshold` (default 0.75) — windows below threshold don't vote.
   - Pick the Person with the most votes; tiebreak by max similarity.
   - Commit the assignment if `votes / total_windows ≥ agreement_threshold` (default 0.6).
3. Return one `IdentifyResult | None` per turn. `transcribe.py` writes the matched `person_id` to `source_speakers.speaker_person_id` and the max similarity to `source_speakers.confidence`.

The matching is per-window with majority-vote rather than per-turn-medoid because a single noisy second can poison the medoid; per-window voting tolerates 30–40 % bad windows without misidentifying the turn.

### Face enrollment — `enroll_face_from_image(person_id, source_id, image_path, frame_ts)`

1. Decode the image (cv2). For video-frame mode the CLI ffmpeg-extracts a single JPEG at the requested timestamp from `sources.video_s3_key` first.
2. Run InsightFace `buffalo_l` — RetinaFace + ArcFace bundle. Pick the largest detected face (by bbox area).
3. Reject NaN/inf embeddings or wrong-dim outputs.
4. Insert one `person_face_embeddings` row (512-dim ArcFace).

`created_by` provenance: `manual` (operator), `headshot` (scraped reference photo), `auto-confirmed` (Phase 5 promotion).

### Visual identification — `visual_identify(audio_s3_key, video_s3_key, pyannote_turns)`

1. **Reuse path**: if a face-track JSON of the current `FACE_TRACK_JSON_VERSION` already exists for this source, skip extraction and re-vote against the persisted frame data. Used for tuning the per-turn vote logic without paying the ~30 min CPU extraction cost. To force re-extract: delete the JSON or bump the version.
2. Otherwise: download video, sample frames at `FRAME_SAMPLE_RATE` (default 1 fps) via cv2.
3. Run InsightFace on each frame — multi-face detection + 512-dim embeddings + det_score + `landmark_3d_68`.
4. For each detected face, k-NN-match against the in-memory face registry (cosine threshold default 0.40, permissive).
5. Compute `mouth_opening` per face — inner-lip distance from 3d68 indices 62/66, normalised by face-bbox height. The ASD signal.
6. Detect the source's `video_format`: face-change-rate ≥ 0.10 → `multi_cam`, < 0.05 → `single_cam`, otherwise default `multi_cam`. Stored on `sources.video_format`.
7. Persist a face-track JSON to S3 alongside the pyannote JSON (drops embeddings, keeps bbox + matched person_id + similarity + mouth_opening).
8. Aggregate per pyannote turn — see [Per-turn vote with ASD](#per-turn-vote-with-asd) below.

### Per-turn vote with ASD

For each pyannote turn span:

- For each frame in span, `_select_active_face` picks the face with the largest `mouth_opening`, provided the value clears `MIN_ACTIVE_MOUTH_OPENING` (default 0.045) AND beats the runner-up by `ACTIVE_FACE_MARGIN` (0.005). Frames with no active face contribute nothing.
- **Density gate**: at least `MIN_ACTIVE_FRACTION` (0.30) of in-span frames must yield an active face. Below that → no match. The actual speaker's mouth-open rate sits at 30–45 %; listeners' is 10–25 %.
- **No fallback to face-presence**: earlier versions fell back to "any matched face in span" when ASD didn't pick anyone, but that re-introduced single-cam false positives. Without an active mouth, the visual modality stays silent and downstream fusion falls back to voice-only.
- Among active faces, vote by `person_id`; require `agreement_threshold` (0.60). With one host enrolled all votes are unanimous so the gate is moot, but it'll matter once 2+ hosts are enrolled.

### Fusion — `fuse_per_turn(audio_pid, audio_score, visual_pid, visual_score)`

| voice match | face match | result |
|---|---|---|
| Person X | Person X | `voice+face`, confidence = avg of scores |
| Person X | NULL | `voice`, confidence = audio_score |
| NULL | Person X | `face`, confidence = visual_score |
| Person X | Person Y | NULL (disagreement, flagged for review) |
| NULL | NULL | NULL |

Disagreement falls through to NULL on purpose: when the modalities conflict we don't know which one to trust. Phase 5 will weight by historical accuracy.

---

## Hand-off contract

| Table | Fields written | Fields left for later passes |
|---|---|---|
| `person_voiceprints` | `person_id`, `source_id`, `start_ts`, `end_ts`, `embedding`, `embedding_model`, `created_by` | — |
| `person_face_embeddings` | `person_id`, `source_id`, `frame_ts`, `embedding`, `embedding_model`, `created_by` | — |
| `source_speakers` | `audio_match_person_id` + `audio_match_score`, `visual_match_person_id` + `visual_match_score`, `match_method`, `match_confidence`, `speaker_person_id`, `confidence` (legacy) | — |
| `sources` | `video_format` (auto-detected: `multi_cam` / `single_cam` / `audio_only`) | — |

Identification is **idempotent** — re-running `make transcribe FORCE=1` recomputes assignments using the current voiceprint registry. New enrollments improve next-run accuracy without any backfill step.

---

## Running

```bash
# 1. Enroll a host's voice. Recommended span: ≥10s of clean monologue,
#    2-3 non-contiguous spans per Person for acoustic variation.
make enroll-voice \
    PERSON_ID=<person-uuid> \
    SOURCE_ID=<source-uuid> \
    START_TS=91.97 \
    END_TS=166.98

# 2. Acquire the low-res video for visual ID (~25s for a 45min source).
make collect-video SOURCE_ID=<source-uuid>

# 3. Enroll the host's face from a frame where they're clearly visible.
make enroll-face \
    PERSON_ID=<person-uuid> \
    SOURCE_ID=<source-uuid> \
    FRAME_TS=120

# 4. Re-transcribe to apply both modalities + fusion. Pyannote artefact
#    is reused (no 40min re-run); only Deepgram + visual ID + DB writes
#    redo. Visual ID adds ~7 min CPU per 45 min of video.
make transcribe SOURCE_ID=<source-uuid> FORCE=1
```

Expected transcribe output (with one host enrolled):
```
turns_recorded:     678
turns_identified:   157     ← combined voice + face
  voice_match:       14
  visual_match:     157
  voice+face:        14     ← dual-modality, highest confidence
  disagreements:      0
video_format:       single_cam
```

---

## Tuning thresholds

The defaults (cosine ≥ 0.75 per window, ≥ 60 % window agreement) are conservative — high precision, modest recall. Adjustments:

- **Higher recall** (more turns identified): drop `DEFAULT_COSINE_THRESHOLD` to 0.70 or 0.65. Expect more false positives from acoustically similar speakers (same accent, same room).
- **Higher precision** (fewer false positives): raise `DEFAULT_COSINE_THRESHOLD` to 0.78 + raise `DEFAULT_AGREEMENT_THRESHOLD` to 0.7 or set `DEFAULT_MIN_WINDOWS` to 2 (kills single-window-fluke matches on short turns).
- **Per-source recovery** (a host with mic/room drift): enroll multiple non-contiguous spans across episodes; nearest-of-many handles drift naturally.

S-norm score normalisation is mentioned in the plan as a future enhancement — not yet implemented. The flat 0.75 threshold is fine while the registry is small and recordings come from a small studio set.

---

## Quality gates

Embedded into both enrollment and matching, in order of importance:

1. **Sub-300 ms turns are skipped at diarization time** ([transcription.md](transcription.md)). They have NULL embeddings and never participate.
2. **NaN/inf embeddings are dropped at every layer**: extraction (`diarize.py`), pre-write (`transcribe.py` `_safe_embedding`), pre-match (`identify_voice.identify_pyannote_turns`), and the threshold check itself uses `math.isfinite` to defend against `NaN < 0.75` returning False.
3. **Sub-`MIN_TURN_DURATION` enrollment spans are hard-rejected.** Spans below `SOFT_MIN_ENROLLMENT_DURATION` (10 s) log-warn but proceed.

---

## Remote vs local inference (Phase 5.5)

Lineup runs locally by default. To use the SageMaker Async endpoint instead:

1. One-time AWS setup per [services/gpu/SETUP.md](../../../services/gpu/SETUP.md) — ECR repo, IAM role, `.env` config additions.
2. Build + push the GPU container: `make lineup-build` (uses `HUGGINGFACE_API_KEY` as a Buildkit secret to bake model weights).
3. Deploy: `make lineup-deploy`. First deploy takes ~5–10 min while SageMaker provisions the `ml.g4dn.xlarge` instance and pulls the image; subsequent deploys roll forward.
4. Set `LINEUP_REMOTE=1` in `.env` and `make transcribe SOURCE_ID=… FORCE=1`. The CLI prints `[Lineup remote] diarize submitted → s3://…` and end-to-end runs complete in ~10–15 min instead of ~50 min.

The artefact contracts are unchanged — the GPU container imports the same `app.analyst.diarize` / `app.analyst.visual_id` modules and writes the same S3 keys, so downstream code (transcribe.py merge, fusion, review UI) is oblivious to where inference ran.

To stop iterating, `make lineup-delete` tears down the endpoint. The model + endpoint config remain (negligible cost); re-create the endpoint with another `make lineup-deploy`.

## Backlog

- **Real audio-sync ASD model.** The mouth-opening heuristic gets us from 55 % → 77 % visual precision but misses reaction-shot false positives (laughing during someone else's monologue still passes the density gate). A model that takes face crops + audio mel-spectrograms and predicts speaking probability (Light-ASD, TalkNet, LoCoNet) would close the remaining gap. None are pip-packaged — they'd need vendoring.
- **Phase 4b — review-UI overlay.** Clickable face boxes over the locally-stored video, with per-turn `match_method` colour-coding. Doubles as the manual override surface (click → reassign → write face + voice embeddings).
- **Phase 5 — cross-modal compounding.** Periodic job that promotes high-confidence `voice+face`-agreement turns into the registries with `created_by='auto-confirmed'`. The mechanism that turns "85 % on day 1" into "95 %+ over six months" without human work.
- **S-norm calibration** — per-source impostor cohort to normalise similarity scores across episodes recorded in different rooms.
- **Voice sliding-window weighting** — currently all windows in a turn vote with equal weight. Weighting by the dominant utterance's pyannote confidence would penalise low-quality windows.
- **Admin enrollment endpoints** — REST endpoints behind `X-Admin-Key`, plus admin-panel UIs. Today it's CLI-only for both modalities.
- **Higher detection resolution** — InsightFace `det_size` is 640 by default; bumping to 1024 catches more profile/distant faces at ~3× latency cost.

---

## Related

- [Transcription (Phase 2)](transcription.md) — predecessor surface that produces the per-turn embeddings this surface matches against.
- [Speaker Identification plan](../../todo/speaker-identification.md) — Phase 1–5 roadmap.
- [Migration 047](../../../packages/db/migrations/047_pyannote_diarization.sql) (voice embeddings on `source_speakers`), [048](../../../packages/db/migrations/048_person_voiceprints.sql) (voiceprint table), [049](../../../packages/db/migrations/049_person_face_embeddings.sql) (face registry), [050](../../../packages/db/migrations/050_speaker_match_provenance.sql) (per-modality provenance + video columns).

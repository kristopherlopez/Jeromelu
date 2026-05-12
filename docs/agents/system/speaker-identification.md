---
tags: [area/agents, subarea/system, status/live]
---
# Speaker Identification (Voice + Visual Fusion)

## Purpose

Podcast transcripts come back from diarization as anonymous turn labels — `SPEAKER_00`, `SPEAKER_01`, etc. Speaker Identification attaches a real `Person` (e.g. *Denan Kemp*) to each spoken turn, so transcripts read like a conversation between named hosts rather than unattributed voices.

That attribution is what lets the rest of the system answer questions like *"What did Denan say about Cleary?"* — opinions, predictions, and claims become traceable to the person who voiced them. Without it, every downstream surface (the wiki, claim extraction, consensus tracking, the ledger) would have to operate on anonymous speaker labels, which is the same as no attribution at all.

## What it produces

For each pyannote turn in `source_speakers`, this layer fills in:

- `speaker_person_id` — the matched `Person`, when one was found
- `match_method` — `voice`, `face`, `voice+face`, `manual`, or NULL
- `match_confidence` — score on the matched modality (averaged when both modalities agreed)
- `audio_match_*` and `visual_match_*` — per-modality provenance (which Person each modality voted for, score) so disagreements stay inspectable

Plus a **face-track JSON** in S3 — the artefact the review-UI overlay renders on top of the YouTube player.

Concrete before / after on one podcast turn:

```
Before:  SPEAKER_00 (45.2s – 51.8s): "Cleary's a top-three buy this week."
After:   Denan Kemp (45.2s – 51.8s): "Cleary's a top-three buy this week."
                                      [match_method=voice+face, confidence=0.91]
```

The system improves itself over time: every operator confirmation and every high-confidence cross-modal agreement grows the registries (`person_voiceprints`, `person_face_embeddings`), so the next episode auto-resolves more turns without manual work.

## At a glance

| | |
|---|---|
| **Modules** | `services/api/app/analyst/identify_voice.py` (voice enroll + match), `services/api/app/analyst/visual_id.py` (face detect + match), `services/api/app/analyst/fusion.py` (cross-modal vote), CLIs in `enroll_voice_cli.py` / `enroll_face_cli.py` |
| **Driver** | Enrollment via `make enroll-voice` / `make enroll-face`. Identification + fusion run inline inside `make transcribe`. |
| **ETL role** | **Transform.** Populates `source_speakers.speaker_person_id`, `match_method`, `match_confidence` plus the per-modality provenance columns (`audio_match_*`, `visual_match_*`). |
| **Cost** | Voice: ~10 s of CPU per enrollment span; matching is sub-second per source (in-memory). Visual: ~7 min CPU per 45-min video at 1 fps (face detection on every frame). With Phase 5.5 remote GPU enabled, both pyannote diarization and visual ID move to a SageMaker Async endpoint on `ml.g5.xlarge` (A10G) — ~$0.13 GPU + ~$0.001 cross-region S3 + $0.30 Deepgram = **~$0.43/source**, scale-to-zero idle, **~3 min total wall time**. |
| **Status** | Phase 3 (voice) live; Phase 4a (visual + fusion) live; Phase 4-asd (mouth-opening ASD) live; Phase 4b-display (review UI overlay) live; Phase 4b-action (click-to-reassign) live; Phase 5.5 (remote GPU on SageMaker Async, `us-east-1`) live. Cross-modal compounding (Phase 5) remains. |

> **Single-cam caveat:** mouth-opening ASD is the current precision-floor (76.7 % vs 55.4 % without it on the test source) but not a substitute for a real audio-sync ASD model. Reaction-shot false positives (smiling at someone else's joke, laughing during their monologue) survive — `voice+face` is still the most trustworthy subset.

## Technology stack

| Layer | Technology | Role |
|---|---|---|
| Turn segmentation | `pyannote/speaker-diarization-3.1` | Splits audio into per-turn spans. The atomic unit everything else attributes to. |
| Voice embedding | `pyannote/wespeaker-voxceleb-resnet34-LM` (256-dim) | One vector per 2-second sliding window inside a turn — the voice fingerprint. |
| ASR (transcription) | Deepgram `nova-3` | Words + timestamps + paragraph breaks. Separate surface — see [transcription-pipeline.md](transcription-pipeline.md). |
| Face detection + embedding | InsightFace `buffalo_l` — RetinaFace detector + ArcFace 512-dim embedder + `landmark_3d_68` | Detects faces in 1 fps video frames, extracts an embedding per face, and provides 3D facial landmarks for active-speaker detection. |
| Active-speaker detection | Mouth-opening heuristic over 3D landmarks (no model) | Picks the *speaking* face when multiple are visible. Phase 4-asd. Real audio-sync ASD models (Light-ASD, TalkNet) are on the backlog. |
| Storage — registries | Postgres + pgvector — `person_voiceprints` (256d), `person_face_embeddings` (512d) | Per-Person voice and face vectors that grow over time. |
| Storage — provenance | Postgres — `source_speakers.audio_match_*` / `visual_match_*` / `match_method` / `match_confidence` / `speaker_person_id` | Per-turn record of how each match was made. |
| Object storage | S3 — `ap-southeast-2` (durable artefacts) + `us-east-1` (SageMaker async staging) | Raw audio, ephemeral video, pyannote JSON, face-track JSON. |
| Remote GPU inference (Phase 5.5) | SageMaker Async, `ml.g5.xlarge` (A10G), `us-east-1` | Hosts pyannote + InsightFace; toggled by `LINEUP_REMOTE=1`. ~3 min wall time vs ~50 min CPU. |
| Review UI overlay | Next.js + canvas-on-iframe (`services/web/src/app/components/YouTubeFaceOverlay.tsx`) | Draws colour-coded face boxes on the YouTube player using the face-track JSON. |

## Where it sits in the pipeline

The Transcription stage runs **two parallel branches** on the same audio: pyannote diarization (turn segmentation + voice embeddings) and Deepgram nova-3 (transcript text). Speaker Identification depends on **pyannote and the video stream** — not Deepgram.

```
audio (Scout)  ─┬─> pyannote ───────────> turns + 256-dim voice embeddings  ──┐
                │                                                              │
                └─> Deepgram nova-3 ────> words → source_chunks (text)        │  ← not consumed
                                                                               │
video (Scout)  ────> InsightFace @ 1 fps > face detections + 512-dim embeds  ─┤
                                                                               │
                                                                               ▼
                                                              Speaker Identification
                                                              (voice + face + fusion)
                                                                               │
                                                                               ▼
                                                              Knowledge Extraction
                                                              (claims, quotes, consensus)
```

- **Direct inputs:** pyannote's per-turn voice embeddings (`source_speakers.embedding`) **and** 1 fps video frames. Both are required for full coverage; either alone produces partial attribution.
- **Not an input:** Deepgram's text. Speaker Identification would still populate `speaker_person_id` correctly with Deepgram disabled — you'd just have no readable transcript text to attribute *to*. Deepgram and Speaker ID are parallel: they fill different columns on the same source.
- **Predecessor:** [Transcription](transcription-pipeline.md) — owns both audio branches (pyannote + Deepgram) and the merge that creates the `source_speakers` and `source_chunks` rows. Speaker ID reads from `source_speakers` and writes back to it.
- **Priors source:** [Presenter Scout](presenter-scout.md) — curates *which* hosts are confirmed for a channel, giving Identification a starting roster before manual enrollment is needed (presenter-scout Phase 3, planned).
- **Consumers:**
  - The in-app stream viewer's face overlay (`YouTubeFaceOverlay.tsx`) — reads the face-track JSON live.
  - Claim extraction + the wiki — attribute opinions and predictions to the named `Person` rather than a `SPEAKER_NN` label.
  - The ledger — tracks per-host prediction accuracy over time, only meaningful with attribution.

## Concepts

| Term | Meaning |
|---|---|
| **Turn** | A continuous span where one speaker is talking, as segmented by pyannote diarization. The atomic unit Identification attributes to. Stored as one `source_speakers` row. |
| **Voiceprint** | A 256-dim voice embedding from a known host's enrolled audio. Each enrollment span yields many — a sliding-window stack. Stored in `person_voiceprints`. |
| **Face embedding** | A 512-dim ArcFace vector from a known host's face. Stored in `person_face_embeddings`. |
| **ASD (Active Speaker Detection)** | Deciding which of several visible faces is speaking *right now*. We use a mouth-opening heuristic; model-based ASD is on the backlog. |
| **Match method** | How a turn was attributed: `voice` (audio only), `face` (visual only), `voice+face` (both modalities agreed — highest auto confidence), `manual` (operator-confirmed via cluster bulk-assign — highest overall confidence), NULL (no match, or modalities disagreed). Stored on `source_speakers.match_method`. Drives the review-UI overlay colour: green = `voice+face`, amber = `face`, blue = `voice` or face/voice disagreement, **purple = `manual`**, grey = NULL / unmatched. |
| **Fusion** | The cross-modal vote that combines per-turn voice and face matches into a single `speaker_person_id`. See the [Fusion](#fusion--fuse_per_turnaudio_pid-audio_score-visual_pid-visual_score) table in [How it works](#how-it-works). |
| **Lineup** | The internal / code name for this surface (voice + face + fusion). Surfaces in `LINEUP_REMOTE`, `services/gpu/`, the phase ledger. The operator-facing name is *Speaker Identification*. |

---

## How it works

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

1. Decode the image (cv2). For video-frame mode the CLI ffmpeg-extracts a single JPEG at the requested timestamp. Source video acquisition: either `sources.video_s3_key` (legacy persistent path) or, when null, an on-demand yt-dlp via `video_staging.staged_video_local` against `sources.canonical_url`.
2. Run InsightFace `buffalo_l` — RetinaFace + ArcFace bundle. Pick the largest detected face (by bbox area).
3. Reject NaN/inf embeddings or wrong-dim outputs.
4. Insert one `person_face_embeddings` row (512-dim ArcFace).

`created_by` provenance: `manual` (operator), `headshot` (scraped reference photo), `auto-confirmed` (Phase 5 promotion).

### Visual identification — `visual_identify(audio_s3_key, video_s3_key, pyannote_turns)`

`video_s3_key` here may be either a persistent key (legacy `sources.video_s3_key`) or a per-request **staging key** under `staging/video/` — the contract is unchanged from `visual_identify`'s perspective. Lifetime management is the caller's job: `transcribe.py` wraps the call in `video_staging.staged_video(...)`, which yt-dlps + uploads on entry and deletes the staging object on exit. See [Video lifecycle](#video-lifecycle).

1. **Reuse path**: if a face-track JSON of the current `FACE_TRACK_JSON_VERSION` already exists for this source, skip extraction and re-vote against the persisted frame data. Used for tuning the per-turn vote logic without paying the ~30 min CPU extraction cost. To force re-extract: delete the JSON or bump the version.

   > **Registry-cleanup gotcha.** The JSON persists matched `person_id` per face but drops the underlying embeddings (the dimensionality reduction is intentional — see [Video lifecycle](#video-lifecycle)). After deleting a Person's embeddings from `person_voiceprints` / `person_face_embeddings`, every face-track JSON that previously matched that Person will continue to attribute those frames to them on re-transcribe — the matcher never re-runs against the cleaned registry. **Always purge affected face-track JSONs (or bump `FACE_TRACK_JSON_VERSION`) as part of any registry cleanup.** Confirmed empirically 2026-05-10: after deleting a stale test-fixture Person's embeddings, a re-transcribe still re-attributed 76 face turns to that Person from the cached JSON; only after purging the JSON did fresh extraction attribute them correctly.
2. Otherwise: download video, sample frames at `FRAME_SAMPLE_RATE` (default 1 fps) via cv2.
3. Run InsightFace on each frame — multi-face detection + 512-dim embeddings + det_score + `landmark_3d_68`.
4. For each detected face, k-NN-match against the in-memory face registry (cosine threshold default 0.40, permissive).
5. Compute `mouth_opening` per face — inner-lip distance from 3d68 indices 62/66, normalised by face-bbox height. The ASD signal.
6. Detect the source's `video_format`: face-change-rate ≥ 0.10 → `multi_cam`, < 0.05 → `single_cam`, otherwise default `multi_cam`. Stored on `sources.video_format`.
7. Persist a face-track JSON to S3 alongside the pyannote JSON (drops embeddings, keeps bbox + matched person_id + similarity + mouth_opening + source `frame_width`/`frame_height` so the review-UI overlay can scale bboxes onto whatever surface it's drawing over). Schema: `FACE_TRACK_JSON_VERSION = 4`.
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
| `source_face_detections` (Slice B) | per-detection `bbox`, `det_score`, `embedding`, `embedding_model`, `mouth_opening`, `matched_person_id`, `match_score` | `cluster_id` populated by the per-source clustering pass (Slice B PR 2) |
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

# 2. Enroll the host's face from a frame where they're clearly visible.
#    `make enroll-face` will yt-dlp the video on-demand if it isn't cached
#    locally — no `make collect-video` step needed.
make enroll-face \
    PERSON_ID=<person-uuid> \
    SOURCE_ID=<source-uuid> \
    FRAME_TS=120

# 3. Re-transcribe to apply both modalities + fusion. Pyannote artefact
#    is reused (no 40min re-run); only Deepgram + visual ID + DB writes
#    redo. Visual ID adds ~7 min CPU per 45 min of video; the video file
#    itself is acquired via yt-dlp into a staging S3 key and deleted
#    after visual_identify returns (see Video lifecycle).
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

1. **Sub-300 ms turns are skipped at diarization time** ([transcription-pipeline.md](transcription-pipeline.md)). They have NULL embeddings and never participate.
2. **NaN/inf embeddings are dropped at every layer**: extraction (`diarize.py`), pre-write (`transcribe.py` `_safe_embedding`), pre-match (`identify_voice.identify_pyannote_turns`), and the threshold check itself uses `math.isfinite` to defend against `NaN < 0.75` returning False.
3. **Sub-`MIN_TURN_DURATION` enrollment spans are hard-rejected.** Spans below `SOFT_MIN_ENROLLMENT_DURATION` (10 s) log-warn but proceed.

---

## Lifecycle and maturation

The accuracy of this surface is not a property of the matching algorithm — it's a property of `person_voiceprints` and `person_face_embeddings`. Both registries grow append-only over time, by three distinct mechanisms (human enrollment, human correction, automatic compounding). This section captures how that happens, what's deliberately left out, and how to observe maturation in flight.

### Human-in-the-loop — three roles

Speaker Identification has no learned classifier; it has a reference library, and the library only exists because humans seed and correct it.

**1. Bootstrap.** Without manual enrollment, both registries are empty and every turn writes NULL to `speaker_person_id`. `make enroll-voice` and `make enroll-face` are the only entry points to populate the registries — ~10 s of audio per host, one frame per host. Until at least one host is enrolled, there is nothing to match against.

**2. Correction (Phase 4b-action — shipped 2026-05-05).** The review-UI overlay shows colour-coded face boxes per turn; clicking a mis-attributed face opens a Person picker, and on save the system extracts new voice and face embeddings from that turn and inserts them into the registries with `created_by='manual'`, plus corrects `speaker_person_id`. A single correction therefore (a) fixes the current turn, (b) adds new exemplars *in the conditions where matching just failed*, (c) improves all future episodes recorded under similar conditions. Full sequence: see [Manual reassign](#manual-reassign) below.

**3. Compounding (Phase 5 — planned).** Once humans have seeded enough high-confidence exemplars, a periodic job auto-promotes turns with `match_method = 'voice+face'` and high per-modality scores. The voice and face embeddings from those turns are inserted with `created_by='auto-confirmed'`. This grows both registries simultaneously — a host originally only voice-enrolled gets a face embedding the first time they appear on camera and voice agrees. Phase 5 is what turns the loop from "human-corrects-each-mistake" into "humans-correct-edge-cases".

The `created_by` enum (`manual` · `headshot` · `auto-confirmed`) records provenance per row. All three vote equally at match time today; future tooling could weight by trust.

### How the registries mature

**Voice (`person_voiceprints`).** Each enrolled span yields ~17 rows per 10 seconds of audio (sliding 2 s window, 0.5 s hop). New spans — manual, corrected, or auto-confirmed — append more rows. What this buys at match time:

- *More votes per turn.* The matcher requires `votes / total_windows ≥ 0.6`. With dozens of voiceprints per Person, one noisy second only dilutes one vote out of many. Robustness scales with registry size.
- *Coverage across conditions.* Different rooms, different mics, different days, different vocal states (sick, tired, energetic). The match is "nearest exemplar wins per window" — adding a sick-voice exemplar is exactly what makes future sick-voice turns auto-resolve.
- *Cross-source generalisation.* As a host appears on multiple podcasts, voiceprints from each recording chain enter the registry. The Person becomes recognisable everywhere they actually appear.

**Face (`person_face_embeddings`).** One 512-dim ArcFace per enrolled image or corrected frame. New entries add new angles, lighting conditions, expressions, beard length, glasses-on/off. The k-NN match is permissive (cosine threshold 0.40) — any single matching exemplar in the registry is enough to recognise that host in that condition.

### What does not happen — architectural non-decisions

Worth being explicit about, since several of these were considered and rejected:

- **No model fine-tuning.** wespeaker (voice) and ArcFace (face) are frozen pretrained models. We don't retrain on Jaromelu data — no GPU training cycles, no model versioning, no MLOps pipeline. All "improvement" is registry-side, observable as `person_voiceprints` row counts growing over time.
- **No centroid / mean voiceprint.** A single representative vector per Person was considered in early design and rejected: a centroid drowns out variation, and one bad span poisons all future matches. Per-window voting tolerates ~30–40 % noisy exemplars without misidentifying.
- **No decay or time-weighting.** Old embeddings carry equal weight to new ones. A 2024 voiceprint still votes in 2026. The volume of normal-condition recordings drowns out outliers, and the cosine threshold filters bad windows. The trade-off: dramatic voice changes (puberty, surgery) are handled by accumulating enough new exemplars rather than by forgetting old ones.
- **No pruning.** Bad embeddings (a cough during enrollment, a blurry frame) stay in the registry forever unless manually deleted from SQL. The matching algorithm votes them down. **Caveat:** when SQL-deleting embeddings, also purge any cached `face_track.json` that referenced them — the cache holds person_ids, not embeddings, so the visual_id reuse path won't re-vote against a cleaned registry. See "Registry-cleanup gotcha" under [How it works → Visual identification](#how-it-works).
- **No S-norm score normalisation.** Mentioned in [Backlog](#backlog). Without it, cosine scores from different recording conditions aren't strictly comparable across sources, but threshold-based matching is robust enough at single-digit-host scale.

### Scaling characteristics

The voice matcher loads the entire `person_voiceprints` table into memory once per source — a single matrix multiply per turn. Sizing:

- *Today:* 1–10 hosts × 1–10 enrollment spans × 17 voiceprints × 256-dim × 4 bytes ≈ <100 KB.
- *Plausible mid-scale:* 100 hosts × 100 episodes × 17 voiceprints × 256-dim × 4 bytes ≈ 174 MB. Still feasible.
- *Large-scale:* 1000 hosts × 1000 episodes ≈ 17 GB. Not feasible in-memory.

Backlog calls out **pgvector HNSW server-side k-NN** as the migration path — same matching semantics, the index lives in Postgres rather than being loaded per source. Until that ships, the in-memory load is the implicit ceiling on registry growth. Face matching has the same shape: in-memory cosine k-NN today, pgvector-able later.

### Auditing the registries

Useful queries when checking system health:

```sql
-- Voiceprints per host, by provenance
SELECT p.full_name, pv.created_by, COUNT(*)
FROM person_voiceprints pv
JOIN people p ON p.person_id = pv.person_id
GROUP BY 1, 2 ORDER BY 1, 2;

-- Face embeddings per host, by provenance
SELECT p.full_name, pfe.created_by, COUNT(*)
FROM person_face_embeddings pfe
JOIN people p ON p.person_id = pfe.person_id
GROUP BY 1, 2 ORDER BY 1, 2;

-- Match-method distribution per source. Over time, as registries mature,
-- this should shift toward voice+face on sources that have video.
SELECT s.source_id, ss.match_method, COUNT(*)
FROM source_speakers ss
JOIN sources s ON s.source_id = ss.source_id
WHERE s.transcription_status = 'transcribed'
GROUP BY 1, 2 ORDER BY 1;
```

The data is there; an admin-panel surfacing of these metrics ("Lineup health") is on the wider backlog.

---

## Manual reassign

When the operator overrides a misidentified turn (the click-to-reassign UI in `YouTubeFaceOverlay.tsx` → `ReassignFaceModal.tsx`), `POST /api/sources/{source_id}/speakers/{segment_id}/reassign` runs the following sequence (see `services/api/app/routers/sources.py::reassign_speaker`).

### Frontend trigger

1. User clicks a face box in the YouTube-iframe overlay.
2. `ReassignFaceModal` opens, prefilled with `segment_id`, `frame_ts`, and the clicked `bbox` (from the face-track JSON).
3. User picks a Person via `PersonPicker` (fuzzy search over `people`), **or** types a name not in the registry and clicks the "Create new: '<name>'" affordance to attribute the turn to a brand-new Person on the fly.
4. POST to the reassign endpoint with `{ frame_ts, bbox, ...personFields }` — where `personFields` is exactly one of `{ person_id }` (existing) or `{ new_person_name }` (lookup-or-create by canonical name, case-insensitive).

### Backend sequence

The endpoint returns **NDJSON** (`application/x-ndjson`) — one JSON event per line emitted as each substep completes. The frontend reads it with a `ReadableStream` reader and renders a 5-row checklist. Validation errors raised before the stream starts still surface as ordinary HTTP 4xx JSON responses.

```
SYNC PRELUDE (HTTP 4xx on failure)
  1. Validate              source exists + has pixels access (video_s3_key OR YouTube canonical_url)
                           speaker turn exists (by segment_id)
                           exactly one of body.person_id / body.new_person_name is provided

  2. Resolve target Person if body.person_id:
                              look up Person; 404 if missing
                           else (body.new_person_name):
                              strip + length-validate (1..200)
                              case-insensitive lookup by canonical_name
                              if missing → INSERT new people row (canonical_name only),
                                            mark person_created=true
                              else → reuse existing row (idempotent on repeat clicks)
                           target_person_id := person.person_id
                           db.flush() makes the new row visible without committing

  3. Resolve frame_ts      body.frame_ts if provided, else turn midpoint

STREAMED STEPS (NDJSON)         emits {"step", "status", "detail"?} per event
  4. person  done              detail = {person_id, person_name, person_created}

  5. frame   start → done      _fetch_reassign_frame:
                                 - YouTube source → worker yt-dlp's a ~6s slice
                                   around frame_ts (`prefer_section=true`).
                                   Cold path ≈ 3 s, no S3 round-trip.
                                 - Otherwise → worker pulls video_s3_key via its
                                   LRU disk cache (/var/cache/video-worker).
                                   Repeat clicks on the same source ≈ instant.
                                 - JPG bytes returned over HTTP, written to tempdir.

  6. face    start → done      enroll_face_from_image:
             or skip             - cv2 decode + InsightFace buffalo_l (RetinaFace + ArcFace)
                                 - Largest face (bbox hint disambiguates if multiple)
                                 - INSERT person_face_embeddings (created_by='manual')
                                 - skip event if no face detected — turn still attributed

  7. voice   start → done      enroll() — same path as enroll_voice_cli:
             or skip             - Pull audio from S3, ffmpeg → 16 kHz mono WAV
                                 - 2 s sliding window / 0.5 s hop over [turn.start_ts, turn.end_ts]
                                 - wespeaker embeddings (256-dim) per window
                                 - INSERT N rows into person_voiceprints (created_by='manual')
                                 - skip event if turn shorter than embedder minimum

  8. commit  start → done      speaker_person_id  = target_person_id
                               match_method       = 'manual'
                               match_confidence   = 1.0
                               Single transaction — Person creation, embeddings,
                               and the SourceSpeaker update all land together.

  9. result  done              Terminal event — detail mirrors the legacy single-shot
                               response: {segment_id, person_id, person_name,
                               person_created, face_embedding_id, voiceprints_written,
                               match_method}.
```

Any unhandled exception in the streamed section emits `{"step": "<current>", "status": "error", "detail": "<msg>"}` and rolls back the session — partial writes never persist.

### Behaviour notes

**Effect.** The clicked turn now displays the corrected Person on the next overlay refresh (re-coloured to the `manual` match-method colour). Both registries gained new exemplars: one face embedding plus ~17 voiceprints per 10 s of turn audio. A single click grows *both* modalities — even if only the face was visually wrong, voice exemplars from the same turn join the voiceprint registry. Subsequent episodes featuring this Person in similar conditions auto-resolve without further operator effort.

**Failure tolerance.** Face or voice enrollment failures during reassign are caught and logged as warnings — they do *not* fail the reassign. The `SourceSpeaker` update always happens (assuming validation passed). Useful when, e.g., the face crop has no detectable face but the operator still wants to mark the turn correctly attributed.

**Idempotency and append-only.** The `SourceSpeaker` update is idempotent — re-clicks rewrite the same fields. Embeddings are append-only — repeated clicks add more rows, never overwrite. Misclick recovery is "click again with the right Person" — the bad embeddings stay but get vote-drowned by the correct ones at match time. Person creation is also idempotent: a second `new_person_name` click with the same string reuses the first run's row rather than duplicating.

---

## Faces tab (Slice A.5 — runs view)

A `Faces` tab on `/wiki/source/{source_id}` (alongside `Transcript` and `Claims`) shows a per-position run-length view of the face-track JSON. Each row is a stretch of contiguous detections at the same on-screen position with the same matched `person_id`. Where the matched person changes, a new row begins — the "material changes" the operator actually cares about. Far higher signal than evenly-spaced thumbnails.

Slice A's standalone gallery and `/face-groups` endpoint were retired in this change; the gallery is now the runs view. The cropping endpoint (`/face-crop`) survives — it backs the start/end thumbnails on each row.

### Endpoints

- `GET /api/sources/{source_id}/face-runs` — downloads the face-track JSON, runs spatial clustering + run detection (`services/api/app/analyst/face_runs.py`), joins each run to overlapping `source_speakers` turns, and returns `{positions: [{position_id, label, centroid, detection_count, runs: [...]}]}`. Each run carries `{person_id, person_name, start_ts, end_ts, frame_count, avg_similarity, start_sample, end_sample, overlapping_turns}`.

- `POST /api/sources/{source_id}/face-runs/assign` — body `{segment_ids: uuid[], person_id?: uuid, new_person_name?: string}`. Bulk-reassigns every supplied turn to the same target Person in one transaction. Streams `application/x-ndjson` events: `person done` → `turn start/done/error` × N → `commit start/done` → `result done`. A failure on any turn rolls back the whole batch; idempotent retries are safe.

- `GET /api/sources/{source_id}/face-crop?ts=<seconds>&bbox=<x1,y1,x2,y2>` — unchanged. ffmpeg crops the bbox before the JPEG encode (`-vf crop=W:H:X:Y -pix_fmt yuvj420p`) so the API container stays free of cv2 / PIL. `max-age=86400` cache so scrolling doesn't re-hit the worker.

### How the runs are computed

1. **Spatial clustering.** Greedy online: each detection joins the nearest existing position whose centroid is within `CENTROID_EPS=120px`, or seeds a new position. Centroids drift to the running mean of their members so a slowly panning camera still tracks.

2. **Position consolidation.** Repeatedly merges the closest pair of positions whose centroids fall within `CONSOLIDATE_EPS=100px` (bigger absorbs smaller); then drops positions with fewer than `MIN_POSITION_DETECTIONS=5` members. Removes the bumper-shot / cutaway / partial-face noise that the greedy first pass would otherwise label as its own row.

3. **Position labels.** Sorted by x-centroid: `Centre` (1), `Left/Right` (2), `Left/Centre/Right` (3), `Position N` (4+). Lets the operator map "Left" / "Right" to camera angles by clicking, without committing to a fixed labelling scheme.

4. **Run detection.** Per position, sort detections by ts and walk in order. A run breaks when (a) `person_id` changes, or (b) the gap to the next detection exceeds `RUN_GAP_SECONDS=5.0`. Single-frame flickers (`< SMOOTH_FLICKER_FRAMES=5`) between two same-person runs are absorbed — those are visual matcher hiccups (NULL between two Denan frames during a brief look-down), not real transitions.

5. **Overlap join.** Each run is joined to every `source_speakers` row whose `[start_ts, end_ts]` overlaps the run's range. Bulk assign reassigns *those turns* — the run itself isn't a first-class DB entity.

### Limitations (and what Slice B unlocks)

- **Spatial clustering misses** when the same Person appears at different bbox positions in the same frame. Fine for podcast formats; breaks for sports/news.
- **Bulk assign only writes for overlapping turns.** A run with no transcript-aligned turn (e.g. a brief cutaway with no one speaking) has the assign button disabled — there's nothing to reassign. Once Slice B persists per-detection embeddings, the assign action also writes face exemplars for every frame in the run.
- **The face-track JSON drops embeddings**, so we still can't ask "which other unassigned runs across this video — or other videos — look like the run I just labelled?" That's the cluster-similarity story Slice B/C delivers, on top of a future `source_face_detections` table.

Today's runs view is the right primitive for review: scan one source top-to-bottom, label the obvious unassigned runs, move on. Re-transcribe (after deleting the cached face-track JSON — see [face-track invalidation gotcha](#visual-identification--visual_identifyaudio_s3_key-video_s3_key-pyannote_turns)) propagates the new exemplars across other sources via the standard visual matcher.

---

## Per-detection embeddings — Slice B PR 1

`source_face_detections` (migration 053) keeps the 512-dim ArcFace embedding from every detected face during visual ID, instead of dropping it into the face-track JSON and forgetting it. This is the canonical store for intra-source face clustering and cross-source label propagation.

### Why a new table

- `person_face_embeddings` is the **registry**: one row per *enrolled* exemplar; small (single-digit thousands at maturity); queried at match time.
- `source_face_detections` is the **observation log**: one row per *detected* face; thousands per source; queried at review time for clustering and at ETL time for matching. Different growth rate, different access pattern, different lifecycle — the registry persists, observations are re-derivable from the source media.

### Schema (per source ≈ 11 MB at 1 fps × 45 min × ~2 faces/frame)

```
detection_id      uuid pk
source_id         uuid fk → sources (CASCADE on delete)
frame_ts          real
bbox_x1, y1, x2, y2  real (ck constraints enforce ordering)
det_score         real
embedding         vector(512)  -- pgvector, same model as person_face_embeddings
embedding_model   text
mouth_opening     real null
matched_person_id uuid null    -- match result from this detection's ID pass
match_score       real null
cluster_id        int null     -- populated by Slice B PR 2; NULL on insert
created_at        timestamptz
```

Indexes: `(source_id, frame_ts)` for the per-source listing query; `(source_id, cluster_id)` partial for the runs view; HNSW on `embedding` with cosine ops for kNN.

### ETL write — visual_identify

`visual_identify` (local branch) now takes a `source_id` parameter and writes one `source_face_detection` row per detected face after the face-track JSON is uploaded. Idempotent — if the source already has detection rows, the persistence step is a no-op. `transcribe.py` passes `source_id=source.source_id` on every call.

The **remote** (SageMaker) branch does NOT yet round-trip embeddings — the container uploads the face-track JSON itself and returns aggregate stats only. Sources visual-ID'd via the remote path won't have detections persisted until the GPU container is updated to either write rows directly (requires DB credentials in the container, currently disallowed) or return embeddings to the API for the API to persist. Until then, the backfill script forces the local path via `force_local=True`.

### Backfill — `app.analyst.backfill_source_face_detections_cli`

For sources visual-ID'd before this table existed (every source pre-2026-05-11):

```bash
cd services/api
source .venv/Scripts/activate
python -m app.analyst.backfill_source_face_detections_cli              # all
python -m app.analyst.backfill_source_face_detections_cli <source_id>  # one
```

Re-runs `visual_identify` with `force_local=True` + `force_reextract=True` so the local path runs end-to-end against the source's video. Cost ≈ 7-9 min CPU per source (video download + InsightFace at 1 fps). Idempotent — sources that already have detection rows are skipped.

## Portrait detection — Slice B PR 2.5

Multi-cam shows expose a class of clusters that aren't people: static wall art, framed portraits, posters. The face detector treats them the same as a real face, but they never speak, they never move, and bulk-assigning them to a Person silently pollutes the registry. `source_face_clusters` (migration 054) carries per-cluster metadata so we can tag them and hide them from the default runs view.

### Heuristic

After clustering, `analyse_clusters` computes per-cluster:

- `mouth_open_std` — standard deviation of `mouth_opening` across the cluster's detections.
- `centroid_std` — `sqrt(var(cx) + var(cy))` of bbox centres in source-frame pixels.
- `temporal_density` — detections per second over the cluster's lifespan (capped at 1.0).

Auto-classification (`_classify_cluster`), in order:

1. `detection_count < 10` → `noise`.
2. `centroid_std < 2 px` → `portrait` regardless of `mouth_open_std`. Lip-landmark jitter on a frozen face can push `mouth_open_std` as high as ~0.01 even when the bbox itself has never moved — strong centroid stability alone is enough signal. Real on-screen people always show > 5 px of centroid drift over hundreds of frames.
3. `mouth_open_std < 0.005` AND `centroid_std < 5 px` → `portrait`. Backup gate for clusters with mild centroid drift (e.g. a less-perfectly-static framed photo, a wall poster catching a draft) where the no-talking signal carries.
4. Otherwise → `person`.

Density was tested as a third gate but proved misleading in multi-cam (portraits and hosts share density when both visible only on certain camera angles). Kept as a stored diagnostic.

Verified 2026-05-12 on a multi-cam Bloke In A Bar source: 9 of 9 wall portraits caught auto (centroid_std 0.08-0.49); 3 of 3 real hosts kept as `person` (centroid_std 12.35-14.18). Zero false-positives; zero false-negatives in this run. The 5 px gap between portrait (< 0.5) and person (> 12) is wide enough that the 2 px strict gate is conservative.

### Operator override

`POST /api/sources/{source_id}/face-clusters/{cluster_id}` body `{kind?, label?, excluded?, notes?}`. Each field is "set if present, leave as-is if null". An empty-string `label` clears.

Once the operator sets `kind` explicitly, subsequent runs of the analyser preserve it (the auto-tag only updates `detected_kind` and only changes `excluded` while `kind IS NULL`).

### Runs view filtering

`GET /api/sources/{source_id}/face-runs` filters out `excluded=true` clusters by default. Append `?include_excluded=true` to see them. The response includes `excluded_count` so the UI can show "N clusters hidden as portraits / noise" with a toggle.

### Per-cluster UI

Each cluster section in the Faces tab now shows:

- Kind badge — `Person` / `Portrait` / `Noise`. Asterisk suffix indicates operator override (vs auto-tag).
- `Assign` button — opens the AssignRunModal cluster-scoped; one click attributes every overlapping `source_speakers` turn across the cluster to a Person. Disabled for the Outliers bucket.
- `Exclude` / `Include` button — flips `excluded` AND sets `kind='portrait'` when excluding so the analyser doesn't re-include on next run.

Each run row shows:

- Start + end thumbnails, time range, frame count, overlapping turn count.
- `Move →` button — opens an inline popover listing all other clusters in this source. Clicking a target POSTs `/face-runs/move-run` which bulk-UPDATEs the `cluster_id` on every detection in the run's `[start_ts, end_ts]` range. Used when HDBSCAN mis-grouped a stretch — e.g. a profile shot of host A whose embedding happened to land closer to host B's centroid.

### Assign-at-cluster, Move-at-run

The semantic separation matters: **one cluster = one identity**, so the Assign action lives at the cluster level. Runs are evidence-chunks that might be mis-clustered; their action is `Move`, not `Assign`. This prevents the older Slice A.5 bug where assigning a run in Cluster B to a different Person than another run in the same Cluster B could silently pollute the registry.

The `POST /face-runs/move-run` endpoint validates that both clusters already exist for the source — clusters are never invented mid-flow. After a move, `source_face_clusters.detection_count` updates on both source and target; full stat re-derivation waits for the next `recompute` call (cheap, mostly cached).

---

## Per-source clustering — Slice B PR 2

Once detections are persisted, the runs view groups by **visual identity** (face cluster) instead of on-screen position. This is the fix for "the '?' run covers two different people in the same chair" — spatial clustering can't tell them apart, but ArcFace embeddings can.

### Clustering pass — `face_clusters.cluster_source_detections`

Per source: load every detection's embedding, run `sklearn.cluster.HDBSCAN(metric="cosine", algorithm="brute")`, write `cluster_id` back. HDBSCAN was picked over k-means / DBSCAN because:

- **N clusters isn't known a priori** — different videos have different head counts. HDBSCAN figures it out from the data's density structure.
- **Outliers go to a -1 noise bucket**, not forced into the nearest cluster. Motion-blurred frames, partial faces, side profiles that drift past similarity — labelled NULL `cluster_id`, surfaced separately in the UI as "Outliers" so the operator can still see them.
- **Mutual-reachability metric merges same-person variation** across camera angles / lighting that look superficially different but share dense neighbourhoods.

Hyperparameters (`face_clusters.py`): `min_cluster_size=20` (at 1 fps that's 20 s of cumulative screen time — minimum to "really be a cluster"), `min_samples=5` (lower = fewer noise points). Clamped down for short clips so HDBSCAN doesn't throw on `min_cluster_size > n_samples`.

After clustering, cluster IDs are re-ranked **by size descending** so cluster 0 is always the busiest face, 1 the next, etc. Stable: same data → same labels. The UI maps these to letters: `Cluster A`, `Cluster B`, …, `Cluster Z`, then `Cluster 27` for the unlikely 27+ case.

### Endpoints

- `POST /api/sources/{source_id}/face-clusters/recompute` — re-runs clustering. Idempotent. Useful after backfill or a re-extract. Returns `{n_detections, n_clusters, n_noise, cluster_sizes}` so the caller can sanity-check that N clusters matches the expected number of people in the video.
- `GET /api/sources/{source_id}/face-runs` — now branches on detection availability:
  - **Cluster-backed** (detections exist): `compute_face_runs_from_detections` groups by `cluster_id`, breaks runs on `matched_person_id` change or >5 s gap. Each position entry carries `cluster_id`, label is `"Cluster A"`/`"Outliers"`/etc. If detections exist but none are clustered yet, the endpoint lazy-runs clustering before returning.
  - **Spatial fallback** (no detections): legacy Slice A.5 path. Same wire shape, `cluster_id: null` everywhere. Sources backfilled later get auto-upgraded on next request.

### Bulk-assign on clusters

`POST /api/sources/{source_id}/face-runs/assign` body `{cluster_id?, segment_ids[], person_id?|new_person_name?}`. SQL-only flow — no per-turn loop, no worker calls:

1. **Face exemplars** (cluster mode only): copy top `CLUSTER_EMBEDDING_SAMPLE_LIMIT=10` detections by `det_score` from `source_face_detections` into `person_face_embeddings` (`created_by='manual'`).
2. **Bulk attribute**: one `UPDATE source_speakers SET speaker_person_id, match_method='manual', match_confidence=1.0 WHERE segment_id = ANY(...)`. Replaces the previous per-turn loop.
3. **Cluster-wide detection update** (cluster mode): one `UPDATE source_face_detections SET matched_person_id WHERE cluster_id=X`.
4. **Cluster metadata stamp** (cluster mode): `source_face_clusters.attributed_person_id` set to the target so the cluster table mirrors the detection writes.
5. Single commit.
6. **Regenerate cached face-track JSON** from the post-commit DB state via `regenerate_face_track_json_from_detections` (`services/api/app/analyst/visual_id.py`). The DB is source of truth, but the YouTube overlay reads the cached JSON — without this step, the assign would land in the DB invisibly and the overlay would keep showing `?` for the cluster. Surfaced as its own NDJSON step (`regen_face_track`) so an S3-write failure is visible to the operator instead of silently leaving the JSON stale.

Total elapsed time is independent of cluster size — a 510-segment cluster completes in ~2 s. The earlier per-turn loop ran pyannote voice enrollment for every segment, producing thousands of voiceprints over ~5 minutes wall time; that was way over the kNN registry's useful scale and made every cluster-assign slower than the matching it enabled.

**Voice enrollment is intentionally NOT done by this endpoint.** A future voice-focused workflow will sample 5-10 representative turns per cluster (longest spans / stratified across timeline) and enroll voiceprints from those, capping the registry contribution per cluster-assign.

NDJSON event sequence: `person done` → `cluster_face start/done` (cluster mode) → `attribute start/done` → `commit start/done` → `regen_face_track start/done` → `result done`. Fixed shape regardless of `segment_ids` length; the modal's checklist is four rows.

#### Recovering from a failed regen

If the `regen_face_track` step errors (S3 outage, creds rotated mid-flight), the DB is still consistent but the cached JSON is stale — the overlay will show `?` for the freshly-assigned cluster until the JSON is rewritten. Two recovery paths, both idempotent:

- `POST /api/sources/{source_id}/face-track/regenerate` — thin wrapper around the same helper. Returns the new key, detection count, and distinct-persons count.
- `python -m app.analyst.regen_face_track_cli <source-uuid>` — same helper from the shell. Supports `--all --stale-only` to walk every source and only rewrite those whose cached JSON disagrees with the DB. Used as the retroactive fix for sources assigned before the inline regen was wired in (anything before commit fixing the `Source` import in `visual_id.py`).

### What's left for Slice B PR 3

- **Cross-source label propagation preview.** With embeddings stored and the HNSW index in place, querying "find detections across all other sources within cosine ≥ X of this cluster's centroid" is a single SQL query. The bulk-assign flow can then offer "this would also attribute N detections across M other videos — confirm?", optionally enqueuing per-source re-attribution jobs.
- **Remote-container support.** Today only the local `visual_identify` branch persists detections. The SageMaker container would need either DB credentials (currently disallowed) or an embedding-augmented S3 artefact the API can read.
- **Cluster review / merge / split.** Once a few sources are clustered, operators may want to merge clusters that HDBSCAN over-split, or split clusters it over-merged. UX-only work on top of the existing data.

---

## Remote vs local inference (Phase 5.5)

Lineup runs locally by default. To use the SageMaker Async endpoint instead:

1. One-time AWS setup per [services/gpu/SETUP.md](../../../services/gpu/SETUP.md) — ECR repo, staging bucket, IAM role, `.env` config additions.
2. Build + push the GPU container: `make lineup-build` (uses `HUGGINGFACE_API_KEY` as a Buildkit secret to bake model weights).
3. Deploy: `make lineup-deploy`. First deploy takes ~5–10 min while SageMaker provisions the `ml.g5.xlarge` instance and pulls the image; subsequent deploys roll forward.
4. Set `LINEUP_REMOTE=1` in `.env` and `make transcribe SOURCE_ID=… FORCE=1`. The CLI prints `[Lineup remote] diarize submitted → s3://jeromelu-sagemaker-async/…` and end-to-end runs complete in ~3 min instead of ~50 min.

The artefact contracts are unchanged — the GPU container imports the same `app.analyst.diarize` / `app.analyst.visual_id` modules and writes the same S3 keys (in Sydney), so downstream code (transcribe.py merge, fusion, review UI) is oblivious to where inference ran.

To stop iterating, `make lineup-delete` tears down the endpoint. The model + endpoint config remain (negligible cost); re-create the endpoint with another `make lineup-deploy`.

### Deployment topology

- **SageMaker endpoint** in `us-east-1` (Sydney capacity is currently constrained for both g4dn and g5 families). Single `ml.g5.xlarge` (A10G GPU), `MaxConcurrentInvocationsPerInstance=1`.
- **Artefact buckets** (`jeromelu-raw-audio`, `jeromelu-raw-transcripts`) stay in `ap-southeast-2` (Sydney) — they host audio + the persisted artefacts the rest of the system reads.
- **Staging bucket** `jeromelu-sagemaker-async` in `us-east-1` carries SageMaker's internal async invoke I/O (small request/response JSONs, ephemeral). SageMaker requires async I/O paths to be in the endpoint's region, hence the split.
- **ECR repository** `jeromelu/lineup-gpu` in `us-east-1`. Image baked with pyannote + InsightFace weights so cold-start is ~30 s, not ~3 min of HF download.

## Video lifecycle

Video is **ephemeral**. The pipeline holds a low-res mp4 only as long as it takes to extract face data and clean up. There is no persistent per-source video file going forward.

| Stage | Where the bytes live | Lifetime |
|---|---|---|
| `transcribe.py` runs visual ID | Per-request staging key `s3://jeromelu-raw-audio/staging/video/<uuid>.mp4` (in-bucket prefix; lifecycle rule expires after 24 h as a safety net) | Until `staged_video` context exits — usually seconds after `visual_identify` returns. |
| Reassign endpoint extracts a face frame | A local `tempfile.TemporaryDirectory` on the API host (`staged_video_local`) | Until the request handler returns. No S3 hop. |
| Persistent legacy keys (`sources.video_s3_key` set) | `s3://jeromelu-raw-audio/youtube/<channel>/<video_id>.video.mp4` | One row remaining, predates this design. Will be purged manually; new sources never write here. |

What this buys: the catalogue can grow without per-source storage cost. ~30 MB × 100 K sources = 3 TB of always-hot S3 storage that the system never persistently needs. The cost moves to ~$0.001 worth of cross-region transfer per Lineup run + ~$0.13 GPU time, both already paid.

What persists across runs: the **face-track JSON** (small, durable, the artefact the review UI consumes), the **face embeddings** in `person_face_embeddings`, and the **voiceprints** in `person_voiceprints`. The video file is the transient intermediate that yields all three.

The review UI overlays the face-track JSON directly on the YouTube iframe via `services/web/src/app/components/YouTubeFaceOverlay.tsx`. No local mp4 is required to draw boxes — bboxes scale from the JSON's `frame_width`/`frame_height` to the iframe's render size.

## Voices tab — cluster-level voiceprint assign

A `Voices` tab on `/wiki/source/{source_id}` (alongside `Transcript`, `Claims`, and `Faces`) shows each pyannote speaker as one section: a per-source group of every `source_speakers` row that shares a `speaker_label`. Unlike the Faces tab (which has to run HDBSCAN over per-detection ArcFace embeddings to *find* the clusters), the Voices tab has nothing to cluster — pyannote already tags every turn with `SPEAKER_NN` at diarisation time. The tab is pure aggregation.

Each cluster section renders **every turn** in the cluster, chronologically, with the time range, duration, full speech text, and a colour-coded dot for the current `match_method`. Same shape as the Faces tab's per-cluster runs view — operators can scan the whole conversation per voice without leaving the section.

The per-cluster `Assign` action is the operator analogue of `make enroll-voice` but ergonomically symmetric with the Faces tab's `Assign`: one click attributes every turn in the cluster to a chosen Person *and* writes a small number of voiceprint exemplars from the cluster's longest turns into the registry. Subsequent re-transcribes of any source recognise that voice without further operator effort.

### Endpoints

- `GET /api/sources/{source_id}/voice-clusters` — aggregates `source_speakers` by `speaker_label` (skipping NULL labels) and returns `{speakers: [{speaker_label, turn_count, total_seconds, first_ts, last_ts, embedding_eligible_count, dominant_person_id, dominant_person_name, dominant_share, match_method_breakdown, turns: [...]}]}`. Sorted by `total_seconds` descending. `turns` is *every* turn in the cluster, chronologically, each carrying `{segment_id, start_ts, end_ts, duration, speaker_person_id, match_method, has_embedding, preview_text}` — `preview_text` is the full concatenated chunk text of the turn (no truncation; the operator needs to read what was actually said). `dominant_person_*` is the mode of `speaker_person_id` across the cluster's turns; the `match_method_breakdown` shows how each turn was attributed so the operator can see at a glance whether the cluster is currently `voice+face` confirmed, face-only, or unattributed.

- `POST /api/sources/{source_id}/voice-clusters/{speaker_label}/assign` — body `{person_id?: uuid, new_person_name?: string}` (exactly one). Streams `application/x-ndjson` events: `person done` → `voice_enrol start/done` (or `skip` when no eligible turns) → `attribute start/done` → `commit start/done` → `result done`. Single transaction; idempotent retries are safe (the SourceSpeaker update is a pure overwrite, voiceprints are append-only).

### How a cluster assign maps to DB writes

1. **Resolve Person.** Look up by `person_id`, or canonical-name-lookup-or-create for `new_person_name` (case-insensitive). New Persons get committed before the streamed steps so a mid-stream failure can't leave a phantom row referenced by half-written exemplars.

2. **Promote medoid voiceprints.** Pick up to `VOICEPRINT_SAMPLE_LIMIT=10` `source_speakers` rows from the cluster, ordered by `(end_ts − start_ts)` descending — longest turns first, on the assumption that longer spans give cleaner, less-overlapped exemplars. Each row's medoid `embedding` (the 256-dim wespeaker vector pyannote produced at diarisation) is copied verbatim into `person_voiceprints` with `created_by='manual'`. Turns with NULL `embedding` (sub-300ms — see [Quality gates](#quality-gates)) are filtered out; if the cluster has none eligible, the step emits a `skip` event and the assign still proceeds with attribution-only.

3. **Bulk attribute.** One UPDATE: `UPDATE source_speakers SET speaker_person_id=…, match_method='manual', match_confidence=1.0 WHERE document_id=… AND speaker_label=…`. Targets every turn in the cluster — not a frontend-supplied segment_id list. Total elapsed time is independent of cluster size.

4. **Commit.** Single transaction. No face-track JSON to regenerate — voice cluster assign doesn't touch the visual side.

### Why medoid copy, not fresh enrolment

The medoid is the same wespeaker model the matcher uses, it's already in the DB (pyannote wrote it at diarisation time), and the per-window-vote machinery downstream tolerates medoid granularity fine — each voiceprint is one vote among many. Re-running `enroll_span_with_context` against the audio would produce ~17 sliding-window voiceprints per sampled turn instead of one medoid, but the *audio is the same audio*; the marginal vote-density isn't worth the S3 fetch + wespeaker pass per assign. This is the voice equivalent of face-runs/assign's "copy top-N detections into person_face_embeddings" — symmetric in shape, symmetric in cost.

The original `make enroll-voice` CLI still exists for the bootstrap workflow where the operator has a specific clean monologue span in mind and doesn't want pyannote's turn boundaries to constrain the enrolment. The Voices tab is the in-app, cluster-level path for everything else.

### Limitations

- **Pyannote clusters are per-source.** SPEAKER_01 on one episode and SPEAKER_01 on another are unrelated labels; the same person across episodes gets different cluster ids. Cross-source identity propagation comes from the registry growing — each voice cluster assign adds exemplars that future episodes match against.
- **No `Move` action at the turn level.** Pyannote's turn boundaries are accepted as-is; if a turn is misattributed within a cluster (e.g. the host laughs during a guest's monologue and pyannote merges them), the existing per-turn reassign click on the face overlay handles it. The Voices tab operates at cluster granularity only.
- **Voice cluster assigns don't regenerate the face-track JSON.** The cached JSON only carries face/visual identity; speaker-label-driven attribution shows up via `source_speakers.speaker_person_id`, which the overlay reads directly from the lifted speakers list.

---

## Identity alignment (face × voice matrix)

Face clusters and pyannote voice clusters are two independent clusterings of the same conversation. The Alignment tab on `/wiki/source/{source_id}` exposes their cross-modal overlap: for every `(face_cluster_id, speaker_label)` pair, how many face detections fall inside that voice cluster's turns, plus a per-turn disagreement worklist where the dominant on-screen face cluster's identity differs from the voice attribution.

This is the bridge between today's per-turn `fuse_per_turn` (local, in `fusion.py`) and the planned [Phase 5 compounding](#backlog) (registry-side, automated). Per-turn fusion catches simultaneous voice+face agreement on individual rows. Cluster-level alignment catches the same signal at *identity* granularity — way stronger evidence, and the dominant pairings stay stable across noisy individual frames.

### Endpoint

- `GET /api/sources/{source_id}/identity-alignment` — read-only. Returns:

```jsonc
{
  "face_clusters": [{cluster_id, detection_count,
                     dominant_person_id, dominant_person_name, dominant_share}, ...],
  "voice_clusters": [{speaker_label, turn_count, total_seconds,
                      dominant_person_id, dominant_person_name, dominant_share}, ...],
  "alignment": [{face_cluster_id, speaker_label,
                 overlap_count, active_overlap_count,
                 face_cluster_share, voice_cluster_share, confidence}, ...],
  "dominant_pairings": [{face_cluster_id, speaker_label,
                         confidence, overlap_count}, ...],
  "disagreements": [{segment_id, start_ts, end_ts, speaker_label,
                     speaker_person_id, speaker_person_name,
                     face_cluster_id, face_person_id, face_person_name,
                     active_overlap_count}, ...],
  "timeline": [{segment_id, start_ts, end_ts, duration,
                speaker_label,
                voice_cluster_person_id, voice_cluster_person_name,
                face_cluster_id,
                face_cluster_person_id, face_cluster_person_name,
                total_face_count, active_face_count,
                audio_match_person_id, audio_match_person_name,
                visual_match_person_id, visual_match_person_name,
                speaker_person_id, speaker_person_name,
                match_method, match_confidence,
                agreement, preview_text}, ...]
}
```

### Timeline — chronological follow-along view

The four older sections (matrix, pairings, disagreements) answer **"is the alignment clean?"** — statistical, cluster-level questions. The timeline answers **"what's happening at minute 23?"** — one row per turn in playback order, with both modalities side-by-side and the conversation text inline so the operator can follow the show and audit attribution simultaneously.

Each row carries the time range, the voice cluster (`speaker_label` + the cluster's dominant person), the dominant face cluster *for that turn's window* (the cluster that contributed the most detections inside the turn — different from the cluster's overall dominance), per-turn face counts (total + active where mouth-opening passed ASD), the current `speaker_person_id` attribution with `match_method`, the per-modality match columns (`audio_match_*` / `visual_match_*`) for inspection, and the full concatenated speech text.

The `agreement` field classifies the row by comparing **cluster dominants** (not per-turn matches — those are noisier):

| `agreement` | Voice cluster | Face cluster | Meaning |
|---|---|---|---|
| `agree`    | Person X | Person X | Both modalities point at the same Person. Highest-trust row. |
| `disagree` | Person X | Person Y | Modalities point at different Persons. Operator worklist. |
| `partial`  | one set, other null | | Only one cluster is named — either nothing's enrolled on the other side, or the turn had no face frames. |
| `none`     | null | null | Neither cluster is attributed. |

The row's left-edge bar is colour-coded by `agreement` (green / red / amber / grey) so the operator can scan the timeline for problems without reading every row.

### Words by attribution — side-by-side transcript

Above the per-turn cards, the Alignment tab leads with a two-column transcript: the same speech text is rendered twice, once labelled with the dominant on-screen face cluster's Person, once with the voice cluster's Person. Reading down the columns shows you what *would* have been attributed if you only had one modality. Disagreement rows are tinted red, partial rows amber; agreeing rows render plain so disagreements pop visually.

A summary line at the top reports the agreement percentage across turns where both sides had a name to attribute (turns with only one modality named, or neither, are excluded from the denominator since they can't agree or disagree). The view is purely derived from the timeline payload — no extra round-trip.

### How overlap is computed

1. **Detection-in-turn check.** Each `source_face_detections` row has a `frame_ts`. Each `source_speakers` row covers `[start_ts, end_ts]`. A detection lands in a turn when `start_ts <= frame_ts <= end_ts`. Turns don't overlap, so a detection lands in at most one — the walk breaks early once matched.

2. **At 1 fps, detection count ≈ seconds.** That's the implicit unit conversion: `face_cluster_share = overlap_count / cluster.detection_count` and `voice_cluster_share = overlap_count / speaker_label.total_seconds` are both ratios in commensurable units. If `FRAME_SAMPLE_RATE` ever changes from 1 fps the shares need a multiplier — flagged in `identity_alignment.py`.

3. **`active_overlap_count`** counts only detections whose `mouth_opening` clears `MIN_ACTIVE_MOUTH_OPENING=0.045` (mirror of the threshold in `visual_id.py`). The full overlap count includes listener / reaction-shot frames; the active subset is the precision-floor signal — the face was probably speaking, not just visible.

4. **`confidence = min(face_cluster_share, voice_cluster_share)`** — the limiting modality's share. A pair confident on both axes is a real alignment; a high-face / low-voice pair means the face is on screen during most of the voice's airtime *and* most of the face cluster's appearance is during this voice — both have to be true.

5. **Pairs with `overlap_count < MIN_OVERLAP_COUNT=5` are dropped.** One-frame appearances clutter the UI without contributing signal.

### Dominant pairings

Greedy walk over the alignment matrix sorted by confidence descending: take pairs whose `face_cluster_id` and `speaker_label` are both still unclaimed; skip otherwise. Each cluster on either side appears in at most one dominant pairing — the cleanest 1:1 mapping the data supports. Doesn't try to globally optimise (Hungarian would; not worth the complexity at podcast scale where N is single-digit per source).

### Disagreements

Per turn: find the face cluster that contributed the most detections to that turn's `[start_ts, end_ts]` window. If both the turn (`speaker_person_id`) and the cluster (`dominant_person_id`) have identities and they differ, the turn is a disagreement. Sorted by turn duration descending and capped at `DISAGREEMENT_LIMIT=50` — the top-N most airtime-significant cases is what the operator can actually action.

This is the **operator worklist**. Each row is either:

- A reaction shot the mouth-opening ASD let through (face was on screen during someone else's monologue and happened to clear the mouth-open density gate) — face cluster identity is correct but visual ID over-attributed.
- A wrong voice attribution (voice cluster bulk-assigned to the wrong Person) — voice side needs fixing.
- A genuine off-screen speaker — the speaking voice is correct, but the dominant on-screen face is somebody else (interviewer cutaway, B-roll, two-shot framing).

The tab doesn't try to auto-resolve. The operator picks: open the turn in the Voices tab and reassign the cluster, or open the face overlay and click-correct the specific frame. Per-turn correction at this granularity is high-leverage *because* the disagreement is exactly where the modalities disagree — the rest of the source can be left alone.

### Concrete wins

1. **One-shot dual assign.** When `dominant_pairings` shows a high-confidence pair where one side has a name and the other doesn't, the UI can offer "Assign both to <Person>" in a single action. Today this is one click on each tab; the alignment view is the data behind making it one click total.

2. **Disagreement review.** Concentrates operator attention on exactly the turns where face and voice disagree. Way higher signal-density than scrolling either tab top-to-bottom.

3. **Asymmetric error correction.** A `match_method='face'` turn (visual-only fired, voice was NULL) whose face cluster's *aligned* voice cluster has a different dominant Person is almost certainly a reaction-shot false positive. A backfill job could drop those attributions automatically. Cluster-level fusion is more trustworthy than per-turn fusion because it pools evidence across an entire identity, not a single frame.

### Limitations

- **Read-only today.** Acting on a disagreement still requires opening the per-modality tab. The one-shot dual assign + auto-drop-asymmetric-errors actions are next on the backlog.
- **Per-source.** Same-Person clusters across episodes aren't aligned here. Cross-source identity propagation is a separate problem and depends on the registry growing via the Faces/Voices tabs.
- **Matrix capped at 8×8 in the UI** — bigger sources omit trailing clusters from the table. The endpoint returns everything; the UI is just opinionated about display density.

---

## Backlog

- **Real audio-sync ASD model.** The mouth-opening heuristic gets us from 55 % → 77 % visual precision but misses reaction-shot false positives (laughing during someone else's monologue still passes the density gate). A model that takes face crops + audio mel-spectrograms and predicts speaking probability (Light-ASD, TalkNet, LoCoNet) would close the remaining gap. None are pip-packaged — they'd need vendoring.
- **Phase 5 — cross-modal compounding.** Periodic job that promotes high-confidence `voice+face`-agreement turns into the registries with `created_by='auto-confirmed'`. The mechanism that turns "85 % on day 1" into "95 %+ over six months" without human work.
- **S-norm calibration** — per-source impostor cohort to normalise similarity scores across episodes recorded in different rooms.
- **Voice sliding-window weighting** — currently all windows in a turn vote with equal weight. Weighting by the dominant utterance's pyannote confidence would penalise low-quality windows.
- **Admin enrollment endpoints** — REST endpoints behind `X-Admin-Key`, plus admin-panel UIs. Today it's CLI-only for both modalities.
- **Higher detection resolution** — InsightFace `det_size` is 640 by default; bumping to 1024 catches more profile/distant faces at ~3× latency cost.

---

## Related

- [Transcription Pipeline](transcription-pipeline.md) — predecessor surface that produces the per-turn embeddings this surface matches against.
- [Speaker Identification plan](../../todo/speaker-identification-plan.md) — Phase 1–5 roadmap.
- [Migration 047](../../../packages/db/migrations/047_pyannote_diarization.sql) (voice embeddings on `source_speakers`), [048](../../../packages/db/migrations/048_person_voiceprints.sql) (voiceprint table), [049](../../../packages/db/migrations/049_person_face_embeddings.sql) (face registry), [050](../../../packages/db/migrations/050_speaker_match_provenance.sql) (per-modality provenance + video columns).

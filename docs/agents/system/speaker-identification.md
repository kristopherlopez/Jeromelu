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
- `match_method` — `voice`, `face`, `voice+face`, or NULL
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
| **Match method** | How a turn was attributed: `voice` (audio only), `face` (visual only), `voice+face` (both modalities agreed — highest confidence), NULL (no match, or modalities disagreed). Stored on `source_speakers.match_method`. |
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
3. User picks a Person via `PersonPicker` (fuzzy search over `people`).
4. POST to the reassign endpoint with `{ person_id, frame_ts, bbox }`.

### Backend sequence

```
1. Validate              source exists + has pixels access (video_s3_key OR YouTube canonical_url)
                         speaker turn exists (by segment_id)
                         target Person exists

2. Resolve frame_ts      body.frame_ts if provided, else turn midpoint

3. Acquire video         _acquire_video_for_reassign:
                           - persisted s3://.../{vid}.video.mp4 (legacy), OR
                           - on-demand yt-dlp via staged_video_local → tempdir
                         Auto-cleaned when context exits.

4. Extract frame         ffmpeg @ frame_ts → frame.jpg in tempdir

5. Enroll face           enroll_face_from_image:
                           - cv2 decode + InsightFace buffalo_l (RetinaFace + ArcFace)
                           - Largest face (bbox hint disambiguates if multiple)
                           - INSERT person_face_embeddings (created_by='manual')

6. Enroll voice          enroll() — same path as enroll_voice_cli:
                           - Pull audio from S3, ffmpeg → 16 kHz mono WAV
                           - 2 s sliding window / 0.5 s hop over [turn.start_ts, turn.end_ts]
                           - wespeaker embeddings (256-dim) per window
                           - INSERT N rows into person_voiceprints (created_by='manual')
                           - Skipped silently if turn shorter than embedder minimum

7. Update SourceSpeaker  speaker_person_id  = body.person_id
                         match_method       = 'manual'
                         match_confidence   = 1.0

8. Commit                Single transaction.

9. Return                Response with face_id_written, voice_rows_written.
```

### Behaviour notes

**Effect.** The clicked turn now displays the corrected Person on the next overlay refresh (re-coloured to the `manual` match-method colour). Both registries gained new exemplars: one face embedding plus ~17 voiceprints per 10 s of turn audio. A single click grows *both* modalities — even if only the face was visually wrong, voice exemplars from the same turn join the voiceprint registry. Subsequent episodes featuring this Person in similar conditions auto-resolve without further operator effort.

**Failure tolerance.** Face or voice enrollment failures during reassign are caught and logged as warnings — they do *not* fail the reassign. The `SourceSpeaker` update always happens (assuming validation passed). Useful when, e.g., the face crop has no detectable face but the operator still wants to mark the turn correctly attributed.

**Idempotency and append-only.** The `SourceSpeaker` update is idempotent — re-clicks rewrite the same fields. Embeddings are append-only — repeated clicks add more rows, never overwrite. Misclick recovery is "click again with the right Person" — the bad embeddings stay but get vote-drowned by the correct ones at match time.

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

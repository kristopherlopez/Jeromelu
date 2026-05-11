"""Visual speaker identification — Phase 4a.

For a source whose video has been collected by Scout (`sources.video_s3_key`):

    1. Sample frames at 1 fps (configurable via FRAME_SAMPLE_RATE).
    2. Run InsightFace `buffalo_l` (RetinaFace + ArcFace) on each frame
       — multi-face detection + 512-dim embeddings.
    3. For each detected face, k-NN-match against `person_face_embeddings`
       in memory; record the winning Person + similarity.
    4. Build a face-track JSON, persist to S3 alongside the pyannote JSON.
    5. Aggregate per pyannote turn: which Person was on camera during
       that span? Majority vote across in-span face detections; clears
       a cosine + agreement threshold to commit.

Phase 4a does NOT yet do active-speaker detection (Light-ASD) — for
multi-cam (cut-to-speaker) podcasts the dominant face IS the speaker;
for single-cam content the visual signal is "who's in frame", which
fusion handles by deferring to voice when face is ambiguous.

NB: this module is a pure transform. It writes nothing to the DB —
fusion.py + transcribe.py are the surfaces that consume the
``VisualIdentifyResult`` it returns and update ``source_speakers``.
"""

from __future__ import annotations

import json
import logging
import math
import shutil
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy.orm import Session

from jeromelu_shared.config import settings
from jeromelu_shared.db import PersonFaceEmbedding, SourceFaceDetection
from jeromelu_shared.s3 import download_raw, get_s3_client, upload_raw
from sqlalchemy import func as sa_func

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Frame sampling rate. 1 fps is plenty for podcast face detection — the
#: speaker is on screen for many consecutive seconds, and we don't need
#: per-second granularity since pyannote turns are coarser than that.
FRAME_SAMPLE_RATE = 1.0

#: InsightFace face detection size (input resolution). 640 is the default
#: and trades latency for small-face recall. Bumping to 1024 catches more
#: distant/profile faces but slows detection ~3x.
DETECTION_SIZE = (640, 640)

#: ArcFace cosine threshold for "same person" — empirically 0.4-0.6 on
#: VoxCeleb-style benchmarks. Start permissive (0.40) since the registry
#: is expected to be small and downstream fusion gates the final answer.
DEFAULT_FACE_COSINE_THRESHOLD = 0.40

#: Fraction of in-span face detections that must agree on the same Person
#: for a per-turn visual match to commit.
DEFAULT_FACE_AGREEMENT_THRESHOLD = 0.6

#: Minimum face detection confidence (det_score) for a face to participate
#: in matching. Below this, the detection is too uncertain to trust.
MIN_DETECTION_SCORE = 0.5

EMBEDDING_MODEL = "insightface/buffalo_l"
EMBEDDING_DIM = 512

#: Mouth-opening threshold (as a fraction of face bbox height) above
#: which we treat the face as "speaking". Calibrated empirically on the
#: first audited podcast: closed-mouth listeners sit around 0.038–0.042,
#: a barely-open speaker is ~0.053, a mid-vowel speaker is 0.07+. The
#: threshold sits just above the closed-mouth baseline.
MIN_ACTIVE_MOUTH_OPENING = 0.045

#: When picking the active face in a frame with multiple detections, the
#: candidate must beat the second-best by this margin (additive). Without
#: it, two listeners both at 0.046 would alternate-flicker. Skip the
#: frame entirely when no face stands out.
ACTIVE_FACE_MARGIN = 0.005

#: Per-turn density gate: at least this fraction of in-span frames must
#: yield an "active speaker" face for the turn to commit. With this on,
#: a stable enrolled face whose mouth happens to open ~13 % of the time
#: (chewing, smiling at someone else's joke) doesn't get credited as the
#: speaker. Empirically, the actual speaker's mouth-open rate is 30–45 %.
MIN_ACTIVE_FRACTION = 0.30

#: Bumped when the face-track JSON shape changes; older versions are
#: re-generated. v3: mouth_opening source switched from landmark_2d_106
#: indices 100/103 (which weren't the inner mouth — they happened to give
#: a stable value of ~0.13 regardless of mouth state) to landmark_3d_68
#: indices 62/66, the well-known Dlib-style inner-mouth top/bottom.
#: v4: added ``frame_width`` and ``frame_height`` (source video pixel
#: dimensions), so the review-UI overlay can scale bboxes correctly when
#: drawn over an iframe whose render size doesn't match the source — see
#: ``YouTubeFaceOverlay`` (the canvas substrate is no longer the local
#: mp4 with intrinsic ``videoWidth``/``videoHeight``).
FACE_TRACK_JSON_VERSION = 4


# ---------------------------------------------------------------------------
# Dataclasses + errors
# ---------------------------------------------------------------------------

@dataclass
class FaceDetection:
    """One face detected in one frame."""
    bbox: list[float]            # [x1, y1, x2, y2] in pixel coords
    det_score: float
    embedding: np.ndarray | None = None  # 512-dim, dropped before JSON write
    person_id: UUID | None = None
    similarity: float | None = None
    #: Mouth opening as a fraction of face bbox height. Used as a
    #: lightweight active-speaker-detection signal — see `_mouth_opening`.
    #: ``None`` when the embedded landmark model didn't produce 2d106
    #: landmarks for this face.
    mouth_opening: float | None = None


@dataclass
class FrameDetections:
    ts: float
    faces: list[FaceDetection] = field(default_factory=list)


@dataclass
class VisualMatch:
    person_id: UUID
    similarity: float
    agreement: float
    face_count: int


@dataclass
class VisualIdentifyResult:
    face_track_s3_key: str
    duration_seconds: float
    frames_processed: int
    frames_with_faces: int
    distinct_persons_seen: int
    video_format: str  # 'multi_cam' | 'single_cam' | 'audio_only'
    turns_visually_matched: int
    per_turn: list[VisualMatch | None]
    # Slice B PR 1.5 — npz artefact with per-detection embeddings,
    # bboxes and metadata. Written when ``emit_detections_artefact=True``
    # (the remote/GPU path uses this to round-trip embeddings to the API
    # for SourceFaceDetection inserts). None on the local path which
    # persists directly via ``_persist_face_detections``.
    face_detections_s3_key: str | None = None


class VisualIdError(Exception):
    """Raised when visual identification fails."""


# ---------------------------------------------------------------------------
# Helpers — S3 + ffmpeg
# ---------------------------------------------------------------------------

def _face_track_s3_key_from_audio(audio_s3_key: str) -> str:
    if audio_s3_key.endswith(".m4a"):
        return audio_s3_key[: -len(".m4a")] + ".face_track.json"
    return audio_s3_key + ".face_track.json"


def _face_detections_s3_key_from_audio(audio_s3_key: str) -> str:
    """Per-source embedding artefact key — sibling to the face-track
    JSON. Used by the GPU container to round-trip per-detection
    embeddings to the API for SourceFaceDetection inserts.
    """
    if audio_s3_key.endswith(".m4a"):
        return audio_s3_key[: -len(".m4a")] + ".face_detections.npz"
    return audio_s3_key + ".face_detections.npz"


def _download_video(video_s3_key: str, dest: Path) -> None:
    client = get_s3_client()
    client.download_file(settings.s3_audio_bucket, video_s3_key, str(dest))


def _frame_iterator(video_path: Path, sample_rate: float):
    """Yield (timestamp, BGR ndarray) tuples sampled at `sample_rate` fps.

    Uses cv2 directly. Cheaper than ffmpeg dump-to-disk + load loop.
    """
    import cv2  # lazy: opencv pulls a chunk of native deps
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise VisualIdError(f"failed to open video at {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    interval = max(1, int(round(fps / sample_rate)))
    i = 0
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if i % interval == 0:
                ts = i / fps
                yield ts, frame
            i += 1
    finally:
        cap.release()


def _video_dimensions(video_path: Path) -> tuple[int, int]:
    """Return (width, height) of the video at ``video_path`` in pixels.

    Bbox coordinates emitted by InsightFace live in this pixel space,
    so the overlay needs the same numbers to scale to its render size.
    """
    import cv2
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise VisualIdError(f"failed to open video at {video_path}")
    try:
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    finally:
        cap.release()
    if w <= 0 or h <= 0:
        raise VisualIdError(f"could not read video dimensions for {video_path}")
    return w, h


# ---------------------------------------------------------------------------
# Helpers — face matching
# ---------------------------------------------------------------------------

def load_face_registry(
    session: Session,
    *,
    embedding_model: str | None = EMBEDDING_MODEL,
) -> tuple[np.ndarray, list[UUID]]:
    """Load all face embeddings (optionally filtered by model) into memory."""
    q = session.query(
        PersonFaceEmbedding.embedding,
        PersonFaceEmbedding.person_id,
    )
    if embedding_model is not None:
        q = q.filter(PersonFaceEmbedding.embedding_model == embedding_model)
    rows = q.all()
    if not rows:
        return np.zeros((0, EMBEDDING_DIM), dtype=np.float32), []
    matrix = np.array([list(r[0]) for r in rows], dtype=np.float32)
    return matrix, [r[1] for r in rows]


def _mouth_opening(face) -> float | None:
    """Mouth opening as a fraction of face bbox height.

    Uses InsightFace's ``landmark_3d_68`` (also provided by the
    ``buffalo_l`` pack). The Dlib-style 68-point layout is well-known
    and stable: index 62 is the top of the inner lip, index 66 is the
    bottom. Their 2D pixel distance (drop z), normalised by face height,
    gives a scale-free mouth-openness signal.

    Originally tried ``landmark_2d_106`` indices 100/103 (the InsightFace
    JD-AI 2d106 layout) but those gave a stable ~0.13 regardless of
    mouth state — they aren't the inner-mouth points in that layout.
    3d68 indices 62/66 are the canonical choice.

    Returns ``None`` when 3d68 landmarks aren't available — the caller
    treats this as "no ASD signal" and falls back to face-presence
    voting.
    """
    landmarks = getattr(face, "landmark_3d_68", None)
    if landmarks is None:
        return None
    arr = np.asarray(landmarks)
    if arr.ndim != 2 or arr.shape != (68, 3):
        return None
    # Drop the z (depth) axis; mouth-opening is a 2D pixel distance.
    top_inner = arr[62][:2]
    bottom_inner = arr[66][:2]
    opening = float(np.linalg.norm(top_inner - bottom_inner))
    bbox = face.bbox
    face_height = float(bbox[3] - bbox[1])
    if face_height <= 0:
        return None
    return opening / face_height


def _match_face(
    embedding: np.ndarray,
    registry: np.ndarray,
    person_ids: list[UUID],
    threshold: float,
) -> tuple[UUID, float] | None:
    """k=1 cosine match for a single face embedding."""
    if registry.shape[0] == 0:
        return None
    e = embedding / max(np.linalg.norm(embedding), 1e-8)
    r_norm = np.linalg.norm(registry, axis=1, keepdims=True)
    r = registry / np.maximum(r_norm, 1e-8)
    sim = r @ e
    idx = int(np.argmax(sim))
    s = float(sim[idx])
    if not math.isfinite(s) or s < threshold:
        return None
    return person_ids[idx], s


# ---------------------------------------------------------------------------
# Helpers — format heuristic
# ---------------------------------------------------------------------------

def _detect_video_format(frames: list[FrameDetections]) -> str:
    """Heuristic: in multi-cam podcasts the dominant on-screen face
    changes frequently as the camera cuts. In single-cam, all hosts are
    in frame at once.

    `face_change_rate` = frames where the dominant person identity
    differs from the previous frame's, divided by frames with a matched
    face. >=0.10 → multi_cam, <0.05 → single_cam, in between → split
    formats / unknown (default to multi_cam since cuts are typical for
    podcast video).
    """
    matched_frames = [
        max(f.faces, key=lambda x: x.det_score, default=None)
        for f in frames
        if f.faces
    ]
    matched_frames = [
        f for f in matched_frames if f and f.person_id is not None
    ]
    if len(matched_frames) < 5:
        return "audio_only"  # not enough visual signal
    changes = sum(
        1 for a, b in zip(matched_frames, matched_frames[1:])
        if a.person_id != b.person_id
    )
    rate = changes / len(matched_frames)
    if rate >= 0.10:
        return "multi_cam"
    if rate < 0.05:
        return "single_cam"
    return "multi_cam"  # default to the more common podcast format


# ---------------------------------------------------------------------------
# Helpers — per-turn vote
# ---------------------------------------------------------------------------

def _select_active_face(faces: list[FaceDetection]) -> FaceDetection | None:
    """Pick the face most likely to be speaking in this frame.

    ASD heuristic: the speaker's mouth opens noticeably; listeners'
    mouths stay near-closed. Of the matched faces in the frame, return
    the one with the largest ``mouth_opening`` provided:

      - The opening clears ``MIN_ACTIVE_MOUTH_OPENING`` (filters out
        listeners and breathing).
      - It beats the runner-up by ``ACTIVE_FACE_MARGIN`` (avoids
        flicker when two listeners are equally near-closed).

    Returns ``None`` if no face stands out — the frame doesn't contribute
    to the per-turn vote. With single-cam multi-host content this is
    what filters most listener faces from voting; the caller falls back
    to face-presence voting when no faces in any frame have a usable
    mouth signal.
    """
    if not faces:
        return None
    # Only matched faces with a usable mouth signal can compete.
    candidates = [f for f in faces if f.mouth_opening is not None and f.person_id is not None]
    if not candidates:
        return None

    candidates.sort(key=lambda f: f.mouth_opening, reverse=True)
    top = candidates[0]
    if top.mouth_opening < MIN_ACTIVE_MOUTH_OPENING:
        return None
    if len(candidates) > 1:
        runner_up = candidates[1]
        if top.mouth_opening - runner_up.mouth_opening < ACTIVE_FACE_MARGIN:
            return None
    return top


def _per_turn_vote(
    frames: list[FrameDetections],
    pyannote_turns: list[dict[str, Any]],
    *,
    agreement_threshold: float,
) -> list[VisualMatch | None]:
    """For each pyannote turn, find which Person dominates the face
    detections in that span. Per-frame ASD selects one "active" face
    (the one with the most-open mouth) before voting; this filters
    listeners out of single-cam frames where multiple hosts are visible.

    Returns a list parallel to ``pyannote_turns``.
    """
    # Index frames by ts for fast in-range lookup. List is already sorted.
    results: list[VisualMatch | None] = []
    f_idx = 0
    for turn in pyannote_turns:
        t_start = float(turn["start"])
        t_end = float(turn["end"])

        # Collect one "active speaker" face per frame in the turn's range.
        active_faces: list[FaceDetection] = []
        i = f_idx
        while i < len(frames) and frames[i].ts < t_start:
            i += 1
        f_idx = i
        frames_in_span = 0
        while i < len(frames) and frames[i].ts <= t_end:
            frames_in_span += 1
            active = _select_active_face(frames[i].faces)
            if active is not None:
                active_faces.append(active)
            i += 1

        # No fallback. If ASD didn't pick an active face for any frame
        # in the span, we have no reliable signal — refuse to vote. The
        # cross-modal voice/face fusion downstream gives this turn a
        # chance via the voice modality. Earlier versions fell back to
        # face-presence voting; that produced 55 % precision in
        # single-cam content because every frame's matched-but-silent
        # face cast a vote for the enrolled host.
        if not active_faces or frames_in_span == 0:
            results.append(None)
            continue

        # Density gate: the speaker's mouth must open in at least
        # MIN_ACTIVE_FRACTION of the frames during the turn. A listener
        # whose mouth happens to open occasionally (chewing, smiling at
        # someone else's joke, brief reactions) sits at 10–25 %; the
        # actual speaker is at 30–45 %.
        if len(active_faces) / frames_in_span < MIN_ACTIVE_FRACTION:
            results.append(None)
            continue

        votes: dict[UUID, list[float]] = defaultdict(list)
        for face in active_faces:
            votes[face.person_id].append(face.similarity or 0.0)

        winner_pid, winner_sims = max(
            votes.items(),
            key=lambda kv: (len(kv[1]), max(kv[1])),
        )
        agreement = len(winner_sims) / len(active_faces)
        if agreement < agreement_threshold:
            results.append(None)
            continue
        results.append(VisualMatch(
            person_id=winner_pid,
            similarity=max(winner_sims),
            agreement=agreement,
            face_count=len(active_faces),
        ))
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _face_track_object_exists(key: str) -> bool:
    client = get_s3_client()
    try:
        client.head_object(Bucket=settings.s3_raw_bucket, Key=key)
        return True
    except Exception:
        return False


def _frames_from_face_track(doc: dict[str, Any]) -> list[FrameDetections]:
    """Reconstruct ``FrameDetections`` list from a persisted face-track JSON.
    Only the fields needed for ``_per_turn_vote`` are populated."""
    out: list[FrameDetections] = []
    for f in doc.get("frames", []):
        faces: list[FaceDetection] = []
        for face in f.get("faces", []):
            pid_str = face.get("person_id")
            faces.append(FaceDetection(
                bbox=face.get("bbox", []),
                det_score=float(face.get("det_score", 0.0)),
                embedding=None,
                person_id=UUID(pid_str) if pid_str else None,
                similarity=face.get("similarity"),
                mouth_opening=face.get("mouth_opening"),
            ))
        out.append(FrameDetections(ts=float(f["ts"]), faces=faces))
    return out


_face_app = None


def _get_face_app():
    """Lazy-singleton InsightFace app — model load is ~3 s.

    Prefers CUDA when available (Phase 5.5 GPU container) and falls back
    to CPU otherwise (local dev without onnxruntime-gpu / no NVIDIA GPU).
    Earlier versions hardcoded CPU which silently nullified the GPU
    container's speedup — the T4 sat idle while face detection ran on
    container CPU at ~30 s per source-minute.
    """
    global _face_app
    if _face_app is not None:
        return _face_app
    from insightface.app import FaceAnalysis
    import onnxruntime
    available = set(onnxruntime.get_available_providers())
    providers: list[str] = []
    if "CUDAExecutionProvider" in available:
        providers.append("CUDAExecutionProvider")
    providers.append("CPUExecutionProvider")
    logger.info("InsightFace providers: %s", providers)
    app = FaceAnalysis(name="buffalo_l", providers=providers)
    app.prepare(ctx_id=0, det_size=DETECTION_SIZE)
    _face_app = app
    return app


def visual_identify(
    session: Session | None = None,
    *,
    audio_s3_key: str,
    video_s3_key: str,
    pyannote_turns: list[dict[str, Any]],
    sample_rate: float = FRAME_SAMPLE_RATE,
    cosine_threshold: float = DEFAULT_FACE_COSINE_THRESHOLD,
    agreement_threshold: float = DEFAULT_FACE_AGREEMENT_THRESHOLD,
    registry: tuple[np.ndarray, list[UUID]] | None = None,
    source_id: UUID | None = None,
    force_local: bool = False,
    force_reextract: bool = False,
    emit_detections_artefact: bool = False,
) -> VisualIdentifyResult:
    """Run face detection + matching over the source's video.

    Persists a face-track JSON to S3 (alongside the pyannote JSON) and
    returns a list of per-turn ``VisualMatch | None`` parallel to the
    input ``pyannote_turns``.

    With an empty face registry (``person_face_embeddings`` empty), every
    turn comes back unidentified and ``video_format='audio_only'`` —
    no error.

    Phase 5.5: when ``settings.lineup_remote`` is true and a session is
    available (so we can pre-load the face registry from Postgres),
    dispatches to the SageMaker Async endpoint. The container does the
    ffmpeg/cv2/InsightFace heavy lifting on a GPU; the artefact contract
    is unchanged.

    Slice B (per-detection embedding persistence): when ``session`` AND
    ``source_id`` are supplied, the **local** branch also writes a row
    per detected face into ``source_face_detections``. The remote branch
    does not yet round-trip embeddings (a future GPU-container change),
    so the backfill script forces the local path via ``force_local=True``
    until that lands.
    """
    if settings.lineup_remote and session is not None and not force_local:
        from .remote import visual_identify_remote
        return visual_identify_remote(
            session,
            audio_s3_key=audio_s3_key,
            video_s3_key=video_s3_key,
            pyannote_turns=pyannote_turns,
            cosine_threshold=cosine_threshold,
            agreement_threshold=agreement_threshold,
            sample_rate=sample_rate,
        )

    face_track_key = _face_track_s3_key_from_audio(audio_s3_key)

    # Face registry: either supplied directly (Phase 5.5 remote inference,
    # where the orchestrator pre-loads it from the prod DB and sends it in
    # the SageMaker request) or loaded from the local session.
    if registry is not None:
        registry_matrix, person_ids = registry
    else:
        if session is None:
            raise VisualIdError(
                "visual_identify needs either `session` or `registry`"
            )
        registry_matrix, person_ids = load_face_registry(session)
    logger.info("Face registry: %d embeddings", registry_matrix.shape[0])

    # Reuse path: if a face-track JSON of the current version already
    # exists, skip the expensive frame-by-frame extraction. This makes
    # tuning the per-turn vote logic cheap. Re-extraction is only needed
    # when the registry changes (different / additional faces enrolled)
    # since face-to-Person matching happens at extract time. To force a
    # re-extract: pass ``force_reextract=True``, delete the JSON, or bump
    # FACE_TRACK_JSON_VERSION.
    #
    # Reuse is also skipped when the caller asked for the npz artefact
    # (emit_detections_artefact=True) — the cached JSON dropped
    # embeddings, so there's nothing to emit. The caller would silently
    # get a result without the artefact key otherwise.
    if (
        not force_reextract
        and not emit_detections_artefact
        and _face_track_object_exists(face_track_key)
    ):
        try:
            existing = json.loads(download_raw(face_track_key))
        except Exception:
            existing = None
        if existing and existing.get("json_version") == FACE_TRACK_JSON_VERSION:
            logger.info(
                "Reusing existing face-track JSON at v%d (skipping extraction)",
                FACE_TRACK_JSON_VERSION,
            )
            frames = _frames_from_face_track(existing)
            duration_seconds = existing.get("duration_seconds", 0.0)
            video_format = existing.get("video_format", "audio_only")
            per_turn = _per_turn_vote(
                frames, pyannote_turns, agreement_threshold=agreement_threshold,
            )
            distinct_persons = len({
                face.person_id
                for f in frames for face in f.faces
                if face.person_id is not None
            })
            turns_matched = sum(1 for r in per_turn if r is not None)
            frames_with_faces = sum(1 for f in frames if f.faces)
            return VisualIdentifyResult(
                face_track_s3_key=face_track_key,
                duration_seconds=duration_seconds,
                frames_processed=len(frames),
                frames_with_faces=frames_with_faces,
                distinct_persons_seen=distinct_persons,
                video_format=video_format,
                turns_visually_matched=turns_matched,
                per_turn=per_turn,
            )

    with tempfile.TemporaryDirectory(prefix="jeromelu-visual-") as tmp:
        tmpdir = Path(tmp)
        video_path = tmpdir / "video.mp4"

        logger.info(
            "Downloading video from s3://%s/%s",
            settings.s3_audio_bucket, video_s3_key,
        )
        _download_video(video_s3_key, video_path)

        frame_width, frame_height = _video_dimensions(video_path)
        logger.info("Source video dimensions: %dx%d", frame_width, frame_height)

        face_app = _get_face_app()

        logger.info("Sampling frames at %.2f fps and running face detection", sample_rate)
        frames: list[FrameDetections] = []
        frames_with_faces = 0
        last_log = 0
        for ts, img in _frame_iterator(video_path, sample_rate):
            faces_raw = face_app.get(img)
            faces: list[FaceDetection] = []
            for f in faces_raw:
                det = float(f.det_score)
                if det < MIN_DETECTION_SCORE:
                    continue
                emb = np.asarray(f.embedding, dtype=np.float32).reshape(-1)
                if emb.shape[0] != EMBEDDING_DIM or not np.all(np.isfinite(emb)):
                    continue
                bbox = [float(x) for x in f.bbox]
                match = _match_face(emb, registry_matrix, person_ids, cosine_threshold)
                detection = FaceDetection(
                    bbox=bbox,
                    det_score=det,
                    embedding=emb,
                    person_id=match[0] if match else None,
                    similarity=match[1] if match else None,
                    mouth_opening=_mouth_opening(f),
                )
                faces.append(detection)
            if faces:
                frames_with_faces += 1
            frames.append(FrameDetections(ts=float(ts), faces=faces))

            if int(ts) // 60 > last_log:
                last_log = int(ts) // 60
                logger.info(
                    "  %d:00 processed (%d frames, %d with faces)",
                    last_log, len(frames), frames_with_faces,
                )

        if not frames:
            raise VisualIdError("video produced zero frames")

        duration_seconds = frames[-1].ts if frames else 0.0
        video_format = _detect_video_format(frames)
        per_turn = _per_turn_vote(
            frames, pyannote_turns, agreement_threshold=agreement_threshold,
        )

        # Build the face-track JSON (drop embeddings — they're not needed
        # by the UI and would balloon the JSON to ~30 MB for a 45-min source).
        face_track_payload = {
            "json_version": FACE_TRACK_JSON_VERSION,
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dim": EMBEDDING_DIM,
            "sample_rate": sample_rate,
            "video_s3_key": video_s3_key,
            "video_format": video_format,
            "duration_seconds": duration_seconds,
            "frame_width": frame_width,
            "frame_height": frame_height,
            "frames": [
                {
                    "ts": f.ts,
                    "faces": [
                        {
                            "bbox": face.bbox,
                            "det_score": face.det_score,
                            "person_id": str(face.person_id) if face.person_id else None,
                            "similarity": face.similarity,
                            "mouth_opening": face.mouth_opening,
                        }
                        for face in f.faces
                    ],
                }
                for f in frames
                if f.faces  # skip empty frames to keep JSON small
            ],
        }
        upload_raw(face_track_key, json.dumps(face_track_payload, ensure_ascii=False))
        logger.info(
            "Stored face-track JSON: s3://%s/%s",
            settings.s3_raw_bucket, face_track_key,
        )

        # Slice B — persist per-detection embeddings to source_face_detections.
        # The JSON above drops them; this table keeps them for intra-source
        # clustering + cross-source similarity propagation. Idempotent:
        # skipped if the source already has detection rows.
        if session is not None and source_id is not None:
            _persist_face_detections(session, source_id, frames)

        # Slice B PR 1.5 — when running remotely (no DB access), emit
        # the per-detection embeddings to an S3 npz so the API can
        # consume them after the SageMaker invoke returns.
        face_detections_key: str | None = None
        if emit_detections_artefact:
            face_detections_key = _emit_face_detections_npz(audio_s3_key, frames)

    distinct_persons = len({
        face.person_id
        for f in frames for face in f.faces
        if face.person_id is not None
    })
    turns_matched = sum(1 for r in per_turn if r is not None)

    return VisualIdentifyResult(
        face_track_s3_key=face_track_key,
        duration_seconds=duration_seconds,
        frames_processed=len(frames),
        frames_with_faces=frames_with_faces,
        distinct_persons_seen=distinct_persons,
        video_format=video_format,
        turns_visually_matched=turns_matched,
        per_turn=per_turn,
        face_detections_s3_key=face_detections_key,
    )


def _emit_face_detections_npz(
    audio_s3_key: str,
    frames: list["FrameDetections"],
) -> str | None:
    """Slice B PR 1.5 — write a ``.npz`` of per-detection data to S3
    so the GPU container can hand embeddings back to the API for
    SourceFaceDetection inserts. Only the *remote* path uses this;
    the local path persists directly via ``_persist_face_detections``.

    Returns the S3 key (under ``settings.s3_raw_bucket``) or ``None``
    if there were no valid detections.
    """
    import io

    rows_ts: list[float] = []
    rows_bbox: list[list[float]] = []
    rows_det: list[float] = []
    rows_emb: list[list[float]] = []
    rows_mouth: list[float] = []
    rows_person: list[str] = []
    rows_match: list[float] = []
    for f in frames:
        for face in f.faces:
            emb = np.asarray(face.embedding, dtype=np.float32).reshape(-1)
            if emb.shape[0] != EMBEDDING_DIM or not np.all(np.isfinite(emb)):
                continue
            rows_ts.append(float(f.ts))
            rows_bbox.append([float(x) for x in face.bbox])
            rows_det.append(float(face.det_score))
            rows_emb.append(emb.tolist())
            # NaN sentinels for nullable floats — the API restores them
            # to None on the way back into Postgres.
            rows_mouth.append(
                float(face.mouth_opening) if face.mouth_opening is not None else float("nan")
            )
            rows_person.append(str(face.person_id) if face.person_id else "")
            rows_match.append(
                float(face.similarity) if face.similarity is not None else float("nan")
            )

    if not rows_ts:
        return None

    key = _face_detections_s3_key_from_audio(audio_s3_key)
    buf = io.BytesIO()
    np.savez_compressed(
        buf,
        frame_ts=np.asarray(rows_ts, dtype=np.float32),
        bbox=np.asarray(rows_bbox, dtype=np.float32),
        det_score=np.asarray(rows_det, dtype=np.float32),
        embedding=np.asarray(rows_emb, dtype=np.float32),
        embedding_model=np.asarray([EMBEDDING_MODEL]),
        mouth_opening=np.asarray(rows_mouth, dtype=np.float32),
        matched_person_id=np.asarray(rows_person),
        match_score=np.asarray(rows_match, dtype=np.float32),
    )
    buf.seek(0)
    upload_raw(key, buf.read())
    logger.info(
        "Wrote %d detections to s3://%s/%s",
        len(rows_ts), settings.s3_raw_bucket, key,
    )
    return key


def _persist_face_detections(
    session: Session,
    source_id: UUID,
    frames: list["FrameDetections"],
) -> int:
    """Slice B — write one ``source_face_detections`` row per detected
    face for the given source. Idempotent: if the source already has
    detection rows, this is a no-op (and the count is returned for
    logging). The clustering pass (Slice B PR 2) populates ``cluster_id``
    later; rows land with NULL here.

    Returns the number of rows inserted (0 if skipped).
    """
    existing = session.query(sa_func.count(SourceFaceDetection.detection_id)).filter(
        SourceFaceDetection.source_id == source_id,
    ).scalar() or 0
    if existing > 0:
        logger.info(
            "source_face_detections already populated for %s (%d rows); skip",
            source_id, existing,
        )
        return 0

    rows: list[SourceFaceDetection] = []
    for f in frames:
        for face in f.faces:
            # Defensive: shape was already validated upstream during
            # detection, but guard so a malformed embedding here can't
            # poison the whole batch.
            emb = np.asarray(face.embedding, dtype=np.float32).reshape(-1)
            if emb.shape[0] != EMBEDDING_DIM or not np.all(np.isfinite(emb)):
                continue
            bbox = face.bbox
            rows.append(SourceFaceDetection(
                source_id=source_id,
                frame_ts=float(f.ts),
                bbox_x1=float(bbox[0]),
                bbox_y1=float(bbox[1]),
                bbox_x2=float(bbox[2]),
                bbox_y2=float(bbox[3]),
                det_score=float(face.det_score),
                embedding=emb.tolist(),
                embedding_model=EMBEDDING_MODEL,
                mouth_opening=(
                    float(face.mouth_opening) if face.mouth_opening is not None else None
                ),
                matched_person_id=face.person_id,
                match_score=(
                    float(face.similarity) if face.similarity is not None else None
                ),
                cluster_id=None,
            ))

    if not rows:
        return 0
    session.add_all(rows)
    session.commit()
    logger.info(
        "Persisted %d source_face_detections rows for %s",
        len(rows), source_id,
    )
    return len(rows)


def enroll_face_from_image(
    session: Session,
    *,
    person_id: UUID,
    source_id: UUID | None,
    image_path: Path,
    frame_ts: float | None,
    created_by: str = "manual",
) -> tuple[UUID, float, float]:
    """Detect the largest face in ``image_path`` and write a
    person_face_embeddings row.

    Returns ``(face_embedding_id, det_score, image_width × image_height)``.
    Raises VisualIdError if no faces are detected.
    """
    import cv2

    if created_by not in ("manual", "headshot", "auto-confirmed"):
        raise VisualIdError(f"created_by must be 'manual'/'headshot'/'auto-confirmed', got {created_by!r}")

    img = cv2.imread(str(image_path))
    if img is None:
        raise VisualIdError(f"could not read image at {image_path}")

    face_app = _get_face_app()
    faces = face_app.get(img)
    if not faces:
        raise VisualIdError("no faces detected in image")

    # Pick the largest face by bbox area.
    def area(f) -> float:
        x1, y1, x2, y2 = f.bbox
        return float((x2 - x1) * (y2 - y1))

    best = max(faces, key=area)
    emb = np.asarray(best.embedding, dtype=np.float32).reshape(-1)
    if emb.shape[0] != EMBEDDING_DIM or not np.all(np.isfinite(emb)):
        raise VisualIdError("face embedding was non-finite")

    row = PersonFaceEmbedding(
        person_id=person_id,
        source_id=source_id,
        frame_ts=frame_ts,
        embedding=emb.tolist(),
        embedding_model=EMBEDDING_MODEL,
        created_by=created_by,
    )
    session.add(row)
    session.commit()

    h, w = img.shape[:2]
    return row.face_embedding_id, float(best.det_score), float(h * w)

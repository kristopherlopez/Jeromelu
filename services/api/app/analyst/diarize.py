"""pyannote diarization + per-turn voice embeddings.

Phase 2: replaces Deepgram's diarizer end-to-end. For an audio object
already in S3:

    1. Download audio, convert to 16 kHz mono WAV.
    2. Run the configured pyannote diarization pipeline (default
       ``pyannote/speaker-diarization-community-1``) → list of speaker turns.
    3. For each turn, compute sliding-window embeddings (2 s window,
       0.5 s hop) using pyannote/wespeaker-voxceleb-resnet34-LM (256-dim,
       the embedder bundled with the diarization pipeline). Pick the
       medoid as the representative.
    4. Persist a single JSON to s3://jeromelu-raw-transcripts that
       carries both diarization and per-turn embeddings; the medoid is
       what gets indexed in source_speakers.embedding (Phase 3 voice
       matching), and the full window list lives here for sliding-window
       voting against the voiceprint registry.

This module makes no DB writes — it produces an artefact that
`transcribe.py` then merges with Deepgram words to populate
source_speakers + source_chunks.

Failure mode: no fallback. Any error → DiarizationError raised.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from jeromelu_shared.config import settings
from jeromelu_shared.s3 import download_raw, get_s3_client, upload_raw

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Sliding-window parameters for per-turn embedding extraction. Tuned for
#: ECAPA/wespeaker — short enough to capture a single phrase, long enough
#: to be acoustically stable. Kept as module constants (not config) because
#: they're tightly coupled to the embedding model's expected receptive field.
WINDOW_SECONDS = 2.0
WINDOW_HOP_SECONDS = 0.5

#: Pyannote sometimes emits sub-100ms "turns" — single-syllable backchannels,
#: laughs, breaths. The wespeaker embedder can't produce a stable embedding
#: from that little audio (returns all-NaN). Skip outright; downstream gets
#: a NULL embedding and these turns simply don't participate in voice ID.
MIN_TURN_DURATION = 0.3

#: The embedding model bundled with the pyannote-3.1 diarization pipeline.
#: Already cached locally as a side-effect of running the pipeline.
EMBEDDING_MODEL = "pyannote/wespeaker-voxceleb-resnet34-LM"
EMBEDDING_DIM = 256

#: Bumped when the JSON shape changes; previous versions are detected as
#: stale and re-run. Phase 1 produced unversioned JSON (treated as v1).
JSON_VERSION = 2


# ---------------------------------------------------------------------------
# Lazy-cached models — loaded once per process. On a long-lived inference
# server (Phase 5.5 SageMaker Async) the pipeline + embedding model load
# is ~30 s and we want to amortise it across calls. Local re-runs benefit
# too (skip ~30 s of model load on every `make transcribe FORCE=1`).
# ---------------------------------------------------------------------------

_pipeline = None
_emb_inference = None


def _get_pipeline():
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    if not settings.huggingface_api_key:
        raise DiarizationError(
            "HUGGINGFACE_API_KEY is not configured. Accept the model license at "
            f"https://huggingface.co/{settings.pyannote_model} (and the "
            "underlying sub-models the pipeline pulls in — segmentation + "
            "wespeaker-voxceleb-resnet34-LM) and put your token in .env as "
            "HUGGINGFACE_API_KEY=hf_..."
        )
    try:
        from pyannote.audio import Pipeline
    except ImportError as exc:
        raise DiarizationError(
            f"pyannote.audio not installed: {exc}. "
            "Run `pip install -r services/api/requirements.txt`."
        ) from exc
    try:
        from ._pyannote_compat import token_kwargs
        pipeline = Pipeline.from_pretrained(
            settings.pyannote_model,
            **token_kwargs(settings.huggingface_api_key),
        )
    except Exception as exc:
        raise DiarizationError(
            f"Failed to load pyannote pipeline ({type(exc).__name__}): {exc}"
        ) from exc
    try:
        import torch
        if torch.cuda.is_available():
            pipeline.to(torch.device("cuda"))
            logger.info("pyannote pipeline loaded on CUDA")
        else:
            logger.info("pyannote pipeline loaded on CPU (5–10× slower than GPU)")
    except Exception:
        pass
    _pipeline = pipeline
    return _pipeline


def _get_emb_inference():
    global _emb_inference
    if _emb_inference is not None:
        return _emb_inference
    try:
        from pyannote.audio import Inference, Model
    except ImportError as exc:
        raise DiarizationError(f"pyannote.audio missing: {exc}") from exc
    try:
        from ._pyannote_compat import token_kwargs
        emb_model = Model.from_pretrained(
            EMBEDDING_MODEL,
            **token_kwargs(settings.huggingface_api_key),
        )
    except Exception as exc:
        raise DiarizationError(
            f"Failed to load embedding model ({type(exc).__name__}): {exc}"
        ) from exc
    try:
        import torch
        if torch.cuda.is_available():
            emb_model = emb_model.to(torch.device("cuda"))
    except Exception:
        pass
    _emb_inference = Inference(emb_model, window="whole")
    return _emb_inference


# ---------------------------------------------------------------------------
# Result + errors
# ---------------------------------------------------------------------------

@dataclass
class DiarizeResult:
    audio_s3_key: str
    pyannote_s3_key: str
    distinct_speakers: int
    turns_count: int
    duration_seconds: float | None
    pyannote_model: str
    embedding_model: str
    skipped: bool  # True when JSON already existed at JSON_VERSION and force=False


class DiarizationError(Exception):
    """Raised when pyannote diarization fails."""


# ---------------------------------------------------------------------------
# Helpers — S3 + ffmpeg
# ---------------------------------------------------------------------------

def _pyannote_s3_key_from_audio(audio_s3_key: str) -> str:
    if audio_s3_key.endswith(".m4a"):
        return audio_s3_key[: -len(".m4a")] + ".pyannote.json"
    return audio_s3_key + ".pyannote.json"


def _download_audio(audio_s3_key: str, dest: Path) -> None:
    client = get_s3_client()
    client.download_file(settings.s3_audio_bucket, audio_s3_key, str(dest))


def _convert_to_wav(src: Path, dst: Path) -> None:
    """m4a → 16 kHz mono WAV. ffmpeg is already a yt-dlp dep."""
    if shutil.which("ffmpeg") is None:
        raise DiarizationError("ffmpeg not found on PATH")
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", "16000", str(dst)],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise DiarizationError(
            f"ffmpeg conversion failed: {proc.stderr.decode('utf-8', errors='replace')}"
        )


def _raw_object_exists(key: str) -> bool:
    client = get_s3_client()
    try:
        client.head_object(Bucket=settings.s3_raw_bucket, Key=key)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Helpers — embeddings
# ---------------------------------------------------------------------------

def _sliding_windows(start: float, end: float) -> list[tuple[float, float]]:
    """Generate (window_start, window_end) pairs for a turn.

    If the turn is shorter than WINDOW_SECONDS, returns a single window
    spanning the entire turn (the embedder handles short audio fine; we
    just lose the per-window granularity).
    """
    if end - start < WINDOW_SECONDS:
        return [(start, end)]
    windows: list[tuple[float, float]] = []
    t = start
    while t + WINDOW_SECONDS <= end:
        windows.append((t, t + WINDOW_SECONDS))
        t += WINDOW_HOP_SECONDS
    # Always include a tail window to cover the last bit if the hop didn't
    # land on `end` exactly.
    if windows and windows[-1][1] < end - 0.1:
        windows.append((max(end - WINDOW_SECONDS, start), end))
    return windows


def _medoid(vectors: np.ndarray) -> np.ndarray:
    """Return the vector with the minimum sum of cosine distances to the
    rest. For N=1, returns the only vector. For N=2, returns the first
    (they're equally far from each other)."""
    if len(vectors) == 1:
        return vectors[0]
    # Cosine distance: 1 - cos_sim = 1 - (a·b) / (|a||b|)
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0  # don't divide by zero on degenerate windows
    normalised = vectors / norms
    sim = normalised @ normalised.T  # NxN cosine similarity
    dists = 1.0 - sim
    sums = dists.sum(axis=1)
    return vectors[int(np.argmin(sums))]


def _extract_turn_embeddings(
    inference,  # pyannote.audio.Inference
    audio_input: Any,
    turns: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """For each turn, compute sliding-window embeddings + medoid.

    ``audio_input`` is whatever ``pyannote.audio.Inference.crop`` accepts
    as its first argument: a file path (pyannote 3.x) or a dict
    ``{"waveform": tensor, "sample_rate": int}`` (pyannote 3 + 4). The
    container ships pyannote 4 without torchcodec, so file-path input
    triggers a silent ``torchcodec.AudioDecoder`` import failure inside
    ``crop`` that gets swallowed by the per-window ``except Exception``
    below — producing empty embeddings on every turn. Always pass the
    dict form so both versions of pyannote work.

    Returns a list parallel to ``turns`` with two extra keys per turn:
    ``embedding_medoid`` (list[float]) and ``embedding_windows``
    (list of {start, end, embedding}).
    """
    from pyannote.core import Segment

    enriched: list[dict[str, Any]] = []
    skipped_short = 0
    skipped_nan = 0
    for i, turn in enumerate(turns):
        # Skip too-short turns — embedder returns NaN on these.
        if turn["end"] - turn["start"] < MIN_TURN_DURATION:
            skipped_short += 1
            enriched.append({**turn, "embedding_medoid": None, "embedding_windows": []})
            continue

        windows = _sliding_windows(turn["start"], turn["end"])
        window_embs: list[dict[str, Any]] = []
        emb_vectors: list[np.ndarray] = []
        for w_start, w_end in windows:
            seg = Segment(w_start, w_end)
            try:
                emb = inference.crop(audio_input, seg)
            except Exception as exc:
                logger.debug(
                    "Embedding extraction failed for turn %d window %.2f-%.2f: %s",
                    i, w_start, w_end, exc,
                )
                continue
            emb = np.asarray(emb).reshape(-1)  # 1-D vector
            if emb.shape[0] != EMBEDDING_DIM:
                raise DiarizationError(
                    f"Unexpected embedding dim {emb.shape[0]} (expected {EMBEDDING_DIM})"
                )
            if not np.all(np.isfinite(emb)):
                # Degenerate audio span — embedder returned NaN/inf. Skip
                # this window; if all windows are bad we'll write a NULL
                # medoid for the turn.
                skipped_nan += 1
                continue
            emb_vectors.append(emb)
            window_embs.append({
                "start": float(w_start),
                "end": float(w_end),
                "embedding": emb.tolist(),
            })

        if not emb_vectors:
            enriched.append({**turn, "embedding_medoid": None, "embedding_windows": []})
            continue

        medoid = _medoid(np.vstack(emb_vectors))
        enriched.append({
            **turn,
            "embedding_medoid": medoid.tolist(),
            "embedding_windows": window_embs,
        })

        if (i + 1) % 50 == 0:
            logger.info("Embedded %d / %d turns", i + 1, len(turns))

    if skipped_short or skipped_nan:
        logger.info(
            "Embedding done. Skipped %d sub-%.2fs turns + %d NaN windows",
            skipped_short, MIN_TURN_DURATION, skipped_nan,
        )
    return enriched


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def diarize(audio_s3_key: str, *, force: bool = False) -> DiarizeResult:
    """Run pyannote diarization + per-turn embedding extraction.

    Writes the combined JSON to ``s3://{raw_bucket}/<key>``. Idempotent:
    if a JSON at the current ``JSON_VERSION`` already exists, returns
    early with ``skipped=True``. Older-version JSONs are re-run to add
    embeddings.

    Phase 5.5: when ``settings.lineup_remote`` is true, dispatches to
    the SageMaker Async endpoint instead of running locally. The
    artefact contract (S3 key, JSON shape) is identical so callers
    don't change.
    """
    if settings.lineup_remote:
        from .remote import diarize_remote
        return diarize_remote(audio_s3_key, force=force)

    if not settings.huggingface_api_key:
        raise DiarizationError(
            "HUGGINGFACE_API_KEY is not configured. Accept the model license at "
            f"https://huggingface.co/{settings.pyannote_model} (and the "
            "underlying sub-models the pipeline pulls in — segmentation + "
            "wespeaker-voxceleb-resnet34-LM) and put your token in .env as "
            "HUGGINGFACE_API_KEY=hf_..."
        )

    pyannote_key = _pyannote_s3_key_from_audio(audio_s3_key)

    if not force and _raw_object_exists(pyannote_key):
        existing = json.loads(download_raw(pyannote_key))
        if existing.get("json_version", 1) >= JSON_VERSION:
            logger.info(
                "pyannote JSON already at version %d at %s — skipping",
                JSON_VERSION, pyannote_key,
            )
            return DiarizeResult(
                audio_s3_key=audio_s3_key,
                pyannote_s3_key=pyannote_key,
                distinct_speakers=existing.get("distinct_speakers", 0),
                turns_count=len(existing.get("turns", [])),
                duration_seconds=existing.get("duration_seconds"),
                pyannote_model=existing.get("model", settings.pyannote_model),
                embedding_model=existing.get("embedding_model", EMBEDDING_MODEL),
                skipped=True,
            )
        logger.info(
            "Existing pyannote JSON is older than v%d — re-running for embeddings",
            JSON_VERSION,
        )

    # Load (or fetch from cache) the pyannote pipeline + embedding model.
    # Module-level caches mean a long-lived inference server (Phase 5.5
    # SageMaker Async) amortises the ~30 s load across calls.
    pipeline = _get_pipeline()
    emb_inference = _get_emb_inference()

    with tempfile.TemporaryDirectory(prefix="jeromelu-diarize-") as tmp:
        tmpdir = Path(tmp)
        m4a_path = tmpdir / "audio.m4a"
        wav_path = tmpdir / "audio.wav"

        logger.info(
            "Downloading audio from s3://%s/%s",
            settings.s3_audio_bucket, audio_s3_key,
        )
        _download_audio(audio_s3_key, m4a_path)

        logger.info("Converting m4a -> 16 kHz mono WAV")
        _convert_to_wav(m4a_path, wav_path)

        logger.info("Running diarization on %s", wav_path)
        # Pre-load audio to dict form. Pyannote 4 hard-requires torchcodec
        # for file-path input (uses torchcodec.AudioDecoder internally),
        # but torchcodec needs a shared-Python build that the AWS DLC
        # base image doesn't ship — so we uninstalled torchcodec in the
        # GPU container and load the WAV with Python's stdlib ``wave``
        # module here. The dict form is also accepted by pyannote 3.x,
        # so local dev still works unchanged. No new pip deps required:
        # the WAV format is fixed (16 kHz mono PCM16) since
        # ``_convert_to_wav`` writes it.
        import wave as _wave
        import torch as _torch
        with _wave.open(str(wav_path), "rb") as _wf:
            _sample_rate = _wf.getframerate()
            _n_channels = _wf.getnchannels()
            _n_frames = _wf.getnframes()
            _sampwidth = _wf.getsampwidth()
            _raw = _wf.readframes(_n_frames)
        if _sampwidth != 2:
            raise DiarizationError(
                f"unexpected WAV sample width {_sampwidth}B; "
                "ffmpeg should write 16-bit PCM"
            )
        # int16 → float32 in [-1, 1], shape (channels, frames)
        _waveform_np = np.frombuffer(_raw, dtype=np.int16).astype(np.float32) / 32768.0
        _waveform_np = _waveform_np.reshape(-1, _n_channels).T
        _waveform = _torch.from_numpy(_waveform_np.copy())
        _audio_input = {"waveform": _waveform, "sample_rate": _sample_rate}
        _result = pipeline(_audio_input)
        # Pyannote 4 returns ``DiarizeOutput`` (dataclass wrapping
        # speaker_diarization + exclusive_speaker_diarization + centroids);
        # pyannote 3 returns the ``Annotation`` directly. Unwrap if needed
        # so the same call site supports both versions.
        diarization = getattr(_result, "speaker_diarization", _result)

        turns: list[dict[str, Any]] = []
        for segment, _, speaker in diarization.itertracks(yield_label=True):
            turns.append({
                "start": float(segment.start),
                "end": float(segment.end),
                "speaker": speaker,  # 'SPEAKER_00', 'SPEAKER_01', ...
            })
        turns.sort(key=lambda t: t["start"])

        logger.info(
            "Extracting embeddings: %d turns × ~%d windows each",
            len(turns),
            int(WINDOW_SECONDS / WINDOW_HOP_SECONDS) + 1,
        )
        # Reuse the already-loaded waveform dict so ``inference.crop``
        # doesn't try to file-read the WAV via torchcodec — see the
        # docstring on ``_extract_turn_embeddings``.
        enriched_turns = _extract_turn_embeddings(emb_inference, _audio_input, turns)

        distinct_speakers = len({t["speaker"] for t in enriched_turns})
        duration_seconds = max(
            (t["end"] for t in enriched_turns), default=None,
        )

        payload = {
            "json_version": JSON_VERSION,
            "model": settings.pyannote_model,
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dim": EMBEDDING_DIM,
            "window_seconds": WINDOW_SECONDS,
            "window_hop_seconds": WINDOW_HOP_SECONDS,
            "audio_s3_key": audio_s3_key,
            "duration_seconds": duration_seconds,
            "distinct_speakers": distinct_speakers,
            "turns": enriched_turns,
        }

        upload_raw(
            pyannote_key,
            json.dumps(payload, ensure_ascii=False),
        )
        logger.info(
            "Stored pyannote JSON: s3://%s/%s",
            settings.s3_raw_bucket, pyannote_key,
        )

    return DiarizeResult(
        audio_s3_key=audio_s3_key,
        pyannote_s3_key=pyannote_key,
        distinct_speakers=distinct_speakers,
        turns_count=len(enriched_turns),
        duration_seconds=duration_seconds,
        pyannote_model=settings.pyannote_model,
        embedding_model=EMBEDDING_MODEL,
        skipped=False,
    )

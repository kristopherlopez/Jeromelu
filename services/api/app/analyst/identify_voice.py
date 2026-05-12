"""Voice enrollment + per-turn identification — Phase 3.

Two public surfaces:

1. ``enroll(...)`` — extract sliding-window embeddings from a span of
   audio explicitly attributed to a Person, write one PersonVoiceprint
   row per valid window. Used by the operator bootstrap CLI today;
   Phase 4 review-UI overrides will write through the same path.

2. ``identify_turn_in_memory(...)`` — per-window cosine k-NN against an
   in-memory voiceprint matrix; majority-vote across windows; return the
   winning Person and confidence stats. Used by ``transcribe.py`` to
   populate ``source_speakers.speaker_person_id``.

The matching is done in-memory, not via pgvector queries, because the
expected registry size in Phase 3 is single-digit hosts × tens of
voiceprints each — well under 1k rows × 256 floats = ~1 MB. Switching
to HNSW server-side k-NN is a Phase 5+ scale concern.
"""

from __future__ import annotations

import contextlib
import logging
import math
import shutil
import subprocess
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import numpy as np
from sqlalchemy.orm import Session

from jeromelu_shared.config import settings
from jeromelu_shared.db import PersonVoiceprint, Source
from jeromelu_shared.s3 import get_s3_client

from .diarize import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
    MIN_TURN_DURATION,
    _medoid,
    _sliding_windows,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Soft floor for an enrollment span. We log-warn below this but don't
#: hard-reject — the operator may have a reason. The plan recommendation
#: is ≥10 s of clean monologue.
SOFT_MIN_ENROLLMENT_DURATION = 10.0

#: Per-window cosine similarity required for a window to vote for a
#: candidate Person. wespeaker on VoxCeleb sits in the 0.6-0.8 range
#: for same-speaker pairs; 0.75 is a reasonable starting threshold.
DEFAULT_COSINE_THRESHOLD = 0.75

#: Fraction of a turn's windows that must agree on the same Person to
#: commit the assignment. With ~5 windows per turn, 0.6 means 3+/5.
DEFAULT_AGREEMENT_THRESHOLD = 0.6

#: Minimum number of windows in a turn for identification to even try.
#: Single-window turns can fluke a high similarity to the wrong host.
DEFAULT_MIN_WINDOWS = 1


# ---------------------------------------------------------------------------
# Result types + errors
# ---------------------------------------------------------------------------

@dataclass
class EnrollResult:
    person_id: UUID
    source_id: UUID | None
    start_ts: float
    end_ts: float
    voiceprints_written: int
    voiceprints_skipped: int  # windows that produced NaN/inf embeddings
    embedding_model: str


@dataclass
class IdentifyResult:
    person_id: UUID
    similarity: float          # max similarity across winning person's windows
    window_agreement: float    # fraction of windows that voted for the winner
    window_count: int          # how many windows participated in the vote


class EnrollmentError(Exception):
    """Raised when enrollment fails (bad audio, missing person, etc.)."""


# ---------------------------------------------------------------------------
# Audio helpers — mirrors diarize.py's lifecycle
# ---------------------------------------------------------------------------

def _download_audio(audio_s3_key: str, dest: Path) -> None:
    client = get_s3_client()
    client.download_file(settings.s3_audio_bucket, audio_s3_key, str(dest))


def _convert_to_wav(src: Path, dst: Path) -> None:
    if shutil.which("ffmpeg") is None:
        raise EnrollmentError("ffmpeg not found on PATH")
    proc = subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", "16000", str(dst)],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise EnrollmentError(
            f"ffmpeg conversion failed: {proc.stderr.decode('utf-8', errors='replace')}"
        )


def _crop_to_wav(src: Path, dst: Path, start_ts: float, end_ts: float) -> None:
    """Crop ``src`` to ``[start_ts, end_ts]`` and write a 16 kHz mono WAV
    to ``dst``. Sample-accurate (``-ss`` *after* ``-i``) at the cost of
    decoding from the start of the file — acceptable for short turn
    spans of a few seconds.
    """
    if shutil.which("ffmpeg") is None:
        raise EnrollmentError("ffmpeg not found on PATH")
    proc = subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(src),
            "-ss", f"{start_ts:.3f}",
            "-to", f"{end_ts:.3f}",
            "-ac", "1", "-ar", "16000",
            str(dst),
        ],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise EnrollmentError(
            f"ffmpeg crop+convert failed for [{start_ts:.2f}, {end_ts:.2f}]: "
            f"{proc.stderr.decode('utf-8', errors='replace')}"
        )


# ---------------------------------------------------------------------------
# Enrollment
# ---------------------------------------------------------------------------

@dataclass
class _EnrollmentContext:
    """Shared setup for a batch of enrollments against the same source.

    Created via :func:`enrollment_context` and consumed by
    :func:`enroll_span_with_context`. Built once per bulk so the
    expensive bits — full-audio download + pyannote model load — are
    amortised across N spans instead of paid per span.
    """
    source_id: UUID
    m4a_path: Path
    tmpdir: Path
    emb_inference: Any  # pyannote Inference; not typed to avoid the heavy import here
    # Slice B PR 2.6 — when prefetch_wav=True the context converts the
    # full m4a to a 16 kHz mono WAV up front. enroll_span_with_context
    # then uses pyannote's native crop on the original timeline instead
    # of doing a per-span ffmpeg crop. Drops per-span overhead from
    # ~3s to ~0.5s. Pays a one-time ~30s conversion cost — worth it
    # above ~5 spans, big win above ~50. None means "fall back to the
    # per-span crop path" — the existing behaviour.
    full_wav_path: Path | None = None


@contextlib.contextmanager
def enrollment_context(
    session: Session,
    source_id: UUID,
    *,
    prefetch_wav: bool = False,
):
    """Yield a shared enrollment context for repeated calls on the same
    source. Use as ``with enrollment_context(db, src_id) as ctx: ...``
    and pass ``ctx`` to :func:`enroll_span_with_context` per span.

    Why this exists: ``enroll(...)`` downloads + converts the full
    source audio and loads the pyannote model **on every call**. The
    bulk-assign endpoint can rack up tens of those — observed ~100s
    per turn (~10 min for a 5-turn batch) before this helper was
    introduced. The context downloads once, loads once, and each span
    only pays for ffmpeg crop + sliding-window embedding (~3s each).
    """
    source = session.query(Source).filter(Source.source_id == source_id).one_or_none()
    if source is None:
        raise EnrollmentError(f"no source with id {source_id}")
    if not source.audio_s3_key:
        raise EnrollmentError(
            f"source {source_id} has no audio_s3_key — run Scout's "
            "acquire_audio first"
        )
    if not settings.huggingface_api_key:
        raise EnrollmentError(
            "HUGGINGFACE_API_KEY is not configured — required to load the "
            "embedding model"
        )

    # Lazy imports — pyannote pulls torch + a chunk of the pip world.
    try:
        from pyannote.audio import Inference, Model
    except ImportError as exc:
        raise EnrollmentError(
            f"pyannote.audio not installed: {exc}. "
            "Run `pip install -r services/api/requirements.txt`."
        ) from exc

    with tempfile.TemporaryDirectory(prefix="jeromelu-enroll-") as tmp:
        tmpdir = Path(tmp)
        m4a_path = tmpdir / "audio.m4a"
        logger.info(
            "Downloading audio for enrollment from s3://%s/%s",
            settings.s3_audio_bucket, source.audio_s3_key,
        )
        _download_audio(source.audio_s3_key, m4a_path)

        full_wav_path: Path | None = None
        if prefetch_wav:
            full_wav_path = tmpdir / "audio.full.wav"
            logger.info(
                "Pre-converting full audio to 16 kHz WAV for bulk enrollment",
            )
            _convert_to_wav(m4a_path, full_wav_path)

        logger.info("Loading embedding model %s", EMBEDDING_MODEL)
        emb_model = Model.from_pretrained(
            EMBEDDING_MODEL,
            use_auth_token=settings.huggingface_api_key,
        )
        try:
            import torch
            if torch.cuda.is_available():
                emb_model = emb_model.to(torch.device("cuda"))
        except Exception:
            pass
        emb_inference = Inference(emb_model, window="whole")

        yield _EnrollmentContext(
            source_id=source_id,
            m4a_path=m4a_path,
            tmpdir=tmpdir,
            emb_inference=emb_inference,
            full_wav_path=full_wav_path,
        )


def enroll_span_with_context(
    session: Session,
    ctx: _EnrollmentContext,
    *,
    person_id: UUID,
    start_ts: float,
    end_ts: float,
    created_by: str = "manual",
) -> EnrollResult:
    """Enroll one span using a pre-built ``ctx`` (see
    :func:`enrollment_context`). Crops the source audio to just the
    span before embedding — sliding-window sizes are unchanged but
    we never reconvert the full 45-min file.

    Voiceprint rows are written with the **original-timeline** start/end
    timestamps so they index correctly against the source's audio later.
    """
    from pyannote.core import Segment

    if end_ts <= start_ts:
        raise EnrollmentError(f"end_ts {end_ts} must be > start_ts {start_ts}")
    duration = end_ts - start_ts
    if duration < MIN_TURN_DURATION:
        raise EnrollmentError(
            f"span {duration:.2f}s is shorter than MIN_TURN_DURATION "
            f"({MIN_TURN_DURATION}s) — embedder won't produce a stable vector"
        )
    if duration < SOFT_MIN_ENROLLMENT_DURATION:
        logger.warning(
            "Enrollment span %.1fs is below the recommended %.0fs minimum. "
            "Voiceprint will be created but match quality may be marginal.",
            duration, SOFT_MIN_ENROLLMENT_DURATION,
        )
    if created_by not in ("manual", "auto-confirmed"):
        raise EnrollmentError(
            f"created_by must be 'manual' or 'auto-confirmed', got {created_by!r}"
        )

    # Two paths:
    #   1. Full WAV pre-converted (prefetch_wav=True in context setup).
    #      Pyannote crops natively against the original timeline. No
    #      per-span ffmpeg crop. ~0.5s per span vs ~3s.
    #   2. m4a only. Crop to a per-span WAV, embed against zero-based
    #      timeline, then offset back. Original behaviour — fine for
    #      single-span use (the upfront WAV convert isn't worth it).
    if ctx.full_wav_path is not None:
        wav_path = ctx.full_wav_path
        windows = _sliding_windows(start_ts, end_ts)
        window_offset = 0.0
    else:
        span_wav = ctx.tmpdir / f"span_{start_ts:.3f}_{end_ts:.3f}.wav"
        _crop_to_wav(ctx.m4a_path, span_wav, start_ts, end_ts)
        wav_path = span_wav
        windows = _sliding_windows(0.0, duration)
        window_offset = start_ts
    logger.info("Embedding %d sliding windows over the span", len(windows))

    skipped = 0
    rows: list[PersonVoiceprint] = []
    for w_start, w_end in windows:
        seg = Segment(w_start, w_end)
        try:
            emb = ctx.emb_inference.crop(str(wav_path), seg)
        except Exception as exc:
            logger.debug(
                "Embedding failed for window %.2f-%.2f: %s", w_start, w_end, exc,
            )
            skipped += 1
            continue
        emb = np.asarray(emb).reshape(-1)
        if emb.shape[0] != EMBEDDING_DIM:
            raise EnrollmentError(
                f"unexpected embedding dim {emb.shape[0]} (expected {EMBEDDING_DIM})"
            )
        if not np.all(np.isfinite(emb)):
            skipped += 1
            continue
        # When using a per-span WAV, windows are zero-based and need
        # `start_ts` added back. With the full WAV, windows are already
        # in original-timeline coords (window_offset=0).
        rows.append(PersonVoiceprint(
            person_id=person_id,
            source_id=ctx.source_id,
            start_ts=float(window_offset + w_start),
            end_ts=float(window_offset + w_end),
            embedding=emb.tolist(),
            embedding_model=EMBEDDING_MODEL,
            created_by=created_by,
        ))

    if not rows:
        raise EnrollmentError(
            f"no valid embeddings produced from the span — all {skipped} windows "
            "failed (audio likely too short, silent, or non-speech)"
        )

    session.add_all(rows)
    session.commit()

    # span_wav is cleaned up with the surrounding tempdir when the
    # context exits — fine to leave it here for the rest of the bulk.

    return EnrollResult(
        person_id=person_id,
        source_id=ctx.source_id,
        start_ts=start_ts,
        end_ts=end_ts,
        voiceprints_written=len(rows),
        voiceprints_skipped=skipped,
        embedding_model=EMBEDDING_MODEL,
    )


def enroll(
    session: Session,
    *,
    person_id: UUID,
    source_id: UUID,
    start_ts: float,
    end_ts: float,
    created_by: str = "manual",
) -> EnrollResult:
    """Enroll a Person from a known span of source audio.

    Quality gate: rejects spans shorter than ``MIN_TURN_DURATION``;
    log-warns but accepts spans shorter than
    ``SOFT_MIN_ENROLLMENT_DURATION``.

    For batches against the same source, prefer the
    :func:`enrollment_context` + :func:`enroll_span_with_context` pair
    — this single-call wrapper rebuilds the audio + model context on
    every invocation.
    """
    with enrollment_context(session, source_id) as ctx:
        return enroll_span_with_context(
            session,
            ctx,
            person_id=person_id,
            start_ts=start_ts,
            end_ts=end_ts,
            created_by=created_by,
        )


# ---------------------------------------------------------------------------
# Identification
# ---------------------------------------------------------------------------

def load_voiceprint_matrix(
    session: Session,
    *,
    embedding_model: str | None = None,
) -> tuple[np.ndarray, list[UUID]]:
    """Load all (or model-scoped) voiceprints into a numpy matrix.

    Returns ``(N×EMBEDDING_DIM matrix, list of N person_ids)``. Empty
    matrix + empty list when the registry is empty — caller must handle.
    """
    q = session.query(
        PersonVoiceprint.embedding,
        PersonVoiceprint.person_id,
    )
    if embedding_model is not None:
        q = q.filter(PersonVoiceprint.embedding_model == embedding_model)
    rows = q.all()
    if not rows:
        return np.zeros((0, EMBEDDING_DIM), dtype=np.float32), []
    matrix = np.array([list(r[0]) for r in rows], dtype=np.float32)
    person_ids = [r[1] for r in rows]
    return matrix, person_ids


def identify_turn_in_memory(
    voiceprints: np.ndarray,        # N × EMBEDDING_DIM
    voiceprint_person_ids: list[UUID],
    window_embeddings: list[list[float]],
    *,
    cosine_threshold: float = DEFAULT_COSINE_THRESHOLD,
    agreement_threshold: float = DEFAULT_AGREEMENT_THRESHOLD,
    min_windows: int = DEFAULT_MIN_WINDOWS,
) -> IdentifyResult | None:
    """Per-window cosine k-NN + majority vote.

    Returns the winning ``IdentifyResult`` if a Person clears both
    thresholds, or ``None`` if the turn is unidentified (no enrolled
    voiceprint matched, or no Person captured enough window votes).
    """
    if len(window_embeddings) < min_windows:
        return None
    if voiceprints.shape[0] == 0:
        return None
    if not window_embeddings:
        return None

    win = np.asarray(window_embeddings, dtype=np.float32)
    if win.ndim != 2 or win.shape[1] != EMBEDDING_DIM:
        return None

    # Cosine similarity: M windows × N voiceprints.
    win_norm = np.linalg.norm(win, axis=1, keepdims=True)
    vp_norm = np.linalg.norm(voiceprints, axis=1, keepdims=True)
    win_n = win / np.maximum(win_norm, 1e-8)
    vp_n = voiceprints / np.maximum(vp_norm, 1e-8)
    sim = win_n @ vp_n.T  # M × N

    best_idx = sim.argmax(axis=1)
    best_sim = sim[np.arange(len(sim)), best_idx]

    # Tally votes per Person, weighted by similarity. Defend against
    # NaN: `NaN < x` returns False, so a naive threshold check would
    # let NaN-similarity windows cast a vote. Skip non-finite explicitly.
    votes: dict[UUID, list[float]] = {}
    for i, idx in enumerate(best_idx):
        s = float(best_sim[i])
        if not math.isfinite(s) or s < cosine_threshold:
            continue
        person_id = voiceprint_person_ids[idx]
        votes.setdefault(person_id, []).append(s)

    if not votes:
        return None

    # Pick the Person with the most votes; tiebreak by max similarity.
    winner_pid, winner_sims = max(
        votes.items(),
        key=lambda kv: (len(kv[1]), max(kv[1])),
    )
    agreement = len(winner_sims) / len(window_embeddings)
    if agreement < agreement_threshold:
        return None

    return IdentifyResult(
        person_id=winner_pid,
        similarity=max(winner_sims),
        window_agreement=agreement,
        window_count=len(window_embeddings),
    )


def identify_pyannote_turns(
    session: Session,
    pyannote_doc: dict[str, Any],
    *,
    cosine_threshold: float = DEFAULT_COSINE_THRESHOLD,
    agreement_threshold: float = DEFAULT_AGREEMENT_THRESHOLD,
) -> list[IdentifyResult | None]:
    """Run identify_turn over every turn in a pyannote JSON.

    Convenience wrapper that loads the voiceprint matrix once, then
    iterates. Returns a list parallel to ``pyannote_doc['turns']``.
    """
    embedding_model = pyannote_doc.get("embedding_model")
    voiceprints, person_ids = load_voiceprint_matrix(
        session, embedding_model=embedding_model,
    )

    results: list[IdentifyResult | None] = []
    if voiceprints.shape[0] == 0:
        # No voiceprints enrolled yet — every turn is unidentified.
        return [None] * len(pyannote_doc.get("turns", []))

    for turn in pyannote_doc.get("turns", []):
        windows = turn.get("embedding_windows") or []
        win_embs = [w["embedding"] for w in windows if "embedding" in w]
        # Defensive filter: pre-fix pyannote JSONs may carry NaN windows.
        # Drop any window that isn't shaped right or has non-finite values.
        win_embs = [
            e for e in win_embs
            if isinstance(e, list) and len(e) == EMBEDDING_DIM
            and all(isinstance(v, (int, float)) and math.isfinite(v) for v in e)
        ]
        if not win_embs:
            results.append(None)
            continue
        results.append(identify_turn_in_memory(
            voiceprints, person_ids, win_embs,
            cosine_threshold=cosine_threshold,
            agreement_threshold=agreement_threshold,
        ))

    return results

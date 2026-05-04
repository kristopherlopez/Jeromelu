"""SageMaker Async Inference handler for Lineup GPU tasks (Phase 5.5).

Single endpoint, two tasks. The request body is a JSON object whose
``task`` field switches between ``diarize`` and ``visual_identify``.
The handler delegates to the same ``app.analyst.diarize`` and
``app.analyst.visual_id`` modules the local CLI uses — only the
process lifecycle (long-lived, GPU-resident model caches) and the
input/output shape change.

The container writes the actual heavyweight artefacts (pyannote.json,
face_track.json) directly to S3 from inside the running task. The
response from this handler is a small status JSON that SageMaker writes
to its own output S3 location; the caller polls there for completion
and then reads the artefacts from their canonical keys.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

# Make the in-tree project source importable. PYTHONPATH already covers
# this in the Dockerfile but we set it again defensively for clarity.
sys.path.insert(0, "/opt/ml/code/services/api")

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s :: %(message)s",
)


# ---------------------------------------------------------------------------
# SageMaker entrypoints
# ---------------------------------------------------------------------------

def model_fn(model_dir: str):
    """Pre-warm the heavyweight models on container startup.

    Each module already keeps its loaded model in a private cache
    (`diarize._pipeline`, `diarize._emb_inference`, `visual_id._face_app`),
    so we just trigger the lazy load once here. Subsequent invocations
    reuse the in-process objects — that's the whole point of the
    long-lived inference server.
    """
    logger.info("[Lineup] model_fn — warming pyannote + InsightFace")
    from app.analyst.diarize import _get_emb_inference, _get_pipeline
    from app.analyst.visual_id import _get_face_app

    _get_pipeline()
    _get_emb_inference()
    _get_face_app()
    logger.info("[Lineup] models ready")
    return {"loaded": True}


def input_fn(request_body: str | bytes, content_type: str) -> dict[str, Any]:
    if isinstance(request_body, bytes):
        request_body = request_body.decode("utf-8")
    if content_type not in ("application/json", "application/x-json"):
        raise ValueError(f"Unsupported content type: {content_type}")
    return json.loads(request_body)


def predict_fn(input_data: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    task = input_data.get("task")
    if task == "diarize":
        return _handle_diarize(input_data)
    if task == "visual_identify":
        return _handle_visual_identify(input_data)
    raise ValueError(f"Unknown task: {task!r}")


def output_fn(prediction: dict[str, Any], accept: str) -> tuple[str, str]:
    return json.dumps(prediction, ensure_ascii=False), "application/json"


# ---------------------------------------------------------------------------
# Task handlers
# ---------------------------------------------------------------------------

def _handle_diarize(payload: dict[str, Any]) -> dict[str, Any]:
    audio_s3_key = payload["audio_s3_key"]
    force = bool(payload.get("force", False))
    logger.info("[Lineup] diarize start: %s force=%s", audio_s3_key, force)

    from app.analyst.diarize import diarize as run_diarize
    result = run_diarize(audio_s3_key, force=force)

    logger.info(
        "[Lineup] diarize ok: %d turns, %d speakers, skipped=%s",
        result.turns_count, result.distinct_speakers, result.skipped,
    )
    return {
        "status": "ok",
        "task": "diarize",
        "audio_s3_key": result.audio_s3_key,
        "pyannote_s3_key": result.pyannote_s3_key,
        "distinct_speakers": result.distinct_speakers,
        "turns_count": result.turns_count,
        "duration_seconds": result.duration_seconds,
        "pyannote_model": result.pyannote_model,
        "embedding_model": result.embedding_model,
        "skipped": result.skipped,
    }


def _handle_visual_identify(payload: dict[str, Any]) -> dict[str, Any]:
    """Visual ID without DB access.

    The orchestrator (the API on Lightsail) loads the face registry from
    Postgres and ships it in the request body. The container does the
    cv2/InsightFace heavy lifting and returns a per-turn match list.
    """
    import numpy as np
    from uuid import UUID

    audio_s3_key = payload["audio_s3_key"]
    video_s3_key = payload["video_s3_key"]
    pyannote_turns = payload["pyannote_turns"]
    cosine_threshold = float(payload.get("cosine_threshold", 0.40))
    agreement_threshold = float(payload.get("agreement_threshold", 0.6))
    sample_rate = float(payload.get("sample_rate", 1.0))

    raw_registry = payload.get("face_registry") or []
    if raw_registry:
        registry_matrix = np.array(
            [r["embedding"] for r in raw_registry], dtype=np.float32,
        )
        person_ids = [UUID(r["person_id"]) for r in raw_registry]
    else:
        registry_matrix = np.zeros((0, 512), dtype=np.float32)
        person_ids = []

    logger.info(
        "[Lineup] visual_identify start: %s registry=%d turns=%d",
        video_s3_key, len(person_ids), len(pyannote_turns),
    )

    from app.analyst.visual_id import visual_identify
    result = visual_identify(
        session=None,
        audio_s3_key=audio_s3_key,
        video_s3_key=video_s3_key,
        pyannote_turns=pyannote_turns,
        sample_rate=sample_rate,
        cosine_threshold=cosine_threshold,
        agreement_threshold=agreement_threshold,
        registry=(registry_matrix, person_ids),
    )

    logger.info(
        "[Lineup] visual_identify ok: %d/%d turns matched, format=%s",
        result.turns_visually_matched, len(pyannote_turns), result.video_format,
    )
    return {
        "status": "ok",
        "task": "visual_identify",
        "face_track_s3_key": result.face_track_s3_key,
        "duration_seconds": result.duration_seconds,
        "frames_processed": result.frames_processed,
        "frames_with_faces": result.frames_with_faces,
        "distinct_persons_seen": result.distinct_persons_seen,
        "video_format": result.video_format,
        "turns_visually_matched": result.turns_visually_matched,
        "per_turn": [
            {
                "person_id": str(m.person_id),
                "similarity": m.similarity,
                "agreement": m.agreement,
                "face_count": m.face_count,
            } if m else None
            for m in result.per_turn
        ],
    }

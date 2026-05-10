"""Local-side wrappers that dispatch Lineup work to the SageMaker
Async endpoint instead of running ML locally (Phase 5.5).

The artefact contracts are unchanged — both `diarize_remote` and
`visual_identify_remote` produce the same S3 keys, JSON shapes, and
return objects as their local counterparts. The container in the GPU
endpoint imports the same `app.analyst.diarize` / `app.analyst.visual_id`
modules and writes to the same buckets, so downstream code (transcribe.py,
the review UI, fusion) is oblivious to where inference ran.

Invocation pattern:
  1. Upload a small JSON request to S3 (audio key, optional registry).
  2. Call ``invoke_endpoint_async`` — returns immediately.
  3. Poll the SageMaker output S3 location for completion (typically
     produces a status JSON within minutes).
  4. Reconstruct the local result type from the persisted artefact.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from jeromelu_shared.config import settings
from jeromelu_shared.s3 import download_raw, get_s3_client, upload_raw

from .diarize import EMBEDDING_MODEL as VOICE_EMBEDDING_MODEL
from .diarize import DiarizationError, DiarizeResult, _pyannote_s3_key_from_audio
from .visual_id import (
    EMBEDDING_DIM as FACE_EMBEDDING_DIM,
    EMBEDDING_MODEL as FACE_EMBEDDING_MODEL,
    VisualIdentifyResult,
    VisualIdError,
    VisualMatch,
    _face_track_s3_key_from_audio,
    load_face_registry,
)

logger = logging.getLogger(__name__)


class RemoteInferenceError(Exception):
    """Raised when the SageMaker invocation fails or times out."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_endpoint_configured() -> str:
    """Return the configured endpoint name; raise if remote mode is on
    without an endpoint name in settings."""
    if not settings.lineup_endpoint_name:
        raise RemoteInferenceError(
            "lineup_endpoint_name is empty — set LINEUP_ENDPOINT_NAME in .env"
        )
    return settings.lineup_endpoint_name


def _runtime_client():
    """boto3 SageMaker Runtime client. Region pinned via settings so the
    endpoint, ECR image, and S3 buckets stay co-located."""
    import boto3
    return boto3.client("sagemaker-runtime", region_name=settings.lineup_aws_region)


def _invoke_async(payload: dict[str, Any], *, timeout: int) -> dict[str, Any]:
    """Submit a request, poll for completion, return the parsed status JSON.

    The SageMaker Async pattern:
      - Client uploads the request body to S3 under InputLocation.
      - Client calls ``invoke_endpoint_async``; SageMaker queues the job.
      - On completion, SageMaker writes the response body to OutputLocation.
      - We poll OutputLocation until the object appears.
    """
    endpoint = _ensure_endpoint_configured()
    client = _runtime_client()

    # Stage the input JSON in the SageMaker staging bucket (us-east-1 if
    # the endpoint is there, regardless of where the artefact buckets
    # live — see lineup_staging_bucket settings doc).
    request_id = str(uuid4())
    input_key = f"{settings.lineup_input_prefix}/{request_id}.json"
    s3 = get_s3_client()
    s3.put_object(
        Bucket=settings.lineup_staging_bucket,
        Key=input_key,
        Body=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
    )
    input_location = f"s3://{settings.lineup_staging_bucket}/{input_key}"
    logger.info("[Lineup remote] %s submitted → %s", payload.get("task"), input_location)

    response = client.invoke_endpoint_async(
        EndpointName=endpoint,
        ContentType="application/json",
        InputLocation=input_location,
        Accept="application/json",
    )
    output_location: str = response["OutputLocation"]

    # Poll for the output object. The output URL points at the staging
    # bucket — SageMaker writes the response body there on success and a
    # separate FailureLocation on error.
    deadline = time.time() + timeout
    output_key = output_location.replace(f"s3://{settings.lineup_staging_bucket}/", "")
    failure_location = response.get("FailureLocation", "")
    failure_key = (
        failure_location.replace(f"s3://{settings.lineup_staging_bucket}/", "")
        if failure_location else None
    )

    while time.time() < deadline:
        try:
            obj = s3.get_object(Bucket=settings.lineup_staging_bucket, Key=output_key)
            body = obj["Body"].read().decode("utf-8")
            return json.loads(body)
        except Exception:
            pass
        if failure_key:
            try:
                obj = s3.get_object(Bucket=settings.lineup_staging_bucket, Key=failure_key)
                msg = obj["Body"].read().decode("utf-8", errors="replace")
                raise RemoteInferenceError(f"Endpoint reported failure: {msg[:500]}")
            except RemoteInferenceError:
                raise
            except Exception:
                pass
        time.sleep(2.0)

    raise RemoteInferenceError(
        f"Timed out after {timeout}s waiting for {output_location}"
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def diarize_remote(audio_s3_key: str, *, force: bool = False, timeout: int = 1200) -> DiarizeResult:
    """Run diarization on the SageMaker endpoint instead of locally.

    Returns a ``DiarizeResult`` identical to the local function — the
    pyannote.json artefact is written to the same S3 key, so callers
    that want the full turn list (transcribe.py) re-fetch it after this
    call returns the lightweight summary.
    """
    pyannote_key = _pyannote_s3_key_from_audio(audio_s3_key)

    # Idempotency: same JSON_VERSION reuse path the local function honors.
    # Local container will skip the heavy work too, but doing the check
    # client-side avoids the round-trip + cold-start when the artefact
    # is already up-to-date.
    if not force:
        try:
            existing = json.loads(download_raw(pyannote_key))
            from .diarize import JSON_VERSION
            if existing.get("json_version", 1) >= JSON_VERSION:
                logger.info(
                    "[Lineup remote] pyannote JSON already at v%d — short-circuit",
                    JSON_VERSION,
                )
                return DiarizeResult(
                    audio_s3_key=audio_s3_key,
                    pyannote_s3_key=pyannote_key,
                    distinct_speakers=existing.get("distinct_speakers", 0),
                    turns_count=len(existing.get("turns", [])),
                    duration_seconds=existing.get("duration_seconds"),
                    pyannote_model=existing.get("model", settings.pyannote_model),
                    embedding_model=existing.get("embedding_model", VOICE_EMBEDDING_MODEL),
                    skipped=True,
                )
        except Exception:
            pass

    response = _invoke_async(
        {"task": "diarize", "audio_s3_key": audio_s3_key, "force": force},
        timeout=timeout,
    )
    if response.get("status") != "ok":
        raise DiarizationError(f"Remote diarize failed: {response}")
    return DiarizeResult(
        audio_s3_key=response["audio_s3_key"],
        pyannote_s3_key=response["pyannote_s3_key"],
        distinct_speakers=response["distinct_speakers"],
        turns_count=response["turns_count"],
        duration_seconds=response.get("duration_seconds"),
        pyannote_model=response.get("pyannote_model", settings.pyannote_model),
        embedding_model=response.get("embedding_model", VOICE_EMBEDDING_MODEL),
        skipped=response.get("skipped", False),
    )


def visual_identify_remote(
    session: Session,
    *,
    audio_s3_key: str,
    video_s3_key: str,
    pyannote_turns: list[dict[str, Any]],
    cosine_threshold: float = 0.40,
    agreement_threshold: float = 0.6,
    sample_rate: float = 1.0,
    timeout: int = 1200,
) -> VisualIdentifyResult:
    """Run visual identification on the SageMaker endpoint.

    The face registry is pre-loaded from Postgres (here, in the API
    process) and shipped in the request — the container has no DB
    credentials. Result objects + S3 face-track JSON keys are
    identical to the local path.
    """
    # Pre-load the face registry from Postgres and serialise into the
    # request body. The container has no DB credentials and shouldn't.
    matrix, person_ids = load_face_registry(session)
    face_registry = [
        {"person_id": str(pid), "embedding": [float(x) for x in matrix[i]]}
        for i, pid in enumerate(person_ids)
    ]

    # Visual ID only uses start/end/speaker from each turn — strip the
    # embedding_medoid + embedding_windows fields before sending. Drops
    # the request body from ~28 MB to ~50 KB on a 45-min source. Earlier
    # versions sent the full turn list and required the TorchServe
    # max-request-size to be raised; this trim makes that bump optional.
    slim_turns = [
        {
            "start": t["start"],
            "end": t["end"],
            "speaker": t.get("speaker"),
        }
        for t in pyannote_turns
    ]

    response = _invoke_async(
        {
            "task": "visual_identify",
            "audio_s3_key": audio_s3_key,
            "video_s3_key": video_s3_key,
            "pyannote_turns": slim_turns,
            "cosine_threshold": cosine_threshold,
            "agreement_threshold": agreement_threshold,
            "sample_rate": sample_rate,
            "face_registry": face_registry,
        },
        timeout=timeout,
    )
    if response.get("status") != "ok":
        raise VisualIdError(f"Remote visual_identify failed: {response}")

    per_turn: list[VisualMatch | None] = []
    for entry in response.get("per_turn", []):
        if entry is None:
            per_turn.append(None)
            continue
        per_turn.append(VisualMatch(
            person_id=UUID(entry["person_id"]),
            similarity=float(entry["similarity"]),
            agreement=float(entry["agreement"]),
            face_count=int(entry["face_count"]),
        ))

    return VisualIdentifyResult(
        face_track_s3_key=response["face_track_s3_key"],
        duration_seconds=float(response.get("duration_seconds", 0.0)),
        frames_processed=int(response.get("frames_processed", 0)),
        frames_with_faces=int(response.get("frames_with_faces", 0)),
        distinct_persons_seen=int(response.get("distinct_persons_seen", 0)),
        video_format=response.get("video_format", "audio_only"),
        turns_visually_matched=int(response.get("turns_visually_matched", 0)),
        per_turn=per_turn,
    )

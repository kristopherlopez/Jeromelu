"""Pure helpers for the transcribe pipeline.

Deliberately split out of transcribe.py so unit tests (and any caller
that just wants the merge math) can import them without dragging in
diarize → pyannote → torch. Anything in this file must stay pure:

  - no DB session
  - no S3 / Deepgram / pyannote clients
  - no settings, no env vars

If a helper grows an IO dependency, move it back into transcribe.py.
"""

from __future__ import annotations

import hashlib
import math
from typing import Any

from jeromelu_shared.db import SourceSpeaker


def transcript_s3_key_from_audio(audio_s3_key: str) -> str:
    """Mirror the audio S3 path under raw-transcripts as a Deepgram JSON."""
    if audio_s3_key.endswith(".m4a"):
        return audio_s3_key[: -len(".m4a")] + ".deepgram.json"
    return audio_s3_key + ".deepgram.json"


def checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def utterances(deepgram_response: dict[str, Any]) -> list[dict[str, Any]]:
    return deepgram_response.get("results", {}).get("utterances", []) or []


def audio_duration(deepgram_response: dict[str, Any]) -> float | None:
    return deepgram_response.get("metadata", {}).get("duration")


def request_id(deepgram_response: dict[str, Any]) -> str | None:
    return deepgram_response.get("metadata", {}).get("request_id")


def safe_embedding(medoid: list[float] | None) -> list[float] | None:
    """Reject embeddings containing NaN/inf — pgvector won't store them.

    Mirrors the diarize-side filter; this is a belt-and-braces check so old
    pyannote JSONs that leaked NaNs (pre-fix) still ingest cleanly: their
    bad rows get a NULL embedding instead of failing the whole transaction.
    """
    if medoid is None:
        return None
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in medoid):
        return None
    return medoid


def max_overlap_turn(
    utt_start: float, utt_end: float, turn_rows: list[SourceSpeaker],
) -> SourceSpeaker | None:
    """Pick the SourceSpeaker turn with maximum temporal overlap with the
    utterance span. Linear scan — fine for the sample sizes here."""
    best: SourceSpeaker | None = None
    best_overlap = 0.0
    for t in turn_rows:
        overlap = max(0.0, min(utt_end, t.end_ts) - max(utt_start, t.start_ts))
        if overlap > best_overlap:
            best_overlap = overlap
            best = t
    return best

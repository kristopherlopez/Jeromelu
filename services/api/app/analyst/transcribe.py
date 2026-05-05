"""Transcript materialisation — Analyst's first Transform surface.

Phase 2 pipeline: Deepgram for words, pyannote for diarization. Reads
audio Scout has already collected (`sources.audio_s3_key`,
``ingestion_status='collected'``), runs both diarizers, merges by
timestamp, and writes the structured transcript:

    source_documents      raw_text + checksum + chunk_count + s3_key
                          (Deepgram JSON in S3, replayable)
    source_speakers       per-pyannote-turn rows. Each row carries a
                          medoid voice embedding (256-dim wespeaker)
                          ready for Phase 3 voice identification.
    source_chunks         per-Deepgram-utterance, FK to the pyannote
                          turn it overlaps most.

Boundary:
- This module **does not** acquire audio. If `audio_s3_key` is NULL,
  raises `MissingAudioError`. Run Scout's `acquire_audio` first.
- This module **does not** produce quotes / claims / consensus. Those
  are later Analyst surfaces, run on the chunks this module produces.

Order of operations: pyannote first (long, CPU-heavy, idempotent at the
JSON_VERSION layer), then Deepgram. Lets us retry without re-paying
either cost.

Failure mode: no fallback. On error: ``transcription_status='failed'``,
exception re-raised. Operator inspects and re-runs with `--force`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from deepgram import DeepgramClient, DeepgramClientOptions, PrerecordedOptions
from sqlalchemy.orm import Session

from jeromelu_shared.config import settings
from jeromelu_shared.db import Source, SourceChunk, SourceDocument, SourceSpeaker
from jeromelu_shared.s3 import download_raw, presign_audio, upload_raw

from .diarize import diarize as run_pyannote
from .fusion import fuse_per_turn
from .identify_voice import identify_pyannote_turns
from .keyterms import build_keyterms
# Aliased to underscore-prefixed names because two of the helpers
# (`utterances`, `checksum`) would otherwise collide with the local
# variable / SourceDocument keyword arg of the same name in transcribe().
from .transcribe_helpers import (
    audio_duration as _audio_duration,
    checksum as _checksum,
    max_overlap_turn as _max_overlap_turn,
    request_id as _request_id,
    safe_embedding as _safe_embedding,
    transcript_s3_key_from_audio as _transcript_s3_key_from_audio,
    utterances as _utterances,
)
from .video_staging import VideoStagingError, staged_video
from .visual_id import VisualIdError, visual_identify

logger = logging.getLogger(__name__)

# Within-turn pause-gap (seconds) above which a chunk is marked as the
# start of a new paragraph. Tuned to capture rhetorical pauses; pyannote
# turns are usually finer-grained than Deepgram's, so this triggers
# inside long monologues spanning multiple consecutive utterances within
# the same pyannote turn.
_PARAGRAPH_GAP_SECONDS = 1.5

EXTRACTION_METHOD = "deepgram_words+pyannote_v1"
DIARIZATION_METHOD = "pyannote-3.1"


# ---------------------------------------------------------------------------
# Result + errors
# ---------------------------------------------------------------------------

@dataclass
class TranscribeResult:
    source_id: str
    document_id: str
    transcript_s3_key: str
    pyannote_s3_key: str
    face_track_s3_key: str | None  # None when no video acquired
    speakers_recorded: int  # distinct pyannote labels
    turns_recorded: int  # SourceSpeaker rows written (one per pyannote turn)
    turns_identified: int  # turns with speaker_person_id populated
    turns_voice_match: int  # voice modality fired (regardless of fusion)
    turns_visual_match: int  # visual modality fired
    turns_fusion_voice_face: int  # both modalities agreed
    turns_fusion_disagreement: int  # both fired but disagreed → NULL
    chunks_recorded: int
    chunks_unassigned: int  # utterances with no overlapping pyannote turn
    duration_seconds: float | None
    deepgram_request_id: str | None
    deepgram_model: str
    pyannote_model: str
    embedding_model: str
    video_format: str | None


class TranscriptionError(Exception):
    """Raised when transcription fails. The source row is marked
    `transcription_status='failed'` before the exception propagates."""


class MissingAudioError(TranscriptionError):
    """Raised when transcribe() is called on a source whose audio Scout
    has not yet acquired (`audio_s3_key IS NULL`)."""


# ---------------------------------------------------------------------------
# Helpers — Deepgram
# ---------------------------------------------------------------------------

def _call_deepgram(audio_url: str, keyterms: list[str]) -> dict[str, Any]:
    """Run a Deepgram prerecorded transcription on a presigned audio URL.

    Phase 2: ``diarize=False`` — speaker assignment comes from pyannote.
    """
    if not settings.deepgram_api_key:
        raise TranscriptionError("DEEPGRAM_API_KEY is not configured")

    client_opts = DeepgramClientOptions(api_key=settings.deepgram_api_key)
    client = DeepgramClient(settings.deepgram_api_key, client_opts)

    options = PrerecordedOptions(
        model=settings.deepgram_model,
        language="en-AU",
        diarize=False,
        punctuate=True,
        smart_format=True,
        utterances=True,
        paragraphs=True,
        keyterm=keyterms,
    )

    try:
        response = client.listen.rest.v("1").transcribe_url(
            {"url": audio_url},
            options,
            timeout=600,
        )
    except Exception as exc:
        raise TranscriptionError(f"Deepgram transcription failed: {exc}") from exc

    return response.to_dict()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transcribe(
    session: Session,
    source: Source,
    *,
    force: bool = False,
) -> TranscribeResult:
    """Run pyannote + Deepgram on Scout's audio and materialise the transcript.

    Preconditions:
        - source.audio_s3_key IS NOT NULL  (Scout has done its job)
        - source has no existing SourceDocument, OR force=True

    Postcondition (success):
        - source_documents row exists for this source
        - source_speakers rows for each pyannote turn (with embedding)
        - source_chunks rows (one per utterance, FK to overlapping turn)
        - sources.transcription_status='transcribed'
        - sources.extraction_method='deepgram_words+pyannote_v1'
        - sources.diarization_method='pyannote-3.1'

    Postcondition (failure):
        - sources.transcription_status='failed' (separate transaction)
        - TranscriptionError raised
    """
    if not source.audio_s3_key:
        raise MissingAudioError(
            f"source {source.source_id} has no audio_s3_key — run Scout's "
            "acquire_audio first"
        )

    if source.documents and not force:
        raise TranscriptionError(
            f"source {source.source_id} already has {len(source.documents)} "
            "document(s); pass force=True to replace"
        )

    transcript_key = _transcript_s3_key_from_audio(source.audio_s3_key)

    try:
        # 1) Pyannote first — it's the long step (CPU 30-60 min). Idempotent
        #    at the JSON_VERSION layer; transcribe.py NEVER forces a re-run
        #    of diarize, even when force=True on transcribe — `force` here
        #    only refreshes Deepgram + DB writes. To re-diarize, use
        #    `make diarize SOURCE_ID=... FORCE=1` first.
        logger.info("Running pyannote diarization for source %s", source.source_id)
        pyannote_result = run_pyannote(source.audio_s3_key)

        # 2) Build pyannote turn data from the JSON we just persisted.
        #    Re-fetch from S3 so we don't keep the full window-embedding
        #    payload in memory longer than necessary.
        pyannote_doc = json.loads(download_raw(pyannote_result.pyannote_s3_key))
        pyannote_turns = pyannote_doc.get("turns", [])
        if not pyannote_turns:
            raise TranscriptionError(
                "pyannote produced zero turns — refusing to write empty transcript"
            )

        # 3) Deepgram for words.
        keyterms = build_keyterms(session)
        if not keyterms:
            logger.warning("No keyterms loaded — Deepgram will run unbiased")
        presigned = presign_audio(source.audio_s3_key, expires_seconds=900)
        logger.info("Calling Deepgram for words+timestamps (diarize=False)")
        deepgram_response = _call_deepgram(presigned, keyterms)

        upload_raw(
            transcript_key,
            json.dumps(deepgram_response, ensure_ascii=False, indent=2),
        )
        logger.info(
            "Stored Deepgram JSON: s3://%s/%s",
            settings.s3_raw_bucket, transcript_key,
        )

        utterances = _utterances(deepgram_response)
        if not utterances:
            raise TranscriptionError("Deepgram returned zero utterances")

        # 4) DB writes — single transaction.

        # Replace existing doc on force
        if force and source.documents:
            for doc in list(source.documents):
                session.delete(doc)
            session.flush()

        raw_text = " ".join(u.get("transcript", "") for u in utterances).strip()

        document = SourceDocument(
            source_id=source.source_id,
            s3_key=transcript_key,
            raw_text=raw_text,
            transcript_available=True,
            language="en",
            checksum=_checksum(raw_text),
            chunk_count=len(utterances),
        )
        session.add(document)
        session.flush()

        # 4a) source_speakers rows — one per pyannote turn. Carries the
        #     medoid embedding for Phase 3 voice matching.
        embedding_model = pyannote_doc.get("embedding_model")
        turn_rows: list[SourceSpeaker] = []
        embeddings_skipped = 0
        for turn in pyannote_turns:
            embedding = _safe_embedding(turn.get("embedding_medoid"))
            if embedding is None and turn.get("embedding_medoid") is not None:
                embeddings_skipped += 1
            row = SourceSpeaker(
                document_id=document.document_id,
                speaker_label=turn["speaker"],  # 'SPEAKER_00', etc.
                start_ts=float(turn["start"]),
                end_ts=float(turn["end"]),
                embedding=embedding,
                embedding_model=embedding_model if embedding is not None else None,
            )
            session.add(row)
            turn_rows.append(row)
        session.flush()
        if embeddings_skipped:
            logger.warning(
                "Dropped %d NaN/inf embeddings (pre-fix pyannote JSON) — "
                "those turns have NULL embedding",
                embeddings_skipped,
            )

        # 4a-bis) Voice identification — match each turn against the
        # voiceprint registry. Empty registry → every turn unidentified.
        voice_results = identify_pyannote_turns(session, pyannote_doc)
        turns_voice_match = sum(1 for r in voice_results if r is not None)
        if turns_voice_match:
            logger.info(
                "Voice ID: matched %d / %d turns to voiceprints",
                turns_voice_match, len(turn_rows),
            )

        # 4a-ter) Visual identification — face detection + matching over
        # video frames. Three input regimes via ``staged_video``:
        #
        #   - ``source.video_s3_key`` set (legacy persistent row): use it
        #     as-is, no cleanup. The one source predating the ephemeral
        #     plan still flows through this branch until the file is
        #     manually purged.
        #   - ``source.video_s3_key`` null + ``canonical_url`` is YouTube:
        #     yt-dlp into a per-request staging key, run visual_identify
        #     against it, delete the staging object on exit. Default for
        #     all new sources.
        #   - Both null (non-YouTube source, or audio-only): skip visual
        #     ID entirely, voice-only fusion downstream.
        visual_per_turn: list = [None] * len(turn_rows)
        face_track_s3_key: str | None = None
        video_format: str | None = None
        try:
            with staged_video(
                source.canonical_url,
                persistent_key=source.video_s3_key,
            ) as video_key:
                if video_key is None:
                    logger.info(
                        "No video available — skipping visual ID, voice-only fusion"
                    )
                else:
                    try:
                        visual_result = visual_identify(
                            session,
                            audio_s3_key=source.audio_s3_key,
                            video_s3_key=video_key,
                            pyannote_turns=pyannote_turns,
                        )
                        visual_per_turn = visual_result.per_turn
                        face_track_s3_key = visual_result.face_track_s3_key
                        video_format = visual_result.video_format
                        source.video_format = video_format
                        logger.info(
                            "Visual ID: video_format=%s, %d / %d turns face-matched",
                            video_format,
                            visual_result.turns_visually_matched,
                            len(turn_rows),
                        )
                    except VisualIdError as exc:
                        logger.warning(
                            "Visual ID failed: %s — proceeding voice-only", exc,
                        )
        except VideoStagingError as exc:
            logger.warning(
                "Video staging failed: %s — proceeding voice-only", exc,
            )

        turns_visual_match = sum(1 for v in visual_per_turn if v is not None)

        # 4a-quater) Fusion — combine voice + face per turn. Writes the
        # full provenance trail on each source_speakers row.
        turns_identified = 0
        turns_fusion_voice_face = 0
        turns_fusion_disagreement = 0
        for row, voice, visual in zip(turn_rows, voice_results, visual_per_turn):
            v_pid = voice.person_id if voice else None
            v_score = float(voice.similarity) if voice else None
            f_pid = visual.person_id if visual else None
            f_score = float(visual.similarity) if visual else None

            row.audio_match_person_id = v_pid
            row.audio_match_score = v_score
            row.visual_match_person_id = f_pid
            row.visual_match_score = f_score

            fused = fuse_per_turn(v_pid, v_score, f_pid, f_score)
            if fused is None:
                if v_pid is not None and f_pid is not None and v_pid != f_pid:
                    turns_fusion_disagreement += 1
                continue

            row.speaker_person_id = fused.person_id
            row.match_method = fused.method
            row.match_confidence = float(fused.confidence)
            # Preserve `confidence` (pre-fusion legacy column) as voice score
            # when voice fired, else face score; lets old consumers keep working.
            row.confidence = v_score if v_score is not None else f_score
            turns_identified += 1
            if fused.method == "voice+face":
                turns_fusion_voice_face += 1

        logger.info(
            "Fusion: %d identified (%d voice-only, %d face-only, %d voice+face), "
            "%d disagreements",
            turns_identified,
            turns_identified - turns_fusion_voice_face - sum(
                1 for r, v, viz in zip(turn_rows, voice_results, visual_per_turn)
                if v is None and viz is not None
            ),
            sum(
                1 for v, viz in zip(voice_results, visual_per_turn)
                if v is None and viz is not None
            ),
            turns_fusion_voice_face,
            turns_fusion_disagreement,
        )

        # 4b) source_chunks rows — one per Deepgram utterance, linked
        #     to the pyannote turn that overlaps it most.
        char_offset = 0
        chunks_unassigned = 0
        utterance_turn_assignments: list[SourceSpeaker | None] = []

        for u in utterances:
            utt_start = float(u["start"])
            utt_end = float(u["end"])
            turn = _max_overlap_turn(utt_start, utt_end, turn_rows)
            utterance_turn_assignments.append(turn)
            if turn is None:
                chunks_unassigned += 1

        # Paragraph-break heuristic: within a single pyannote turn, mark
        # a break when the pause between consecutive utterances exceeds
        # _PARAGRAPH_GAP_SECONDS. Cross-turn boundaries already produce
        # a visual break via turn grouping.
        paragraph_break_indices: set[int] = set()
        for i in range(1, len(utterances)):
            prev_turn = utterance_turn_assignments[i - 1]
            cur_turn = utterance_turn_assignments[i]
            if prev_turn is None or cur_turn is None or prev_turn is not cur_turn:
                continue
            try:
                gap = float(utterances[i]["start"]) - float(utterances[i - 1]["end"])
            except (KeyError, TypeError, ValueError):
                continue
            if gap >= _PARAGRAPH_GAP_SECONDS:
                paragraph_break_indices.add(i)

        for idx, u in enumerate(utterances):
            text = u.get("transcript", "")
            turn = utterance_turn_assignments[idx]

            chunk = SourceChunk(
                document_id=document.document_id,
                speaker_segment_id=turn.segment_id if turn else None,
                chunk_index=idx,
                start_ts=float(u["start"]),
                end_ts=float(u["end"]),
                start_offset=char_offset,
                end_offset=char_offset + len(text),
                raw_text=text,
                paragraph_break=idx in paragraph_break_indices,
            )
            session.add(chunk)
            char_offset += len(text) + 1

        # 5) Mark transcription complete (Scout's ingestion_status stays
        #    'collected' — that step succeeded).
        source.transcription_status = "transcribed"
        source.extraction_method = EXTRACTION_METHOD
        source.diarization_method = DIARIZATION_METHOD

        session.commit()

        return TranscribeResult(
            source_id=str(source.source_id),
            document_id=str(document.document_id),
            transcript_s3_key=transcript_key,
            pyannote_s3_key=pyannote_result.pyannote_s3_key,
            face_track_s3_key=face_track_s3_key,
            speakers_recorded=len({t.speaker_label for t in turn_rows}),
            turns_recorded=len(turn_rows),
            turns_identified=turns_identified,
            turns_voice_match=turns_voice_match,
            turns_visual_match=turns_visual_match,
            turns_fusion_voice_face=turns_fusion_voice_face,
            turns_fusion_disagreement=turns_fusion_disagreement,
            chunks_recorded=len(utterances),
            chunks_unassigned=chunks_unassigned,
            duration_seconds=_audio_duration(deepgram_response),
            deepgram_request_id=_request_id(deepgram_response),
            deepgram_model=settings.deepgram_model,
            pyannote_model=pyannote_result.pyannote_model,
            embedding_model=pyannote_result.embedding_model,
            video_format=video_format,
        )

    except Exception as exc:
        session.rollback()
        try:
            session.refresh(source)
            source.transcription_status = "failed"
            session.commit()
        except Exception:
            session.rollback()
            logger.exception(
                "Failed to mark transcription_status='failed'; manual cleanup required"
            )
        if isinstance(exc, TranscriptionError):
            raise
        raise TranscriptionError(str(exc)) from exc

"""Analyst — Jaromelu's Transform-stage agent.

.. warning::

   **LEGACY — speaker identification ("Lineup") is being moved out of this repo.**
   Much of this package — diarization, voiceprint matching, visual ID, fusion,
   the recluster runner, and the SageMaker ``LINEUP_REMOTE`` pathway — is the
   in-repo Lineup surface. It will be replaced by an external API call that
   returns a speaker-attributed transcript. Keep this code working (the live
   pipeline still depends on it) but do not invest in new features here. See
   ``memory/project_lineup_external.md`` and
   ``docs/agents/system/speaker-identification.md``.

Owns everything that interprets Scout's raw bytes:

    1. Transcript materialisation — Deepgram-driven audio→text+speakers+chunks
       (`transcribe.py`). Sits in front of the historical Analyst surface.
    2. Quote / claim / consensus extraction (TBD — moved here when built).

Per Scout's hand-off contract, Analyst is invoked once a `sources` row has
``ingestion_status='collected'`` (audio in S3, audio_s3_key set). Analyst
reads from there and writes ``source_documents``, ``source_speakers``,
``source_chunks`` plus ``transcription_status`` on the source.
"""

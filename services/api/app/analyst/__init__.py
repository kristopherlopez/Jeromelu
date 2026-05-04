"""Analyst — Jaromelu's Transform-stage agent.

Owns everything that interprets Scout's raw bytes:

    1. Transcript materialisation — Deepgram-driven audio→text+speakers+chunks
       (`transcribe.py`). Sits in front of the historical Analyst surface.
    2. Quote / claim / consensus extraction (TBD — moved here when built).

Per Scout's hand-off contract, Analyst is invoked once a `sources` row has
``ingestion_status='collected'`` (audio in S3, audio_s3_key set). Analyst
reads from there and writes ``source_documents``, ``source_speakers``,
``source_chunks`` plus ``transcription_status`` on the source.
"""

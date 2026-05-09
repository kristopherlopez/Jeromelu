---
tags: [area/sources, status/live]
---

# Extraction Method

How raw source bytes are turned into the canonical raw layer (`source_documents` + `source_chunks` + `source_speakers`). The current canonical method is **audio-first via Deepgram**, replacing the legacy YouTube auto-caption ingest.

---

## Tiers

`sources.extraction_method` records which method produced a given source's chunks. Downstream consumers should treat the tiers as different trust levels.

| Value | Method | Trust | Notes |
|---|---|---|---|
| `deepgram_v1` | yt-dlp audio + Deepgram nova-3 (diarisation + keyterm) | Canonical | First-class. Speaker labels, punctuation, AU-accent biased model. ~$0.30 / 90-min video. |
| `youtube_captions` | youtube-transcript-api auto-captions | Legacy | Single channel, no diarisation, NRL names mangled. Backfill-only. |
| `NULL` | Discovered but not yet extracted | n/a | `sources` row exists (Scout enumerated it); no chunks. |

The 221k auto-caption-era chunks are archived in `source_chunks_v1` (migration 044). They aren't visible to current downstream queries because nothing JOINs that table — re-extract via the canonical path when ready.

---

## Pipeline (`deepgram_v1`)

`services/api/app/analyst/transcribe.py` · `transcribe(session, source)` · driver `python -m app.analyst.transcribe_cli <source_id>` (or `make transcribe SOURCE_ID=...`). Audio acquisition is a separate Scout step (`make collect-audio`); `make extract-transcript` chains both.

```
Source.canonical_url
        │
        ▼
   yt-dlp audio download (m4a, audio-only)
        │
        ▼
   s3://jeromelu-raw-audio/youtube/{channel_id}/{video_id}.m4a
        │
        ▼
   Deepgram batch — nova-3, diarize=true, language=en-AU,
                    keyterm=<roster vocabulary>, smart_format=true,
                    utterances=true, paragraphs=true
        │
        ▼
   s3://jeromelu-raw-transcripts/youtube/{channel_id}/{video_id}.deepgram.json
        │
        ▼
   PostgreSQL:
     • source_documents      — raw_text, s3_key, checksum, chunk_count
     • source_speakers       — one row per *speaker turn* (a contiguous span
                                where one speaker is talking; multiple rows
                                per speaker, all sharing speaker_label)
     • source_chunks         — one row per Deepgram utterance, FK to its
                                turn; paragraph_break=true on chunks where
                                the within-turn pause exceeds 1.5s
     • sources               — ingestion_status='collected',
                                transcription_status='transcribed',
                                extraction_method='deepgram_v1',
                                audio_s3_key, ingested_at
```

Idempotent on the audio object (`audio_object_exists` check skips re-download). Idempotent on the source via `force=False` default — already-ingested sources raise unless `--force` is passed.

---

## Keyterm vocabulary

`services/api/app/analyst/keyterms.py` · `build_keyterms(session)` — Deepgram's `keyterm` parameter biases the ASR toward specific terms. We supply NRL surnames, team identifiers and aliases pulled from the canonical backend roster.

Source of truth: `people` (canonical_name + aliases) joined with `people_roles` (role='player', effective_to IS NULL) and `people_attributes` (is_current=true) filtered to teams of grade `nrl` / `nrlw`. Also `teams` (short_name + aliases) for the same grades.

`players.yaml` is **not** consulted — the database is canonical. The legacy `/clean-transcript` skill still uses it; that path is independent.

Per-band caps (so a long surname pool doesn't crowd out teams):

| Band | Cap | Why |
|---|---|---|
| Player surnames (last token of canonical_name) | 60 | Highest confusion source. First names rarely garbled. |
| Team short_names | 25 | "Broncos", "Storm", etc. |
| Team aliases | 10 | "Bronx", "Phins", "Sharkies" — slang the LLM doesn't know without bias. |
| Player aliases (Person.aliases) | 25 | Empty today — will fill once the alias-backfill script lands. |

Hard cap 100 entries — Deepgram's practical limit. The actual count today is ~89 (player aliases empty). Logged at `app.analyst.keyterms` INFO on every run.

### Player alias gap

`people.aliases` is `ARRAY(Text)` (mig 036) but is empty across the active roster — nothing has populated it yet. A backfill script seeding common nicknames ("Reece Walsh" → ["Walshy", "Reesy"], "Jahrome Hughes" → ["Jah"]) is a follow-up. Until then, only surnames carry the player-name bias.

---

## Error handling

No fallback chain.

- **yt-dlp failure** (Scout): `sources.ingestion_status='failed'`, `AudioError` re-raised. Operator inspects and re-runs `make collect-audio`.
- **Deepgram failure** (Analyst): `sources.transcription_status='failed'` (separate transaction), `TranscriptionError` re-raised. Operator inspects and re-runs `make transcribe ... FORCE=1`. Audio is already in S3 — no re-download.

Common failure modes seen so far:

| Failure | Root cause | Fix |
|---|---|---|
| `yt-dlp DownloadError` | YouTube anti-bot, member-only video, 403 | Re-run; if persistent, the source needs manual investigation. |
| `Deepgram 400 — remote server returned 403` | Presigned URL pointed at the global S3 endpoint instead of the regional virtual-host endpoint. | **Fixed in `packages/shared/jeromelu_shared/s3.py`** — boto3 client now uses `addressing_style='virtual'` for AWS. |
| `Zero utterances` | Audio is silent / music-only | Mark source as not-applicable manually. |

The recurring "drain pending sources" job (APScheduler / cron) has not been built — extraction is one-source-per-CLI-invocation today. That's the next slice.

---

## Auditability

Every successful run produces:

- A `TranscribeResult` returned by the function (`document_id`, `transcript_s3_key`, `speakers_recorded` — distinct speaker labels, `turns_recorded` — `source_speakers` rows written, `chunks_recorded`, `duration_seconds`, `deepgram_request_id`, `deepgram_model`).
- The full Deepgram response in S3 — re-process locally without re-paying the API cost.
- The audio file in S3 — re-transcribe with a different model later (e.g. when nova-4 ships, or for voice-fingerprint clustering).

There is **no** `agent_runs` row for this work today. Audio extraction is deterministic and synchronous; if we add cost / latency dashboards later, the same pattern as Scout's `agent_id='scout-det'` could apply.

---

## Cost model (rough)

| Item | Per video | At 200 vids × 150 channels |
|---|---|---|
| Deepgram nova-3 batch | $0.0043 / minute → ~$0.30 for a 90-min video | ~$9k for full backfill |
| S3 raw audio storage | ~$0.001 / GB-month → ~$0.05 / video / month | ~$1.5k / month |
| S3 raw transcript JSON | < $0.001 / video / month | negligible |
| yt-dlp / compute | free | free |

Backfill of the 215 prod sources currently in `source_chunks_v1` is deferred — re-run cost is real. A targeted backfill of *high-leverage* channels (top-5 by view-velocity per `scout/refresh.py`) would be ~$50 and is the natural first step.

---

## Related

- [Scout § 3.5 — Audio acquisition](../agents/crew/scout.md#35-audio-acquisition-deterministic-shipped)
- [Analyst (crew)](../agents/crew/analyst.md) — owns transcription + later passes
- [Audio ingestion system spec](../agents/system/ingestion.md) — Scout's audio-pull surface
- [Transcription system spec](../agents/system/transcription-pipeline.md) — Analyst's Deepgram surface
- [Migration 044](../../packages/db/migrations/044_audio_first_extract.sql) — chunks rebuilt with speaker FK
- [Migration 045](../../packages/db/migrations/045_split_ingestion_transcription.sql) — split Scout ingest from Analyst transcription
- [Migration 046](../../packages/db/migrations/046_chunk_paragraph_break.sql) — `source_chunks.paragraph_break`

---
tags: [area/avatar]
---

# Content Production Pipeline — Future Vision

## Intent

Build toward a self-sufficient media production capability where the crew can produce video and audio content using the voices and likenesses of real NRL commentary figures — cheaply, at scale, and cross-posted to social platforms.

This is not required for launch. It is a strategic accumulation play: gather data now, reduce production costs later.

---

## Phase 1: Animated Crew Clips (Kling 3.0)

Use Kling 3.0 (or equivalent) to generate short video clips of the crew characters reacting, arguing, and presenting.

**How it works:**
- Each crew member has a static photo/character image
- Kling animates the photo into short clips (expressions, gestures, reactions)
- Chain multiple clips together to compose a scene (Scout briefs Jaromelu, Critic pushes back, Jaromelu makes the call)
- Add TTS voiceover per character
- Compose into 30-90 second clips for cross-posting

**Cost model:**
- Kling 3.0: ~$1 per 8 seconds of video
- 60-second clip: ~$8 in video generation
- TTS audio: negligible by comparison
- Target: 2-3 clips per week at tentpole moments (boldest call, Critic showdown, The Reckoning)

**Cross-post targets:**
- YouTube Shorts
- TikTok
- Instagram Reels
- Embedded in the Feed on the website

**Reusable templates:**
- Scout briefing Jaromelu (intel drop)
- Analyst presenting contradictions (tension)
- Critic challenging the call (conflict)
- Jaromelu making the call (commitment)
- The Reckoning (accountability)

Same visual setup each week, different content. Production cost is per-clip, not per-concept.

---

## Phase 2: Speaker Diarisation and Voice Accumulation

Build a pipeline to isolate individual speaker audio from YouTube podcast sources, creating a growing library of voice data per expert.

**What's already in place** (since [extraction-method.md](sources/extraction-method.md) shipped 2026-05-02):

1. **Audio retention** — every Scout audio pull (`app/scout/media/audio.py`) downloads the audio via yt-dlp and persists it to `s3://jeromelu-raw-audio/youtube/{channel_id}/{video_id}.m4a`. Long-term storage; never deleted.
2. **Speaker diarisation** — Deepgram nova-3 with `diarize=true` is the canonical extract (`app/analyst/transcribe.py`). Each video produces `source_speakers` *turns* (one row per contiguous speaker span — multiple per speaker, all sharing the raw `speaker_label`) and `source_chunks` rows linked to their turn via FK.
3. **Speaker rename UI** — operators can name a speaker via `PATCH /api/sources/speakers/{segment_id}` (rename cascades to every turn sharing the current label). Visible in the transcript panel on `/wiki/source/{source_id}` — click any speaker label to rename inline.

**What's still to build:**

4. **Speaker → Person resolution** — populate `source_speakers.speaker_person_id`. Two complementary signals: (a) voice-fingerprint clustering across episodes (a recurring speaker on the same podcast should converge), and (b) LLM-assisted attribution from contextual cues ("Hey Pat, what do you reckon?"). Manual override UI builds on the rename endpoint above.
5. **Per-speaker audio isolation** — once a `Person` is mapped, slice the m4a into per-speaker WAVs using the `source_speakers` turn spans. Store as `s3://jeromelu-raw-audio/by-person/{person_id}/{document_id}_{segment_id}.wav`.
5. **Accumulation** — over weeks/months, hours of isolated audio per expert build up automatically as new episodes are extracted.

**Storage:**
- Raw audio: `s3://jeromelu-raw-audio/youtube/{channel_id}/{video_id}.m4a` (full episode, kept long-term)
- Deepgram JSON: `s3://jeromelu-raw-transcripts/youtube/{channel_id}/{video_id}.deepgram.json` (re-processable)
- Per-person isolated clips (future): `s3://jeromelu-raw-audio/by-person/{person_id}/...`

**Tagging UI:**
- Minimal admin interface: play segment, assign to expert entity, confirm
- Only needed for initial tagging per source — once a speaker is identified in a recurring podcast, future episodes can be pre-labelled

---

## Phase 3: Voice Model Fine-Tuning

Once sufficient speaker-isolated audio is accumulated, fine-tune TTS voice models per expert.

**Goal:** A library of voice clones for real NRL commentary figures, usable in content production.

**Use cases:**
- Crew clips where "KingOfSC" responds to Jaromelu's take — in KingOfSC's actual voice
- Reaction clips: "Here's what KingOfSC said about Cleary this week" with real voice + animated likeness
- Expert vs Jaromelu debate format content

**Requirements before proceeding:**
- Sufficient audio hours per speaker (model-dependent, typically 1-10 hours)
- Legal/ethical review of voice cloning for public figures in commentary context
- Quality validation — generated voice must be recognisably accurate

**Model options (evolving):**
- Fine-tuned TTS (e.g., ElevenLabs, Coqui, or open-source alternatives)
- Cost advantage: once fine-tuned, per-clip generation is cheap vs general-purpose models

---

## Phase 4: Video Model Evolution

As video generation models improve and costs drop, the same accumulation strategy applies to video:

- Collect video frames/clips of expert speakers from YouTube
- Build per-speaker visual datasets
- Fine-tune or use reference-based video models to generate likenesses cheaply
- Replace expensive general-purpose models (Kling) with speaker-specific models

**Timeline:** Dependent on video model ecosystem maturity. Not actionable now, but the data accumulation in Phase 2 positions for this.

---

## Strategic Summary

```
Now:     Collect transcripts + audio from YouTube (already happening)
Soon:    Add Deepgram diarisation + manual tagging to isolate speakers
Medium:  Kling clips for crew content (expensive but compelling)
Later:   Fine-tuned voice models make audio content cheap
Future:  Fine-tuned video models make video content cheap
```

The insight: every podcast ingested today is also a training data deposit for tomorrow's production capability. The intelligence pipeline and the media pipeline share the same source material.

---

## Dependencies

| Dependency | Status |
|------------|--------|
| YouTube audio download | Not yet built (transcripts only) |
| Deepgram integration | Not yet built |
| Speaker tagging UI | Not yet built |
| Crew character images | Not yet created |
| Kling API integration | Not yet built |
| TTS per crew character | Not yet built |
| Voice fine-tuning pipeline | Future |
| Legal review for voice cloning | Future |

---

## Ethical Considerations

- Voice cloning of real public figures requires careful handling
- Commentary/parody context provides some latitude, but should be reviewed
- Consider: attribution, consent norms in the podcast ecosystem, platform policies on synthetic media
- Start with crew-original characters (Scout, Analyst, etc.) before using real voices

# Avatar Clip Pipeline

## Overview

Jeromelu's avatar is a looping video that reacts to system events and user interactions. It's powered by a library of short video clips, a JSON manifest that describes them, and a frontend state machine that sequences them in real time.

This document covers the end-to-end workflow: generating clips, preparing them for web, registering them in the manifest, auto-detecting transitions, and how the frontend orchestrates playback.

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Kling 3.0                       │
│         (generate clips from reference)          │
└──────────────────┬──────────────────────────────┘
                   │ raw clips
                   ▼
┌─────────────────────────────────────────────────┐
│            scripts/trim_clip.py                  │
│     crop · scale · compress · strip audio        │
└──────────────────┬──────────────────────────────┘
                   │ web-ready clips
                   ▼
┌─────────────────────────────────────────────────┐
│     services/web/public/avatar/*.mp4             │
│     services/web/public/avatar/manifest.json     │
└──────────────────┬──────────────────────────────┘
                   │ manifest + clips
                   ▼
┌─────────────────────────────────────────────────┐
│       scripts/match_clip_frames.py               │
│   extract boundary frames · compute similarity   │
│   auto-populate transitions_to in manifest       │
└──────────────────┬──────────────────────────────┘
                   │ updated manifest
                   ▼
┌─────────────────────────────────────────────────┐
│            AvatarEngine (frontend)               │
│   load manifest · sequence clips · crossfade     │
│   respond to events · cycle idle · play reactions │
└─────────────────────────────────────────────────┘
```

---

## Step 1: Generate Clips in Kling

Use Kling 3.0's image-to-video mode with the reference photo as the input image.

**Reference photo:** `assets/avatar/reference.png`

All clips must use the same reference photo to ensure visual consistency.

### Clip categories to generate

| Category | Purpose | Count | Loop? | Notes |
|----------|---------|-------|-------|-------|
| **idle** | Default resting state | 3-4 | Yes | Subtle variations — breathing, blinks, slight movements. Should start and end in a similar neutral pose. |
| **reaction** | Triggered by system events | 6-8 | No | One emotional arc per clip. Starts neutral, emotes, returns to neutral. |
| **directional** | Triggered by user hover | 2-4 | No | Eyes glance in a direction. Starts neutral, glances, returns. |
| **micro** | Sprinkled between idle clips | 3-4 | No | Very subtle — blink, head adjust, weight shift. Barely noticeable individually, but they break up the idle loop. |

### Reaction moods to generate

| Mood | Trigger | Description |
|------|---------|-------------|
| `greeting` | First page load | Brief eye contact, slight nod. "I see you." |
| `watching` | Source being scanned | Eyes scanning left-to-right, slight lean forward. |
| `confident` | Trade executed / prediction posted | Subtle smirk, lean back, knowing nod. |
| `annoyed` | Prediction wrong | Subtle eye roll or head shake. Composing himself quickly. |
| `celebrating` | Prediction correct | Satisfied nod, slight smile. Restrained — expected this. |
| `impatient` | Visitor idle 30+ seconds | Slight fidget, waiting energy. |
| `engaged` | Visitor navigates to Feed | Leans forward, alert. |

### Directional moods to generate

| Mood | Trigger | Description |
|------|---------|-------------|
| `glance-left` | Hover left-side thought bubble | Eyes look left, return to center. |
| `glance-right` | Hover right-side thought bubble | Eyes look right, return to center. |
| `glance-up` | Hover top thought bubble | Eyes look up briefly, return. |

### Kling v3 prompt guide

**Settings:** Image-to-video mode, 5 seconds, High Quality / Professional, 1080p, 24fps. Always use `assets/avatar/reference.png` as the input image.

**Base template** — every prompt starts from this and swaps the `[ACTION]` portion:

```
Living portrait, natural idle animation, [ACTION], warm studio lighting,
photorealistic, cinematic color grading, shallow depth of field,
static tripod shot, fixed camera, no zoom, no pan, no camera movement
```

**General tips:**
- Use "subtle", "gentle", "slight" — never "dramatic", "sudden", "quick"
- The word "idle" is powerful — Kling understands idle animation from game dev context
- Don't over-specify blink timing — let the model handle rhythm
- For loops: describe cyclical/oscillating motion, not directional motion
- Post-process loops: crossfade last 0.5s with first 0.5s using FFmpeg

**Negative prompt (if field available):**
```
no camera shake, no zoom, no pan, no morphing, no warping, no distortion,
no face deformation, no identity change, no fast motion, no text, no watermark
```

---

### Prompts per clip

#### Idle clips (loop: yes, 5s each, generate 3-4 variants)

**idle-1** — Breathing baseline
```
Living portrait, natural idle animation, subtle breathing motion with gentle
chest rise, occasional soft eye blinks, relaxed neutral expression, minimal
natural body sway, warm studio lighting, photorealistic, cinematic color
grading, shallow depth of field, static tripod shot, fixed camera, no zoom,
no pan, no camera movement
```

**idle-2** — Slight head drift
```
Living portrait, natural idle animation, gentle rhythmic breathing, head
drifts slightly side to side then returns to center, soft relaxed expression,
occasional blink, warm studio lighting, photorealistic, cinematic color
grading, shallow depth of field, static tripod shot, fixed camera, no zoom,
no pan, no camera movement
```

**idle-3** — Weight shift
```
Living portrait, natural idle animation, subtle weight shift in seated
position, gentle shoulder movement, natural breathing rhythm, relaxed
micro-expressions, warm studio lighting, photorealistic, cinematic color
grading, shallow depth of field, static tripod shot, fixed camera, no zoom,
no pan, no camera movement
```

#### Reaction clips (loop: no, 5s each)

**greeting-1** — First page load
```
Living portrait, person looks up at camera with brief direct eye contact,
gives a slight knowing nod of acknowledgment, subtle hint of a smile,
then settles back to neutral relaxed expression, warm studio lighting,
photorealistic, cinematic color grading, shallow depth of field, static
tripod shot, fixed camera, no zoom, no pan, no camera movement
```

**watching-1** — Source being scanned
```
Living portrait, person's eyes slowly scan from left to right as if reading
something off-screen, slight lean forward with focused concentration,
attentive expression, then settles back to neutral, warm studio lighting,
photorealistic, cinematic color grading, shallow depth of field, static
tripod shot, fixed camera, no zoom, no pan, no camera movement
```

**confident-1** — Trade executed / prediction posted
```
Living portrait, person develops a subtle confident smirk, leans back
slightly with a knowing nod, self-assured expression as if proven right,
then returns to composed neutral, warm studio lighting, photorealistic,
cinematic color grading, shallow depth of field, static tripod shot,
fixed camera, no zoom, no pan, no camera movement
```

**annoyed-1** — Prediction wrong
```
Living portrait, person gives a subtle eye roll and slight dismissive head
shake, brief flash of irritation, quickly composes himself back to neutral
expression, minimal movement, warm studio lighting, photorealistic,
cinematic color grading, shallow depth of field, static tripod shot,
fixed camera, no zoom, no pan, no camera movement
```

**celebrating-1** — Prediction correct
```
Living portrait, person gives a satisfied slow nod, slight restrained smile
of quiet vindication, composed and unsurprised as if he expected this,
returns to calm neutral expression, warm studio lighting, photorealistic,
cinematic color grading, shallow depth of field, static tripod shot,
fixed camera, no zoom, no pan, no camera movement
```

**impatient-1** — Visitor idle 30+ seconds
```
Living portrait, person shifts slightly in seat with restless waiting energy,
subtle fidget, glances around briefly as if expecting something, mild
impatience in expression, then settles back to neutral, warm studio lighting,
photorealistic, cinematic color grading, shallow depth of field, static
tripod shot, fixed camera, no zoom, no pan, no camera movement
```

**engaged-1** — Visitor navigates to Feed
```
Living portrait, person leans forward slightly with alert interested
expression, eyes widen subtly, attentive posture as if something caught
their attention, engaged and focused, warm studio lighting, photorealistic,
cinematic color grading, shallow depth of field, static tripod shot,
fixed camera, no zoom, no pan, no camera movement
```

#### Directional clips (loop: no, 3-4s each)

**glance-left** — Hover left thought bubble
```
Living portrait, person's eyes glance to the left as if noticing something
off-screen, slight head turn in that direction, brief pause, then eyes and
head return smoothly to center neutral position, warm studio lighting,
photorealistic, cinematic color grading, shallow depth of field, static
tripod shot, fixed camera, no zoom, no pan, no camera movement
```

**glance-right** — Hover right thought bubble
```
Living portrait, person's eyes glance to the right as if noticing something
off-screen, slight head turn in that direction, brief pause, then eyes and
head return smoothly to center neutral position, warm studio lighting,
photorealistic, cinematic color grading, shallow depth of field, static
tripod shot, fixed camera, no zoom, no pan, no camera movement
```

**glance-up** — Hover top thought bubble
```
Living portrait, person's eyes glance upward briefly as if noticing something
above, slight upward head tilt, brief pause, then eyes and head return
smoothly to center neutral position, warm studio lighting, photorealistic,
cinematic color grading, shallow depth of field, static tripod shot,
fixed camera, no zoom, no pan, no camera movement
```

#### Micro clips (loop: no, 2-3s each)

**micro-blink** — Double blink
```
Living portrait, person does a natural double blink, otherwise completely
still with neutral expression, minimal movement, warm studio lighting,
photorealistic, cinematic color grading, shallow depth of field, static
tripod shot, fixed camera, no zoom, no pan, no camera movement
```

**micro-adjust** — Head adjust
```
Living portrait, person makes a very subtle head position adjustment,
barely perceptible tilt and resettle, neutral expression throughout,
warm studio lighting, photorealistic, cinematic color grading, shallow
depth of field, static tripod shot, fixed camera, no zoom, no pan,
no camera movement
```

**micro-shift** — Weight shift
```
Living portrait, person makes a very subtle seated weight shift, barely
perceptible shoulder movement, neutral expression throughout, warm studio
lighting, photorealistic, cinematic color grading, shallow depth of field,
static tripod shot, fixed camera, no zoom, no pan, no camera movement
```

#### Talking clips (loop: no, 5-15s each, script-driven)

Talking clips are generated when Jeromelu has something specific to say — a prediction call, a bold take, a weekly recap line. Unlike silent reaction clips, these include lip-synced speech driven by a text script.

**Kling settings:** Image-to-video mode, duration matched to script length (5-15s), High Quality / Professional, 1080p, 24fps. Use `assets/avatar/reference.png` as input image. Enable audio/lip-sync if available, otherwise generate silent and dub with TTS in post.

**How it works:** Pick the emotion that matches the content of the script. Swap `[SCRIPT]` with the actual line. The emotion shapes the delivery — same words sound completely different when said with confidence vs. frustration.

**Base talking template** — swap `[EMOTION_DIRECTION]` for the emotion block and `[SCRIPT]` for the actual words:

```
Living portrait, person speaking directly to camera saying "[SCRIPT]",
natural lip movement synced to speech, [EMOTION_DIRECTION], natural
hand gestures where appropriate, warm studio lighting, photorealistic,
cinematic color grading, shallow depth of field, static tripod shot,
fixed camera, no zoom, no pan, no camera movement
```

**Negative prompt (if field available):**
```
no camera shake, no zoom, no pan, no morphing, no warping, no distortion,
no face deformation, no identity change, no fast motion, no text,
no watermark, no exaggerated mouth movement, no robotic lip sync
```

### Emotion prompts for talking clips

Each prompt below includes an example script in the `saying "..."` portion. Replace it with the actual line before generating.

**talking-confident** — Bold calls, predictions, trade announcements
```
Living portrait, person speaking directly to camera saying "I'm locking
in Cleary as captain. Not even close.", natural lip movement synced to
speech, confident self-assured expression, subtle smirk while talking,
relaxed posture leaning back slightly, steady eye contact, occasional
knowing nod between phrases, delivering with authority, warm studio
lighting, photorealistic, cinematic color grading, shallow depth of
field, static tripod shot, fixed camera, no zoom, no pan, no camera
movement
```

**talking-fired-up** — Hype moments, big wins, streak milestones
```
Living portrait, person speaking directly to camera saying "Three in a
row. The model is cooking.", natural lip movement synced to speech,
animated and energised expression, slightly faster speech cadence,
forward lean with engaged posture, emphatic hand gestures, eyes bright
and alive, restrained excitement building through the delivery, warm
studio lighting, photorealistic, cinematic color grading, shallow depth
of field, static tripod shot, fixed camera, no zoom, no pan, no camera
movement
```

**talking-measured** — Analysis breakdowns, explaining reasoning
```
Living portrait, person speaking directly to camera saying "Here's why
the matchup data says sell Munster this week.", natural lip movement
synced to speech, thoughtful measured expression, deliberate pacing,
occasional pause as if choosing words carefully, slight head tilts while
explaining, calm authoritative tone, hand gestures marking key points,
warm studio lighting, photorealistic, cinematic color grading, shallow
depth of field, static tripod shot, fixed camera, no zoom, no pan,
no camera movement
```

**talking-frustrated** — Bad beats, variance rants, missed calls
```
Living portrait, person speaking directly to camera saying "Sixty-two
points on the bench. The process was right. The result was pain.",
natural lip movement synced to speech, mild frustration in expression,
slight jaw tension, occasional head shake while talking, exhale between
points, composing himself as he speaks, maintains eye contact but with
visible irritation, warm studio lighting, photorealistic, cinematic
color grading, shallow depth of field, static tripod shot, fixed camera,
no zoom, no pan, no camera movement
```

**talking-sarcastic** — Roasting consensus, contrarian takes
```
Living portrait, person speaking directly to camera saying "Everyone's
panic-trading Cleary. I'm shopping while you're crying.", natural lip
movement synced to speech, dry amused expression, one eyebrow slightly
raised, subtle smirk that comes and goes, slight lean to one side,
deadpan delivery with occasional knowing look, as if sharing an inside
joke with the viewer, warm studio lighting, photorealistic, cinematic
color grading, shallow depth of field, static tripod shot, fixed camera,
no zoom, no pan, no camera movement
```

**talking-serious** — Warnings, risk flags, important caveats
```
Living portrait, person speaking directly to camera saying "Do not chase
the hype on this one. The bye schedule is brutal.", natural lip movement
synced to speech, serious focused expression, direct unwavering eye
contact, minimal gestures, still posture, slower deliberate delivery,
slight forward lean conveying gravity, warm studio lighting,
photorealistic, cinematic color grading, shallow depth of field, static
tripod shot, fixed camera, no zoom, no pan, no camera movement
```

**talking-playful** — Teases, previews, audience engagement
```
Living portrait, person speaking directly to camera saying "I've got a
spicy trade brewing for Round 8. Stay tuned.", natural lip movement
synced to speech, playful mischievous expression, hint of a grin, slight
head tilt, relaxed casual posture, animated eyebrows, delivery that
suggests he knows something the viewer doesn't yet, warm studio lighting,
photorealistic, cinematic color grading, shallow depth of field, static
tripod shot, fixed camera, no zoom, no pan, no camera movement
```

### Talking clip naming conventions

```
talking-confident-1.mp4, talking-confident-2.mp4
talking-fired-up-1.mp4
talking-measured-1.mp4
talking-frustrated-1.mp4
talking-sarcastic-1.mp4
talking-serious-1.mp4
talking-playful-1.mp4
```

### Talking clip manifest entry

```json
{
  "id": "talking-confident-1",
  "file": "talking-confident-1.mp4",
  "category": "talking",
  "mood": "confident",
  "duration_ms": 8000,
  "loop": false,
  "transitions_to": [],
  "priority": 15,
  "script": "I'm locking in Cleary as captain. Not even close."
}
```

### Post-production for talking clips

1. **If Kling generates with lip sync:** Trim, compress, keep audio track (do NOT strip audio)
2. **If generating silent + TTS dub:** Generate the silent video with mouth movement, then overlay TTS audio (ElevenLabs or similar) in post using FFmpeg:
   ```bash
   ffmpeg -i talking-confident-1_silent.mp4 -i voiceover.mp3 \
     -c:v copy -c:a aac -shortest talking-confident-1.mp4
   ```
3. **Audio spec:** AAC, 128kbps, mono. Keep file size under 2MB total.

---

## Step 2: Prepare Clips for Web

Use the trim script to crop, scale, compress, and strip audio (for non-talking clips).

### Usage

```bash
# Basic — auto-crop to square, scale to 400x400, compress
python scripts/trim_clip.py assets/raw_clip.mp4 --out services/web/public/avatar/idle-2.mp4

# With trimming — cut to specific time range
python scripts/trim_clip.py assets/raw_clip.mp4 --start 0.3 --end 3.8 --out services/web/public/avatar/confident-1.mp4

# Custom size or quality
python scripts/trim_clip.py assets/raw_clip.mp4 --out ... --size 600 --crf 24
```

### What it does

1. Strips audio track (skip `--strip-audio` for talking clips)
2. Center-crops to square (based on smallest dimension)
3. Scales to 400x400 (retina-ready for 200px display)
4. Compresses with H.264 CRF 28 (~100-200KB per clip)
5. Adds `faststart` flag for instant web playback

### Output spec

| Property | Value |
|----------|-------|
| Format | MP4 (H.264) |
| Resolution | 400x400 |
| Audio | None |
| Frame rate | 24fps (preserved from source) |
| Target size | < 500KB per clip |

---

## Step 3: Register in Manifest

Add an entry to `services/web/public/avatar/manifest.json` for each new clip.

### Manifest schema

```json
{
  "clips": [
    {
      "id": "idle-1",
      "file": "idle-1.mp4",
      "category": "idle",
      "mood": "neutral",
      "duration_ms": 5000,
      "loop": true,
      "transitions_to": ["idle-2", "idle-3"],
      "priority": 0
    }
  ]
}
```

### Field reference

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique identifier. Convention: `{category}-{variant}` or `{mood}-{variant}` |
| `file` | string | Filename in `public/avatar/` |
| `category` | string | `idle`, `reaction`, `directional`, `micro`, or `talking` |
| `mood` | string | Emotional state: `neutral`, `confident`, `annoyed`, `glance-left`, etc. |
| `duration_ms` | number | Clip length in milliseconds |
| `loop` | boolean | `true` for idle clips, `false` for reactions/directional/micro |
| `transitions_to` | string[] | IDs of clips this can smoothly transition to. Empty = allow all (loose mode). |
| `priority` | number | Higher number = higher priority. Idle = 0, directional = 5, reactions = 10 |
| `transitions_override` | string[] | (Optional) Manual override — if present, `match_clip_frames.py` won't touch `transitions_to`. |

### Naming conventions

```
idle-1.mp4, idle-2.mp4, idle-3.mp4
confident-1.mp4, confident-2.mp4
annoyed-1.mp4
celebrating-1.mp4
watching-1.mp4
greeting-1.mp4
impatient-1.mp4
engaged-1.mp4
glance-left.mp4, glance-right.mp4, glance-up.mp4
micro-blink.mp4, micro-adjust.mp4, micro-shift.mp4
talking-confident-1.mp4, talking-fired-up-1.mp4
talking-measured-1.mp4, talking-frustrated-1.mp4
talking-sarcastic-1.mp4, talking-serious-1.mp4
talking-playful-1.mp4
```

---

## Step 4: Auto-Detect Transitions

Run the frame matching script to automatically populate `transitions_to` based on visual similarity between clip boundaries.

### Usage

```bash
python scripts/match_clip_frames.py
```

### What it does

1. **Extracts boundary frames** from each clip (first frame + last frame)
   - Saved to `services/web/public/avatar/frames/{clip_id}_first.png`
   - Saved to `services/web/public/avatar/frames/{clip_id}_last.png`

2. **Computes perceptual hash** for each boundary frame using `imagehash`

3. **Compares all pairs** — if the last frame of clip A has a hash distance ≤ 8 from the first frame of clip B, they're a match

4. **Updates manifest** — writes detected matches to `transitions_to` for each clip

5. **Respects overrides** — clips with `transitions_override` are skipped

### Requirements

```bash
pip install imagehash Pillow
```

### Tuning

The threshold (default: 8) controls match strictness:
- **Lower (4-6):** Only very similar frames match. Tighter cuts, fewer valid transitions.
- **Higher (10-12):** More lenient matching. More transitions available, but some may look slightly jarring.

Edit `HASH_THRESHOLD` in the script to adjust.

### Manual review

After running the script, review the manifest. You can:
- Remove transitions that look bad in practice
- Add `transitions_override` to lock down specific clips
- Force transitions by manually editing `transitions_to`

---

## Step 5: Frontend Playback

The frontend handles everything automatically once the manifest is populated.

### Components

| Component | File | Role |
|-----------|------|------|
| `AvatarEngine` | `components/AvatarEngine.tsx` | React context. Loads manifest, manages state machine, exposes `triggerClip()`. |
| `ConnectedAvatar` | `components/ConnectedAvatar.tsx` | Reads current clip from engine, passes to `JeromeluAvatar`. |
| `JeromeluAvatar` | `components/JeromeluAvatar.tsx` | Renders dual `<video>` elements with crossfade transitions. |

### State machine behaviour

1. **Startup:** Picks a random idle clip from manifest, starts looping.
2. **Idle cycling:** Every 8-12 seconds (random), swaps to a different idle clip. 20% chance to play a micro-expression clip instead.
3. **On trigger:** Finds the highest-priority clip matching the requested category/mood. Crossfades to it (300ms). If the clip is non-looping, returns to idle after it finishes.
4. **Priority enforcement:** A high-priority clip (e.g., reaction) won't be interrupted by a lower-priority one (e.g., directional glance).
5. **Transition validation:** If a direct transition isn't valid per `transitions_to`, the engine goes through an idle clip first.

### Triggering clips

Any component inside an `<AvatarEngineProvider>` can trigger a clip:

```tsx
const { triggerClip } = useAvatarEngine();

// Trigger by category + mood
triggerClip("reaction", "confident");
triggerClip("directional", "glance-left");

// Category only (picks random mood within category)
triggerClip("micro");
```

### Currently wired triggers

| Trigger | Where | Clip |
|---------|-------|------|
| Hover left thought bubble | `ThoughtBubbles.tsx` | `directional/glance-left` |
| Hover right thought bubble | `ThoughtBubbles.tsx` | `directional/glance-right` |
| Hover top thought bubble | `ThoughtBubbles.tsx` | `directional/glance-up` |

### Adding new triggers

To wire a new trigger (e.g., Feed page events):

1. Wrap the relevant page/component in `<AvatarEngineProvider>`
2. Call `useAvatarEngine()` to get `triggerClip`
3. Call `triggerClip(category, mood)` on the event

Example — trigger "confident" when an action feed item appears:
```tsx
const { triggerClip } = useAvatarEngine();
// On new action feed item:
triggerClip("reaction", "confident");
```

---

## Quick Reference: Full Workflow

```bash
# 1. Generate clip in Kling (external)

# 2. Trim and compress
python scripts/trim_clip.py assets/new_clip.mp4 \
  --out services/web/public/avatar/confident-1.mp4

# 3. Add to manifest.json
# Edit services/web/public/avatar/manifest.json:
# {
#   "id": "confident-1",
#   "file": "confident-1.mp4",
#   "category": "reaction",
#   "mood": "confident",
#   "duration_ms": 4000,
#   "loop": false,
#   "transitions_to": [],
#   "priority": 10
# }

# 4. Auto-detect transitions
python scripts/match_clip_frames.py

# 5. Review manifest, test in browser
# The frontend picks it up immediately — no rebuild needed
# (manifest.json is served as a static file)
```

---

## File Locations

| File | Purpose |
|------|---------|
| `services/web/public/avatar/*.mp4` | Processed clip files |
| `services/web/public/avatar/manifest.json` | Clip metadata and transition graph |
| `services/web/public/avatar/frames/` | Extracted boundary frames (auto-generated) |
| `services/web/src/app/components/AvatarEngine.tsx` | Sequencing state machine |
| `services/web/src/app/components/JeromeluAvatar.tsx` | Video player with crossfade |
| `services/web/src/app/components/ConnectedAvatar.tsx` | Connects avatar to engine |
| `scripts/trim_clip.py` | Clip preparation script |
| `scripts/match_clip_frames.py` | Frame matching script |
| `docs/avatar-system.md` | High-level avatar system design |

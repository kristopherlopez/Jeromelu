# Avatar System

## Overview

Jaromelu has a digital avatar — a pre-generated video loop library driven by system state. The avatar sits on the site as a persistent presence, reacting to what Jaromelu is doing in real time.

The approach: generate a library of short video clips using Kling 3.0 (image-to-video), anchored to a single reference photo. The frontend maps Jaromelu's current state to a clip, crossfading between them on state changes.

---

## Reference Photo

A single reference photo defines Jaromelu's appearance. All generated clips must use this photo as the anchor/seed image to ensure visual consistency across the library.

**Location:** `assets/avatar/reference.png` (to be added)

**Requirements:**
- Head and shoulders framing
- Neutral expression (Kling will animate from here)
- Good lighting, clean background (or transparent)
- High resolution (1080p minimum) — clips will be cropped from this

---

## Clip Library

### Format Spec

| Property | Value |
|----------|-------|
| Format | MP4 (H.264) |
| Resolution | 720x720 or 1080x720 (head/shoulders crop) |
| Duration | 3-4 seconds per clip |
| Looping | First frame should approximate last frame for seamless looping |
| Audio | None (silent) |
| Frame rate | 24fps |
| File size target | < 2MB per clip (for fast preloading) |

### Storage

Clips are stored in `public/avatar/` in the web service and preloaded on page mount.

```
services/web/public/avatar/
  idle-1.mp4
  idle-2.mp4
  idle-3.mp4
  watching-1.mp4
  watching-2.mp4
  thinking-1.mp4
  thinking-2.mp4
  confident-1.mp4
  confident-2.mp4
  annoyed-1.mp4
  annoyed-2.mp4
  locked-in-1.mp4
  celebrating-1.mp4
  celebrating-2.mp4
```

### States

Each state maps to a set of clips. When multiple clips exist for a state, the frontend picks randomly to avoid repetition.

#### idle (3 clips)
**Trigger:** Default state. No active processing, no recent state-changing event.
**What it looks like:** Slight breathing, occasional blink, eyes forward as if looking at a screen. Calm, attentive, unhurried. This is the state visitors see 80% of the time.
**Prompt guidance for Kling:** "Person sitting at desk, subtle idle movement, slight breathing, occasional blink, looking at screen, calm and focused"

#### watching (2 clips)
**Trigger:** Ingestion worker is scanning sources, or a new source was just ingested (feed item type: `system` with scanning text).
**What it looks like:** Eyes moving left-to-right as if reading/scanning. Slight lean forward. Alert, engaged.
**Prompt guidance:** "Person reading screen intently, eyes scanning left to right, slight forward lean, focused and alert"

#### thinking (2 clips)
**Trigger:** Feed item type `reasoning` was just posted, or extraction is in progress.
**What it looks like:** Hand on chin or looking slightly up/to the side. Head tilted. Processing, deliberating.
**Prompt guidance:** "Person thinking deeply, hand on chin, looking slightly upward, head tilted, contemplative expression"

#### confident (2 clips)
**Trigger:** Feed item type `action` (trade made, captain locked) or `prediction` posted.
**What it looks like:** Subtle smirk. Slight lean back. A barely perceptible nod — "I know something you don't."
**Prompt guidance:** "Person leaning back slightly with subtle smirk, confident expression, slight knowing nod, self-assured"

#### annoyed (2 clips)
**Trigger:** Prediction resolved as `wrong`, or a review feed item acknowledging a miss.
**What it looks like:** Subtle eye roll or brief head shake. Slight exhale. Not angry — more "variance robbed me" energy.
**Prompt guidance:** "Person with subtle eye roll, slight head shake, mild annoyance, composing themselves quickly"

#### locked-in (1 clip)
**Trigger:** Squad is finalised for the week. Pre-match state.
**What it looks like:** Intense forward stare. Minimal movement. Still and focused. The calm before the storm.
**Prompt guidance:** "Person staring forward intensely, very still, minimal movement, locked in concentration, determined"

#### celebrating (2 clips)
**Trigger:** Prediction resolved as `correct`, or a streak milestone (3+ correct in a row).
**What it looks like:** Subtle nod, a small smile breaking through. Restrained — Jaromelu doesn't jump around, he just looks like he expected this.
**Prompt guidance:** "Person with subtle satisfied nod, slight smile forming, restrained celebration, 'told you so' energy"

**Total: 14 clips.**

---

## State Machine

The avatar state is derived from system events. The logic runs on the frontend, reading from the feed data or a lightweight status API.

```
┌──────────────────────────────────────────┐
│              IDLE (default)              │
│         returns here after 10s           │
└──────┬──────┬──────┬──────┬──────┬──────┘
       │      │      │      │      │
  scanning  reasoning action  prediction  review
       │      │      │    resolves   resolves
       ▼      ▼      ▼      │           │
  WATCHING THINKING CONFIDENT │           │
                      ▲      │           │
                      │   correct?     wrong?
                      │      │           │
                      │      ▼           ▼
                      │  CELEBRATING  ANNOYED
                      │
                 LOCKED IN
              (squad finalised)
```

### Transition rules

| Current State | Event | New State | Hold Duration |
|---------------|-------|-----------|---------------|
| any | ingestion scanning | watching | while scanning |
| any | reasoning feed item | thinking | 8s |
| any | action feed item | confident | 10s |
| any | prediction posted | confident | 8s |
| any | prediction correct | celebrating | 10s |
| any | prediction wrong | annoyed | 8s |
| any | squad locked | locked-in | until next event |
| any | no event for 10s | idle | indefinite |

Hold duration = how long the avatar stays in that state before falling back to idle (unless a new event overrides it).

---

## Frontend Component

### `<JaromeluAvatar />`

**Location:** `services/web/src/app/components/JaromeluAvatar.tsx`

**Behaviour:**
1. On mount, preload all 14 clips into memory using `<link rel="preload">` or JS `fetch()` into blob URLs
2. Render two overlapping `<video>` elements (front and back) for crossfade transitions
3. Accept a `state` prop (or derive from context/API)
4. On state change:
   - Pick a random clip for the new state (avoiding the last-played clip for that state)
   - Start playing the new clip on the back `<video>` element
   - Crossfade: fade out front, fade in back (300ms transition)
   - Swap front/back references
5. Each clip loops (`loop` attribute on `<video>`)
6. On state timeout (hold duration expires), transition back to idle

### Props

```tsx
interface JaromeluAvatarProps {
  state: AvatarState;
  size?: "sm" | "md" | "lg";  // sm=80px, md=120px, lg=200px
}

type AvatarState =
  | "idle"
  | "watching"
  | "thinking"
  | "confident"
  | "annoyed"
  | "locked-in"
  | "celebrating";
```

### Placement Options

**Option A: Feed page — top right, fixed position.**
Floats in the corner while scrolling. Always visible. The avatar reacts as you scroll past feed items.

**Option B: Feed page — inside the agent state banner.**
Replace or augment the "JEROMELU is online" banner with the avatar on the left. More integrated, less floating.

**Option C: Global — persistent across all pages.**
Small avatar in the global `JeromeluTopBar` (top-right). Shows on every inner page. Reacts to system state regardless of which page you're on. (This is the path currently shipped.)

**Recommendation:** Start with Option B (in the agent state banner on the feed page). It's the most natural home. Expand to Option C later if it feels right.

---

## Crossfade Implementation

Two `<video>` elements stacked with `position: absolute`, each with `opacity` controlled by CSS transition.

```
Container (position: relative, overflow: hidden, border-radius: 50%)
  ├── Video A (opacity: 1, transition: opacity 300ms)
  └── Video B (opacity: 0, transition: opacity 300ms)
```

On state change:
1. Set Video B `src` to new clip, call `play()`
2. Set Video B `opacity: 1`, Video A `opacity: 0`
3. After transition completes, pause Video A, swap A/B roles

This avoids any flash of black/empty between clips.

---

## Generation Workflow

### Step 1: Prepare reference photo
- Crop to head and shoulders
- Clean background (solid dark or transparent)
- Save as `assets/avatar/reference.png`

### Step 2: Generate clips in Kling 3.0
- Use image-to-video mode with reference photo as input
- For each state, use the prompt guidance from the States section above
- Generate 2-3 attempts per state, keep the best
- Aim for seamless loops (Kling has loop-friendly generation options)

### Step 3: Post-process
- Trim to exactly 3-4 seconds
- Ensure first/last frame similarity for smooth looping
- Compress to < 2MB each (H.264, CRF 28-30)
- Strip audio track
- Export as MP4

### Step 4: Add to project
- Place clips in `services/web/public/avatar/`
- Name using `{state}-{variation}.mp4` convention
- Update the clip manifest in the component

---

## Fallback

If clips haven't been generated yet, or fail to load, the avatar component falls back to the static reference photo with a subtle CSS breathing animation (scale pulse). This means the component can be built and integrated into the site immediately, with clips dropped in later.

---

## Future Enhancements

These are not part of v1 but worth noting as upgrade paths:

1. **Canvas overlay** — Layer a transparent `<canvas>` over the video for reactive effects (eye glow, scan lines during processing, orange pulse on actions). Adds interactivity without regenerating video.

2. **Talking clips** — For high-impact feed items (predictions, bold calls), generate a 5-10 second talking clip via Hedra or similar. Store in S3, attach to the feed item. Items with video get a play button in the feed.

3. **Audience awareness** — Avatar occasionally "looks at" the viewer (a dedicated clip) when page analytics detect activity. Breaks the fourth wall.

4. **Seasonal evolution** — Regenerate clips periodically with slight appearance changes (different outfit, background) to mark season milestones or reflect Jaromelu's "character arc."

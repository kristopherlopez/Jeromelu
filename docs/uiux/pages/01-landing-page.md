# Landing Page

Status: **Implemented — refinement ongoing**

---

## Purpose

The landing page is the front door. The audience arrives and sees Jeromelu mid-thought — avatar centred on screen, thought bubbles orbiting, the logo animating in. It establishes the character and offers navigation into the product.

---

## Current Implementation

```
┌─────────────────────────────────────┐
│                                     │
│          ○  ○  ○  ○  ○              │  ← Thought bubbles (upper arc)
│        ·· ·· ·· ·· ··              │  ← Connector dots
│          ┌──────────┐               │
│          │  AVATAR  │               │  ← 180px, centred
│          └──────────┘               │
│            Jeromelu                  │  ← Animated logo (outside-in orange sweep)
│   "I watch everything. I read       │  ← Tagline
│    everyone. I make moves."         │
│          [Crew Status]              │  ← Crew online pill
│          [Activity Pulse]           │
│                                     │
└─────────────────────────────────────┘
```

### Components

| Component | File | Role |
|-----------|------|------|
| `JeromeluPresence` | `components/JeromeluPresence.tsx` | Avatar + nav bubbles (persistent across pages) |
| `JeromeluLogo` | `components/JeromeluLogo.tsx` | Animated wordmark with outside-in orange sweep |
| `CrewStatus` | `components/CrewStatus.tsx` | Shows who's online in the crew |
| `ActivityPulse` | `components/ActivityPulse.tsx` | Recent activity indicator |
| `LatestThought` | `components/LatestThought.tsx` | Latest thought text (currently unused) |

### Entrance Animation Sequence

1. **Bubbles sweep out** (0–420ms) — connector dots then bubbles appear with orange glow, staggered per bubble
2. **Logo sweeps in** (0–640ms) — letters light up orange from outside-in
3. **Pause** (640–940ms) — everything glowing
4. **Sweep back** (940–1580ms) — glow removed from bubbles and logo settles to white
5. **Below-fold content fades in** — crew status, activity pulse

### Thought Bubbles (Resting State)

Bubbles use a breathing glow animation (`thought-float`) that combines a gentle vertical bob with a pulsing orange border/shadow to keep them visible against the dark background.

---

## Navigation Targets

| Bubble | Label | Route |
|--------|-------|-------|
| 1 | The Feed | `/feed` |
| 2 | My Squad | `/squad` |
| 3 | The Dossier | `/dossier` |
| 4 | The Ledger | `/ledger` |
| 5 | Ask Me | `/ask` |

---

## Transition to Inner Pages

When a bubble is clicked:
- Page content transitions out
- Avatar shrinks from 180px → 160px
- Bubble layout shifts from upper arc → full orbital
- Cluster moves from centre → top-left (32px inset)
- Target page content fades in

---

## Open Questions

- [ ] Should the landing page feel more like "arriving mid-show" (per design principles) or a deliberate front door?
- [ ] Is the tagline pulling its weight? Could it be dynamic / contextual?
- [ ] `LatestThought` component exists but is unused — should it show Jeromelu's latest take?
- [ ] Mobile layout — how does the landing page adapt below 1024px?

---

## Notes

<!-- Add discussion notes, screenshots, or references here -->

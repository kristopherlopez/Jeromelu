# Theme & Style Guide

Status: **Living document — evolves with the product**

---

## Metaphor

Jeromelu is a live broadcast, not a website. The dark background is the stage. Orange is the spotlight. The audience is watching a show that's already running.

---

## Colour Palette

### Core Tokens

| Token | Value | CSS Variable | Usage |
|-------|-------|-------------|-------|
| Background | `#0c0c0f` | `--background` | Near-black stage — the default canvas |
| Foreground | `#ededed` | `--foreground` | Primary text, high-contrast content |
| Tigers Orange | `#F58220` | `--tigers-orange` | Accent, interactive elements, highlights, Jeromelu's colour |
| Orange Glow | `rgba(245, 130, 32, 0.4)` | `--tigers-orange-glow` | Hover states, active indicators, emphasis halos |

### Grey Scale (Zinc)

Used for hierarchy, surfaces, and secondary content. Drawn from Tailwind's zinc palette.

| Shade | Hex | Usage |
|-------|-----|-------|
| zinc-950 | `#09090b` | Deepest surfaces (near background) |
| zinc-900 | `#18181b` | Card backgrounds, elevated surfaces |
| zinc-800 | `#27272a` | Borders, dividers, subtle structure |
| zinc-700 | `#3f3f46` | Input borders, secondary borders |
| zinc-600 | `#52525b` | Disabled text, de-emphasised elements |
| zinc-500 | `#71717a` | Secondary text, timestamps, metadata |
| zinc-400 | `#a1a1aa` | Taglines, descriptions, body secondary |
| zinc-300 | `#d4d4d8` | Prominent secondary text |

### Semantic Colours

| Colour | Usage |
|--------|-------|
| `text-green-400` | Success, verified, confirmed |
| `text-red-400` | Error, failed, danger |
| `text-red-300` / `bg-red-900/60` | Diff deletions |
| `text-green-300` / `bg-green-900/60` | Diff additions |

---

## Typography

| Role | Font | Tailwind | Usage |
|------|------|----------|-------|
| Body | Geist Sans | `font-sans` | All body text, labels, navigation |
| Data | Geist Mono | `font-mono` | Timestamps, scores, stats, code, technical values |

### Scale (commonly used)

| Class | Size | Usage |
|-------|------|-------|
| `text-6xl` | 60px | Landing page logo |
| `text-2xl` | 24px | Page headings, stat hero numbers |
| `text-xl` | 20px | Section headings |
| `text-lg` | 18px | Subheadings |
| `text-sm` | 14px | Body text, table content |
| `text-xs` | 12px | Metadata, timestamps, badges |
| `text-[11px]` | 11px | Tooltips, micro labels |
| `text-[10px]` | 10px | Smallest labels, timestamps in tight spaces |

### Weight

- `font-bold` — headings, logo, emphasis
- `font-medium` — labels, tooltips, navigation
- Default (400) — body text

### Tracking

- `tracking-tight` — headings and logo (tighter letter spacing)

---

## Surfaces & Elevation

The UI uses transparency-based elevation rather than solid backgrounds. This keeps the dark stage visible through every layer.

| Level | Background | Border | Usage |
|-------|-----------|--------|-------|
| Stage | `#0c0c0f` | — | Page background |
| Card | `bg-zinc-900/50` | `border-zinc-800` | Cards, panels, elevated containers |
| Interactive (resting) | `rgba(255,255,255, 0.10)` | `rgba(255,255,255, 0.18)` | Nav bubbles, buttons at rest |
| Interactive (hover) | `rgba(245,130,32, 0.12)` | `rgba(245,130,32, 0.5)` | Hovered interactive elements |
| Interactive (active) | `rgba(245,130,32, 0.15)` | `rgba(245,130,32, 0.5)` + glow | Current page, selected state |

---

## Borders & Rounding

- Default border: `border-zinc-800` (1px)
- Interactive border: `1.5px solid` (slightly heavier for clickable elements)
- Rounding: `rounded-lg` for cards, `rounded-md` for badges/tooltips, `rounded-full` for avatars and nav bubbles

---

## Shadows & Glow

Shadows are orange-tinted and used sparingly — they are the "spotlight" effect.

| State | Box Shadow |
|-------|-----------|
| Resting (animated) | `0 0 12px rgba(245, 130, 32, 0.15)` — via `thought-float` keyframe |
| Hovered | `0 0 8px rgba(245, 130, 32, 0.2)` |
| Active | `0 0 16px rgba(245, 130, 32, 0.25)` |
| Avatar glow | `0 0 24px 8px rgba(245, 130, 32, 0.4), 0 0 48px 16px rgba(245, 130, 32, 0.15)` |

No white/neutral box shadows. If it glows, it glows orange.

---

## Animation

### Timing

| Curve | Usage |
|-------|-------|
| `cubic-bezier(0.4, 0, 0.2, 1)` | Layout transitions (position, size) |
| `ease-in-out` | Looping animations (float, pulse) |
| `ease-out` | Hover responses, fade-outs |
| `ease-in` | Fade-ins with delay |

### Durations

| Duration | Usage |
|----------|-------|
| 200ms | Hover states, opacity, scale |
| 300ms | Colour transitions, box-shadow, border |
| 3s | Breathing/float loops (thought-float, crew-pill-pulse) |

### Keyframe Animations

| Name | Effect | Used by |
|------|--------|---------|
| `thought-float` | Vertical bob (±3px) + orange border/shadow breathe | Nav bubbles on landing page |
| `crew-pill-pulse` | Border colour pulse (orange 0.2 → 0.4) | Crew status pill |
| `ping` | Scale + fade pulse (Tailwind built-in) | Online indicator dot |

### Entrance Choreography

Entrances are sequenced, not simultaneous. Elements sweep in with staggered timing to create a "reveal" feel rather than a pop-in.

- Outside-in ordering (edges first, centre last)
- Orange glow on entrance, settling to neutral
- 80–210ms stagger between elements

---

## Scrollbars

Two variants, both thin and minimal:

| Class | Thumb | Track | Usage |
|-------|-------|-------|-------|
| `.custom-scrollbar` | `rgba(255, 255, 255, 0.1)` | transparent | Dark backgrounds |
| `.light-scrollbar` | `rgba(0, 0, 0, 0.12)` | transparent | Light backgrounds (feed cards) |

---

## Interaction Patterns

### Hover

- Scale up: `scale(1.15)` on nav bubbles
- Background shifts from white-transparent to orange-transparent
- Icon colour shifts from `rgba(255,255,255, 0.55)` to `var(--tigers-orange)`
- Connectors glow inward toward avatar (sequential, 120ms stagger)

### Active / Current Page

- Orange background, border, and glow — always visible, not just on hover
- Icon stays orange

### Tooltips

- Appear on hover, positioned radially from the bubble
- Style: `rgba(245, 130, 32, 0.12)` background, orange text, thin orange border
- Size: `text-[11px] font-medium`
- No tooltip on mobile (tap navigates directly)

---

## Voice in UI Copy

Per design principles — every piece of text has a speaker. No "system copy."

| State | Pattern | Example |
|-------|---------|---------|
| Loading | Crew member is working | "Analyst is thinking..." |
| Empty | Crew hasn't done this yet | "Scout hasn't found anything yet." |
| Error | Crew acknowledges failure | "Something broke. Even the best crews have bad days." |
| Timestamps | Relative, conversational | "3 hours ago" not ISO strings |

---

## Design Tokens Summary (CSS Variables)

```css
:root {
  --background: #0c0c0f;
  --foreground: #ededed;
  --tigers-orange: #F58220;
  --tigers-orange-glow: rgba(245, 130, 32, 0.4);
}
```

All other values (zinc shades, transparency levels, glow intensities) are used inline or via Tailwind utilities. If a value appears in three or more components, it should be promoted to a CSS variable.

---

## Notes

<!-- Add new patterns, decisions, or refinements here -->

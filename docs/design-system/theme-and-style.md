# Theme & Style Guide

Status: **Living document — evolves with the product**

---

## Metaphor

Jaromelu is a live broadcast from a warm room. The dark background is rich and coloured — not black, but deep brown with visible warmth. The audience is watching a show that's already running, from a comfortable seat in a dimly-lit studio.

---

## Colour Palette — "Warm Earth"

The dark theme uses a lifted, warm brown base with multiple coloured accents. The grey scale is brown-tinted — every surface, border, and muted text tone carries the warm undertone. This is the dark-mode sibling of the wiki's light theme.

### Core Surfaces

| Token | Value | CSS Variable | Usage |
|-------|-------|-------------|-------|
| Background | `#2a2420` | `--background` | Main canvas — warm brown-charcoal |
| Background Deep | `#241e1a` | `--background-deep` | Sidebar, deeper wells |
| Surface | `#342c26` | `--surface` | Cards, elevated containers |
| Surface Hover | `#3e3630` | `--surface-hover` | Hovered cards and panels |

### Foreground Scale (Warm Stone)

| Token | Value | CSS Variable | Usage |
|-------|-------|-------------|-------|
| Foreground | `#ede4d6` | `--foreground` | Primary text — warm cream |
| Secondary | `#c0b4a0` | `--foreground-secondary` | Descriptions, body secondary |
| Muted | `#948878` | `--foreground-muted` | Secondary text, timestamps |
| Faint | `#6e6458` | `--foreground-faint` | Disabled text, de-emphasised |
| Ghost | `#504840` | `--foreground-ghost` | Barely-visible, scrollbar thumbs |

### Borders

| Token | Value | CSS Variable | Usage |
|-------|-------|-------------|-------|
| Border | `#3e3630` | `--border` | Default borders, dividers |
| Border Subtle | `#504840` | `--border-subtle` | Input borders, secondary borders |

### Primary Accents

| Token | Value | CSS Variable | Usage |
|-------|-------|-------------|-------|
| Accent (Ember) | `#d4874a` | `--accent` | Jaromelu's voice, CTAs, active states |
| Accent Glow | `rgba(212,135,74,0.35)` | `--accent-glow` | Hover halos, emphasis |
| Accent BG | `rgba(212,135,74,0.10)` | `--accent-bg` | Tinted surfaces, callout boxes |
| Accent Border | `rgba(212,135,74,0.22)` | `--accent-border` | Remark card borders, active borders |
| Terracotta | `#b85c38` | `--terracotta` | Secondary warm accent — shared with wiki's accent |
| Ochre | `#c4a840` | `--ochre` | Archivist, receipts, gold badges, contradiction emphasis |

### Semantic / Crew Colours

| Token | Value | CSS Variable | Crew | Usage |
|-------|-------|-------------|------|-------|
| Teal | `#5a9e8a` | `--teal` | Scout | Success, verified, buy signals |
| Slate Blue | `#8aadcc` | `--slate` | Analyst | Context, mechanisms, neutral info |
| Lilac | `#a898c8` | `--lilac` | Bookkeeper | Numbers, stats, captain picks |
| Clay Red | `#c45050` | `--red` | Critic | Sell signals, warnings, injuries |

Each semantic colour has `*-bg` and `*-border` variants at reduced opacity for tinted surfaces and borders.

---

## Typography

| Role | Font | Tailwind | Usage |
|------|------|----------|-------|
| Body | Geist Sans | `font-sans` | All body text, labels, navigation |
| Data | Geist Mono | `font-mono` | Timestamps, scores, stats, code, technical values |
| Editorial | Cormorant Garamond | `font-serif` | Wiki headings, stat hero numbers |

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

Surfaces use warm solid backgrounds, not transparency on black. Each crew member's content cards use colour-tinted surfaces from their semantic colour.

| Level | Background | Border | Usage |
|-------|-----------|--------|-------|
| Canvas | `--background` `#2a2420` | — | Page background |
| Deep | `--background-deep` `#241e1a` | — | Sidebar, wells |
| Card | `--surface` `#342c26` | `--border` | Cards, panels, elevated containers |
| Card (hover) | `--surface-hover` `#3e3630` | `--border` | Hovered cards |
| Crew card (Scout) | `var(--teal-bg)` | `var(--teal-border)` | Scout content cards |
| Crew card (Analyst) | `var(--slate-bg)` | `var(--slate-border)` | Analyst content cards |
| Crew card (Bookkeeper) | `var(--lilac-bg)` | `var(--lilac-border)` | Bookkeeper content cards |
| Crew card (Archivist) | `var(--ochre-bg)` | `var(--ochre-border)` | Archivist content cards |
| Crew card (Critic) | `var(--red-bg)` | `var(--red-border)` | Critic content cards |
| Remark | `var(--accent-bg)` | `var(--accent-border)` + glow | Jaromelu's Remarks |
| Interactive (hover) | `var(--accent-bg)` | `var(--accent-border)` | Hovered interactive elements |
| Interactive (active) | `var(--accent-bg)` | `var(--accent-border)` + glow | Current page, selected state |

---

## Borders & Rounding

- Default border: `var(--border)` (1px)
- Interactive border: `1.5px solid` (slightly heavier for clickable elements)
- Rounding: `rounded-lg` for cards, `rounded-md` for badges/tooltips, `rounded-full` for avatars and nav bubbles

---

## Shadows & Glow

Shadows use the accent colour (ember) and are used sparingly.

| State | Box Shadow |
|-------|-----------|
| Resting (animated) | `0 0 12px rgba(212, 135, 74, 0.15)` — via `thought-float` keyframe |
| Hovered | `0 0 8px rgba(212, 135, 74, 0.2)` |
| Active | `0 0 16px rgba(212, 135, 74, 0.25)` |
| Avatar glow | `0 0 24px 8px var(--accent-glow), 0 0 48px 16px rgba(212, 135, 74, 0.15)` |
| Remark glow | `0 0 24px rgba(212, 135, 74, 0.06)` |

No neutral box shadows. If it glows, it glows ember.

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
| `thought-float` | Vertical bob (±3px) + ember border/shadow breathe | Nav bubbles on landing page |
| `crew-pill-pulse` | Border colour pulse (ember 0.2 → 0.4) | Crew status pill |
| `ping` | Scale + fade pulse (Tailwind built-in) | Online indicator dot |

### Entrance Choreography

Entrances are sequenced, not simultaneous. Elements sweep in with staggered timing to create a "reveal" feel rather than a pop-in.

- Outside-in ordering (edges first, centre last)
- Ember glow on entrance, settling to neutral
- 80–210ms stagger between elements

---

## Scrollbars

Two variants, both thin and minimal:

| Class | Thumb | Track | Usage |
|-------|-------|-------|-------|
| `.custom-scrollbar` | `var(--foreground-ghost)` | transparent | Dark backgrounds |
| `.light-scrollbar` | `rgba(0, 0, 0, 0.12)` | transparent | Light backgrounds (wiki) |

---

## Interaction Patterns

### Hover

- Scale up: `scale(1.15)` on nav bubbles
- Background shifts to `var(--accent-bg)`
- Icon colour shifts from `var(--foreground-muted)` to `var(--accent)`
- Connectors glow inward toward avatar (sequential, 120ms stagger)

### Active / Current Page

- Accent background, border, and glow — always visible, not just on hover
- Icon stays accent-coloured

### Tooltips

- Appear on hover, positioned radially from the bubble
- Style: `var(--accent-bg)` background, accent text, thin accent border
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
  /* Core surfaces */
  --background: #2a2420;
  --background-deep: #241e1a;
  --surface: #342c26;
  --surface-hover: #3e3630;
  --foreground: #ede4d6;
  --foreground-secondary: #c0b4a0;
  --foreground-muted: #948878;
  --foreground-faint: #6e6458;
  --foreground-ghost: #504840;

  /* Borders */
  --border: #3e3630;
  --border-subtle: #504840;

  /* Primary accents */
  --accent: #d4874a;
  --accent-glow: rgba(212, 135, 74, 0.35);
  --accent-bg: rgba(212, 135, 74, 0.10);
  --accent-border: rgba(212, 135, 74, 0.22);
  --terracotta: #b85c38;
  --ochre: #c4a840;

  /* Semantic / crew colours */
  --teal: #5a9e8a;       /* Scout */
  --slate: #8aadcc;      /* Analyst */
  --lilac: #a898c8;      /* Bookkeeper */
  --red: #c45050;        /* Critic */

  /* Each with *-bg and *-border variants */
}
```

All colours should reference CSS variables. Hardcoded hex values in components are not acceptable — use `var(--token-name)` in all styles.

---

## Wiki Theme (Light / Editorial)

The Wiki is an intentional departure from the dark broadcast stage. It uses a **clean, warm off-white light theme** with serif typography — evoking an editorial reference document rather than a live show. The wiki is where the audience goes to read, study, and browse what Jaromelu knows.

### Design Intent

| Aspect | Stream (dark) | Wiki (light) |
|--------|--------------|--------------|
| Metaphor | Live broadcast stage | Editorial reference / encyclopedia |
| Background | Near-black (`#0c0c0f`) | Warm off-white (`#FAF9F5`) |
| Typography | Geist Sans / Geist Mono | Serif (Georgia) for headings & body, sans for labels |
| Accent | Tigers orange (`#F58220`) | Burnt orange (`#b85c38`) — warmer, muted to suit the light palette |
| Interaction | Orange glow, spotlight | Subtle hover shifts, underlines, no glow |

The wiki does **not** use the main app's CSS variables (`--background`, `--foreground`, etc.). It defines its own scoped set under `.wiki-page`.

### Colour Palette

#### Core Tokens

| Token | Value | CSS Variable | Usage |
|-------|-------|-------------|-------|
| Background | `#FAF9F5` | `--wiki-bg` | Warm off-white canvas |
| Surface | `#FFFFFF` | `--wiki-surface` | Cards, elevated containers, table headers |
| Ink | `#1c1a14` | `--wiki-ink` | Primary text, headings |
| Ink Muted | `#5c5848` | `--wiki-ink-muted` | Body text, secondary content |
| Ink Faint | `#9c9484` | `--wiki-ink-faint` | Metadata, timestamps, labels |
| Accent | `#b85c38` | `--wiki-accent` | Links, kickers, dividers, interactive highlights |
| Accent BG | `#FFF0E8` | `--wiki-accent-bg` | Callout backgrounds, active filter state |

#### Borders

| Token | Value | CSS Variable | Usage |
|-------|-------|-------------|-------|
| Border | `rgba(28,26,20,0.12)` | `--wiki-border` | Default borders, section dividers, grid gaps |
| Border Strong | `rgba(28,26,20,0.18)` | `--wiki-border-strong` | Heavier separators |

#### Semantic Colours

| Token | Value / BG | CSS Variable | Usage |
|-------|-----------|-------------|-------|
| Teal | `#2d7d6b` / `#e8f5f0` | `--wiki-teal` / `--wiki-teal-bg` | Mechanism boxes, BREAKOUT tags |
| Amber | `#8a6a20` / `#f5ecd4` | `--wiki-amber` / `--wiki-amber-bg` | Verdict boxes, HOLD/NEUTRAL/PLAUSIBLE tags |
| Purple | `#5a3d8a` / `#f0eaf8` | `--wiki-purple` / `--wiki-purple-bg` | CAPTAIN tags |
| Green | `#2d6040` / `#e4f2e6` | `--wiki-green` / `--wiki-green-bg` | BUY/SOLID/BULLISH tags |
| Red | `#9a2020` / `#fae0e0` | `--wiki-red` / `--wiki-red-bg` | Warning boxes, SELL/AVOID/BEARISH tags |
| Gray | `#5c5848` / `#e8e5de` | (inline) | NEUTRAL tags |

### Typography

| Role | Font | Usage |
|------|------|-------|
| Headings | `var(--font-serif), Georgia, serif` | Page titles, section headings, stat values |
| Body | Inherited (Geist Sans) | Paragraphs, descriptions |
| Labels | System (sans-serif) | Kickers, section labels, meta, tags |
| Data | `var(--font-serif)` | Stat card values, timeline dots |

#### Scale

| Element | Size | Weight | Extras |
|---------|------|--------|--------|
| Page title (h1) | `clamp(2.6rem, 5.5vw, 3.6rem)` | 600 | `line-height: 1.1`, `tracking-tight` equivalent |
| Section heading (h2) | `clamp(1.8rem, 4vw, 2.4rem)` | 600 | Serif |
| Subsection (h3) | `1.25rem` | 600 | Serif |
| Section label (kicker) | `11px` | 600 | Uppercase, `letter-spacing: 0.14em`, accent colour |
| Body | `15px` | 400 | `line-height: 1.7`, ink-muted |
| Meta / timestamps | `13px` | 400 | Ink-faint |
| Tags | `10px` | 600 | Uppercase, `letter-spacing: 0.08em` |

### Surfaces & Elevation

Unlike the main app's transparency-based elevation, the wiki uses **opaque warm tones**.

| Level | Background | Border | Usage |
|-------|-----------|--------|-------|
| Canvas | `#FAF9F5` | — | Page background |
| Surface | `#FFFFFF` | `--wiki-border` | Cards, meta boxes, table headers, stat cards |
| Hover | `#FAF9F5` | — | Card hover (drops back to canvas) |

### Components

#### Structured Boxes

All boxes use a **left border accent** pattern (3px coloured left border).

| Box | Left Border | Background | Usage |
|-----|------------|-----------|-------|
| Callout | `--wiki-accent` | `--wiki-accent-bg` | Agent's strong take or opinion |
| Mechanism | `--wiki-teal` | `--wiki-surface` | Factual context, game mechanics |
| Verdict | `--wiki-amber` | `--wiki-surface` | Summary judgement |
| Warning | `--wiki-red` | `--wiki-red-bg` | Risk flags, danger zones |

#### Tags

Inline status badges using `wiki-tag` class. Uppercase, 10px, pill-shaped (`border-radius: 2px`).

Colour mapping for ratings:

| Tag | Colour |
|-----|--------|
| BUY, SOLID, BULLISH, HIT | Green |
| HOLD, NEUTRAL, PLAUSIBLE | Amber |
| SELL, AVOID, BEARISH, MISS, SPECULATIVE | Red |
| CAPTAIN | Purple |
| BREAKOUT | Teal |

#### Stat Cards

4-column grid (2-column on mobile) with 1px gap borders. Each card contains a label (10px uppercase), a value (serif, 1.6rem), and a sub line (12px faint).

#### Trust / Advisor List

Stacked rows with a rating badge column (100px) and a body column. Used for advisor trust ratings on player and team pages.

#### Timeline

Vertical timeline with coloured dot markers (40px circles, serif text). A gradient line runs behind (`red → amber → faint`). Each step has a title (uppercase, 13px), description, and optional signal line (italic, faint).

#### Final Verdict

Centred box with kicker ("Jaromelu's Call"), serif italic text, surface background. Used as the closing statement on wiki pages.

### Custom Markdown Blocks

The wiki markdown renderer supports fenced blocks for rich components:

| Syntax | Renders |
|--------|---------|
| `:::stats` | Stat card grid (from table rows: Label, Value, Sub) |
| `:::trust` | Trust/advisor list (from table rows: Rating, Name, Description) |
| `:::timeline` | Timeline (from table rows: Year, Color, Title, Description, Signal) |
| `:::final-verdict` | Final verdict box |

Blockquote prefixes map to styled boxes:

| Prefix | Box |
|--------|-----|
| `> Callout:` | `.wiki-callout` |
| `> Mechanism:` | `.wiki-mechanism` |
| `> Verdict:` | `.wiki-verdict` |
| `> Warning:` | `.wiki-warning` |

Wiki links use `[[slug]]` syntax, resolved against linked pages at render time.

### Sticky Navigation

Section nav extracted from `## Heading` markers. Sticky at top with frosted glass effect (`rgba(232,227,217,0.93)` + `backdrop-filter: blur(8px)`). Links are 11px uppercase with accent underline on hover.

### Animation

Minimal compared to the main app. Single `wikiFadeUp` entrance animation (0.6s hero, 0.4s content sections with 80ms delay). No looping animations, no glow effects.

### Layout

- **Max content width:** 820px, centred
- **Desktop offset:** 240px left padding (clears the main app sidebar)
- **Mobile:** Full width, no offset
- **Page grid (index):** 1 / 2 / 3 columns responsive

### CSS Variables Summary

```css
.wiki-page {
  --wiki-serif: var(--font-serif), Georgia, serif;
  --wiki-bg: #FAF9F5;
  --wiki-surface: #FFFFFF;
  --wiki-border: rgba(28,26,20,0.08);
  --wiki-border-strong: rgba(28,26,20,0.14);
  --wiki-ink: #1c1a14;
  --wiki-ink-muted: #5c5848;
  --wiki-ink-faint: #9c9484;
  --wiki-teal: #2d7d6b;
  --wiki-teal-bg: #e8f5f0;
  --wiki-amber: #8a6a20;
  --wiki-amber-bg: #f5ecd4;
  --wiki-purple: #5a3d8a;
  --wiki-purple-bg: #f0eaf8;
  --wiki-green: #2d6040;
  --wiki-green-bg: #e4f2e6;
  --wiki-red: #9a2020;
  --wiki-red-bg: #fae0e0;
  --wiki-accent: #b85c38;
  --wiki-accent-bg: #FFF0E8;
}
```

---

## Notes

<!-- Add new patterns, decisions, or refinements here -->

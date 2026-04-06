# The Wiki

Status: **Phase 1 built**

---

## Summary

The wiki is a prose-dominant, agent-maintained knowledge base about the NRL. Users browse interlinked entity pages written and continuously updated by Jeromelu. It replaces the earlier "Knowledge Base page" concept with a full editorial reading experience.

Design reference: [docs/designs/wiki-player.html](../../designs/wiki-player.html)
Feature doc: [docs/features/wiki.md](../../features/wiki.md)

---

## Design Philosophy

The wiki deliberately breaks from the rest of the app. Where the main Jeromelu experience is a dark, broadcast-style stage, the wiki is a **warm, editorial reading surface** — closer to a well-typeset journal than a dashboard. This distinction reinforces that the wiki is a knowledge artifact: something to read, browse, and follow links through, not a live feed to monitor.

The visual language is adapted from the [Stay Human analysis](../../designs/wiki-player.html) pattern — a serif/sans pairing on a warm parchment background with structured editorial components.

---

## Colour Palette

The wiki uses its own palette, independent of the main app's dark theme.

### Surfaces

| Token | Value | CSS Variable | Usage |
|-------|-------|-------------|-------|
| Background | `#f5f0e8` | `--wiki-bg` | Warm parchment — the wiki canvas |
| Surface | `#fdfaf4` | `--wiki-surface` | Cards, panels, elevated elements |
| Border | `rgba(28,26,20,0.12)` | `--wiki-border` | Hairline dividers, card edges |

### Ink

| Token | Value | CSS Variable | Usage |
|-------|-------|-------------|-------|
| Ink | `#1c1a14` | `--wiki-ink` | Primary text, headings |
| Ink Muted | `#5c5848` | `--wiki-ink-muted` | Body text, descriptions |
| Ink Faint | `#9c9484` | `--wiki-ink-faint` | Timestamps, labels, secondary metadata |

### Accent

| Token | Value | CSS Variable | Usage |
|-------|-------|-------------|-------|
| Accent | `#b85c38` | `--wiki-accent` | Links, kickers, dividers, interactive elements |
| Accent BG | `#f0ddd5` | `--wiki-accent-bg` | Callout box backgrounds, active filter states |

### Domain Colours

Used for tags, rating badges, timeline dots, and box variants.

| Token | Value | CSS Variable | Usage |
|-------|-------|-------------|-------|
| Teal | `#2d7d6b` / `#d4ede8` | `--wiki-teal` / `--wiki-teal-bg` | Mechanism boxes, breakout tags |
| Amber | `#8a6a20` / `#f0e5c8` | `--wiki-amber` / `--wiki-amber-bg` | Verdict boxes, hold/neutral tags |
| Purple | `#5a3d8a` / `#e8e0f5` | `--wiki-purple` / `--wiki-purple-bg` | Captain tags |
| Green | `#2d6040` / `#d4ead8` | `--wiki-green` / `--wiki-green-bg` | Buy/bullish/solid tags |
| Red | `#9a2020` / `#f5dada` | `--wiki-red` / `--wiki-red-bg` | Sell/avoid/warning boxes |

---

## Typography

| Element | Font | Size | Weight | Notes |
|---------|------|------|--------|-------|
| Page title (h1) | Cormorant Garamond | `clamp(2.6rem, 5.5vw, 3.6rem)` | 600 | Centered hero |
| Section heading (h2) | Cormorant Garamond | `clamp(1.8rem, 4vw, 2.4rem)` | 600 | With section border above |
| Subheading (h3) | Cormorant Garamond | `1.25rem` | 600 | |
| Kicker label | Geist Sans | `11px` | 600 | Uppercase, tracked, accent colour |
| Body text | Geist Sans | `15px` | 400 | `line-height: 1.7`, muted ink |
| Stat card value | Cormorant Garamond | `1.6rem` | 600 | Big serif numbers |
| Table header | Geist Sans | `11px` | 600 | Uppercase, tracked, faint ink |

The serif/sans pairing (Cormorant Garamond for headings and display, Geist Sans for body and UI) gives the wiki an editorial character that separates it from the dashboard-style main app.

---

## Page Layout

### Wiki Index (`/wiki`)

```
┌────────────────────────────────────────────────────┐
│                   KNOWLEDGE BASE                   │  ← kicker
│                    The Wiki                        │  ← serif h1
│        Everything Jeromelu knows — ...             │  ← italic subtitle
│                    ───────                         │  ← accent divider
│                                                    │
│  [Search...] [All] [Players] [Teams] [Advisors]   │  ← filters
│                                                    │
│  ┌─────────────────────────────────┐ ┌───────────┐│
│  │  TEAMS (3)                      │ │  RECENT   ││
│  │ ┌─────┬─────┬─────┐            │ │  CHANGES  ││
│  │ │card │card │card │  ← 1px gap │ │           ││
│  │ └─────┴─────┴─────┘            │ │  Tom T.   ││
│  │                                 │ │  Updated..││
│  │  ADVISORS (2)                   │ │           ││
│  │ ┌─────┬─────┐                  │ │  Cleary   ││
│  │ │card │card │                  │ │  Updated..││
│  │ └─────┴─────┘                  │ │           ││
│  │                                 │ └───────────┘│
│  │  PLAYERS (2)                    │              │
│  │ ┌─────┬─────┐                  │              │
│  │ │card │card │                  │              │
│  │ └─────┴─────┘                  │              │
│  └─────────────────────────────────┘              │
└────────────────────────────────────────────────────┘
```

Cards use the 1px-gap grid pattern (container has border colour as background, cards sit in the gaps) for hairline dividers. Each card shows: serif title, summary (2-line clamp), timestamp, optional status badge.

### Wiki Entity Page (`/wiki/player/[slug]`)

```
┌────────────────────────────────────────────────────┐
│ [OVERVIEW] [FORM] [PRICE] [EXPERTS] [INJURIES] .. │  ← sticky section nav
├────────────────────────────────────────────────────┤
│  Wiki › Players › Tom Trbojevic                    │  ← breadcrumb
│                                                    │
│                      PLAYER                        │  ← kicker
│                 Tom Trbojevic                       │  ← serif h1
│          Premium fullback for Manly...             │  ← italic subtitle
│        Updated 5m ago · 12 revisions               │  ← meta line
│                    ───────                         │  ← accent divider
│                                                    │
│  ─────────────────────────────────────────────     │
│  ## Overview                                       │  ← serif h2
│                                                    │
│  Body text with [[wiki-links]] in accent...        │
│                                                    │
│  ┌─ Callout: agent's strong take ──────────────┐   │  ← accent border-left
│  └─────────────────────────────────────────────┘   │
│                                                    │
│  ─────────────────────────────────────────────     │
│  ## Current Form                                   │
│                                                    │
│  ┌──────┬──────┬──────┬──────┐                     │  ← stat cards (4-col)
│  │ 74.3 │$487k │  61  │ 4/5  │  ← serif numbers   │
│  │ Avg  │Price │ BEV  │Games │  ← labels           │
│  └──────┴──────┴──────┴──────┘                     │
│                                                    │
│  ─────────────────────────────────────────────     │
│  ## Expert Opinions                                │
│                                                    │
│  ┌──────────┬──────────────────────────────────┐   │  ← trust list
│  │ BULLISH  │ SC Playbook                      │   │
│  │  (green) │ Description text...              │   │
│  ├──────────┼──────────────────────────────────┤   │
│  │  HOLD    │ SuperCoach NRL Pod               │   │
│  │ (amber)  │ Description text...              │   │
│  └──────────┴──────────────────────────────────┘   │
│                                                    │
│  ┌─ Verdict: assessment text ──────────────────┐   │  ← amber border-left
│  └─────────────────────────────────────────────┘   │
│                                                    │
│  ─────────────────────────────────────────────     │
│  ## Injury History                                 │
│                                                    │
│  ●─ '25  2025 Season — missed 10 games...      │  ← timeline
│  │       Signal: returned for finals...         │
│  ●─ '24  2024 Season — missed 8 games...       │
│  │                                              │
│  ●─ '23  2023 Season — knee reconstruction     │
│  │                                              │
│  ●─ '22  2022 Season — 20 games (healthy)      │
│                                                    │
│  ┌─ Warning: 3 of 4 seasons... ────────────────┐   │  ← red border-left
│  └─────────────────────────────────────────────┘   │
│                                                    │
│  ─────────────────────────────────────────────     │
│  ## SuperCoach Verdict                             │
│                                                    │
│  ┌─────────────────────────────────────────────┐   │  ← final verdict box
│  │            JEROMELU'S CALL                   │   │     (centered, bordered)
│  │    [BUY] at current price if bench cover     │   │
│  │    [AVOID] if you need reliability           │   │
│  └─────────────────────────────────────────────┘   │
│                                                    │
│  ───── Wiki page maintained by Jeromelu ─────      │  ← footer
└────────────────────────────────────────────────────┘
```

---

## Component Vocabulary

The agent writes markdown content using these conventions. The frontend `MarkdownRenderer` parses and renders them as styled editorial components.

### Standard Markdown (rendered with wiki styling)

| Markdown | Renders As |
|----------|-----------|
| `## Heading` | Serif h2 with section border-top separator |
| `### Subheading` | Serif h3 |
| `[[slug]]` | Accent-coloured interlink to another wiki page |
| `**bold**` | Bold in ink colour |
| Standard tables | Arch-table with uppercase headers, hover rows |
| `---` | Centered accent decorative divider (60px) |
| `> plain quote` | Accent border-left, italic |

### Callout Boxes (blockquote variants)

| Markdown | Box Style | Usage |
|----------|-----------|-------|
| `> **Callout:** text` | Accent border-left + accent bg | Agent's strong take, key opinion |
| `> **Mechanism:** text` | Teal border-left + surface bg | Factual context, how something works |
| `> **Verdict:** text` | Amber border-left + surface bg | Assessment, recommendation |
| `> **Warning:** text` | Red border-left + red bg | Risk alert, injury concern |

### Inline Tags

Written as backtick-wrapped brackets: `` `[BUY]` `[SELL]` `[HOLD]` `[CAPTAIN]` `[AVOID]` `[BREAKOUT]` ``

Also: `` `[BULLISH]` `[BEARISH]` `[NEUTRAL]` `[SOLID]` `[PLAUSIBLE]` `[SPECULATIVE]` ``

Each renders as a small uppercase badge in the appropriate domain colour.

### Custom Blocks (fenced with `:::`)

#### Stat Cards
```markdown
:::stats
| Label | Value | Sub |
|-------|-------|-----|
| Avg SC Points | 74.3 | Ranked 4th (FLB) |
| Price | $487k | Mid-premium |
:::
```
Renders as a 4-column grid of cards with serif numbers, uppercase labels, and sub-text.

#### Trust / Advisor List
```markdown
:::trust
| Rating | Name | Description |
|--------|------|-------------|
| Bullish | SC Playbook | They argue the discount is too steep... |
| Hold | The SuperCoach NRL Podcast | They flag the hamstring... |
:::
```
Renders as a structured list with coloured rating badges on the left and name/description on the right.

#### Timeline
```markdown
:::timeline
| Year | Color | Title | Description | Signal |
|------|-------|-------|-------------|--------|
| '25 | red | 2025 Season | Missed <strong>10 games</strong> | Returned for finals |
| '22 | green | 2022 Season | Played <strong>20 games</strong> | Healthiest season |
:::
```
Renders as a vertical timeline with coloured numbered dots and a gradient connecting line.

#### Final Verdict
```markdown
:::final-verdict
`[BUY]` at current price if you have bench cover. `[AVOID]` if you need reliability.
:::
```
Renders as a centered bordered box with "Jeromelu's Call" kicker and serif italic text.

---

## Routes

| Route | Page | Content |
|-------|------|---------|
| `/wiki` | Index | Grouped page grid + recent changes sidebar |
| `/wiki/player/[slug]` | Player page | Full editorial page |
| `/wiki/team/[slug]` | Team page | Full editorial page |
| `/wiki/advisor/[slug]` | Advisor page | Full editorial page + track record |
| `/wiki/round/[season]/[round]` | Round page | Preview → recap with game subsections |

---

## Key Files

| File | Purpose |
|------|---------|
| `services/web/src/app/wiki/wiki.css` | All wiki-specific styles and CSS variables |
| `services/web/src/app/wiki/components/WikiPageClient.tsx` | Page layout — hero, nav, footer |
| `services/web/src/app/wiki/components/MarkdownRenderer.tsx` | Markdown → editorial components |
| `services/web/src/app/wiki/WikiIndexClient.tsx` | Index page — grid, filters, sidebar |
| `docs/designs/wiki-player.html` | Standalone HTML design reference |

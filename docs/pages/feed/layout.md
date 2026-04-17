# Feed Page Layout

Status: **Draft — deciding on layout and feature placement**

---

## Context

The feed page (`/feed`) is now the default entry point — `/` redirects here. This is where the audience lands and spends most of their time. The decision to skip the landing page (see [archive/landing-page.md](../../archive/landing-page.md)) means the feed must immediately deliver value: the show is already running when you arrive.

We need to decide how to use the available screen real estate, particularly the three-column desktop layout now that the Jaromelu avatar + nav bubbles live in the top-left.

The existing design principles (see [concepts/00-design-principles.md](../../concepts/00-design-principles.md)) describe a single-screen "Stream" model. This document works through how that vision maps to the actual page layout and what belongs where.

---

## Desktop Layout (≥1024px)

```
┌──────────────┬──────────────────────────┬──────────────┐
│              │                          │              │
│  LEFT PANEL  │       MAIN FEED          │  RIGHT PANEL │
│              │                          │              │
│  - Avatar    │  - The Stream            │  - ???       │
│  - Nav       │  - Feed cards            │              │
│  - ???       │                          │              │
│              │                          │              │
└──────────────┴──────────────────────────┴──────────────┘
```

### Left Panel (currently: avatar + nav bubbles, floating)

What we have:
- Jaromelu avatar (160px, clickable → home)
- 5 orbital nav bubbles (The Feed, The Wiki, The Ledger, The Analysis, Ask Me)
- Online indicator

Open questions:
- [ ] Should this be a proper sidebar container or keep the floating aesthetic?
- [ ] What else belongs here? Crew status? Activity pulse?
- [ ] Fixed or scrollable?

### Main Feed (centre column)

What we have:
- Feed cards from the API

Open questions:
- [ ] Card design — what information density per card?
- [ ] Infinite scroll vs pagination?
- [ ] Filtering / sorting controls?
- [ ] How does this relate to "The Stream" concept from the design principles?

### Right Panel

Currently: empty / unused.

Open questions:
- [ ] Drill-down panel (per design principles) — opens when tapping a feed item?
- [ ] Player spotlight / trending topics?
- [ ] "Ask Me" chat interface?
- [ ] Squad alignment or leaderboard widget?
- [ ] Always visible or only opens on interaction?

---

## Mobile Layout (<1024px)

Open questions:
- [ ] Single column — how does nav work?
- [ ] Bottom nav bar replacing orbital bubbles?
- [ ] Right panel becomes a slide-up sheet?

---

## Decisions Needed

1. **Sidebar vs floating nav** — does the left panel get a container/background, or stay as floating elements?
2. **Right panel purpose** — what is the primary use of the right column?
3. **Stream integration** — is the feed page *the* Stream, or a different view?
4. **Information hierarchy** — what's the most important thing the user sees on this page?

---

## Notes

<!-- Add discussion notes, screenshots, or references here -->

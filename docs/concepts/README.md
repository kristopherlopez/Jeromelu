---
tags: [area/concepts]
---

# Design Language & Concepts

These docs define the design language, narrative framing, and interaction concepts for the Jaromelu experience. They are not page specs — for those see [docs/pages/](../pages/).

## Page name changes (2026-04-17)

The app now has five canonical pages. Where these concept docs reference older names, translate as follows:

| Legacy name in concepts | Current page |
|-------------------------|--------------|
| **My Squad** / "the Squad panel" | Retired — role superseded by [The Analysis](../pages/analysis/overview.md) |
| **The Dossier** / "the Dossier panel" | Now [The Wiki](../pages/wiki/overview.md) — per-entity pages written and maintained by Jaromelu |
| **Insights** (as a nav label) | Now labelled **The Analysis** in the UI (route still `/insights`) |

The underlying concepts (drill-downs, remarks, crew presence, the stream) still apply — only the surface naming shifted.

## Files

| File | Purpose |
|------|---------|
| [00-design-principles.md](00-design-principles.md) | Core design principles |
| [01-the-stream.md](01-the-stream.md) | The Stream — single-screen model the feed is built on |
| [02-remarks.md](02-remarks.md) | Remark cards — Jaromelu's voiced calls |
| [03-episode-beats.md](03-episode-beats.md) | Narrative structure of feed items |
| [04-drill-downs.md](04-drill-downs.md) | Drill-down panel mechanics |
| [05-crew-presence.md](05-crew-presence.md) | Crew character presence |
| [06-audience.md](06-audience.md) | Audience interaction patterns |
| [07-first-run.md](07-first-run.md) | First-run experience |
| [08-stitch-requirements.md](08-stitch-requirements.md) | Stitch requirements for composed UI |
| [entity-roles.md](entity-roles.md) | Entity-role SCD-2 model — how a single person carries multiple roles over time |

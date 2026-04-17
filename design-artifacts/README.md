# Design Artifacts

Frozen HTML design snapshots. Not living docs — kept for design continuity ("what did we decide on Stream v3?"). Moved out of `docs/` to reduce doc-tree bloat.

## Contents

| Folder | What | Referenced from |
|--------|------|-----------------|
| [design-system/](design-system/) | Global tokens: colour palettes, typography, box variants, font explorations, dark theme refresh | [`docs/design-system/theme-and-style.md`](../docs/design-system/theme-and-style.md) |
| [feed/](feed/) | Stream variants v1–v7 + home-crew mockups | [`docs/pages/feed/`](../docs/pages/feed/overview.md) |
| [wiki/](wiki/) | Wiki index-at-scale + player page | [`docs/pages/wiki/`](../docs/pages/wiki/overview.md) |
| [ledger/](ledger/) | Ledger page + round overview | [`docs/pages/ledger/`](../docs/pages/ledger/overview.md) |

## When to add new artifacts

A design HTML is worth committing when:
- It captures a point-in-time decision worth preserving
- It's distinct enough from prior variants to be useful reference
- The concept isn't already documented in `docs/`

Otherwise, sketch locally and move on.

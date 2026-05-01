---
tags: [area/pages, subarea/ledger]
---

# The Ledger

Status: **Stub — feature doc to be written**

---

## Summary

The Ledger tracks every prediction Jaromelu (and each advisor source) has made, and scores them against actuals once the round resolves. It's the accountability surface — a public record of conviction and accuracy over time.

Route: `/ledger`
Code: `services/web/src/app/ledger/`

---

## Intent

- Multi-source prediction tracking — Jaromelu, advisors, and any other voices feeding the wiki
- Future accuracy index — rolling scorecards per source
- Ties into [Wiki advisor pages](../wiki/overview.md) — each advisor's track record surfaces here

---

## Documents

| Doc | Purpose |
|-----|---------|
| [design-artifacts/ledger/ledger-page.html](../../../design-artifacts/ledger/ledger-page.html) | Design snapshot of the ledger page |
| [design-artifacts/ledger/round-overview.html](../../../design-artifacts/ledger/round-overview.html) | Round-level summary reference (related) |

---

## TODO

- [ ] Feature doc with schema, API endpoints, scoring rules
- [ ] Advisor prediction table spec (see [wiki/overview.md § Advisor Accuracy Tracking](../wiki/overview.md))
- [ ] Integration with [PlayerRound actuals resolution](../../agents/system/daily-intel-sweep.md)

---
tags: [area/architecture]
---

# Explainability Design

Users should see internal reasoning steps, but not raw technical internals.

Good public reasoning:
- "12 approved sources now leaning buy"
- "matchup sentiment flipped in the last 24 hours"
- "my current plan improves round flexibility"

Bad public reasoning:
- model architecture details
- token-level internals
- vector retrieval mechanics

Rule:
Show process, not plumbing.

---

# Governance & Risk

## Public Truthfulness Rules
- Jaromelu is explicitly disclosed as AI-generated.
- Public claims should be traceable to evidence.
- Confidence can be postured stylistically, but not fabricated as fake certainty metrics.
- Contrarian-for-show decisions must stay bounded and intentional.

## Hidden Controls
Not publicly disclosed:
- kill switch
- pause engine
- pause publishing
- emergency moderation tools

## Reputation Risk
You do want external expert tracking.
That creates upside and risk.

To avoid needless fights in V1:
- track accuracy objectively
- avoid loaded labels
- show methodology page
- preserve exact source lineage
- do not editorialise maliciously

---

# Operating Signals

How we know the product is working. Each core job has a leading signal (early, behavioural) and a lagging signal (durable, outcome-based). Vanity metrics — page views, session count alone — don't appear here. These are the questions we ask in product review, not in marketing.

| Job | Leading signal | Lagging signal |
|--------|---------------|----------------|
| **Compression** | Time-to-first-Remark per session under 30s. Ratio of sources ingested → Remarks published per round. | The audience can articulate the week's consensus after one visit (qual). Returning users skip directly to the Feed, not to source links. |
| **Truth filter** | Number of commentator sources tracked with stable Alignment scores (>10 graded predictions). | Inbound search/social traffic for commentator names lands on Jaromelu's Wiki pages. The Index gets cited externally. |
| **A show worth following** | Return rate concentrated at episode beats (Monday and Thursday peaks visible in traffic). Session depth on Thursdays (The Call beat). | Viewers refer to Jaromelu by name in inbound traffic / share copy. The crew is named (Scout, Analyst) in user language unprompted. |
| **Skin in the game** | Reaction rate per open Remark (% of viewers who tap agree/disagree). Challenge volume per Remark. | Distribution of personal Alignment Index scores tightens over a season — engaged users improve. Cohort returning to check their own record weekly. |
| **Public stakes** | % of Remarks that resolve on schedule (no orphaned calls). Receipt-card share count per resolved Remark. | Jaromelu's Alignment Index trends upward across a season. Audience trust signal: agree/disagree ratio shifts toward agreement on high-conviction calls over time. |

> Migrated from the former `02-value-and-delivery.md` (2026-05-23). The job labels map to the show's mechanisms in [The Show](../vision/02-the-show.md).

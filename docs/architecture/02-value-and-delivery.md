---
tags: [area/architecture]
---

# Value & Delivery

> Created: 2026-05-06

This doc sits between the [Venture Thesis](01-venture-thesis.md) (*why* Jaromelu exists) and the [Experience Architecture](03-experience-architecture.md) (*how* the show is structured). It traces a single line: **promise → pillar → mechanism → signal.**

If you read only one architecture doc to understand what we owe the customer and how we'll know we're delivering it, read this one.

---

## The Promise

> **"Help me quickly understand what the SuperCoach world is thinking — and entertain me while doing it."**
> — [Venture Thesis, §Core Job To Be Done](01-venture-thesis.md)

The customer is a hardcore NRL SuperCoach player who already consumes multiple podcasts and YouTube channels each week. They are time-poor, opinion-saturated, and decision-fatigued. They don't need more content. They need:

1. **Compression** — the ecosystem distilled into a few sharp positions.
2. **Conviction** — somebody willing to put their name on a call and live with it.
3. **Spectacle** — a reason to come back that isn't a chore.

Everything we build serves these three. If a feature doesn't strengthen at least one, it doesn't ship.

---

## The Five Value Pillars

The promise unpacks into five pillars. Each one is a *job the customer is hiring Jaromelu to do.*

| # | Pillar | What the customer gets |
|---|--------|------------------------|
| 1 | **Compression** | The week's NRL SuperCoach commentary collapsed into a small number of opinionated calls. |
| 2 | **Conviction with receipts** | Every call is public, locked, and graded against reality. No retconning. |
| 3 | **Spectacle** | A watchable production — a crew working in public, an episode arc, a voice. |
| 4 | **Ecosystem authority** | A trust ranking for *every* expert source, not just Jaromelu — answering "who actually reads the game?" |
| 5 | **Participation** | The audience reacts, challenges, and gets graded too. They're in the show. |

---

## How Each Pillar Is Delivered

Each pillar maps to specific surfaces, crew members, and mechanisms.

### 1. Compression

**Mechanism:**
- **Scout** ingests the NRL podcast and media ecosystem. ([Scout architecture](../agents/crew/scout.md))
- **Analyst** cross-references claims, finds contradictions, surfaces consensus shifts. ([Analyst](../agents/crew/analyst.md))
- **Remarks** are the compressed output — opinionated, voiced positions Jaromelu puts his name on. ([Remarks](../concepts/02-remarks.md))

**Customer experience:**
- "12 podcast hours compressed into 4 Remarks" — but the compression is *visible*, not hidden. (See [Show the Work](../concepts/00-design-principles.md#show-the-work).)
- The Feed surfaces both the raw intake (crew activity) and the distilled output (Remarks).

### 2. Conviction with receipts

**Mechanism:**
- **Remark lifecycle**: `OPEN → LOCKED → RESOLVED`. Once locked, a call cannot be edited.
- **The Ledger** ([pages/ledger](../pages/ledger/overview.md)) tracks every Remark to resolution and grades it.
- **Receipt cards** are generated for resolved Remarks — purpose-built shareable content.
- **Jaromelu owns misses publicly** — the voice references past calls, including the wrong ones. ([Jaromelu](../agents/crew/jaromelu.md))

**Customer experience:**
- An open Remark is a prediction the customer can agree or disagree with.
- A resolved Remark is a receipt the customer can share.
- The customer trusts Jaromelu more *because* the misses are visible, not despite it.

### 3. Spectacle

**Mechanism:**
- **The Crew as characters** — Scout, Analyst, Critic, Bookkeeper, Archivist, Jaromelu. Visible, differentiated roles. ([Crew Presence](../concepts/05-crew-presence.md))
- **The Episode Arc** — Mon (intel) → Tue–Wed (tension) → Thu (the call) → Sat–Sun (the match) → Mon (the reckoning). ([Episode Beats](../concepts/03-episode-beats.md))
- **Voice everywhere** — no system copy. Loading states, empty states, errors all speak in character. ([Design Principles §Voice Everywhere](../concepts/00-design-principles.md#voice-everywhere))
- **The rhythm is the UI** — the Stream looks different on Monday than on Thursday.

**Customer experience:**
- You don't land on a homepage. You arrive mid-episode, with the crew already working.
- You learn the rhythm: when to check in for new intel, when the call drops, when to come back for receipts.
- The site feels like a broadcast, not a dashboard.

### 4. Ecosystem authority

**Mechanism:**
- **The Alignment Index** scores *every* expert source Scout ingests, not just Jaromelu. ([Experience Architecture §The Alignment Index](03-experience-architecture.md#the-alignment-index))
- **The Wiki** maintains per-advisor pages with track records. ([pages/wiki](../pages/wiki/overview.md))
- **Head-to-head framing** — "I'm beating KingOfSC on captain picks this season."

**Customer experience:**
- The site has authority *beyond* Jaromelu's own performance. Even on a bad week, the Index is still useful.
- Answers a question no other site answers cleanly: "Which podcasters should I actually listen to?"

### 5. Participation

**Mechanism:**
- **Reactions** — agree / disagree on every open Remark. ([Audience §Reactions](../concepts/06-audience.md#reactions))
- **Challenges** — ask Jaromelu directly about a call. He responds in character.
- **Squad submission** — submit your team for a review. Tone control: straight / sharp / roast.
- **Personal Alignment Index** — every customer accumulates their own accuracy record.
- **Crowd moments** — Jaromelu references the crowd in vindication, collective miss, contrarian-was-right beats.

**Customer experience:**
- The customer is in the show, not watching it. Their reactions are part of the record.
- Reasons to return that don't depend on Jaromelu being right: "How am *I* tracking?"

---

## How We Know It's Working

Each pillar has a leading signal (early, behavioural) and a lagging signal (durable, outcome-based). Vanity metrics — page views, session count alone — don't appear here.

| Pillar | Leading signal | Lagging signal |
|--------|---------------|----------------|
| **Compression** | Time-to-first-Remark per session under 30s. Ratio of sources ingested → Remarks published per round. | Customer can articulate the week's consensus after one visit (qual). Returning users skip directly to the Feed, not to source links. |
| **Conviction with receipts** | % of Remarks that resolve on schedule (no orphaned calls). Receipt-card share count per resolved Remark. | Jaromelu's Alignment Index trends upward across a season. Customer trust signal: agree/disagree ratio shifts toward agreement on high-conviction calls over time. |
| **Spectacle** | Return rate concentrated at episode beats (Monday and Thursday peaks visible in traffic). Session depth on Thursdays (The Call beat). | Customers refer to Jaromelu by name in inbound traffic / share copy. The crew is named (Scout, Analyst) in user language unprompted. |
| **Ecosystem authority** | Number of advisor sources tracked with stable Alignment scores (>10 graded predictions). | Inbound search/social traffic for advisor names lands on Jaromelu's Wiki pages. The Index gets cited externally. |
| **Participation** | Reaction rate per open Remark (% of viewers who tap agree/disagree). Challenge volume per Remark. | Distribution of personal Alignment Index scores tightens over a season — engaged users improve. Cohort returning to check their own record weekly. |

These are the questions we ask in product review, not the questions we ask in marketing.

---

## What This Is *Not*

To stay honest about scope, the promise excludes:

- **A stats site.** Raw data is not the value. Compressed, voiced opinion is.
- **A neutral aggregator.** Jaromelu has a position on every call. Neutral summaries are explicitly disallowed.
- **A SuperCoach optimiser tool.** We are not solving the optimisation problem. We are entertaining the customer who already has tools and wants synthesis. (See [Venture Thesis §Why A Character Instead Of A Tool](01-venture-thesis.md#why-a-character-instead-of-a-tool).)
- **A general NRL site.** The audience is hardcore SuperCoach players. Casual NRL fans are not the target.
- **A chatbot.** Ask Me exists, but it's a contextual surface, not the product. The product is the Feed and the show.

If a proposed feature conflicts with this list, the feature is wrong — not the list.

---

## Related

- [Venture Thesis](01-venture-thesis.md) — strategic frame: who the customer is, why a character.
- [Experience Architecture](03-experience-architecture.md) — full breakdown of crew, surfaces, and the episode arc.
- [Design Principles](../concepts/00-design-principles.md) — the visual and editorial rules that make spectacle work.
- [V1 Scope & Roadmap](09-v1-scope-and-roadmap.md) — what we ship first against this promise.
- [Explainability & Governance](08-explainability-and-governance.md) — how the receipts stay honest.

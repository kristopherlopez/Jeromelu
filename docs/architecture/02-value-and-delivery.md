---
tags: [area/architecture]
---

# Value & Delivery

> Created: 2026-05-06

This doc sits between the [Venture Thesis](01-venture-thesis.md) (*why* Jaromelu exists) and the [Experience Architecture](03-experience-architecture.md) (*how* the show is structured). It traces a single line: **promise → pillar → mechanism → signal.**

If you read only one architecture doc to understand what we owe the customer and how we'll know we're delivering it, read this one.

This doc covers the **NRL commentary spoke** — the first spoke off the core (persona + knowledge graph). Other spokes (SuperCoach, tipping, sports betting) inherit this value model and add their own. See [Venture Thesis §Core and Spokes](01-venture-thesis.md#core-and-spokes).

---

## The Promise

> **"Help me quickly understand what the NRL world is thinking — and entertain me while doing it."**
> — [Venture Thesis, §Core Job To Be Done](01-venture-thesis.md)

The customer is a hardcore NRL fan who already consumes multiple podcasts and YouTube channels each week. They are time-poor, opinion-saturated, and decision-fatigued. They don't need more content. They need:

1. **Compression** — the ecosystem distilled into a few sharp positions.
2. **Conviction** — somebody willing to put their name on a call and live with it.
3. **Spectacle** — a reason to come back that isn't a chore.

Everything we build serves these three. If a feature doesn't strengthen at least one, it doesn't ship.

---

## The Five Value Pillars

The promise unpacks into five pillars. Each one is a *job the customer is hiring Jaromelu to do.* These match the [Value Proposition table in the thesis](01-venture-thesis.md#the-value-proposition).

| # | Pillar | What the customer gets |
|---|--------|------------------------|
| 1 | **Compression** | The week's NRL commentary collapsed into a small number of opinionated calls. |
| 2 | **Truth filter** | A trust ranking for *every* commentator, not just Jaromelu — answering "who actually reads the game?" |
| 3 | **A show worth following** | A watchable production — a crew working in public, an episode arc, a voice. |
| 4 | **Skin in the game** | The audience reacts, challenges, and gets graded too. They're in the show. |
| 5 | **Public stakes** | Every call is public, locked, and graded against reality. No retconning. |

---

## How Each Pillar Is Delivered

Each pillar maps to specific surfaces, crew members, and mechanisms.

### 1. Compression

**Mechanism:**
- **Scout** ingests the NRL media ecosystem (YouTube first — podcasts, panels, post-match shows). ([Scout architecture](../agents/crew/scout.md))
- **Analyst** cross-references claims, finds contradictions, surfaces consensus shifts. ([Analyst](../agents/crew/analyst.md))
- **Remarks** are the compressed output — opinionated, voiced positions Jaromelu puts his name on. ([Remarks](../concepts/02-remarks.md))

**Customer experience:**
- "12 podcast hours compressed into 4 Remarks" — but the compression is *visible*, not hidden. (See [Show the Work](../concepts/00-design-principles.md#show-the-work).)
- The Feed surfaces both the raw intake (crew activity) and the distilled output (Remarks).

### 2. Truth filter

**Mechanism:**
- **The Alignment Index** scores *every* commentator Scout ingests, not just Jaromelu. ([Experience Architecture §The Alignment Index](03-experience-architecture.md#the-alignment-index))
- **Speaker diarisation** attributes claims to people, not just shows — so accuracy can be sliced by individual commentator and by topic (tipping, narrative, fantasy, injuries, drama).
- **The Wiki** maintains per-commentator pages with track records. ([pages/wiki](../pages/wiki/overview.md))
- **Head-to-head framing** — "I'm beating *[commentator]* on injury calls this season."

**Customer experience:**
- The site has authority *beyond* Jaromelu's own performance. Even on a bad week, the Index is still useful.
- Answers a question no other site answers cleanly: "Which podcasters and pundits should I actually listen to?"

### 3. A show worth following

**Mechanism:**
- **The Crew as characters** — Scout, Analyst, Critic, Bookkeeper, Archivist, Jaromelu. Visible, differentiated roles. ([Crew Presence](../concepts/05-crew-presence.md))
- **The Episode Arc** — Mon (intel) → Tue–Wed (tension) → Thu (the call) → Thu–Sun (the match) → Mon (the reckoning). ([Episode Beats](../concepts/03-episode-beats.md))
- **Voice everywhere** — no system copy. Loading states, empty states, errors all speak in character. ([Design Principles §Voice Everywhere](../concepts/00-design-principles.md#voice-everywhere))
- **The rhythm is the UI** — the Stream looks different on Monday than on Thursday.

**Customer experience:**
- You don't land on a homepage. You arrive mid-episode, with the crew already working.
- You learn the rhythm: when to check in for new intel, when the call drops, when to come back for receipts.
- The site feels like a broadcast, not a dashboard.

### 4. Skin in the game

**Mechanism:**
- **Reactions** — agree / disagree on every open Remark. ([Audience §Reactions](../concepts/06-audience.md#reactions))
- **Challenges** — ask Jaromelu directly about a call. He responds in character.
- **Personal Alignment Index** — every customer accumulates their own accuracy record.
- **Crowd moments** — Jaromelu references the crowd in vindication, collective miss, and contrarian-was-right beats.

**Customer experience:**
- The customer is in the show, not watching it. Their reactions are part of the record.
- Reasons to return that don't depend on Jaromelu being right: "How am *I* tracking?"

(Squad submission is part of the SC spoke — see [Venture Thesis §Core and Spokes](01-venture-thesis.md#core-and-spokes).)

### 5. Public stakes

**Mechanism:**
- **Remark lifecycle**: `OPEN → LOCKED → RESOLVED`. Once locked, a call cannot be edited.
- **The Ledger** ([pages/ledger](../pages/ledger/overview.md)) tracks every Remark to resolution and grades it.
- **Receipt cards** are generated for resolved Remarks — purpose-built shareable content.
- **Jaromelu owns misses publicly** — the voice references past calls, including the wrong ones. ([Jaromelu](../agents/crew/jaromelu.md))

**Customer experience:**
- An open Remark is a prediction the customer can agree or disagree with.
- A resolved Remark is a receipt the customer can share.
- The customer trusts Jaromelu more *because* the misses are visible, not despite it.

---

## How We Know It's Working

Each pillar has a leading signal (early, behavioural) and a lagging signal (durable, outcome-based). Vanity metrics — page views, session count alone — don't appear here.

| Pillar | Leading signal | Lagging signal |
|--------|---------------|----------------|
| **Compression** | Time-to-first-Remark per session under 30s. Ratio of sources ingested → Remarks published per round. | Customer can articulate the week's consensus after one visit (qual). Returning users skip directly to the Feed, not to source links. |
| **Truth filter** | Number of commentator sources tracked with stable Alignment scores (>10 graded predictions). | Inbound search/social traffic for commentator names lands on Jaromelu's Wiki pages. The Index gets cited externally. |
| **A show worth following** | Return rate concentrated at episode beats (Monday and Thursday peaks visible in traffic). Session depth on Thursdays (The Call beat). | Customers refer to Jaromelu by name in inbound traffic / share copy. The crew is named (Scout, Analyst) in user language unprompted. |
| **Skin in the game** | Reaction rate per open Remark (% of viewers who tap agree/disagree). Challenge volume per Remark. | Distribution of personal Alignment Index scores tightens over a season — engaged users improve. Cohort returning to check their own record weekly. |
| **Public stakes** | % of Remarks that resolve on schedule (no orphaned calls). Receipt-card share count per resolved Remark. | Jaromelu's Alignment Index trends upward across a season. Customer trust signal: agree/disagree ratio shifts toward agreement on high-conviction calls over time. |

These are the questions we ask in product review, not the questions we ask in marketing.

---

## What This Is *Not*

To stay honest about scope, the promise excludes:

- **A stats site.** Raw data is not the value. Compressed, voiced opinion is.
- **A neutral aggregator.** Jaromelu has a position on every call. Neutral summaries are explicitly disallowed.
- **A SuperCoach optimiser tool.** Even when the SC spoke ships, we are not solving the optimisation problem. We are entertaining the customer who already has tools and wants synthesis. (See [Venture Thesis §Why A Crew Of Characters, Not A Tool](01-venture-thesis.md#why-a-crew-of-characters-not-a-tool).)
- **A casual NRL site.** The audience is hardcore NRL fans who consume heavy amounts of commentary. Casual viewers are not the target.
- **A chatbot.** Ask Me exists, but it's a contextual surface, not the product. The product is the Feed and the show.

If a proposed feature conflicts with this list, the feature is wrong — not the list.

---

## Related

- [Venture Thesis](01-venture-thesis.md) — strategic frame: who the customer is, the bet, the core-and-spokes model.
- [Experience Architecture](03-experience-architecture.md) — full breakdown of crew, surfaces, and the episode arc.
- [Design Principles](../concepts/00-design-principles.md) — the visual and editorial rules that make a show worth following.
- [V1 Scope & Roadmap](09-v1-scope-and-roadmap.md) — what we ship first against this promise.
- [Explainability & Governance](08-explainability-and-governance.md) — how the receipts stay honest.

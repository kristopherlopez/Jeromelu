---
tags: [area/architecture]
status: draft
---

# What We Promise (Draft — split from `02-value-and-delivery.md`)

> Draft created 2026-05-09. Splits the customer-facing half of `02-value-and-delivery.md` into a clean sequel to the customer-centered 01 draft. Delivery mechanics ("How Each Pillar Is Delivered") proposed to move to `03-experience-architecture.md`. Signals ("How We Know It's Working") proposed to move to `08-explainability-and-governance.md` (or a new operations doc).

---

# What We Promise

> Draft. Last reviewed: 2026-05-10.

01 says who the customer is, what they're frustrated with, and what they'd want. This doc says what we owe them in return — the contract Jaromelu makes with the audience. 03 is where each promise gets delivered.

---

## The Promise

> **"Help me quickly understand what the NRL world is thinking — and entertain me while doing it."**

The customer is hardcore. Time-poor, opinion-saturated, decision-fatigued. They don't need more content. They need three things, and we promise all three:

1. **Compression** — the ecosystem distilled into a few sharp positions.
2. **Conviction** — somebody willing to put their name on a call and live with it.
3. **Spectacle** — a reason to come back that isn't a chore.

Everything we build serves these three. If a feature doesn't strengthen at least one, it doesn't ship.

---

## The Five Promises

Each is a job we take on for the customer. They map directly back to what they're frustrated with today.

| # | Promise | Customer pain it answers | What we owe |
|---|---------|--------------------------|-------------|
| 1 | **Compression** | 12+ hours of commentary per round; always behind. | The week's noise collapsed into a small number of opinionated calls — visible compression, not hidden synthesis. |
| 2 | **Truth filter** | Conflicting takes; nobody held accountable. | A trust ranking for *every* commentator, sliced by what they're actually good at. Not just Jaromelu. |
| 3 | **A show worth following** | Hot takes are cheap; nothing worth returning to. | A watchable production — a host with a voice, a crew working in public, an episode arc, not a dashboard. |
| 4 | **Skin in the game** | Spectator-only; nothing personal to track. | The customer is graded alongside Jaromelu — their reactions become part of the record, their accuracy becomes their own. |
| 5 | **Public stakes** | Pundits never get held to their calls. | Every Jaromelu call is public, locked, and resolved against reality. No retconning. Misses owned. |

### Compression

**The week's NRL noise — twelve-plus hours of audio across the major channels — collapsed into a small number of opinionated calls the customer can absorb in 90 seconds.** The compression is *visible*, not hidden: the customer sees what was ingested, sees the synthesis, sees what got dropped.

Where the line is:

- We don't summarise long-form content. We replace it with calls.
- We don't hide the source material. The customer can always trace a call back to the audio it came from.
- We don't compress neutrally. Every output is voiced and opinionated.

Why this matters: the customer is drowning. Compression is the thing they need someone else to do for them — and the visibility of *how* it happened is what makes them trust the result.

### Truth filter

**An accuracy record for every commentator we ingest, not just our own host.** Sliced by what each pundit is actually good at — tipping, narrative reads, fantasy, injuries — so the customer knows who to weight on what.

Where the line is:

- Rankings come from graded calls, not from our judgement of tone or personality.
- A commentator needs sample size before their score becomes load-bearing — single-round verdicts don't count.
- We rank speakers, not shows. A panellist who's right on injuries can be wrong on tipping; the index reflects that.

Why this matters: today the customer can't tell whose conviction is earned and whose is fluff. The truth filter answers a question no other NRL site answers cleanly — *"who should I actually listen to?"*

### A show worth following

**A watchable production — a host with a voice, a crew working in public, an episode arc — not a dashboard you visit and leave.** The crew aren't infrastructure; they're characters. The week has a rhythm. Every line of copy speaks in character.

Where the line is:

- No generic UI copy. No "Sorry, something went wrong." Every surface speaks in voice.
- No push-notifications-as-product — the rhythm of the week is the return mechanism.
- No polished avatar in V1. Text-led, with voice for set-piece moments. The avatar layer slots in when the medium can sustain it.

Why this matters: the customer already has access to plenty of NRL information. They come back for a show, not a data product.

### Skin in the game

**The customer is graded alongside Jaromelu.** Their reactions on open Remarks become part of the record. Their direct challenges to Jaromelu get answered in character. Their own track record — the Personal Alignment Index — accumulates over the season the same way Jaromelu's does.

Where the line is:

- The customer is graded against *reality*, not against a leaderboard of other users.
- Anonymous lurking is fine, but it earns no record. Participation is opt-in but consequential when chosen.
- Their score uses the same rubric as Jaromelu's. No softer curve for being human.

Why this matters: the customer becomes a participant rather than a viewer. Reasons to return that don't depend on Jaromelu being right — *"how am I doing this season?"* works either way.

### Public stakes

**Every call is public, locked, and resolved against reality. No retconning.** Open Remarks accept the audience's reactions. Locked Remarks are frozen — no edits. Resolved Remarks become permanent receipts, whether right or wrong.

Where the line is:

- Misses are not removed or hidden. They surface in Jaromelu's own voice, alongside the wins.
- No soft-grading. A call is right, wrong, or partially right against a clear rubric — never "well, technically…"
- Once locked, a Remark cannot be edited even if Jaromelu changes his mind. The new view becomes a new Remark.

Why this matters: in a category where pundits face no consequence for being wrong, public stakes is the trust mechanism. The customer trusts Jaromelu *because* the misses are visible — not despite it.

---

## What This Is Not

To stay honest about scope, the promise excludes:

- **A stats site.** Raw data is not the value. Compressed, voiced opinion is.
- **A neutral aggregator.** Jaromelu has a position on every call. Neutral summaries are explicitly disallowed.
- **A SuperCoach optimiser tool.** Even when the SuperCoach extension ships, we are not solving the optimisation problem. We are entertaining the customer who already has tools and wants synthesis.
- **A casual NRL site.** The audience is hardcore NRL fans who consume heavy amounts of commentary. Casual viewers are not the target.
- **A chatbot.** Ask Me exists, but it's a contextual surface, not the product. The product is the Feed and the show.

If a proposed feature conflicts with this list, the feature is wrong — not the list.

---

## Related

- [Venture Thesis (draft)](01-venture-thesis.draft.md) — who the customer is and what they want
- [Experience Architecture](../03-experience-architecture.md) — how each promise gets delivered (crew, surfaces, episode arc)
- [Explainability & Governance](../08-explainability-and-governance.md) — how the receipts stay honest *(signals proposed to land here)*
- [Design Principles](../../concepts/00-design-principles.md) — the editorial rules the show runs on

---

## Drafting notes (delete before merge)

**Source:** `02-value-and-delivery.md` (current). This draft retains:

- **The Promise** (3-need intro: Compression, Conviction, Spectacle).
- **The Five Value Pillars**, rewritten as **The Five Promises**, with a "Customer pain it answers" column added to anchor each promise back to 01's "What They're Frustrated With Today." Each promise is then unpacked into its own H3 section with: the promise restated, where the line is (what we won't do), and why it matters to the customer. Mechanism details (how it gets delivered) are deliberately absent — they live in `03`.
- **What This Is Not**.

**What was cut and where it's proposed to go:**

- **How Each Pillar Is Delivered** (mechanism per pillar — Scout/Analyst/Remarks/Wiki/etc.) → move to `03-experience-architecture.md`. That doc already covers crew/surfaces/episode arc; pillar-to-mechanism mapping belongs with it.
- **How We Know It's Working** (leading/lagging signals table) → move to `08-explainability-and-governance.md`, or a new `08-operating-signals.md` if 08 gets crowded. Internal-facing metrics, not customer-facing promise.

**Framing changes vs source:**

- Title: "Value & Delivery" → "What We Promise" — matches 01's customer-question heading style.
- Pillar heading: "The Five Value Pillars" → "The Five Promises" — same content, framed as commitments rather than features.
- Pillar table: added "Customer pain it answers" column to tie each promise back to 01's pain section. The original "What the customer gets" column collapsed into "What we owe."
- Removed the doc-positioning preamble ("This doc sits between the Venture Thesis…"). Replaced with a tighter handoff: 01 → 02 → 03.

**Open question — pillar #4 ("Skin in the game"):**

Overlaps heavily with 01's "What They Do Here." Two options:

1. **Keep in both.** 01 frames it as customer behaviour ("they react, they challenge, they get graded"). 02 frames it as our commitment ("we will grade you alongside Jaromelu"). Different angles — customer action vs. our promise.
2. **Drop from 02.** Already covered upstream. The pillar set goes from 5 to 4.

Recommendation: option 1. The framing distinction is real, and dropping the pillar would make the promise list lopsided — four customer-facing promises and a hole where customer participation should sit.

**Open question — sequencing note:**

The current 01 used to carry a sequencing note ("build Compression and Truth Filter first…") that referred to the value pillars. That note got dropped when 01 trimmed the value-prop section. It might belong here in 02 as a "what we deliver first" line, or in `09-v1-scope-and-roadmap.md`. Worth deciding before merge.

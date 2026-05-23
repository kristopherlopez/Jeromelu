---
tags: [area/architecture]
status: draft
---

# The Show (Draft — experience-led reframe of `03-experience-architecture.md`)

> Draft created 2026-05-10. Reframes existing 03 around the customer experience and absorbs sections proposed to move from old 01 (already partially in current 03) and old 02 (pillar-to-mechanism mapping, currently absent). Trims technical "Maps to" references that belong in deeper architecture docs.

---

# The Show

> Draft. Last reviewed: 2026-05-10.

01 says what Jaromelu is and why. This doc says how the show actually works — the crew the audience watches, the rhythm of the week, the surfaces they land on, and the way they get pulled in. The knowledge that powers it all gets [its own doc](03-knowledge-asset.draft.md); the lines we deliberately won't cross are at the end of this one.

---

## The Core Experience

Watch an AI crew break down the NRL week, make public calls, and get held accountable — live, every round.

This is not a stats site with an AI label. It's a **show**. Visitors watch an intelligence operation unfold in public — agents gathering intel, cross-referencing sources, resolving contradictions, and committing to calls that get judged by real outcomes.

The experience should feel like following a newsroom with a glass wall. You see the work happening. You see the moment the call gets made. You come back to see if it landed.

### The Design Principle

Every surface answers one question: **"What is the crew working on right now, and what is Jaromelu about to call?"**

Data is never presented raw. It flows through a visible process — gathered by Scout, analysed by Analyst, called by Jaromelu — and arrives as a **Remark**: an opinionated, voiced position with Jaromelu's name on it.

---

## Why It's A Crew, Not A Tool

A solo agent answering questions feels like a chatbot. A crew working in public — Scout pulling intel, Analyst cross-referencing, Critic challenging, Bookkeeper tracking, Archivist remembering, Jaromelu putting his name on the call — feels like a **production**.

| A character | A tool |
|---|---|
| Has personality | Has features |
| Makes calls feel dramatic | Returns results |
| Encourages sharing | Encourages bookmarking |
| Can be wrong publicly and own it | Just stays accurate |
| Builds a following | Builds a userbase |

Tools feel useful. Characters feel followable.

To be precise: **Jaromelu** is the character — the one with personality, a voice, a following. The crew aren't five more characters; they're his visible workforce. What makes this a production rather than a chatbot isn't that the crew have personalities — it's that you can *watch them work* on his behalf. Single voice, visible labour.

The crew makes the process *legible* and the show *watchable*. Each role creates anticipation for the next:

- Scout is busy → new intel incoming
- Analyst found a contradiction → tension building
- Jaromelu is making his call → the moment of commitment

That's what makes it a show — not the data, the rhythm of the work.

---

## The Crew

Six roles. Each does something the customer can see.

> **Note on voice.** The crew has *visible activity* — status lines, indicators, work that surfaces in the Feed — but only Jaromelu has *personality*. Scout, Analyst, Critic, Bookkeeper, and Archivist report in clean, functional voice. Jaromelu is the host. He's the one who makes calls and owns them.

### Scout — the intelligence gatherer

Scans the NRL podcast and media ecosystem for new takes, data, and narratives.

**What the customer sees:**

- *"Scout picked up 4 new episodes overnight"*
- *"Scout flagged 3 new takes on Cleary from this week's pods"*
- *"Scanning the ecosystem... 2 new sources found"*

Detail: [agents/crew/scout.md](../../agents/crew/scout.md).

### Analyst — the knowledge resolver

Cross-references claims across sources, finds contradictions, detects consensus shifts, builds the evidence base.

**What the customer sees:**

- *"Analyst is cross-referencing — 2 sources agree on Munster, 1 contradicts"*
- *"Consensus just shifted: the market is turning bearish on Cleary"*
- *"Analyst found a contradiction: KingOfSC says buy, NRLBrothers says sell"*

Detail: [agents/crew/analyst.md](../../agents/crew/analyst.md).

### Critic — the challenger

Pushes back on Jaromelu's draft calls. The internal devil's advocate that stops the show from getting cocky.

**What the customer sees:**

- *"Critic is poking holes in the Cleary call"*
- *"Critic flagged: this contradicts what Jaromelu said two weeks ago"*

### Bookkeeper — the scorekeeper

Tracks every prediction — Jaromelu's and every commentator's — through the Open → Locked → Resolved lifecycle, and grades them against reality.

**What the customer sees:**

- *"Bookkeeper resolved 4 Remarks from last round — 3/4 hit"*
- *"Bookkeeper flagged: this matches an open prediction from KingOfSC"*

### Archivist — the memory

Maintains the Wiki — per-player, per-team, per-commentator pages — so nothing the crew learns goes missing. Continuity is their job.

**What the customer sees:**

- *"Archivist updated Cleary's page with last round's view"*
- *"Archivist linked this Remark to Jaromelu's earlier call from Round 3"*

### Jaromelu — the front man

Reviews the crew's work, makes the call, puts his name on it publicly. The voice. The personality. The one with skin in the game.

**What the customer sees:**

- *"Jaromelu is reviewing the evidence..."*
- *"The call is in: selling Cleary this week. Here's why."*
- *"Jaromelu disagrees with consensus. Going contrarian on Munster."*

Detail: [agents/crew/jaromelu.md](../../agents/crew/jaromelu.md).

---

## The Episode Arc

The week isn't a flat timeline. It's an **episode** with narrative structure — buildup, commitment, stakes, accountability. Every week is self-contained. Every week has tension that resolves.

| Beat | Day | What's Happening | Feel |
|------|-----|------------------|------|
| **Intel Drops** | Monday | Scout surfaces new takes from the weekend's pods and media. *"The pods are in. Let's see what they're saying."* | Discovery. The raw material arrives. |
| **Tension Builds** | Tue–Wed | Analyst cross-references. Sources disagree. Contradictions surface. Critic is challenging the draft calls. *"Three sources selling Cleary. One buying hard. Something's off."* | Suspense. The picture is incomplete. |
| **The Call** | Thursday | Jaromelu locks in his Remarks. *"Here's where I stand. Judge me."* | Commitment. Public, irreversible. |
| **The Match** | Sat–Sun | Results come in. Predictions resolve live. The audience watches alongside Jaromelu. | Stakes. Real consequences. |
| **The Reckoning** | Monday | Bookkeeper resolves. Receipts. Alignment Index updates. *"I said it publicly. Here's how it landed."* | Accountability. The loop closes. |

The arc creates natural return triggers without push notifications. The customer learns when to check in:

- Monday morning: *what did Scout find?*
- Wednesday: *where is Analyst stuck?*
- Thursday: *what did Jaromelu call?*
- Monday: *was he right?*

---

## Remarks — The Atomic Unit

A **Remark** is everything the crew does, condensed. Every flow ends in Remarks. Every customer interaction starts from one.

A Remark is **not**:

- A raw data point (*"Cleary scored 85"*)
- A system log (*"Ingestion complete"*)
- A neutral summary (*"Sources are divided on Cleary"*)

A Remark **is**:

- *"Cleary is overpriced this week. Three sources sold, one bought. I'm selling. Here's the matchup case."*
- *"Munster's floor is higher than people think. Everyone's scared of the bye. I'm not."*
- *"That Munster call aged badly. Variance. The process was sound."*

### Lifecycle

```
OPEN → LOCKED → RESOLVED
```

1. **Open** — Jaromelu states a position. Live and unresolved. The audience reacts.
2. **Locked** — The round begins. No edits. The call is on the record.
3. **Resolved** — Outcomes arrive. The Remark is graded. Receipts generated.

Open Remarks are predictions you can agree or disagree with. Resolved Remarks are receipts you can share.

### What's In A Remark

| Field | Purpose |
|-------|---------|
| Voice text | The Remark in Jaromelu's words |
| Subject entities | Players, teams, or matchups referenced |
| Position | Buy / sell / hold / captain / avoid |
| Conviction | Low / medium / high |
| Evidence trail | Links to claims, sources, and crew activity that built it |
| Status | Open / locked / resolved |
| Resolution | Outcome data once resolved |

---

## The Surfaces

Five pages. Each one earns the right to exist by doing something the Feed alone can't.

### 1. The Feed — `/`

The spine. A live, rewindable view of the crew at work and the Remarks they produce.

The Feed shows three layers, interleaved:

**Crew Activity** — the visible process. Scout discovering, Analyst cross-referencing, Critic challenging, Bookkeeper resolving. Progress indicators with crew attribution.

**Remarks** — the output. Jaromelu's calls, displayed prominently with conviction level. Open Remarks with reaction counts. Resolved Remarks with receipts.

**Audience Interaction** — the participation. Reactions on open Remarks. Questions directed at Jaromelu. His responses in character.

The Feed is *not a log*. Crew activity is shown as supporting context for Remarks. System events without narrative value are suppressed. Every entry either builds toward a Remark or resolves one.

### 2. The Wiki — `/wiki`

Prose-dominant, agent-maintained knowledge base. Per-entity pages written and continuously updated by the Archivist on Jaromelu's behalf.

Pages exist for:

- **Players** — current stance, form, expert opinions, injury, SuperCoach verdict
- **Teams** — roster, form, fixtures, narratives
- **Commentators** — accuracy track record, recent takes, trust rating, how often Jaromelu agrees
- **Rounds** — preview → recap, key narratives

Every page links back to the Remarks, crew activity, and source chunks that informed the view. Lineage is visible.

The feel is **editorial**, not dashboard — warm parchment, serif typography. A reading surface that breaks deliberately from the dark broadcast stage of the Feed.

Detail: [pages/wiki/](../../pages/wiki/overview.md).

### 3. The Ledger — `/ledger`

Prediction tracking and accountability. Every call lives here with resolution status and score.

Core concerns:

- The Open → Locked → Resolved lifecycle, visualised
- The Alignment Index for Jaromelu and every tracked commentator
- Rolling accuracy by domain (tipping / narrative / fantasy / injuries)
- Shareable receipt cards for bold calls

Detail: [pages/ledger/](../../pages/ledger/overview.md).

### 4. The Analysis — `/insights`

Editorial content hub. Each round, Jaromelu publishes opinionated analytical articles — round tips, team of the week, trade targets, captain picks, podcast consensus.

Framing: *"Here's what I'm thinking this round, in full."* Long-form to complement the Feed's live cadence.

Detail: [pages/analysis/](../../pages/analysis/overview.md).

### 5. Ask Me — `/ask`

Chat. Customers ask Jaromelu about strategy, players, or his own calls. Answers are RAG-retrieved from the Knowledge Base and rendered in Jaromelu's voice.

Available standalone (`/ask`) and embedded in the Feed as Twitch-style chat — same backend, different surface.

Detail: [pages/ask-me/](../../pages/ask-me/overview.md).

---

## The Alignment Index

Answers the question: **"Who actually reads the game well?"**

Tracks prediction accuracy not just for Jaromelu but for **every commentator** the crew monitors. This creates a dimension beyond *"is Jaromelu right?"* — it becomes *"who in the NRL ecosystem is most aligned with reality?"*

### How It Works

1. Claims are extracted from every source Scout ingests
2. Claims that constitute predictions are identified and tracked by Bookkeeper
3. Outcomes are matched against predictions when results arrive
4. Alignment scores are computed — how often each source's calls match reality

### What The Customer Sees

- **Expert leaderboard** — ranked by alignment score, updated weekly
- **Jaromelu's position** — where he sits relative to the commentators he's monitoring
- **Head-to-head** — *"I'm beating KingOfSC on captain picks this season"*
- **Consensus accuracy** — when everyone agrees, how often is the consensus right?
- **Contrarian value** — when Jaromelu goes against consensus, how often does it pay off?

### Why It Matters

The site has authority *beyond* Jaromelu's own performance. Even on a bad week, the Index is still useful — it's a trust ranking for the whole NRL commentary ecosystem. It answers a question no other NRL property answers cleanly: *"who should I actually listen to?"*

### The Customer In The Index

Customers who react to Remarks accumulate their own alignment score — the **Personal Alignment Index**:

- *"You vs Jaromelu"* comparison
- *"Your accuracy this season"* as a personal stat
- Leaderboard participation for engaged customers

---

## How The Audience Plays

The customer is in the show — a participant with skin in the game, not an audience member with a remote. The surfaces below are how that actually appears on screen.

### Reactions On Remarks

Before a Remark resolves, the audience can weigh in:

- **Agree / Disagree** — simple binary, creates crowd sentiment
- These contribute to the customer's Personal Alignment Index

When a Remark resolves, Jaromelu can reference the crowd:

- *"68% of you disagreed with my Munster call. Receipts."*
- *"The crowd was with me on this one. We all saw it."*

### Challenging Jaromelu

Customers ask Jaromelu about specific Remarks directly in the Feed:

- *"Why are you selling Cleary?"*
- *"Your Munster call looks shaky after that injury report"*

Jaromelu responds in character, referencing the crew's evidence.

### Squad Submission *(SuperCoach extension)*

Customers can submit their own squads for Jaromelu to review:

- *"Here's my squad. Roast me."*
- Jaromelu responds in character with a temperature control (straight / sharp / roast)

This is part of the SuperCoach extension, not V1.

### Shareable Receipts

Bold calls that resolve create receipt cards — shareable images or links:

- *"Jaromelu called Munster over Cleary in Round 6. He was right."*
- *"Jaromelu went 4/5 on captain picks this month."*

These are the viral moments. Correct bold calls and spectacular misses owned with humour.

---

## Agent Presence

### Crew Status

The site always communicates what the crew is doing *right now*. A persistent status indicator shows crew activity:

- *"Scout is scanning new episodes..."* (ingestion)
- *"Analyst is cross-referencing Round 5 claims..."* (extraction)
- *"Jaromelu is reviewing the evidence..."* (decision in progress)
- *"Squad locked. Watching the market."* (idle but attentive)
- *"The Reckoning: reviewing Round 5 outcomes..."* (post-round review)

Subtle — a status line, not a modal. But it makes the crew feel alive and creates micro-anticipation: *Analyst is working — a Remark is coming.*

### First-Person Voice

All copy on the site is written from the crew's perspective. Never neutral database language.

- Nav labels: *"The Wiki", "The Ledger", "The Analysis"* — not "Knowledge Base", "Predictions", "Articles"
- Empty states: *"Scout hasn't found anything yet. Give it time."* — not "No data available"
- Error states: *"Something broke. Even the best crews have bad days."* — not "500 Internal Server Error"
- Loading states: *"Analyst is thinking..."* — not "Loading..."

### Continuity

The strongest retention mechanic is that the crew remembers. Past Remarks, past mistakes, evolving opinions — all visible and referenced.

Jaromelu references his own history:

- *"I called Cleary overpriced three weeks ago. Still overpriced."*
- *"Last time I went against KingOfSC on a captain pick, I lost. Not this time."*

Customers return to see: did the crew find something new? Did Jaromelu change his mind? Was he right?

---

## The Seasonal Arc

Beyond the weekly episode, the season itself is a narrative:

- **Early rounds** — Jaromelu establishing his style, making bold opening calls, crew building its intelligence base
- **Mid-season** — track record forming, Alignment Index gaining meaning, rivalries with commentator sources emerging
- **Run home** — stakes increasing, every call matters more, the audience invested in the outcome
- **Finals** — season review, full accountability — *"Season X: The Verdict"*

The strongest retention mechanic is not content. It's **public continuity** — an ongoing show with real stakes that people follow like a season of television.

---

## Scope — What We Won't Build

The show is defined as much by what it refuses to be. These are the lines we hold even under pressure to relax them.

### What This Is Not

- **A stats site.** Raw data is not the value. Compressed, voiced opinion is.
- **A neutral aggregator.** Jaromelu has a position on every call. Neutral summaries are explicitly disallowed.
- **A SuperCoach optimiser tool.** Even when the SuperCoach extension ships, we are not solving the optimisation problem. We entertain the customer who already has tools and wants synthesis.
- **A casual NRL site.** The audience is hardcore NRL fans who consume heavy amounts of commentary. Casual viewers are not the target.
- **A chatbot.** Ask Me exists, but it's a contextual surface, not the product. The product is the Feed and the show.

If a proposed feature conflicts with this list, the feature is wrong — not the list.

### Where We Draw The Lines

**On compression (the output):**

- We don't summarise long-form content. We replace it with calls.
- We don't hide the source material. The customer can always trace a call back to the audio it came from.
- We don't compress neutrally. Every output is voiced and opinionated.

**On rankings (the truth filter / Alignment Index):**

- Rankings come from graded calls, not from our judgement of tone or personality.
- A commentator needs sample size before their score becomes load-bearing — single-round verdicts don't count.
- We rank speakers, not shows. A panellist who's right on injuries can be wrong on tipping; the index reflects that.

**On the show (voice & format):**

- No generic UI copy. No "Sorry, something went wrong." Every surface speaks in voice.
- No push-notifications-as-product — the rhythm of the week is the return mechanism.
- No polished avatar in V1. Text-led, with voice for set-piece moments. The avatar layer slots in when the medium can sustain it.

**On participation:**

- The customer is graded against *reality*, not against a leaderboard of other users.
- Anonymous lurking is fine, but it earns no record. Participation is opt-in but consequential when chosen.
- The customer's score uses the same rubric as Jaromelu's. No softer curve for being human.

**On accountability:**

- Misses are not removed or hidden. They surface in Jaromelu's own voice, alongside the wins.
- No soft-grading. A call is right, wrong, or partially right against a clear rubric — never "well, technically…"
- Once locked, a Remark cannot be edited even if Jaromelu changes his mind. The new view becomes a new Remark.

---

## Related

- [Venture Thesis (draft)](01-venture-thesis.draft.md) — what Jaromelu is and why
- [Knowledge Asset (draft)](03-knowledge-asset.draft.md) — the asset the crew builds and what it unlocks
- [Design Principles](../../concepts/00-design-principles.md) — visual and editorial rules
- Per-page specs in [`docs/pages/`](../../pages/)
- Per-agent specs in [`docs/agents/crew/`](../../agents/crew/)

---

## Drafting notes (delete before merge)

**Source:** `03-experience-architecture.md` (current). This draft is a customer-centered reframe — most content carried over, with these substantive changes:

**Title:** "Experience Architecture" → "The Show." The spine is now 01 (what Jaromelu is — experience-led) → 03 (the show). 02 became a Scope & Non-Goals reference, not a narrative step.

**Crew section:**

- Added **Critic, Bookkeeper, Archivist** — referenced in 01 source but never detailed in current 03. Each gets a one-line role and *"What the customer sees"* examples.
- Added an explicit **note on voice**: the crew has visible activity, but only Jaromelu has personality. Scout/Analyst/Critic/Bookkeeper/Archivist all report in clean functional voice. This reconciles with the project's settled framing — *single voice, visible labour*: the crew compose into Jaromelu's one voice, but their work is shown as the spectacle.
- Removed **"Maps to: …"** technical lines from each agent. Those belong in deeper architecture docs (`05-runtime-architecture`, per-agent specs), not in the customer-facing show doc.

**Pillar-to-mechanism mapping:** Added a new "How Each Promise Gets Delivered" section at the end — the content proposed to move from old 02's "How Each Pillar Is Delivered." Compressed from per-pillar prose into a single mapping table. Per-promise depth lives in 02; per-mechanism depth lives throughout 03.

**Sequencing:** The reading flow is now 01 → 03 (02 is a side reference, not a step). Participation lives entirely here in 03 ("How The Audience Plays" + "The Customer In The Index"); 01 no longer carries a "What They Do Here" section, so back-references to it were removed.

**Realignment (2026-05-23).** After 01 flipped to experience-led and 02 collapsed to Scope & Non-Goals, this draft was realigned: rewrote the opening handoff (dropped "02 says what we owe them"); removed the orphaned "How Each Promise Gets Delivered" section (its premise — the five promises in 02 — no longer exists); fixed two now-dead cross-references to 01 (PAI is introduced here now, not in 01; the "What They Do Here" back-ref removed); and resolved the crew-personality contradiction in "Why It's A Crew, Not A Tool" — Jaromelu is the character, the crew are his visible workforce (single voice, visible labour). Body content otherwise unchanged; the doc was already spiritually aligned with experience-led 01.

**Renumber + scope fold (2026-05-23).** New spine: **01 thesis → 02 the show → 03 knowledge asset.** This doc moves into the 02 slot (file to be renamed `02-the-show.draft.md`). The former `02-what-we-promise` (Scope & Non-Goals) was dissolved; its content folded in here as the closing "Scope — What We Won't Build" section. Knowledge-asset detail moved to its own new 03.

**What got tightened or dropped:**

- "What Got Absorbed" table dropped (page-set churn history isn't customer-facing; belongs in a project-history note if anywhere).
- "UI/UX Specifications" pointer trimmed — Related links section at the bottom covers it.
- 2026-04-17 status note from current 03 is no longer needed: the consolidated five-page surface set is now the body content, not a retrofit.
- Some prose tightened throughout but core content preserved.

**Pending decisions:**

- Whether to keep the Crew section inline in 03 or split into its own `04-the-crew.md`. This draft keeps it inline (no separate doc needed since per-agent docs already exist under `docs/agents/crew/`).
- Where the Seasonal Arc should live — could move to `09-v1-scope-and-roadmap.md` if 03 gets long. Kept here for now since it ties tightly to the rhythm material.
- The Critic / Bookkeeper / Archivist role descriptions are my best read from 01 + memory; worth verifying against any per-agent docs that may already exist (or flagging as gaps to fill).

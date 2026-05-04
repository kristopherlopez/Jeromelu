---
tags: [area/architecture]
---

# Experience Architecture

> **Status note (2026-04-17):** The live app has consolidated to five canonical pages — **The Feed** (`/`), **The Wiki** (`/wiki`), **The Ledger** (`/ledger`), **The Analysis** (`/insights`), **Ask Me** (`/ask`). This doc pre-dates that consolidation. Where it references **"My Squad"**, the concept was retired in favour of [The Analysis](../pages/analysis/overview.md) as an editorial hub. Where it references **"The Dossier"**, that role now lives in [The Wiki](../pages/wiki/overview.md) — per-entity pages written and maintained by Jaromelu. The narrative and design principles below still apply; only the page names have shifted.

## Core Experience

Watch an AI crew break down the NRL week, make public calls, and get held accountable — live, every round.

This is not a stats site with an AI label. It is a **show**. Visitors watch an intelligence operation unfold in public — agents gathering intel, cross-referencing sources, resolving contradictions, and committing to calls that get judged by real outcomes.

The experience should feel like following a newsroom with a glass wall. You see the work happening. You see the moment the call gets made. You come back to see if it landed.

### Design Principle

Every surface answers the question: **"What is the crew working on right now, and what is Jaromelu about to call?"**

Data is never presented raw. It flows through a visible process — gathered by Scout, analysed by Analyst, called by Jaromelu — and arrives as a **Remark**: an opinionated, voiced position that Jaromelu puts his name on.

---

## The Crew

The system is powered by multiple agents, but the audience experiences them as **characters with roles**. The crew makes the process legible and the show watchable.

### Scout

**Role:** Intelligence gatherer. Scans the NRL podcast and media ecosystem for new takes, data, and narratives.

**What the audience sees:**
- "Scout picked up 4 new episodes overnight"
- "Scout flagged 3 new takes on Cleary from this week's pods"
- "Scanning the ecosystem... 2 new sources found"

**Voice:** Efficient, factual, no opinion. Scout reports what's out there without editorialising.

**Maps to:** Scout module in the api container — discovery loop (`app/scout/loop.py`), enumeration / refresh (`app/scout/refresh.py`), and audio acquisition (`app/scout/audio.py`). The legacy Temporal `IntelSweepWorkflow` under `services/worker-ingestion/` is superseded. Transcription itself is Analyst's responsibility (`app/analyst/transcribe.py` + Deepgram) — see [extraction-method.md](../sources/extraction-method.md).

### Analyst

**Role:** Knowledge resolver. Cross-references claims across sources, finds contradictions, detects consensus shifts, and builds the evidence base.

**What the audience sees:**
- "Analyst is cross-referencing — 2 sources agree on Munster, 1 contradicts"
- "Consensus just shifted: the market is turning bearish on Cleary"
- "Analyst found a contradiction: KingOfSC says buy, NRLBrothers says sell"

**Voice:** Precise, measured, presents both sides. Analyst surfaces the tension without resolving it.

**Maps to:** Analyst module in the api container — transcription (`app/analyst/transcribe.py`, Deepgram-driven diarisation + chunking), plus the cleaning / claim extraction / consensus surfaces (skill-driven today, workerised version pending). See [analyst.md](../agents/crew/analyst.md).

### Jaromelu

**Role:** The front man. Reviews the crew's work, makes the call, puts his name on it publicly.

**What the audience sees:**
- "Jaromelu is reviewing the evidence..."
- "The call is in: selling Cleary this week. Here's why."
- "Jaromelu disagrees with consensus. Going contrarian on Munster."

**Voice:** Confident, opinionated, dry, self-aware. Jaromelu is the character defined in [agents/crew/jaromelu.md](../agents/crew/jaromelu.md) — a cocky operator who is right just often enough.

**Maps to:** Decision engine and characterisation layer (strategy generation, voice application, final output).

### Why a Crew, Not a Solo Agent

A solo agent doing everything feels like a chatbot. A crew doing visible, differentiated work feels like a **production**. The audience learns the rhythm:
- Scout is busy → new intel incoming
- Analyst found a contradiction → tension building
- Jaromelu is making his call → the moment of commitment

Each role creates anticipation for the next. That's what makes it a show.

---

## The Episode Arc

The week is not a flat timeline. It is an **episode** with a narrative structure — buildup, commitment, stakes, and accountability. Every week is self-contained. Every week has tension that resolves.

| Beat | Day | What's Happening | Feel |
|------|-----|------------------|------|
| **Intel Drops** | Monday | Scout surfaces new takes from the weekend's pods and media. "The pods are in. Let's see what they're saying." | Discovery. The raw material arrives. |
| **Tension Builds** | Tue–Wed | Analyst cross-references. Sources disagree. Contradictions surface. Open threads form. "Three sources selling Cleary. One buying hard. Something's off." | Suspense. The picture is incomplete. |
| **The Call** | Thursday | Jaromelu locks in his Remarks. Squad set. Captain picked. Trades executed. "Here's where I stand. Judge me." | Commitment. Public, irreversible. |
| **The Match** | Sat–Sun | Results come in. Predictions resolve live. The audience watches alongside Jaromelu. | Stakes. Real consequences. |
| **The Reckoning** | Monday | Postmortem. Receipts. Alignment Index updates. "I said it publicly. Here's how it landed." | Accountability. The loop closes. |

### Why the Arc Matters

Without structure, the Feed is just a timeline you scroll. With the arc, it's a **story you follow**. Users learn when to check in:
- Monday morning: what did Scout find?
- Wednesday: where is Analyst stuck?
- Thursday: what did Jaromelu call?
- Monday: was he right?

The weekly arc creates natural return triggers without needing push notifications (though those help — see Audience Participation).

---

## Remarks

A **Remark** is the atomic unit of the entire experience. Everything the crew does leads to Remarks. Everything the audience interacts with is a Remark.

### What Is a Remark

A Remark is an opinionated, voiced analytical piece that Jaromelu puts his name on. It is built from the crew's resolved knowledge — claims cross-referenced, contradictions resolved, evidence weighed — and delivered in Jaromelu's voice.

A Remark is **not**:
- A raw data point ("Cleary scored 85")
- A system log ("Ingestion complete")
- A neutral summary ("Sources are divided on Cleary")

A Remark **is**:
- "Cleary is overpriced this week. Three sources sold, one bought. I'm selling. Here's the matchup case."
- "Munster's floor is higher than people think. Everyone's scared of the bye. I'm not."
- "Calling it now: Hynes outscores Cleary in Round 6. Book it."
- "That Munster call aged badly. Variance. The process was sound."

### Remark Lifecycle

Every Remark has a lifecycle that creates tension and resolution:

```
OPEN → LOCKED → RESOLVED
```

1. **Open** — Jaromelu states a position. It's a live, unresolved call. The audience can react.
2. **Locked** — The round begins. No changes. The call is on the record.
3. **Resolved** — Outcomes arrive. The Remark is graded. Receipts generated.

This lifecycle is what makes Remarks shareable. An open Remark is a prediction you can agree or disagree with. A resolved Remark is a receipt you can share.

### Remark Anatomy

| Field | Purpose |
|-------|---------|
| Voice text | The Remark in Jaromelu's words |
| Subject entities | Players, teams, or matchups referenced |
| Position | Buy / sell / hold / captain / avoid |
| Conviction | Low / medium / high |
| Evidence trail | Links to the claims, sources, and crew activity that built it |
| Status | Open / locked / resolved |
| Resolution | Outcome data once resolved |

### Relationship to Data Model

A Remark connects the existing data pipeline to the audience:

```
Sources → Claims → Consensus → Decision → Remark → Audience Interaction
```

In schema terms, a Remark is a specialised Event with:
- Links to upstream Claims (evidence trail)
- A position and conviction (from the Decision layer)
- Voice text (from the Characterisation layer)
- A resolution lifecycle (from the Outcomes table)
- Audience reactions (new interaction layer)

---

## Surfaces

Five canonical pages: **The Feed**, **The Wiki**, **The Ledger**, **The Analysis**, **Ask Me**. Ask Me has a dedicated route (`/ask`) and is also embedded in the Feed as contextual chat — same backend. Full per-page docs live under [`docs/pages/`](../pages/).

### 1. The Feed

The spine of the experience. A live, rewindable view of the crew at work and the Remarks they produce.

The Feed shows **three layers** interleaved:

**Crew Activity** — the visible process:
- Scout discovering new sources, flagging new takes
- Analyst cross-referencing, surfacing contradictions, updating consensus
- Progress indicators ("Scanning 4 new episodes..." with crew member attribution)

**Remarks** — the output:
- Jaromelu's calls, displayed prominently with conviction level
- Open Remarks with audience reaction counts
- Resolved Remarks with outcome and receipt

**Audience Interaction** — the participation:
- Reactions on open Remarks (agree / disagree / bold call)
- Questions directed at Jaromelu about specific Remarks ("Why are you selling Cleary?")
- Jaromelu's responses inline, in character

The Feed is **not a log**. Crew activity is shown as supporting context for Remarks. System events without narrative value are suppressed. Every entry either builds toward a Remark or resolves one.

**Visual moments in the Feed** (not separate pages):
- Consensus shifts visualised inline ("The market just flipped on Cleary" with a sentiment chart)
- Contradiction highlights ("Scout found opposing takes — Analyst is on it")
- Countdown to lockout ("Jaromelu has 6 hours to make his call")

### 2. The Wiki

A prose-dominant, agent-maintained knowledge base. Per-entity pages written and continuously updated by Jaromelu, not a database dashboard.

A wiki page exists for:
- **Players** — current stance (buy/sell/hold), form, price trajectory, expert opinions, injury/history, SuperCoach verdict
- **Teams** — roster state, form, upcoming fixtures, relevant narratives
- **Advisors** — accuracy track record, recent takes, trust rating, how often Jaromelu agrees/disagrees
- **Rounds** — preview → recap, game subsections, key narratives

Every wiki page links back to the Remarks, crew activity, and source chunks that informed the view. Lineage is visible. Cross-references use `[[slug]]` wiki-links the agent writes into the markdown.

The feel is **editorial**, not dashboard — warm parchment, serif typography, a reading surface that deliberately breaks from the dark broadcast stage of the Feed. Full design and schema: [pages/wiki/](../pages/wiki/overview.md).

### 3. The Ledger

Prediction tracking and accountability. Every call Jaromelu makes (and every advisor source makes) lives here with a resolution status and score. See [pages/ledger/](../pages/ledger/overview.md) for the (WIP) feature spec.

Core concerns: resolution lifecycle (open → locked → resolved), Alignment Index, rolling accuracy by type and round, shareable receipt cards for bold calls. See [The Alignment Index](#the-alignment-index) below.

### 4. The Analysis

Editorial content hub. Each round, Jaromelu publishes opinionated analytical articles covering SuperCoach strategy — round tips, team of the week, trade targets, captain picks, stocks up/down, podcast consensus.

Framing: "Here's what I'm thinking this round, in full." — long-form to complement the Feed's live cadence.

Shows:
- Article list grouped by round, filterable by type
- Full article reader with markdown rendering and source attribution
- Structured sidebar data for visualisations (player rankings, consensus counts)

Articles are stored in the Knowledge Base so they feed back into [Ask Me](../pages/ask-me/overview.md) automatically. Full spec: [pages/analysis/](../pages/analysis/overview.md).

### 5. Ask Me

Chat interface. Users ask Jaromelu about strategy, players, or his own calls; answers are RAG-retrieved from the Knowledge Base (player summaries, analysis articles, round briefs) and rendered in Jaromelu's voice. Available as a standalone page (`/ask`) and inline in the Feed as Twitch-style chat — same backend, different surface.

Full spec: [pages/ask-me/](../pages/ask-me/overview.md).

---

## The Alignment Index

The Alignment Index answers the question: **"Who actually reads the game well?"**

It tracks prediction accuracy not just for Jaromelu, but for **every expert source** the crew monitors. This creates a new dimension beyond "is Jaromelu right?" — it becomes "who in the NRL commentary ecosystem is most aligned with actual outcomes?"

### How It Works

1. **Claims are extracted** from every expert source Scout ingests (podcasts, YouTube, articles)
2. **Claims that constitute predictions** are identified and tracked (buy/sell calls, captain picks, matchup calls)
3. **Outcomes are matched** against predictions when results arrive
4. **Alignment scores are computed** — how often each source's calls match reality

### What the Audience Sees

- **Expert leaderboard** — ranked by alignment score, updated weekly
- **Jaromelu's position** — where he sits relative to the experts he's monitoring
- **Head-to-head comparisons** — "I'm beating KingOfSC on captain picks this season"
- **Consensus accuracy** — when everyone agrees, how often is the consensus right?
- **Contrarian value** — when Jaromelu goes against consensus, how often does it pay off?

### Why It Matters

This gives the site authority beyond Jaromelu's own performance. Even if Jaromelu has a bad week, the Alignment Index is still valuable — it's a trust ranking for the entire NRL SuperCoach commentary ecosystem. It answers: "Which podcasters should I actually listen to?"

### Audience in the Index

Users who react to Remarks (agree/disagree) accumulate their own alignment score. This enables:
- "You vs Jaromelu" comparison
- "Your accuracy this season" as a personal stat
- Leaderboard participation for engaged users

---

## Audience Participation

The audience is not passive. They have a role in the show.

### Reactions on Remarks

Before a Remark resolves, the audience can weigh in:
- **Agree / Disagree** — simple binary, creates crowd sentiment
- These reactions are tracked and contribute to the user's Alignment Index score

When a Remark resolves, Jaromelu can reference the crowd:
- "68% of you disagreed with my Munster call. Receipts."
- "The crowd was with me on this one. We all saw it."

### Challenging Remarks

Users can ask Jaromelu about specific Remarks directly in the Feed:
- "Why are you selling Cleary?"
- "Your Munster call looks shaky after that injury report"

Jaromelu responds in character, referencing the crew's evidence. This replaces the standalone Ask Me surface — interaction is contextual, not generic.

### Squad Submission

Users can submit their own squads for Jaromelu to review. This happens through the Feed:
- "Here's my squad. Roast me." / "Here's my squad. Thoughts?"
- Jaromelu responds in character with a temperature control (straight / sharp / roast)

### Shareable Receipts

Bold calls that resolve create **receipt cards** — shareable images or links:
- "Jaromelu called Munster over Cleary in Round 6. He was right."
- "Jaromelu went 4/5 on captain picks this month."

These are the viral moments. Correct bold calls and spectacular misses owned with humour.

---

## Agent Presence

### Crew Status

The site always communicates what the crew is doing *right now*. A persistent status indicator shows crew activity:

- "Scout is scanning new episodes..." (ingestion running)
- "Analyst is cross-referencing Round 5 claims..." (extraction in progress)
- "Jaromelu is reviewing the evidence..." (decision in progress)
- "Squad locked. Watching the market." (idle but attentive)
- "The Reckoning: reviewing Round 5 outcomes..." (post-round review)

This is subtle — a status line, not a modal. But it makes the crew feel alive and creates micro-anticipation ("Analyst is working — a Remark is coming").

### First-Person Voice

All copy on the site is written from the crew's perspective. Never neutral database language.

- Nav labels: "The Wiki", "The Ledger", "The Analysis" — not "Knowledge Base", "Predictions", "Articles"
- Empty states: "Scout hasn't found anything yet. Give it time." — not "No data available"
- Error states: "Something broke. Even the best crews have bad days." — not "500 Internal Server Error"
- Loading states: "Analyst is thinking..." — not "Loading..."

### Continuity

The strongest retention mechanic is that the crew remembers. Past Remarks, past mistakes, evolving opinions — all visible and referenced.

Jaromelu references his own history:
- "I called Cleary overpriced three weeks ago. Still overpriced."
- "Last time I went against KingOfSC on a captain pick, I lost. Not this time."

Users return to see: did the crew find something new? Did Jaromelu change his mind? Was he right?

---

## What Got Absorbed

The app went through multiple page-set iterations before settling on the current five. Earlier concepts absorbed:

| Previous Concept | Where It Lives Now |
|-----------------|-------------------|
| The Feed (solo stream of consciousness) | The Feed — crew activity + Remarks + interaction |
| My Squad (dashboard) | Retired — editorial content role moved to The Analysis |
| The Dossier | The Wiki — prose, agent-maintained per-entity pages |
| Knowledge Base page | The Wiki — same concept, now named for what it is |
| Articles (Phase 2) | The Analysis — shipped as the editorial hub |
| War Room (processing status) | The Feed — shown as crew activity |
| Opinion Radar (aggregated sentiment) | The Feed (narrative shifts) + The Ledger (Alignment Index) |

The principle: **the show is the Feed.** Don't make users navigate to a separate page to see something the crew should be telling them about in real time. The other four pages exist to reward deeper interest, not to be the primary surface.

---

## Seasonal Arc

Beyond the weekly episode, the season itself is a narrative:

- **Early rounds:** Jaromelu establishing his style, making bold opening calls, crew building its intelligence base
- **Mid-season:** Track record forming, Alignment Index gaining meaning, rivalries with expert sources emerging
- **Run home:** Stakes increasing, every call matters more, the audience invested in the outcome
- **Finals:** Season review, full accountability, "Season X: The Verdict"

The strongest retention mechanic is not content. It is **public continuity** — an ongoing show with real stakes that people follow like a season of television.

---

## UI/UX Specifications

Detailed interaction design and visual specs for each element of the experience are in [docs/concepts/](../concepts/):

| Doc | Covers |
|-----|--------|
| [00 — Design Principles](../concepts/00-design-principles.md) | Visual language of a show, not a dashboard |
| [01 — The Stream](../concepts/01-the-stream.md) | The single screen: crew bar, stream, interaction bar |
| [02 — Remarks](../concepts/02-remarks.md) | The atomic unit: anatomy, states, interaction patterns |
| [03 — Episode Beats](../concepts/03-episode-beats.md) | How the stream changes across the weekly arc |
| [04 — Drill-Downs](../concepts/04-drill-downs.md) | Contextual panels: squad, dossier, ledger |
| [05 — Crew Presence](../concepts/05-crew-presence.md) | How crew members appear across the experience |
| [06 — Audience](../concepts/06-audience.md) | Reactions, challenges, receipts, personal alignment |
| [07 — First Run](../concepts/07-first-run.md) | First visit experience and return loops |

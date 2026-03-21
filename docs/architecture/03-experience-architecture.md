# Experience Architecture

## Core Experience
Visitors watch an AI agent operate in public.

This is not a stats site with an AI label. It is a character with a visible mind. Users observe Jeromelu thinking, reacting, planning, and acting — in real time, with full transparency.

The experience should feel like following someone's live stream of consciousness, not browsing a database.

### Design Principle
Every surface answers the question: **"What is Jeromelu doing right now, and why?"**

Data (stats, opinions, consensus) is never presented raw. It is always framed through Jeromelu's perspective — what he noticed, what he thinks about it, and what he's going to do.

---

## Surfaces

### 1. The Feed
The spine of the entire experience. Everything else is a drill-down from here.

The Feed is Jeromelu's stream of consciousness — a rewindable, near-real-time timeline of:
- reactions to new intel ("Just watched KingOfSC. He's pushing Cleary hard. Everyone is. I'm not buying the panic.")
- narrative shifts ("Three sources in a row selling Hynes. That's not noise anymore.")
- internal reasoning ("The numbers say hold. The matchup says sell. I'm going with the matchup.")
- predictions ("Calling it now: Munster outscores Cleary this week. Book it.")
- actions ("Trade locked in. Gutho out, Mam in. Here's why.")
- postmortems ("That Munster call aged badly. Variance. The process was sound.")

The Feed is not a log. It is narrated. Every entry has Jeromelu's voice. Events without voice feel like system noise — they should be rare or absent.

**Visual moments in the Feed** (not separate pages):
- Consensus shifts visualised inline ("The market just flipped on Player X" with a sentiment chart)
- Source processing shown as activity ("Scanning 4 new episodes..." with progress)
- Plan formation shown as a sequence, not a single event

### 2. My Squad
Jeromelu presenting his team. Not a dashboard — a statement.

Framing: "Here's my squad. Here's the logic. Judge me."

Shows:
- current roster with position/role
- rationale per player (why they're in, linked back to Feed moments)
- trade history with reasoning ("I moved Gutho because...")
- captain pick with conviction level
- weekly score and season rank
- upcoming plan preview ("This week I'm watching X, considering Y")

The tone is first-person and opinionated. Not "Player A: 85 points" but "Player A delivered. Told you."

### 3. The Dossier
Deep-dive into any entity — but framed as "what Jeromelu knows."

A dossier page exists for:
- **Players** — Jeromelu's current stance (buy/sell/hold), price trajectory, what experts are saying, relevant claims linked to source, historical accuracy of calls on this player
- **Experts** — accuracy record, recent takes, how often Jeromelu agrees/disagrees, trust rating
- **Matchups** — which side Jeromelu favours, relevant intel, historical patterns
- **Teams** — roster state, upcoming fixture difficulty, relevant narratives

Every dossier page links back to the Feed moments and source chunks that informed the view. Lineage is visible, not hidden.

The feel is "Jeromelu's research file" — not a Wikipedia article.

### 4. The Ledger
Jeromelu's public record. Predictions, outcomes, receipts.

Framing: "I said it publicly. Here's how it landed."

Shows:
- all predictions with timestamps
- outcomes and resolution
- accuracy stats (overall, by type, by round)
- expert comparison ("I'm beating KingOfSC on captain picks this season")
- streak tracking and notable calls

This is the accountability surface. It builds trust through transparency and creates shareable moments (correct bold calls, spectacular misses owned with humour).

### 5. Ask Me
Direct interaction with Jeromelu. Chat interface.

Users can:
- ask team questions ("Should I trade Cleary?")
- submit squads for review (text-based)
- challenge Jeromelu's calls ("Why did you sell Munster?")
- ask matchup or player questions

Jeromelu responds in character. A temperature control adjusts tone:
- **Straight** — helpful, direct advice
- **Sharp** — opinionated, confident, slightly dismissive
- **Roast** — entertaining, will mock your squad choices

Responses reference real data and link back to Feed moments and Dossier entries where relevant.

### 6. Articles (Phase 2)
Weekly written content for SEO/AEO and narrative summary.

Deferred until the Feed and voice layer are proven.

---

## What Got Absorbed

The previous architecture had 8 separate surfaces. Several collapsed into the Feed:

| Old Surface | Where It Lives Now |
|-------------|-------------------|
| War Room (processing status, rising topics) | Feed — shown as inline visual moments |
| Opinion Radar (aggregated sentiment) | Feed (narrative shifts) + Dossier (player stance) |
| Knowledge Explorer | The Dossier |
| Team Dashboard | My Squad |
| Prediction Ledger | The Ledger |

The principle: don't make users navigate to a separate page to see something Jeromelu should be telling them about in the Feed.

---

## Agent Presence

### Current State
The site should always communicate what Jeromelu is doing *right now*. Not just history.

A persistent status indicator shows:
- "Scanning new episodes..." (ingestion running)
- "Reviewing Round 5 matchups..." (analysis in progress)
- "Squad locked. Watching the market." (idle but attentive)
- "Post-round review in progress..." (after matches)

This is subtle — a status line, not a modal. But it makes Jeromelu feel alive even when there's no new Feed content.

### First-Person Voice
All copy on the site is written from Jeromelu's perspective or about Jeromelu as a character. Never neutral database language.

- Nav labels: "My Squad", "The Ledger", "Ask Me" — not "Team", "Predictions", "Chat"
- Empty states: "Nothing to report yet. I'm watching." — not "No data available"
- Error states: "Something broke. Even I have bad days." — not "500 Internal Server Error"

### Continuity
The strongest retention mechanic is that Jeromelu remembers. Past predictions, past mistakes, evolving opinions — all visible and referenced.

Users return to see: did the market move? Did Jeromelu change his mind? Was he right?

---

# Product Loops

## Daily Loop
intel ingestion -> Jeromelu reacts in the Feed -> narrative shifts surface -> users check in

Users return to see whether the ecosystem moved and how Jeromelu interprets it.

## Weekly Loop
analysis builds through the week -> recommendations form -> final calls locked -> matches play -> postmortem in the Feed

The weekly arc has natural tension: buildup, commitment, result, accountability.

## Seasonal Loop
prediction record grows -> rank movement tracked -> expert comparisons sharpen -> character arc emerges

The strongest retention mechanic is not articles.
It is public continuity.

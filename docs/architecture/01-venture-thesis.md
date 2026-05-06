---
tags: [area/architecture]
---

# Venture Thesis

> Last reviewed: 2026-05-06.

Jaromelu is an autonomous AI **commentator on the NRL** — backed by a crew of agents who ingest the NRL media ecosystem (especially YouTube), build a continuously evolving view of the competition, form opinions, make calls, and live with the consequences. Visitors watch the operation unfold in public and come back to see whether his takes held up.

The product is designed as an **entertainment spectacle first** and a utility second. Where those two are in tension, spectacle wins.

The project is also a public demonstration of what's possible when data pipelines, agentic LLM reasoning, character voice, and orchestration are composed into a single coherent product — but the show is the primary thing, not the build.

---

# Strategic Layer

## V1 Scope vs V2

**V1 is about Jaromelu having decent, credible views on the NRL.**

The current focus is **knowledge creation across NRL YouTube sources** — podcasts, panels, post-match shows, weekly preview/review content. Scout ingests, Analyst cross-references, Jaromelu forms a position. Output is takes, calls, narrative reads — the substrate to talk credibly about anything happening in the league.

**V1 deliberately excludes:**
- SuperCoach gameplay (trades, captaincy, breakevens, squad management) — this is **V2**
- Live tipping competitions
- Personalised user squads
- Prediction markets

**V2 layers SuperCoach on top of an already-credible NRL commentator.** Voice and authority are built first; gameplay is built on top of an audience that already trusts the character.

This sequencing matters: a SuperCoach AI is one of many in a crowded space. An NRL commentator with track-record is rarer, more durable, and a better foundation for SC content when it lands.

## Audience

**Primary audience:** Hardcore NRL fans who consume heavy amounts of NRL commentary — podcasts, YouTube panels, post-match shows. Above-average game literacy.

**Typical user:**
- Australian, predominantly male
- Already consumes multiple NRL podcasts and YouTube channels each week
- Time-poor, opinion-saturated, decision-fatigued
- Wants fast synthesis over long-form content
- On a phone, on the bus, on the couch — checking in for 90 seconds at a time

We are not building for the casual NRL viewer. The thesis assumes the audience already lives in NRL discourse and is hiring Jaromelu to compress and entertain.

In V2, this audience overlaps heavily with hardcore SuperCoach players — but V1 builds the relationship before SC gameplay enters the product.

## Core Job To Be Done

> "Help me quickly understand what the NRL world is thinking — and entertain me while doing it."

Compression *and* entertainment — neither alone is enough. See [Value & Delivery](02-value-and-delivery.md) for how this unpacks into pillars and signals.

## Why A Crew Of Characters, Not A Tool

A solo agent answering questions feels like a chatbot. A crew working in public — Scout pulling YouTube intel, Analyst cross-referencing takes, Critic challenging, Jaromelu putting his name on the call — feels like a **production**.

| A character | A tool |
|---|---|
| Has personality | Has features |
| Makes calls feel dramatic | Returns results |
| Encourages sharing | Encourages bookmarking |
| Can be wrong publicly and own it | Just stays accurate |
| Builds a following | Builds a userbase |

Tools feel useful. Characters feel followable.

The crew (defined in [Experience Architecture §The Crew](03-experience-architecture.md#the-crew)) makes the process *legible* and the show *watchable*. Each role creates anticipation for the next.

## The Show Has Structure

The week follows the NRL match week — not a flat timeline:

| Beat | Day | Tension |
|---|---|---|
| Intel Drops | Mon | Crew ingests post-match takes, news, narratives |
| Tension Builds | Tue–Wed | Contradictions surface across commentators |
| The Call | Thu | Jaromelu locks in his Remarks for the round |
| The Match | Thu–Sun | Footy plays out. Takes meet reality. |
| The Reckoning | Mon | Receipts, grades, narrative shifts |

This rhythm creates natural return triggers without push notifications. The audience learns when to check in. Full breakdown in [Episode Beats](../concepts/03-episode-beats.md).

## The Audience Is In The Show

The audience is not passive. They:

- React to open Remarks (agree / disagree)
- Challenge Jaromelu directly — "you're wrong about the Eels, here's why"
- Accumulate their own **Personal Alignment Index** — graded against reality alongside Jaromelu

This converts the site from "AI shows you stuff" into "you are part of the show, and you are also being graded." Detailed in [Audience](../concepts/06-audience.md).

(Squad submission and SC-specific participation arrive in V2.)

## Return Triggers

**Daily:**
- New intel processed (Scout activity visible)
- Remarks forming, locking, resolving
- Inline drama — contradictions surfacing, consensus shifting on storylines

**Weekly (the episode arc):**
- Thursday — the call
- Thursday–Sunday — the football
- Monday — the reckoning, receipts, alignment updates

**Seasonal:**
- Jaromelu's ranking against expert NRL commentators
- Personal accuracy track record
- Expert leaderboard movement (the Alignment Index)
- Season narrative arc — early-bold → mid-track-record → run-home stakes → finals verdict

## The Strategic Moat: The Alignment Index

The most durable thing the site builds is **not** Jaromelu's track record — it is the **Alignment Index**: a public, standing trust ranking of every NRL commentator the crew tracks.

The Index answers a question no other site answers cleanly: *"Which podcasters and pundits should I actually listen to?"*

Even in a week Jaromelu calls badly, the Index is still useful — and the longer the season runs, the more authoritative it becomes. It is the asset that compounds across V1, and the foundation that makes V2 SuperCoach content land harder when it ships.

## Category

Character-driven AI sports commentator — closer to a daily NRL show with a host than a stats site with a chatbot.

---

## Related

- [Value & Delivery](02-value-and-delivery.md) — the promise unpacked into pillars and signals
- [Experience Architecture](03-experience-architecture.md) — the crew, surfaces, and episode arc in full
- [Design Principles](../concepts/00-design-principles.md) — visual and editorial rules
- [Audience](../concepts/06-audience.md) — how participation works
- [V1 Scope & Roadmap](09-v1-scope-and-roadmap.md) — what we ship first against this thesis

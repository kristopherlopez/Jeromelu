---
tags: [area/architecture]
---

# Venture Thesis

> Last reviewed: 2026-05-06.

Jaromelu is an autonomous AI character who plays NRL SuperCoach publicly — backed by a **crew of agents** who gather intelligence, cross-reference claims, form opinions, make calls, and live with the consequences. Visitors watch the operation unfold in public, see calls go on the record, and come back to see how they landed.

The product is designed as an **entertainment spectacle first** and a utility second. Where those two are in tension, spectacle wins.

The project is also a public demonstration of what's possible when data pipelines, agentic LLM reasoning, character voice, and orchestration are composed into a single coherent product — but the show is the primary thing, not the build.

---

# Strategic Layer

## Audience

**Primary audience:** Hardcore NRL SuperCoach players with average or higher game literacy.

**Typical user:**
- Australian, predominantly male
- Already consumes multiple SuperCoach podcasts and YouTube channels each week
- Time-poor, opinion-saturated, decision-fatigued
- Wants fast synthesis over long-form content
- On a phone, on the bus, on the couch — checking in for 90 seconds at a time

We are not building for the casual NRL fan. The thesis assumes the audience already lives in the SuperCoach world and is hiring Jaromelu to compress it and entertain them.

## Core Job To Be Done

> "Help me quickly understand what the SuperCoach world is thinking — and entertain me while doing it."

This one line drives every product decision. Compression *and* entertainment — neither alone is enough. See [Value & Delivery](02-value-and-delivery.md) for how this unpacks into pillars and signals.

## Why A Crew Of Characters, Not A Tool

A solo agent answering questions feels like a chatbot. A crew working in public — Scout gathering intel, Analyst cross-referencing, Critic challenging, Jaromelu putting his name on the call — feels like a **production**.

| A character | A tool |
|---|---|
| Has personality | Has features |
| Makes decisions feel dramatic | Returns results |
| Encourages sharing | Encourages bookmarking |
| Can be wrong publicly and own it | Just stays accurate |
| Builds a following | Builds a userbase |

Tools feel useful. Characters feel followable.

The crew (defined in [Experience Architecture §The Crew](03-experience-architecture.md#the-crew)) makes the process *legible* and the show *watchable*. Each role creates anticipation for the next.

## The Show Has Structure

The week is not a flat timeline. It is a weekly episode with a narrative arc:

| Beat | Day | Tension |
|---|---|---|
| Intel Drops | Mon | Discovery — what did the pods say? |
| Tension Builds | Tue–Wed | Contradictions surface |
| The Call | Thu | Public commitment — Remarks lock |
| The Match | Sat–Sun | Real consequences |
| The Reckoning | Mon | Receipts, grades, accountability |

This rhythm creates natural return triggers without push notifications. The audience learns when to check in. Full breakdown in [Episode Beats](../concepts/03-episode-beats.md).

## The Audience Is In The Show

The audience is not passive. They:

- React to open Remarks (agree / disagree)
- Challenge Jaromelu directly — "why are you selling Cleary?"
- Submit their own squads for review (straight / sharp / roast)
- Accumulate their own **Personal Alignment Index** — graded against reality alongside Jaromelu

This converts the site from "AI shows you stuff" into "you are part of the show, and you are also being graded." Detailed in [Audience](../concepts/06-audience.md).

## Return Triggers

**Daily:**
- New intel processed (Scout activity visible)
- Remarks forming, locking, resolving
- Inline drama — contradictions surfacing, consensus shifting

**Weekly (the episode arc):**
- Thursday — the call
- Saturday–Sunday — the match
- Monday — the reckoning, receipts, alignment updates

**Seasonal:**
- Jaromelu's ranking against expert sources
- Personal accuracy track record
- Expert leaderboard movement (the Alignment Index)
- Season narrative arc — early-bold → mid-track-record → run-home stakes → finals verdict

## The Strategic Moat: The Alignment Index

The most durable thing the site builds is **not** Jaromelu's track record — it is the **Alignment Index**: a public, standing trust ranking of every NRL SuperCoach commentator the crew tracks.

The Index answers a question no other site answers cleanly: *"Which podcasters should I actually listen to?"*

Even in a week Jaromelu calls badly, the Index is still useful — and the longer the season runs, the more authoritative it becomes. It is the asset that compounds.

## Category

Character-driven AI sports analyst — closer to a daily show with a host than a stats site with a chatbot.

---

## Related

- [Value & Delivery](02-value-and-delivery.md) — the promise unpacked into pillars and signals
- [Experience Architecture](03-experience-architecture.md) — the crew, surfaces, and episode arc in full
- [Design Principles](../concepts/00-design-principles.md) — visual and editorial rules
- [Audience](../concepts/06-audience.md) — how participation works in detail
- [V1 Scope & Roadmap](09-v1-scope-and-roadmap.md) — what we ship first against this thesis

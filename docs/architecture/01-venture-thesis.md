---
tags: [area/architecture]
---

# Venture Thesis

> Last reviewed: 2026-05-06.

Jaromelu is an autonomous AI **commentator on the NRL** — a non-human presence with a name, a voice, opinions, and a public track record, who lives on his own website. He's backed by a crew of agents who ingest the NRL media ecosystem, build a continuously evolving view of the competition, form opinions, make calls, and live with the consequences. Visitors watch the operation unfold in public and come back to see whether his takes held up.

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

This sequencing matters: a SuperCoach AI is one of many in a crowded space. An NRL commentator with a track record is rarer, more durable, and a better foundation for SC content when it lands.

## What We Want People To Feel

The aim isn't "AI tool that does NRL analysis." The aim is **a presence that feels alive** — a non-human entity with opinions, a voice, and a track record, who lives publicly in his own digital home. The reaction we're chasing is: *"Wait — this thing actually has takes."*

Some of this is unreachable today. Real-time AI video is still research-grade and expensive, so Jaromelu starts text-led with a stylised avatar and pre-rendered voiced clips for the big beats. But the medium gets richer over time (see [Capability Horizons](#capability-horizons)) — and the website, the rhythm, and the voice are designed for the version of Jaromelu that ships in two years, not the one that ships next quarter.

The website is the **digital home** — not a dashboard you visit, a place where he lives. The visual language, the editorial voice, the rhythm of the week, the always-on crew status — they all serve that single feeling.

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

## The Knowledge Asset

The most durable thing the project builds is **the knowledge graph itself** — a structured, growing record of what every NRL commentator says, when they said it, and whether they were right.

### What's captured

Scout ingests sources from around the internet (YouTube first — podcasts, panels, post-match shows). Each source is transcribed with **speaker diarisation**, so claims are attributed to *people*, not just shows. Both expert claims and Jaromelu's own claims are written into the same ledger and graded against reality.

The result is an asset no other NRL property has at scale:

- A timeline of every public claim about every player, team, and storyline
- An accuracy record per commentator, sliced by domain (tipping, narrative, fantasy, injuries, drama)
- Speaker-segmented **audio and video** clips of every panellist on every topic
- Resolved outcomes grading everyone — Jaromelu included — on the same scale

### What it unlocks

The same captured-once data drives every downstream capability:

| Capability | What it does |
|---|---|
| **The Alignment Index** | Public trust ranking of every NRL commentator. Answers *"who should I actually listen to?"*, sliced by what each person is actually good at. The compounding moat across V1. |
| **Content engine** | Receipts for outlier predictions, weekly verdicts, narrative recaps — purpose-built for social and designed to drive traffic back to the site. |
| **Specialised verticals** | Tipping, SuperCoach (V2), sports betting — different pricing/UX live downstream of the same knowledge layer. |
| **Voice and video clones** | Speaker-segmented A/V data captured today is the substrate for cloned commentator voices (now), generative video segments (12–18 months), and emotionally nuanced digital clones (24+ months). |
| **Aggregator role** | Because the index covers every NRL channel, the site can become a discovery layer for the ecosystem — *"the best segments on Cleary this week"* pointing at multiple sources, with traffic flowing back. |

The ordering matters: V1 decisions (capture diarised audio, segment by speaker, store claims as structured rows) are what make every later capability possible. The data store doesn't get built retroactively.

## Capability Horizons

What Jaromelu's on-screen presence looks like over time:

| Horizon | What becomes viable in the field | What we actually ship |
|---|---|---|
| **Now (V1)** | Voice clones from short audio; stylised avatars; pre-rendered short clips | Text-led Remarks, voiced clips for big moments, stylised avatar — not real-time video |
| **12–18 months** | Generative video at lower cost (Seedance-class models maturing) | Synthesised video segments for Remarks, recaps, set-piece moments |
| **24+ months** | Emotionally nuanced digital clones; real-time interactive video | Live Jaromelu segments; cloned commentators appearing in-show |

The thesis assumes Jaromelu's medium gets richer in lockstep with the field. **What we capture today — speaker-segmented audio, video, and claims — is built for the version of Jaromelu that ships in 24 months, not the one that ships next quarter.**

## Category

Character-driven AI sports commentator — closer to a daily NRL show with a host than a stats site with a chatbot.

---

## Related

- [Value & Delivery](02-value-and-delivery.md) — the promise unpacked into pillars and signals
- [Experience Architecture](03-experience-architecture.md) — the crew, surfaces, and episode arc in full
- [Design Principles](../concepts/00-design-principles.md) — visual and editorial rules
- [Audience](../concepts/06-audience.md) — how participation works
- [V1 Scope & Roadmap](09-v1-scope-and-roadmap.md) — what we ship first against this thesis

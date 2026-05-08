---
tags: [area/architecture]
---

# Venture Thesis

> Last reviewed: 2026-05-06.

Jaromelu is an autonomous AI **commentator on the NRL** — a non-human presence with a name, a voice, opinions, and a public track record, who lives on his own website. He's backed by a crew of agents who ingest the NRL media ecosystem, build a continuously evolving view of the competition, form opinions, make calls, and live with the consequences. Visitors watch the operation unfold in public and come back to see whether his takes held up.

The product is designed as an **entertainment spectacle first** and a utility second. Where those two are in tension, spectacle wins.

The project is also a public demonstration of what's possible when data pipelines, agentic LLM reasoning, character voice, and orchestration are composed into a single coherent product — but the show is the primary thing, not the build.

---

## The Strategic Bet

The defensible thing is **the persona plus the knowledge graph, captured together over time.**

A character with a name, a voice, opinions, and a public accuracy record is harder to copy than a tool with the same features. A growing ledger of speaker-attributed claims, graded against reality, is harder to copy than a season of stats. Stack the two and a competitor can't catch up by spending money — they need to spend a season.

**What we're betting on:**

- Hardcore NRL fans will follow a non-human personality if it has takes worth following
- The medium gets richer fast enough that today's text-led show becomes tomorrow's video-rich show on the same captured data
- Public accuracy *and* public misses build more trust than a polished UI ever could

**What we're trading away:**

- Mass-market reach — we are not for the casual NRL viewer
- SuperCoach as the wedge — SC is one spoke off the core; the persona and knowledge graph come first
- A polished avatar in V1 — pre-generated clips don't scale; we wait for the medium to mature

**Why now:** LLMs are good enough to hold a voice across thousands of outputs; speaker-diarised transcription is cheap and accurate; generative voice and video are on a clear cost-down curve. The "capture everything now, compose richer later" pattern is finally viable.

## Core and Spokes

The thesis is a **hub-and-spoke model**:

- **Core** — the persona (Jaromelu, his crew, his voice) plus the knowledge graph (speaker-attributed claims graded against reality). Built once. Compounds over time.
- **Spokes** — every downstream application plugs into the core. NRL commentary is the first spoke — built first because it produces a richer persona on richer data than any narrower opener would. SuperCoach, tipping, sports betting, content for social, voice and video clone services, aggregator — all later spokes.

Spoke detail: see [The Knowledge Asset](#the-knowledge-asset) and [V1 Scope & Roadmap](09-v1-scope-and-roadmap.md).

## What We Want People To Feel

The aim isn't "AI tool that does NRL analysis." The aim is **a presence that feels alive** — a non-human entity with opinions, a voice, and a track record, who lives publicly in his own digital home. The reaction we're chasing is: *"Wait — this thing actually has takes."*

Some of that is unreachable today. Real-time AI video is still research-grade and expensive, and pre-generated avatar clips have already been explored and parked — at the volume the show needs, they take too long to produce, run expensive, and risk feeling tiresome quickly. So in V1 Jaromelu is **text-led**, with voice for the big set-piece moments. The "alive" feeling has to come from somewhere else, and it does:

- The crew's **visible work** — Scout discovering, Analyst cross-referencing, contradictions surfacing
- The **editorial voice** everywhere — no system copy; every line has a speaker
- The **rhythm of the week** — the screen looks different on Monday than on Thursday
- The **always-on crew status** — there's always something happening
- The **digital home** — the website is a place he lives, not a dashboard you visit

When generative video gets cheap enough to run sustainably, the avatar layer slots in on top of all that. Until then, the show carries itself.

## Audience

**Primary audience:** Hardcore NRL fans who consume heavy amounts of NRL commentary — podcasts, YouTube panels, post-match shows. Above-average game literacy.

**Typical user:**

- Australian, predominantly male
- Already consumes multiple NRL podcasts and YouTube channels each week
- Time-poor, opinion-saturated, decision-fatigued
- Wants fast synthesis over long-form content
- On a phone, on the bus, on the couch — checking in for 90 seconds at a time

We are not building for the casual NRL viewer. The thesis assumes the audience already lives in NRL discourse and is hiring Jaromelu to compress and entertain.

The SC spoke, when it ships, overlaps heavily with this audience — but the relationship is built first on NRL commentary.

## Core Job To Be Done

> "Help me quickly understand what the NRL world is thinking — and entertain me while doing it."

Compression *and* entertainment — neither alone is enough.

## The Value Proposition

Here's the value the customer gets, and what's being built to unlock it. Full breakdown in [Value & Delivery](02-value-and-delivery.md).

| Customer value | What we're doing to unlock it |
|---|---|
| **Compression** — the week's NRL commentary distilled into a small number of opinionated takes | Scout ingests YouTube sources; Analyst cross-references claims; Jaromelu publishes Remarks that compress 12+ hours of audio into 4–6 calls per round |
| **Truth filter** — know which commentators are actually accurate, sliced by topic | Speaker-diarised claims ledger; every claim graded against reality; published as the Alignment Index |
| **A show worth following** — entertainment with a host and a crew, not a dashboard | Crew presented as characters; weekly episode arc; visible work as spectacle; voice-everywhere editorial |
| **Skin in the game** — the customer is in the show with their own track record | Reactions on open Remarks; challenges directed at Jaromelu; Personal Alignment Index tracks customer accuracy |
| **Public stakes** — every call carries real consequences | Open → Locked → Resolved Remark lifecycle; receipts for resolved calls; rolling accuracy never reset |

Sequencing: **build Compression and Truth Filter first** — they need only the core (persona + knowledge graph). Skin-in-the-Game and Public Stakes layer in as the audience interaction surfaces mature. SC-specific value comes with the SC spoke.

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

The crew (defined in [Experience Architecture §The Crew](03-experience-architecture.md#the-crew)) makes the process *legible* and the show *watchable*. Each role creates anticipation for the next — and in V1 it's the crew's visible work that carries the alive feeling, not an avatar.

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

(Squad submission and SC-specific participation come with the SC spoke.)

## Return Triggers

**Daily** — new intel processed (Scout activity visible), Remarks forming and locking and resolving, contradictions surfacing inline.

**Weekly** — the episode arc above. Thursday is the call, the weekend is the football, Monday is the reckoning.

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

### How to monetise

Multiple revenue layers compound; none is make-or-break. V1 builds audience and authority; monetisation lands in stages.

| Revenue stream | What unlocks it | Timing |
|---|---|---|
| **Sports-betting affiliate** | Hardcore NRL audience + claims-graded recommendations; high-intent users | V1, once audience scales |
| **Display + sponsorship** | Audience scale; episode beats give natural ad surfaces ("brought to you by") and sponsored Remarks | V1 |
| **Subscription tier** | Premium access — full Ledger, deeper Wiki, ad-free, early Remarks, full Alignment Index slices | V1 → V2 |
| **Content engine → social → traffic** | Receipts and recaps built for social; brings audience back to the owned home | V1 → V2 |
| **Tipping & SC subscriptions** | Specialised vertical features built on the same knowledge graph | V2 |
| **Data / index licensing** | Alignment Index becomes a recognised authority; licensed to media, teams, broadcasters | Mid-term, after the Index has a track record |
| **Voice / video clone services** | Speaker-segmented A/V data + clone tech maturity; license cloned voices back to commentators; B2B media production | 12–24+ months |
| **Aggregator referral revenue** | Site becomes a discovery layer for NRL channels; YouTube affiliate / partner revenue; channel placements | Mid-term |

The defensible position is **the knowledge asset itself**. Most of these revenue streams draw on the same captured-once data — a competitor has to spend a season catching up before they can monetise the same way.

The ordering matters: V1 decisions (capture diarised audio, segment by speaker, store claims as structured rows) are what make every later capability — and every revenue stream — possible. The data store doesn't get built retroactively.

## Capability Horizons

What Jaromelu's on-screen presence looks like over time:

| Horizon | What becomes viable in the field | What we actually ship |
|---|---|---|
| **Now (V1)** | Voice clones from short audio; pre-generated avatar clips technically possible but slow and expensive at show volume | Text-led Remarks; voice for big moments; the crew's visible work and the editorial voice carrying the alive feeling. No persistent avatar — pre-generated clips don't scale. |
| **12–18 months** | Generative video at lower cost (Seedance-class models maturing); near-real-time clip generation | Synthesised video segments for Remarks, recaps, set-piece moments. Avatar layer slots in sustainably. |
| **24+ months** | Emotionally nuanced digital clones; real-time interactive video | Live Jaromelu segments; cloned commentators appearing in-show. |

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

---
tags: [area/architecture]
status: draft
---

# Venture Thesis (Draft — customer-centered revision)

> Draft created 2026-05-09 alongside the existing `01-venture-thesis.md`. Same source content, restructured around the customer: who they are, why they'd want this, and what we want them to feel. Delivery, asset, and roadmap content has been pulled out for placement elsewhere.

---

# Venture Thesis

> Last reviewed: 2026-05-06.

Jaromelu is an autonomous AI **commentator on the NRL** — a non-human presence with a name, a voice, opinions, and a public track record, who lives on his own website. He's backed by a crew of agents who ingest the NRL media ecosystem, build a continuously evolving view of the competition, form opinions, make calls, and live with the consequences. Visitors watch the operation unfold in public and come back to see whether his takes held up.

The product is designed as an **entertainment spectacle first** and a utility second. Where those two are in tension, spectacle wins.

---

## Who Are The People

**Primary audience:** Hardcore NRL fans who consume heavy amounts of NRL commentary — podcasts, YouTube panels, post-match shows. Above-average game literacy.

**Typical user:**

- Australian, predominantly male
- Already consumes multiple NRL podcasts and YouTube channels each week
- Time-poor, opinion-saturated, decision-fatigued
- Wants fast synthesis over long-form content
- On a phone, on the bus, on the couch — checking in for 90 seconds at a time

**What they hire Jaromelu to do:**

> "Help me quickly understand what the NRL world is thinking — and entertain me while doing it."

Compression *and* entertainment — neither alone is enough.

We are not building for the casual NRL viewer. The thesis assumes the audience already lives in NRL discourse and is hiring Jaromelu to compress and entertain. SuperCoach players, when that extension ships, overlap heavily with this audience — but the relationship is built first on NRL commentary.

## What They're Frustrated With Today

The audience is drowning, not searching. They already follow more NRL commentary than they can keep up with — three podcasts deep, two YouTube channels behind, panel takes contradicting each other on Tuesday and forgotten by Thursday.

The pain isn't a lack of content. The pain is:

- **Too much, all at once.** A round produces 12+ hours of audio across the major channels. Even the hardcore fan is always behind.
- **Conflicting takes, no accountability.** Three commentators say three different things about the same player. Nobody tracks who was right last week, let alone last season — and the customer isn't going to do that math themselves.
- **Opinion saturation.** Hot takes are cheap. The customer can't tell whose conviction is earned and whose is fluff.
- **No fast lane.** The synthesis they want — *"what's the consensus, where are the contradictions, who's calling it differently?"* — only exists if they spend the hours to assemble it.

The customer doesn't need another podcast. They need someone to listen to all of them and tell them what matters.

## Why Would People Want This

There's nothing else like him, and that's the point.

A character with a name, a voice, opinions, and a public accuracy record is harder to copy than a tool with the same features. A growing ledger of speaker-attributed claims, graded against reality, is harder to copy than a season of stats. Stack the two and a competitor can't catch up by spending money — they need to spend a season.

**What we believe about the audience:**

- Hardcore NRL fans will follow a non-human personality if it has takes worth following
- Public accuracy *and* public misses build more trust than a polished UI ever could
- The medium gets richer fast enough that today's text-led show becomes tomorrow's video-rich show on the same captured data — anyone who joins now is following something that keeps getting richer

**Why this is possible now:** LLMs are good enough to hold a voice across thousands of outputs; speaker-diarised transcription is cheap and accurate; generative voice and video are on a clear cost-down curve. The "capture everything now, compose richer later" pattern is finally viable.

## What We Want People To Feel

The aim isn't "AI tool that does NRL analysis." The aim is **a presence that feels alive** — a non-human entity with opinions, a voice, and a track record, who lives publicly in his own digital home. The reaction we're chasing is: *"Wait — this thing actually has takes."*

Some of that is unreachable today. Real-time AI video is still research-grade and expensive, and pre-generated avatar clips have already been explored and parked — at the volume the show needs, they take too long to produce, run expensive, and risk feeling tiresome quickly. So in V1 Jaromelu is **text-led**, with voice for the big set-piece moments. The "alive" feeling has to come from somewhere else, and it does:

- The crew's **visible work** — Scout discovering, Analyst cross-referencing, contradictions surfacing
- The **editorial voice** everywhere — no system copy; every line has a speaker
- The **rhythm of the week** — the screen looks different on Monday than on Thursday
- The **always-on crew status** — there's always something happening
- The **digital home** — the website is a place he lives, not a dashboard you visit

When generative video gets cheap enough to run sustainably, the avatar layer slots in on top of all that. Until then, the show carries itself.

## What They Do Here

The customer isn't watching the show. They're in it.

- **They react.** Every open Remark accepts agree/disagree from the audience. Their reactions become part of the record.
- **They challenge.** They ask Jaromelu directly about a call — *"you're wrong about the Eels, here's why"* — and he responds, in character, with whatever the ledger says.
- **They get graded.** Every customer accumulates a **Personal Alignment Index** — graded against reality the same way Jaromelu is. They earn their own track record over a season.
- **They come back to see how they're tracking.** Reasons to return that don't depend on Jaromelu being right: *"How am I doing this season?"*

The customer is a participant with skin in the game, not an audience member with a remote.

---

## Related

- [Value & Delivery](02-value-and-delivery.md) — the promise unpacked into pillars and signals
- [Experience Architecture](03-experience-architecture.md) — the crew, surfaces, and episode arc in full
- [Design Principles](../concepts/00-design-principles.md) — visual and editorial rules
- [Audience](../concepts/06-audience.md) — how participation works
- [V1 Scope & Roadmap](09-v1-scope-and-roadmap.md) — what we ship first against this thesis

---

## Drafting notes (delete before merge)

**Section restructure** (vs source):

- New order: Opening → Who Are The People → What They're Frustrated With Today → Why Would People Want This → What We Want People To Feel → What They Do Here. Customer-flow: meet the audience, understand the pain, understand the pull, understand the feel, understand what they actually do. (Source order was: Strategic Bet → Feel → Audience → Show structure → Audience-in-show → Return triggers → Knowledge asset → Horizons → Category.)
- Heading: "Audience" → "Who Are The People"
- Heading: "The Strategic Bet" → "Why Would People Want This"
- Heading: "What We Want People To Feel" — unchanged
- New section: "What They're Frustrated With Today" — surfaces the pain that's currently buried as a single bullet ("time-poor, opinion-saturated, decision-fatigued"). Sets up the pull more concretely.
- New section: "What They Do Here" — customer-as-participant. Pulls the *identity* framing out of the original "The Audience Is In The Show" section; the participation surfaces (UI, mechanics) still proposed for `03`.

**What was cut and where it's proposed to go:**

- **Core and Spokes** — dropped (defensibility argument now sits inside "Why Would People Want This").
- **Core Job To Be Done** — folded into "Who Are The People" as "What they hire Jaromelu to do."
- **The Value Proposition** — dropped (already a pointer to 02; kept as Related link).
- **Why A Crew Of Characters, Not A Tool** — proposed move to `03-experience-architecture.md`.
- **The Show Has Structure** — proposed move to `03` (episode arc).
- **The Audience Is In The Show** — split. Customer-identity framing now lives in 01 as "What They Do Here." Participation surfaces (UI, mechanics) still proposed for `03`.
- **Return Triggers** — proposed move to `03` (engagement rhythm).
- **The Knowledge Asset** (capture / capabilities / monetisation / moat) — proposed new doc, e.g. `04-knowledge-asset.md`.
- **Capability Horizons** — proposed move to `09-v1-scope-and-roadmap.md`.
- **Category** — dropped (opening paragraph already establishes the category).
- **"What we're trading away" bullets** (from old Strategic Bet) — dropped from this customer-centered doc. Mass-market reach is already in "Who Are The People." The V1-text-led trade-off is in "What We Want People To Feel." SC-as-wedge is no longer load-bearing once Core and Spokes is gone.

**Wording changes:**

- "The defensible thing is **the persona plus the knowledge graph…**" → "There's nothing else like him, and that's the point." (opening line of Why-section, reframes from defensibility to customer pull; the persona-plus-graph argument follows in the next paragraph).
- Subhead: "What we're betting on" → "What we believe about the audience" (customer-framed).
- "Why now:" → "Why this is possible now:" (slight customer-framing tweak).
- "The SC spoke, when it ships, overlaps heavily…" → "SuperCoach players, when that extension ships, overlap heavily…" (avoids referencing a section that no longer exists in this doc).
- Opening paragraph 3 ("The project is also a public demonstration of what's possible when data pipelines, agentic LLM reasoning, character voice, and orchestration are composed…") — dropped. Builder-framing, not customer-framing; belongs in a project-level README or a "for builders" doc.

---
tags: [area/agents, subarea/crew]
---

# Crew Dynamics

The crew describes Jaromelu's *internal* reasoning rhythm — the shape of the thinking that produces a call. Users never see this rhythm play out as separate characters. They see Jaromelu's final voice, which carries traces of the internal process (research findings, cross-references, self-doubt, math citations, historical pattern matches).

The **Archivist** is an exception to that rhythm — it is a worker, not a tonal mode, and it runs out-of-band relative to the call chain. See [Out of band: the Archivist](#out-of-band-the-archivist) below.

This doc maps the internal flow for engineering, prompt design, and copy purposes. It is **not** a UI specification.

---

## Internal Reasoning Flow

The default flow inside Jaromelu's reasoning before a call is published:

1. **Scout (research)** — gather intel, surface what's new
2. **Analyst (cross-reference)** — find contradictions and consensus shifts
3. **Bookkeeper (numbers)** — breakevens, cap space, math
4. **Critic (challenge)** — pre-call objection on thin evidence
5. **Jaromelu (the call)** — integrate everything, commit, voice it

In the system, this corresponds to a chain of workers (ingestion → extraction → scraper math → decision) and prompt phases (research → analysis → critique → final voice).

---

## Internal Handoff (engineering view)

Each step's output is the next step's input:

```
Scout: "3 new takes on Cleary — KingOfSC SELL, NRLBrothers SELL, PodcastNRL BUY"
   ↓
Analyst: "Contradiction. Same matchup data, opposite reads. Sell side has 2/3 sources;
         one is below 50% accuracy historically."
   ↓
Bookkeeper: "Breakeven 42. Last 4: 51, 48, 42, 61. Trend down."
   ↓
Critic: "Two sell sources are below 50% accuracy. Numbers do support sell though."
   ↓
Jaromelu (published voice):
   "Three takes on Cleary this week, two saying sell. One of those sources is shaky
    historically — but the breakeven's 42 and he's been trending down for a month.
    I almost held him out of stubbornness. Selling."
```

The published Remark may *reference* the internal process ("almost held him out of stubbornness") but never renders the internal contributors as separate visible characters.

---

## When Self-Doubt Becomes Voice

Jaromelu's most resonant beats expose the internal Critic mode through his own voice — never as a second character on screen:

> "I almost talked myself out of it. The accuracy on those sources is bad. But I trust the matchup more than I trust the messenger."

> "The Critic in me said hold. I didn't listen. My fault. Moving on."

> "Bookkeeper said the breakeven was unforgiving. I overrode it. Variance is going to hurt or vindicate me."

This is the only place the internal rhythm leaks out — as authored self-awareness, not as a multi-character interaction.

---

## Cadence

The cadence of internal reasoning maps to system events, not to on-screen beats:

| Internal step | System trigger | User-facing surface |
|---|---|---|
| Scout | New transcript discovered / source added | "Jaromelu found new sources / new takes" — published as a Jaromelu update in the feed |
| Analyst | Extraction worker output | Numbers / claims cited in Jaromelu's next Remark |
| Bookkeeper | Scout scrape complete | Numbers cited inline in Jaromelu's next Remark |
| Critic | Pre-publish gate on a draft Remark | Self-aware framing in the final voice ("almost talked myself out of it") |
| Jaromelu | Decision worker commits | Remark card publishes |
| **Archivist** *(out-of-band)* | New claims / stats / team lists / Remarks land | Wiki page rewrites, surfaced in `/wiki` and the activity Feed (revisions) |

---

## Out of band: the Archivist

The five-step flow above is the **call chain** — the reasoning that produces a Remark. The Archivist is not in that chain. It runs continuously and asynchronously, downstream of every other crew member, and writes to a separate user-facing surface (the wiki).

```
Scout      →  Analyst    →  Bookkeeper  →  Critic     →  Jaromelu
(acquire)     (extract)     (numbers)      (challenge)    (voice / Remark)
                  ↓             ↓                            ↓
                  ───────────► Archivist ◄────────────────────
                          (composes wiki prose,
                           curates relations,
                           links continuity)
```

The Archivist consumes the structured outputs of every other crew member and composes them into a browsable knowledge artifact. It does not contribute to a single Remark; it maintains the wiki that frames *all* Remarks.

Two consequences for the dynamics:

1. **Different rhythm.** The call chain converges weekly on Thursday's Remark. The Archivist runs whenever new data lands — claims arrive, stats post-round, a Remark gets published. Its work is ambient and distributed across the week.
2. **Different voice.** Where Jaromelu speaks in his confident on-screen voice, the Archivist writes in encyclopedic third-person. The same fact ("Cleary's breakeven is 42") can appear in both — voiced as bravado in a Remark, reported neutrally on Cleary's wiki page.

Full role spec: [`archivist.md`](archivist.md). Runtime spec: [`../../pages/wiki/content-pipeline.md`](../../pages/wiki/content-pipeline.md).

---

## Related

- [`../../concepts/05-crew-presence.md`](../../concepts/05-crew-presence.md) — Jaromelu's on-screen presence (the only on-screen character)
- [`../../concepts/02-remarks.md`](../../concepts/02-remarks.md) — Remark cards (Jaromelu's primary output)

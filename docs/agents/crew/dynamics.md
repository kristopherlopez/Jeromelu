---
tags: [area/agents, subarea/crew]
---

# Crew Dynamics

The crew describes Jaromelu's *internal* reasoning rhythm — the shape of the thinking that produces a call. Users never see this rhythm play out as separate characters. They see Jaromelu's final voice, which carries traces of the internal process (research findings, cross-references, self-doubt, math citations, historical pattern matches).

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
| Analyst | Extraction worker output | Wiki update authored by Jaromelu, citing the cross-reference |
| Bookkeeper | Scraper sweep complete | Numbers cited inline in Jaromelu's next Remark |
| Critic | Pre-publish gate on a draft Remark | Self-aware framing in the final voice ("almost talked myself out of it") |
| Jaromelu | Decision worker commits | Remark card publishes |

---

## Related

- [`../../concepts/05-crew-presence.md`](../../concepts/05-crew-presence.md) — Jaromelu's on-screen presence (the only on-screen character)
- [`../../concepts/02-remarks.md`](../../concepts/02-remarks.md) — Remark cards (Jaromelu's primary output)

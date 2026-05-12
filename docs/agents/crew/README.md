---
tags: [area/agents, subarea/crew]
---

# Crew

The crew is **the internal reasoning architecture of Jaromelu, plus the Archivist who maintains the wiki**. Jaromelu is the only on-screen *character*; the wiki itself (composed by the Archivist) is the only other thing a user sees that wasn't routed through Jaromelu's voice.

Most of the crew — Scout, Analyst, Critic, Bookkeeper — are **tonal modes and reasoning shards** that compose into Jaromelu's single on-screen voice. They are not visible characters; users see Jaromelu's voice that traces of these modes ("I've been digging through the pods..." carries Scout mode; "the math is brutal..." carries Bookkeeper mode).

The **Archivist** is the exception: it is a worker that produces a persistent, browsable artifact (the wiki) in encyclopedic voice. Its output is not channelled through Jaromelu — readers see Archivist-authored prose directly when they browse `/wiki`.

| Crew member | Kind | What it does | What the user sees |
|---|---|---|---|
| [Jaromelu](jaromelu.md) | On-screen character | Integrates everything below; makes the call | His voice on every Feed entry, Remark, and reply |
| [Scout](scout.md) | Reasoning mode + system worker | Research and intelligence gathering | "I've been digging through the pods this week..." (in Jaromelu's voice) |
| [Analyst](analyst.md) | Reasoning mode + system worker | Cross-referencing, contradiction detection | "Three sources agree, one's the outlier..." (in Jaromelu's voice) |
| [Critic](critic.md) | Reasoning mode | Pre-call skeptical challenge | "I almost talked myself out of it because..." (in Jaromelu's voice) |
| [Bookkeeper](bookkeeper.md) | Reasoning mode + system worker | Numbers, breakevens, math | "Breakeven's 42 — needs 55+ to pay off..." (in Jaromelu's voice) |
| [Archivist](archivist.md) | Worker (separate output) | Wiki composition, cross-page integrity, relation curation | The wiki itself — entity pages in encyclopedic voice |

See [dynamics.md](dynamics.md) for how the internal-mode crew composes into Jaromelu's voice, and how the Archivist sits out-of-band relative to that flow. On-screen presence — i.e. characters with faces and personality — is Jaromelu-only; see [`../../concepts/05-crew-presence.md`](../../concepts/05-crew-presence.md).

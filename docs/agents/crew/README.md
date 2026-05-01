---
tags: [area/agents, subarea/crew]
---

# Crew

The crew is the **internal reasoning architecture of Jaromelu** — not a visible cast. Users only see Jaromelu. The "crew" is how he thinks: research, analysis, skepticism, math, memory. Each member is a function — a tonal mode, a system worker, a reasoning shard — that composes into Jaromelu's single on-screen voice.

This file and the per-member docs are **internal architecture documentation**. They describe how Jaromelu's reasoning is decomposed for engineering and authoring purposes (system workers, prompts, internal voices). They do not describe separate visible characters.

| Internal function | What it does | When Jaromelu's voice uses it |
|---|---|---|
| [Jaromelu](jaromelu.md) | The on-screen character — integrates everything below | Always — every user-facing surface |
| [Scout](scout.md) | Research and intelligence gathering | "I've been digging through the pods this week..." |
| [Analyst](analyst.md) | Cross-referencing, contradiction detection | "Three sources agree, one's the outlier..." |
| [Critic](critic.md) | Pre-call skeptical challenge | "I almost talked myself out of it because..." |
| [Bookkeeper](bookkeeper.md) | Numbers, breakevens, math | "Breakeven's 42 — needs 55+ to pay off..." |
| [Archivist](archivist.md) | Historical pattern matching | "Last time three sources agreed on a sell, they were right..." |

See [dynamics.md](dynamics.md) for how these internal functions compose into Jaromelu's voice (handoffs are internal reasoning patterns, not on-screen interactions). On-screen presence is Jaromelu-only — see [`../../concepts/05-crew-presence.md`](../../concepts/05-crew-presence.md).

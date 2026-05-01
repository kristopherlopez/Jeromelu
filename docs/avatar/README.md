---
tags: [area/avatar]
---

# The Jaromelu Avatar

The avatar is the **sixth surface**. The [five canonical pages](../pages/) define *where* users go; the avatar defines *who is always there*. It's the connective tissue that makes the site feel alive rather than inert.

Goal: **fun, interactive, and engaging throughout the website.**

---

## What the avatar is

A persistent, reactive presence. Jaromelu shows up on every page — idle-breathing when nothing's happening, animated when the system is doing work, reactive when the user does something. Not a mascot in the corner; a character who's watching the room.

Powered by:
- A library of short pre-generated video clips (Kling) — see [clip-pipeline.md](clip-pipeline.md)
- A state machine that sequences clips based on system state + user actions — see [system.md](system.md)
- A per-page behavioural layer that shapes what "presence" means on each surface — see [per-page.md](per-page.md)
- An interaction layer for clickable / hoverable / user-triggered reactions — see [interactions.md](interactions.md)

---

## The three layers

| Layer | Doc | Concern |
|-------|-----|---------|
| **Character** | [`agents/crew/jaromelu.md`](../agents/crew/jaromelu.md) | Who Jaromelu is — persona, voice, behavioural rules |
| **Presence design** | [`concepts/05-crew-presence.md`](../concepts/05-crew-presence.md) | Visual identity, avatar sizes, full animation library spec (all crew, not just Jaromelu) |
| **Implementation** | This folder | How the avatar actually behaves on the live site |

---

## Docs in this folder

| Doc | Covers |
|-----|--------|
| [system.md](system.md) | Runtime state machine — how the avatar reacts to system events in real time |
| [clip-pipeline.md](clip-pipeline.md) | How clips are produced: Kling generation, manifest, upload workflow |
| [interactions.md](interactions.md) | User-triggered reactions: clicks, hovers, idle easter eggs |
| [per-page.md](per-page.md) | How the avatar behaves differently on each of the five canonical pages |

---

## Principles

1. **Never static.** When nothing else is happening, the avatar still breathes, glances, blinks. The site should never feel paused.
2. **React to the system, not just the clock.** Workers ingesting, claims extracting, consensus shifting — the avatar should reflect what Jaromelu is *actually* doing.
3. **React to the user.** Clicks, hovers, long dwells, returning visits — the avatar acknowledges.
4. **Expressive, not busy.** The goal is *warmth and personality*, not constant motion. If it distracts from reading, it's wrong.
5. **Unique per page.** The same avatar feels different on the Feed (active, commenting) vs the Wiki (quiet, letting you read) vs the Ledger (receipt-mode, smug or sheepish depending on record).

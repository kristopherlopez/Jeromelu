---
tags: [area/concepts]
---

# Jaromelu Presence

Jaromelu is the only on-screen character. There is no multi-character "crew bar" — the user-facing surface shows one face, one voice, one presence. The internal "crew" (see [`../agents/crew/README.md`](../agents/crew/README.md)) describes Jaromelu's internal reasoning architecture, not separate visible characters.

This doc covers Jaromelu's on-screen presence: avatar states, animation library, attribution, and how internal-mode shifts surface in the UI.

---

## Always-Present Avatar

Jaromelu is never absent from the UI. His avatar is the persistent character anchor — replaces logo / nav / hamburger menu in the header. Tap returns to home.

### States

**Idle**
- Slow looped animation: thinking at desk, occasionally glancing at camera
- Subtle orange accent (his signature colour)
- Status text: "Squad locked. Watching the market."

**Active (working)**
- Idle loop continues, status text shifts to reflect current internal mode:
  - "Investigating new sources" — Scout mode (recon / source discovery)
  - "Reading this week's pods" — Scout mode (transcript ingestion)
  - "Cross-referencing claims" — Analyst mode (extraction)
  - "Doing the math on Cleary" — Bookkeeper mode (scraper math)
  - "Sleeping on a call" — Critic mode (pre-publish review)
  - "Preparing the call" — final voice synthesis
- Pulsing orange ring around avatar

**Decision moment (publishing a Remark)**
- "Confident call" animation plays (3-5s)
- Status: "On the call: SELL Cleary"
- Avatar transitions to lean-toward-camera pose

**Postmortem**
- Animation matches outcome: smirk/lean back (correct), grimace/shrug (wrong), head in hands (spectacular miss)

The status string is always written in Jaromelu's first person, even when reporting internal-function activity. The audience sees one character doing many things — never separate workers.

---

## Avatar Sizes

| Context | Size | Format |
|---|---|---|
| Header pill | 32px circle | Idle loop |
| Stream card attribution | 24px circle | Static |
| Remark card | 48px circle | Idle / decision animation |
| Drill-down panel header | 64px circle | Static or idle loop |
| Receipt card | 80px | Static, expression matches result |
| Video clip (inline) | Full width, 16:9 | 3-8 second Kling video |

---

## Animation Library

Jaromelu has a focused library of ~15-20 clips covering the full emotional range:

**Idle / ambient**
- Idle loop (2-3s, looping) — default state
- Thinking/reviewing (3-5s, looping) — active analysis
- Yawn/glance (3-5s) — long-idle easter egg

**Decision moments**
- Confident call (3-5s) — making The Call
- Pointing at camera (2-3s) — crowd callout
- Dismissive wave (2-3s) — overriding self-doubt

**Outcomes**
- Smirk / lean back (3-5s) — correct call
- Grimace / shrug (3-5s) — wrong call
- Head in hands (5-8s) — spectacular miss

**Self-aware moments**
- Looking off-camera (2-3s) — internal Critic moment ("I almost talked myself out of it")
- Slight nod (1-2s) — agreeing with the numbers
- Browsing / scrolling (3-5s, looping) — Scout mode visible (the recon segment)

**Cost estimate:** ~$1/8s on Kling. Library of ~20 clips averaging 3s each ≈ ~$8. One-time production cost.

### Fallback: Static Portraits

Before video is produced, the system uses static portrait variants (neutral, confident, smirk, grimace, head-in-hands, thinking). These swap based on context — no animation, but expression changes carry character.

---

## Attribution in the Stream

Every card is authored by Jaromelu. Attribution is compact: avatar + name + timestamp, top-left of the card.

```
🎤 Jaromelu · 20m ago
"I've seen enough. Selling."
```

For internal-process narration (research updates, analysis snapshots, pre-call reasoning), the same Jaromelu attribution applies — voiced in the appropriate internal mode.

```
🎤 Jaromelu · 3h ago
"Found three new takes on Cleary this week. Two say sell."
```

```
🎤 Jaromelu · 1h ago
"Breakeven 42. Last four: 51, 48, 42, 61. Trend's down."
```

```
🎤 Jaromelu · 45m ago
"Two of those sell sources have a 50% accuracy record. I'm not blindly trusting them."
```

The voice shifts mode (research / numbers / skepticism) but the attribution and the face stay constant — one character expressing different facets of his reasoning.

---

## Hierarchy

There is no second character to compare against. The visual hierarchy is **Remark cards (the call) > everything else (process narration)** — both authored by Jaromelu, but Remark cards are larger, with the orange accent more prominent.

| Card type | Author | Visual weight |
|---|---|---|
| Remark (the call) | Jaromelu | Large. Orange left border. Bold voice text. Hero. |
| Process narration | Jaromelu | Compact. Zinc left border. Standard text weight. Supporting. |

---

## Recon: Jaromelu Visibly Browsing

When Jaromelu is in active source-discovery mode, the UI surfaces this as a visible activity:

- Avatar status: "Investigating new sources"
- Browsing / scrolling animation plays
- A live activity stream shows what he's looking at: current search query, page being fetched, candidate just spotted
- Each judgement publishes as a Jaromelu-authored card ("Found a new pod — 'Tackles and Tinnies' — three episodes deep, mentions Munster a lot")

This is the only place the *process* of recon is rendered visibly. Internally it's the Scout function (see [agents/crew/scout.md](../agents/crew/scout.md)), but on screen it's always Jaromelu.

---

## Implementation

The canonical implementation is `services/web/src/app/components/JeromeluPresence.tsx` (single-character presence with avatar, live status pill, expandable activity timeline). Status data comes from `GET /api/jaromelu/status` (single-Jaromelu shape — aggregates internal-mode telemetry into one status). Round overview at `GET /api/round/{n}` no longer includes per-internal-mode breakdowns; activity log is rendered as a single Jaromelu-authored timeline.

## Related

- [`../agents/crew/jaromelu.md`](../agents/crew/jaromelu.md) — voice, behavioural rules, persona
- [`../agents/crew/dynamics.md`](../agents/crew/dynamics.md) — internal reasoning patterns

# Design Principles

## The Show Is On

You never land on a homepage. You land in the middle of the show. The crew is working. Something is happening. An unresolved thread is hanging. A Remark is forming.

Every design decision flows from this: **the audience arrives mid-episode, not at a front door.**

No welcome hero. No feature tour. No "Sign up to get started." Just — the show is already running, and you walked in.

---

## One Screen

There is one screen. The Stream. Everything the audience needs is here or reachable from here.

Squad details, player dossiers, the ledger, the alignment index — these are **contextual panels** that slide in when you tap something in the Stream. They are not pages. There is no navigation bar. There is no sitemap.

The mental model is a live broadcast, not a website. You don't navigate a broadcast. You watch it, and occasionally lean in to look at something more closely.

**Rule:** If you're tempted to create a new page, make it a panel instead. If you're tempted to create a panel, ask whether the information should just be inline in the Stream.

---

## The Rhythm Is the UI

The Stream doesn't look the same on Monday as it does on Thursday. The visual density, pacing, and emphasis shift with the episode arc.

| Beat | Stream Feel |
|------|-------------|
| Intel Drops (Mon) | Busy. Rolling updates. Scout activity stacking up. High information density. |
| Tension Builds (Tue–Wed) | Threading. Contradictions highlighted. Open questions visible. Analyst working. |
| The Call (Thu) | Sparse. One big Remark dominates the screen. The moment of commitment. |
| The Match (Sat–Sun) | Live. Locked Remarks resolving. Outcomes appearing. |
| The Reckoning (Mon) | Retrospective. Receipts. Grades. The loop closing. |

The audience doesn't need to be told what beat the show is on. They feel it. The screen tells them.

---

## Mobile First, Actually

The primary audience is an NRL fan on their phone. On the bus. On the couch. Checking in for 90 seconds between tasks.

This isn't "responsive design" — it's **phone-native design that scales up to desktop.** The Stream is a single column. Drill-down panels are full-screen overlays on mobile, side panels on desktop. Interactions are tap-sized.

Desktop gets more room for panels to sit alongside the Stream. It doesn't get a fundamentally different layout.

---

## The Moment Worth Sharing

Every Remark should be screenshottable. Every receipt card should be sendable. The unit of virality is not "the site" — it's a single Remark that someone sends to their SuperCoach group chat.

Design implications:
- Remark cards must look good in isolation (cropped screenshot)
- Receipt cards are purpose-built for sharing (clean, bold, includes context)
- The site URL is visible but not dominant — the content speaks for itself
- Aspect ratios should work in iMessage previews, Twitter cards, Instagram stories

**Rule:** Before finalising any Remark or receipt design, screenshot it on a phone and send it to yourself. If it doesn't make sense without the surrounding page, redesign it.

---

## Show the Work

The crew's process is the spectacle. The audience wants to see *how* the analysis got made, not just the result.

- Scout's findings are visible, not hidden behind an API
- Analyst's contradictions are highlighted, not silently resolved
- The Critic's challenge appears before Jeromelu's final call
- Evidence trails are expandable on every Remark
- The Archivist's historical references are inline

Transparency is entertainment. "12 podcast hours compressed into 4 Remarks" is the value proposition — but only if you can see the compression happening.

---

## Less Is Louder

When Jeromelu makes The Call on Thursday, the Stream should feel different. Quieter. More space. One Remark, big and bold.

Conversely, during Intel Drops, the Stream is alive with Scout activity — fast-moving, dense, lots of small updates.

**The amount of whitespace is a storytelling tool.** Sparse = important. Dense = building. The audience reads the rhythm unconsciously.

---

## Voice Everywhere

Every piece of text on the screen has a speaker. Nothing is "system copy."

- Loading state: "Analyst is thinking..." (not "Loading...")
- Empty state: "Scout hasn't found anything yet. Give it time." (not "No data available")
- Error state: "Something broke. Even the best crews have bad days." (not "500 Internal Server Error")
- Timestamps are contextual: "3 hours ago" not "2026-03-28T14:32:00Z"

If text appears on screen and you can't attribute it to a crew member, it shouldn't be there.

---

## Visual Language

The existing visual foundation:

| Token | Value | Usage |
|-------|-------|-------|
| Background | `#0c0c0f` | Near-black, the "stage" |
| Foreground | `#ededed` | Light gray, primary text |
| Accent | `#F58220` | Tigers orange, all interactive/highlight elements |
| Accent glow | `rgba(245, 130, 32, 0.4)` | Hover states, active indicators, emphasis |
| Gray scale | Zinc (`#18181b` → `#a1a1aa`) | Cards, borders, secondary text, hierarchy |
| Fonts | Geist Sans / Geist Mono | Body / data and timestamps |

The dark background is the stage. Orange is the spotlight. Everything else recedes.

---

## Principles Summary

1. **The show is on** — arrive mid-episode, not at a front door
2. **One screen** — the Stream is the product; everything else is a drill-down
3. **The rhythm is the UI** — density and pacing shift with the episode arc
4. **Mobile first** — phone on the bus is the primary context
5. **The moment worth sharing** — every Remark is screenshottable
6. **Show the work** — the crew's process is the spectacle
7. **Less is louder** — whitespace is a storytelling tool
8. **Voice everywhere** — every piece of text has a speaker

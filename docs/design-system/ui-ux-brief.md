---
tags: [area/design-system]
---

# UI/UX Design Brief

> Created: 2026-05-07. Living document — a starter pack for designers exploring UI/UX. Each section is a summary; deeper specs live in linked docs.

If you're starting fresh on Jaromelu's design, read this end-to-end first. Then go deep into the specific areas you're working on.

---

## 1. Who You're Designing For

Hardcore NRL fans who consume heavy amounts of NRL commentary — podcasts, YouTube panels, post-match shows. Above-average game literacy. Australian, predominantly male. Time-poor, opinion-saturated, decision-fatigued.

They're on their phone, on the bus, on the couch — checking in for 90 seconds at a time. They want fast synthesis, not more content.

**Not designing for:** casual NRL viewers.

→ [Venture Thesis §Who Finds This Irresistible](../architecture/01-venture-thesis.md#who-finds-this-irresistible)

## 2. What You're Designing Toward

A presence that **feels alive** — a non-human commentator with opinions, a voice, and a public track record, who lives in his own digital home. The reaction we're chasing: *"Wait — this thing actually has takes."*

The website is **the digital home** — a place Jaromelu lives, not a dashboard you visit. The visual language, editorial voice, and weekly rhythm all serve this single feeling.

→ [Venture Thesis §What We Want People To Feel](../architecture/01-venture-thesis.md#what-we-want-people-to-feel)

## 3. Hard Constraints (V1)

- **Mobile first.** Phone-native, scales up to desktop. Single column on mobile. Drill-downs are full-screen overlays on mobile, side panels on desktop.
- **Text-led, no animated avatar.** Pre-generated video clips were tried and parked — too slow, too expensive, would tire users at show volume. Static portrait variants may still appear; the animation library is on hold until generative video gets cheaper.
- **Single character on screen.** The internal "crew" (Scout, Analyst, Critic, Bookkeeper, Archivist) is *internal reasoning*, not separate visible characters. **Every card is authored by Jaromelu.** Semantic colours indicate which internal mode he was operating in.
- **Episode-arc rhythm.** The Stream looks different on Monday than on Thursday. Whitespace and density are storytelling tools, not just layout.
- **Mid-episode entry.** No homepage, no welcome, no feature tour. Users land in the middle of the show.

→ [Design Principles](../concepts/00-design-principles.md), [Crew Presence](../concepts/05-crew-presence.md)

## 4. The Five Surfaces

| Surface | Role | URL |
|---|---|---|
| **The Feed** | The spine — live, rewindable view of crew activity, Remarks, and audience interaction | `/` |
| **The Wiki** | Editorial reference — per-entity prose pages maintained by Jaromelu (light theme, serif) | `/wiki` |
| **The Ledger** | Prediction tracking + accountability — every Remark to resolution, plus the Alignment Index | `/ledger` |
| **The Analysis** | Long-form articles — round tips, trade targets, captain picks (richer when SC spoke ships) | `/insights` |
| **Ask Me** | Chat with Jaromelu in his voice; also embedded in the Feed as contextual chat | `/ask` |

The Feed *is* the product. The other four are reachable from the Feed and reward deeper interest. **If you're tempted to create a new page, make it a panel instead.**

→ [The Show §The Surfaces](../architecture/02-the-show.md#the-surfaces), [pages/](../pages/)

## 5. Design Principles

1. **The show is on** — arrive mid-episode, not at a front door
2. **One screen** — the Stream is the product; everything else is a drill-down
3. **The rhythm is the UI** — density and pacing shift with the episode arc
4. **Mobile first** — phone on the bus is the primary context
5. **The moment worth sharing** — every Remark is screenshottable
6. **Show the work** — the process of reasoning is the spectacle
7. **Less is louder** — whitespace is a storytelling tool
8. **Voice everywhere** — every piece of text has a speaker

→ [Design Principles (concepts/00)](../concepts/00-design-principles.md)

## 6. Visual Language

**Metaphor:** A live broadcast from a warm room. The dark base is rich brown, not black — visible warmth, comfortable seat in a dimly-lit studio.

**Stream theme (dark, main app):**

| Token | Value | Role |
|---|---|---|
| Background | `#2a2420` | Warm brown-charcoal — the stage |
| Foreground | `#ede4d6` | Warm cream — primary text |
| Accent (Ember) | `#d4874a` | Jaromelu's voice, CTAs, glow |
| Teal / Slate / Lilac / Red / Ochre | semantic | Internal-mode tints (Scout / Analyst / Bookkeeper / Critic / Archivist) |
| Body / Data fonts | Geist Sans / Geist Mono | |

**Wiki theme (light, editorial):**

A deliberate departure from the broadcast stage. Warm off-white (`#FAF9F5`), serif typography (Cormorant Garamond / Georgia), burnt-orange accent (`#b85c38`). The wiki *reads*. The Stream *watches*.

→ [Theme & Style Guide](theme-and-style.md)

## 7. Editorial Voice

Every piece of text on screen has a speaker. **Nothing is "system copy."** All voice flows in Jaromelu's first person — even when reporting internal-function activity.

| State | Pattern | Example |
|---|---|---|
| Loading | First-person status — Jaromelu's current internal mode | "Cross-referencing claims..." / "Doing the math on Cleary..." |
| Empty | Acknowledged in voice | "Nothing new from the pods this week. Give it time." |
| Error | Owned in voice | "Something broke. Even the best crews have bad days." |
| Timestamps | Relative, conversational | "3 hours ago" not "2026-03-28T14:32:00Z" |
| Nav labels | Editorial naming, never database-speak | "The Wiki" / "The Ledger" — not "Knowledge Base" / "Predictions" |

If you can't attribute a line to Jaromelu, it doesn't belong on screen.

→ [Design Principles §Voice Everywhere](../concepts/00-design-principles.md#voice-everywhere), [Theme & Style §Voice in UI Copy](theme-and-style.md#voice-in-ui-copy)

## 8. Reference Moments

**The Remark** is the atomic unit — an opinionated, voiced position Jaromelu puts his name on.

```
JAROMELU                    ● OPEN
"Cleary is overpriced this week.
 Three sources sold, one bought.
 I'm selling. The matchup against
 Melbourne is a trap."

[SELL]  [Cleary]  [High conviction]

▸ Evidence trail (3 sources, 5 claims)

👍 142 agree · 👎 89 disagree · 62% agree
[Agree]   [Disagree]              [Share ↗]
```

States: `OPEN → LOCKED → RESOLVED`. Resolution generates a **receipt card** — purpose-built for screenshots, group chats, social sharing. The voice text is the hero; it must look good cropped.

**Conviction scales the visual.** Low conviction = muted card. Medium = orange border. High = bold border, slight glow, the card demands attention. Without the animated avatar, conviction has to land through typography, weight, and motion of the surrounding context.

**Jaromelu's persistent presence** anchors the header — a portrait pill with status text reflecting his current internal mode ("Cross-referencing claims", "Sleeping on a call", "On the call: SELL Cleary"). The status string is always first-person.

→ [Remarks](../concepts/02-remarks.md), [Crew Presence (Jaromelu's avatar / status)](../concepts/05-crew-presence.md), [Episode Beats](../concepts/03-episode-beats.md)

## 9. What This Is NOT (Anti-Patterns)

- **No homepage.** Users land mid-episode. No welcome hero, no feature tour, no "Sign up to get started."
- **No system copy.** Loading, empty, and error states all speak in Jaromelu's voice.
- **No multiple visible characters.** The internal crew is internal — only Jaromelu appears on screen.
- **No top nav with a sitemap.** Drill-downs slide in over the Stream; they're not separate pages with chrome.
- **No neutral summaries.** Jaromelu has a position on every call; "Sources are split on Cleary" is not a Remark.
- **No raw-data dashboards.** Compressed, voiced opinion is the value; raw stats are not.
- **No ISO timestamps in user-facing copy.** Conversational time only ("3 hours ago").

→ [The Show §What This Is Not](../architecture/02-the-show.md#what-this-is-not)

## 10. Open Questions for Design Exploration

Worth playing with as you explore — these are unresolved, and good design here will shape the product:

- **How does Jaromelu's "presence" feel without an animated avatar?** What carries the alive feeling — status text, microcopy, motion of the surrounding context, the rhythm of arrivals?
- **How does the Stream visually shift across the episode arc?** Mon dense-and-busy → Thu sparse-and-bold → Mon retrospective. What changes between beats — density, palette weight, sound, emphasis?
- **What does a "high conviction" Remark look like without video?** Typography? Border weight? Glow? Layout dominance?
- **Receipt cards** — meme-format, screenshottable, must work in iMessage/Twitter/Instagram previews. What's the visual format that travels furthest from the home site?
- **First-time visitor confusion vs return-visit familiarity.** A newcomer needs context; a regular needs to skip it. How do we serve both without a homepage?

---

## Related (deeper reading)

**Strategic frame:**
- [Venture Thesis](../architecture/01-venture-thesis.md)
- [The Show](../architecture/02-the-show.md)
- [Knowledge Asset](../architecture/03-knowledge-asset.md)

**Design rules and tokens:**
- [Design Principles](../concepts/00-design-principles.md)
- [Theme & Style Guide](theme-and-style.md)

**Surface-level concepts:**
- [The Stream](../concepts/01-the-stream.md)
- [Remarks](../concepts/02-remarks.md)
- [Episode Beats](../concepts/03-episode-beats.md)
- [Drill-Downs](../concepts/04-drill-downs.md)
- [Crew Presence](../concepts/05-crew-presence.md)
- [Audience](../concepts/06-audience.md)
- [First Run](../concepts/07-first-run.md)

**Per-page specs:**
- [pages/feed/](../pages/feed/overview.md), [pages/wiki/](../pages/wiki/overview.md), [pages/ledger/](../pages/ledger/overview.md), [pages/analysis/](../pages/analysis/overview.md), [pages/ask-me/](../pages/ask-me/overview.md)

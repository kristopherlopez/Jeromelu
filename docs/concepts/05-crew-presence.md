# Crew Presence

The crew is always present. Even when nothing is happening, the audience can see who's dormant, who last acted, and who's about to wake up. The crew *is* the interface.

---

## The Crew Bar

The Crew Bar is the only persistent UI element besides the Interaction Bar. It replaces the traditional site header. There is no logo, no nav, no hamburger menu.

### Anatomy

A horizontal strip of crew member **avatar portraits**, fixed to the top of the viewport. Each slot is a 32px circular portrait with name and optional status.

```
[👤 Scout — Scanning 4 new episodes]   [👤 Analyst]   [👤 Critic]   [👤 Bookkeeper]   [👤 Archivist]   [👤 Jaromelu — Reviewing]
```

### Avatar States

**Active**
- Avatar is full colour, playing an idle animation loop (breathing, slight movement, eyes scanning)
- Pulsing orange ring around the portrait
- Name + status text visible
- Example: Scout's avatar is animated, head turning as if scanning. Status: "Scanning 4 new episodes"

**Dormant**
- Avatar is desaturated/dimmed. Static image (no animation). Slightly smaller or recessed.
- Name only on desktop. Hidden on mobile (collapsed into overflow).
- Tap/hover reveals a personality card tooltip:
  ```
  ┌─────────────────────────────┐
  │ [👤 Analyst portrait]      │
  │ Knowledge Resolver          │
  │                             │
  │ Last: Cross-referenced      │
  │ Round 6 claims · 2h ago    │
  │                             │
  │ Next: Activates when Scout │
  │ delivers Round 7 intel     │
  └─────────────────────────────┘
  ```

**Waking Up** (transition: dormant → active)
- The avatar plays a brief "wake" animation (1-2 seconds): colour returning, eyes opening, head turning to face camera
- The orange ring fades in
- Status text appears alongside

**Completing** (transition: active → dormant)
- Avatar plays a brief completion animation: satisfied nod, checkmark gesture
- Status text briefly shows completion: "Done. 4 episodes collected."
- Colour desaturates. Animation stops. Fades to dormant.

### Mobile Behaviour

Only show active crew members + Jaromelu. Dormant members collapse into a "+3" overflow showing stacked, tiny, greyed-out avatar faces. Tap to expand.

```
[👤 Scout — Scanning...]   [👤 Jaromelu — Reviewing]   [👤👤👤 +4]
```

### All Dormant State

When the crew is idle between episodes:

All crew avatars are desaturated and static except Jaromelu. His avatar plays a slow idle loop — thinking at his desk, occasionally glancing at camera, reviewing something on a screen. Status: "Squad locked. Watching the market."

Jaromelu is never fully dormant. His avatar is always animated. This maintains the "someone's home" feeling. The audience sees a character, not a status string.

---

## Crew Members

### Visual Identity

Each crew member is a **character with a face**, not an emoji with a label. They have a generated character portrait (static image for base, animated loops via Kling for active states), a visual style, and a personality expressed through micro-animations.

| Crew Member | Role | Visual Style | Character Energy |
|-------------|------|-------------|-----------------|
| Scout | Intelligence | Field operative. Alert eyes. Collar up. Always looking at something off-screen. | Efficient, watchful. Head on a swivel. |
| Analyst | Knowledge | Clean, precise. Glasses optional. Surrounded by data. Thoughtful expression. | Measured, focused. Slight furrowed brow when processing. |
| Critic | Challenge | Arms often crossed. Sceptical eyebrow. Direct eye contact. | Challenging, sharp. Not hostile — rigorous. |
| Bookkeeper | Numbers | Neat, orderly. Calculator energy. Neutral expression. | Precise, unemotional. The numbers are the numbers. |
| Archivist | History | Slightly older feel. Surrounded by records. Knowing look. | Patient, long-memory. Has seen this before. |
| Jaromelu | The Call | The front man. Confident posture. Leans toward camera. Orange accent in his visual design. | Cocky, self-aware. The star of the show. |

### Avatar Sizes

| Context | Size | Format |
|---------|------|--------|
| Crew Bar pill | 32px circle | Static (dormant) or 2-3s idle animation loop (active) |
| Stream card attribution | 24px circle | Static |
| Remark card (Jaromelu) | 48px circle | Idle animation loop |
| Drill-down panel header | 64px circle | Static or idle loop |
| Receipt card | 80px | Static, expression matches result |
| Video clip (inline) | Full width, 16:9 | 3-8 second Kling video |

### Avatar Animation Library

Each crew member has a set of **pre-generated animation clips** stored as short loops or one-shot clips. These are produced once using Kling (or equivalent) and reused across the experience.

**Per crew member (~5-8 clips each):**
- Idle loop (2-3s, looping) — default active state
- Wake up (1-2s, one-shot) — transitioning from dormant to active
- Complete/nod (1-2s, one-shot) — finished their task
- Reaction: positive (2-3s) — something confirmed their work
- Reaction: negative (2-3s) — something contradicted their work

**Jaromelu gets an expanded library (~15-20 clips):**
- Confident call (3-5s) — making The Call
- Smirk/lean back (3-5s) — correct call resolution
- Grimace/shrug (3-5s) — wrong call resolution
- Head in hands (5-8s) — spectacular miss
- Thinking/reviewing (3-5s, looping) — idle during analysis
- Pointing at camera (2-3s) — crowd callout
- Looking at Critic (2-3s) — confrontation scene
- Dismissive wave (2-3s) — overriding the Critic
- Yawn/glance (3-5s) — long idle easter egg

**Cost estimate:** ~$1/8s on Kling. Full library of ~60 clips averaging 3s each = ~$23. One-time production cost.

### Fallback: Static Portraits

Before video clips are produced, the system works with **static portraits with expression variants**. Each crew member has 3-5 portrait images showing different expressions (neutral, positive, negative, focused, idle). These swap based on context — no animation, but the expression changes create character.

Only Jaromelu gets the orange accent. The crew supports; Jaromelu stars. This visual hierarchy reinforces who the front man is.

---

## Crew Attribution in the Stream

Every card in the Stream is attributed to a crew member. The attribution is compact: icon + name + timestamp, top-left of the card.

```
🔍 Scout · 3h ago
Picked up 4 new episodes overnight.
```

```
🧠 Analyst · 1h ago
Cross-referencing complete: 2 sources bullish on Munster, 1 bearish.
```

```
⚖️ Critic · 45m ago
You're selling Cleary on thin evidence. Two of those sources are below 50% accuracy.
```

```
🎤 Jaromelu · 20m ago
"I've seen enough. Selling."
```

### Attribution Hierarchy

Jaromelu's cards are visually distinct from crew cards:
- **Crew cards**: Compact. Zinc left border. Standard text weight. Supporting content.
- **Jaromelu's cards (Remarks)**: Large. Orange left border. Bold voice text. Hero content.

The visual weight tells the audience instantly: crew card = process, Jaromelu card = the call.

---

## Crew Personality in Copy

Voice, tone, and example lines per crew member live in [`agents/crew/`](../agents/crew/README.md) — one file per character. This doc focuses on *presence* (visual identity, avatar library, attribution in the Stream), not what the crew says.

Quick links: [Jaromelu](../agents/crew/jaromelu.md) · [Scout](../agents/crew/scout.md) · [Analyst](../agents/crew/analyst.md) · [Critic](../agents/crew/critic.md) · [Bookkeeper](../agents/crew/bookkeeper.md) · [Archivist](../agents/crew/archivist.md)

---

## The Handoff

The most compelling crew moment is the **handoff** — when one crew member's work feeds into another's, visually connected in the Stream.

### How It Looks

A handoff is shown as a sequence of crew cards with avatars and visual connectors:

```
[👤] Scout · Mon 10:14 PM
Picked up 3 new takes on Cleary from this week's pods.
KingOfSC (SELL), NRLBrothers (SELL), PodcastNRL (BUY).
        │
        ▼
[👤] Analyst · Tue 8:30 AM
Cross-referencing the Cleary claims.
2 selling on matchup data. 1 buying on form.
Contradiction: same data, opposite reads.
        │
        ▼
[👤] Bookkeeper · Tue 10:15 AM
Cleary breakeven: 42. Last 4 scores: 51, 48, 42, 61.
Needs 55+ to justify the hold. Trend is down.
        │
        ▼
[👤] Critic · Thu 9:00 AM
Thin evidence. Two sell sources below 50% accuracy.
The Bookkeeper's numbers are more convincing than the pods.
        │
        ▼
[👤] Jaromelu · Thu 11:00 AM
[REMARK CARD — SELL Cleary]
```

Each crew member's **avatar** (24px) appears alongside their contribution. The vertical connector between entries animates subtly — data flowing downward, a visual representation of information passing between characters.

### When to Show Handoffs

Not every Remark needs the full handoff chain visible. By default, the handoff is collapsed inside the Remark's evidence trail. But during The Call beat, the most important Remark of the round can show the handoff expanded — making the process visible as the climax of the episode.

---

## The Face-Off

When the Critic challenges Jaromelu, the Stream shows a **face-off layout** — two characters visually confronting each other.

### Layout

```
┌─────────────────────────────────────────────────┐
│                                                 │
│  [👤 Critic]              vs       [👤 Jaromelu]│
│                                                 │
│  "Two of your three        "I've watched the    │
│   sell sources are below    tape. The matchup    │
│   50% accuracy. You         is bad. I don't care │
│   sure about this?"         what the accuracy    │
│                              says."              │
│                                                 │
└─────────────────────────────────────────────────┘
```

- Critic's avatar on the left, Jaromelu's on the right. Both at ~48px.
- Critic's text on the left side, Jaromelu's response on the right.
- A "vs" divider between them — subtle but clear.
- The Critic's expression is sceptical (arms crossed, raised eyebrow). Jaromelu's is unflinching (direct eye contact, slight lean forward).

### Video Version

For the most important confrontations, a short video clip (5-8 seconds) plays inline before the text face-off:
- Split screen: Critic on the left, Jaromelu on the right
- Critic shakes head, crosses arms
- Jaromelu dismisses with a hand wave or leans in defiantly
- This is a reusable template — same visual setup, different context each time

### When No Objection

When the Critic has no objection (rare), the face-off format isn't used. Instead, a simple card:

```
[👤] Critic · "The numbers support this. No objection."
```

The Critic's avatar shows a brief nod — the rarest and most notable gesture in the experience. The audience learns: when the Critic agrees, pay attention.

---

## Crew Status Updates

The Crew Bar shows real-time status through avatar animations, but the Stream also shows crew **transition moments** — when a crew member activates, completes, or hands off.

These are compact cards with the crew member's avatar:

```
[👤 Scout waking up] Scout activated · Scanning the ecosystem for Round 7 intel
```

```
[👤 Analyst, focused] Analyst activated · Cross-referencing Scout's findings
```

```
[👤 Critic, arms crossed] Critic activated · Reviewing Jaromelu's proposed calls
```

These act as **stage directions** — they tell the audience the scene is changing. The avatar expression previews the crew member's role: Scout looks alert, Analyst looks focused, Critic looks sceptical.

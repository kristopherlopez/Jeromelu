# Remarks

A Remark is the atomic unit of the entire experience. It is the thing the crew produces. It is the thing the audience interacts with. It is the thing that gets shared. Everything in the Stream either builds toward a Remark or resolves one.

---

## What a Remark Is

A Remark is an opinionated, voiced analytical piece that Jaromelu puts his name on publicly. It is built from the crew's resolved knowledge — claims cross-referenced, contradictions weighed, evidence assembled — and delivered in Jaromelu's voice.

A Remark is **not**:
- A data point ("Cleary scored 85 last week")
- A log entry ("Ingestion pipeline completed")
- A neutral summary ("Sources are split on Cleary")
- A long-form article or blog post

A Remark **is**:
- A punchy, opinionated position with evidence behind it
- Something you can agree or disagree with
- Something that resolves into a receipt

---

## A Remark Is a Performance

A Remark doesn't just appear in the Stream. It **arrives**. Jaromelu is making a public call, putting his reputation on the line. The UI should make that feel like a moment, not a card rendering.

### Entry Animation

When a new Remark enters the Stream:

1. **Jaromelu's avatar slides in** from the left — full size (~48px), full colour.
2. For **high conviction Remarks**: A short **video clip** (3-5 seconds) plays inline first — Jaromelu leaning in, looking at camera, confident. The clip is from the reusable reaction library, not generated per Remark.
3. The **voice text types out** phrase by phrase — fast enough to feel punchy (not tedious character-by-character). Think: 2-3 words appearing at a time, full text visible in ~3 seconds. This creates the sensation of Jaromelu *speaking*, not text *rendering*.
4. **Tags fade in** after the voice text completes — position, subject, conviction.
5. **Evidence trail and reaction bar** appear last, sliding up from below.

The whole entry takes ~4-6 seconds. It's quick but theatrical. The Remark announces itself.

### Low Conviction vs High Conviction

The entry animation scales with conviction:

- **Low**: No video clip. Avatar appears. Text fades in (no typewriter). Quick, understated. "Slight lean."
- **Medium**: Avatar slides in. Text types out. Standard Remark entrance.
- **High**: Video clip plays first. Avatar is larger. Text types out with slightly more dramatic pacing. The card has a subtle glow. The Crew Bar briefly highlights Jaromelu. **This is the moment.**

---

## Remark Anatomy

```
┌─────────────────────────────────────────────────┐
│  ┌──────┐                                       │
│  │      │  JAROMELU                  ● OPEN     │
│  │  👤  │                                       │
│  │      │  "Cleary is overpriced this week.     │
│  └──────┘   Three sources sold, one bought.     │
│             I'm selling. The matchup against    │
│             Melbourne is a trap — his last two  │
│             against the Storm: 42 and 51.       │
│             The market hasn't priced this in."  │
│                                                 │
│  ┌──────────┐ ┌──────────┐ ┌───────────────┐   │
│  │ SELL     │ │ Cleary   │ │ High conviction│   │
│  └──────────┘ └──────────┘ └───────────────┘   │
│                                                 │
│  ▸ Evidence trail (3 sources, 5 claims)         │
│  ▸ Critic's take: [👤 avatar] "Thin evidence.  │
│    Two of those sources are below 50%."         │
│                                                 │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━   │
│  👍 142 agree  ·  👎 89 disagree    62% agree   │
│                                                 │
│  [Agree]        [Disagree]           [Share ↗]  │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Elements

| Element | Description |
|---------|-------------|
| **Avatar** | Jaromelu's character portrait (~48px). Plays a subtle idle loop within the card. For high conviction: slightly larger with orange glow ring. |
| **Attribution** | "JAROMELU" alongside the avatar. Top-left. |
| **Status badge** | OPEN / LOCKED / RESOLVED. Top-right. Colour-coded. |
| **Voice text** | The Remark itself. First-person. Opinionated. 2-5 sentences. Large, bold, oversized quote marks in orange. This is the headline — it must be good enough to screenshot. |
| **Position tag** | BUY / SELL / HOLD / CAPTAIN / AVOID. Colour-coded chip. |
| **Subject tag** | The player, team, advisor, or round the Remark is about. Tappable — opens Wiki panel. |
| **Conviction tag** | LOW / MEDIUM / HIGH. Visual intensity scales with conviction. High conviction pulses. |
| **Evidence trail** | Expandable. Shows the claims, sources, and crew activity that built this Remark. Each crew member's avatar appears alongside their contribution. |
| **Critic's take** | Optional. The Critic's avatar appears alongside their dissent — a visual face-off between two characters within the card. |
| **Reaction bar** | Aggregate agree/disagree counts + percentage. Shows crowd sentiment. |
| **Action buttons** | Agree, Disagree, Share. Primary interaction affordances. |

---

## Remark States

### Open

The Remark has been published. The round hasn't started. The audience can react.

**Visual:**
- Orange left border (accent highlight)
- Status badge: `● OPEN` in orange
- Jaromelu's avatar plays a confident idle loop within the card — slight lean, occasional glance at camera
- Reaction buttons active
- Conviction tag pulses subtly on high-conviction Remarks
- Background slightly elevated from the Stream

**Behaviour:**
- Agree/Disagree buttons are active
- Crowd sentiment updates in real time
- Evidence trail is expandable
- Share generates a "pre-game" receipt card

### Locked

The round has started. The call is on the record. No more reactions.

**Visual:**
- **Lock animation**: A brief visual "seal" effect plays — a lock icon stamps onto the card, the orange border shifts to amber, the card slightly darkens. Jaromelu's avatar shifts expression to a calm, committed look. The Remark has been committed.
- Status badge: `◆ LOCKED` in amber
- Reaction buttons disabled (counts still visible)
- The card feels closed, committed — subtly darker, more static
- Optional countdown to resolution if match time is known

**Behaviour:**
- No new reactions accepted
- Existing crowd sentiment frozen and displayed
- Share still works — "This call is locked in. Waiting for the result."

### Resolved

The round is over. Outcomes are in. The Remark has been graded. The resolution is a **moment**, not just a badge change.

**Resolution Animation — Correct:**
1. A brief green flash across the card border
2. A short **video clip** (3-5 seconds) of Jaromelu plays — smirking, leaning back, the victor. From the reusable clip library.
3. Status badge animates in: `✓ CORRECT` in green
4. Outcome data slides in below: "Cleary scored 42. Sold at the right time."
5. Postmortem text types out: "Told you. The Storm matchup was a trap."
6. Receipt card auto-generated with a "share this" prompt

**Resolution Animation — Wrong:**
1. A brief red tint across the card border (muted, not aggressive)
2. A short **video clip** of Jaromelu — grimacing, shrugging, owning it. Self-deprecating but not defeated.
3. Status badge: `✗ WRONG` in muted red
4. Outcome data: "Cleary scored 95. Well. That happened."
5. Postmortem types out: "Variance. The process was sound. The Storm just forgot how to defend."
6. Receipt card still generated — owning the miss is content too

**Resolution Animation — Mixed:**
- A brief amber tint. Jaromelu's avatar shows a "hmm, close" expression.
- Status badge: `~ MIXED` in zinc/grey
- Jaromelu's take on why it's a push

---

## Evidence Trail (Expanded)

When the user taps "Evidence trail", the Remark card expands to show the full lineage:

```
▾ Evidence trail

  [👤] Scout · Tue 8:14 AM
  "Picked up 3 new takes on Cleary from this week's pods"

  [👤] Bookkeeper · Tue 10:30 AM
  "Cleary breakeven: 42. Needs 55+ to justify price.
   Last 4 weeks: 51, 48, 42, 61. Trending down."

  [👤] Analyst · Wed 2:15 PM
  "3 sources selling Cleary (KingOfSC, NRLBrothers, SCPlaybook).
   1 source buying (PodcastNRL). Consensus: bearish.
   Contradiction: PodcastNRL cites form, others cite matchup."

  [👤] Critic · Thu 9:00 AM
  "Two of the three sell sources are below 50% on the
   Alignment Index this season. Thin evidence."

  [👤] Archivist · Thu 9:05 AM
  "Last time Jaromelu sold Cleary against consensus:
   Round 3. Cleary scored 38. Correct call."

  [👤] Jaromelu · Thu 11:00 AM
  "I've seen enough. Selling."
```

Each crew member's **avatar** (small, ~24px) appears alongside their contribution. The evidence trail reads like a conversation between characters, not a log of system events. Vertical connector lines between entries visualise the information flowing from one crew member to the next — the handoff chain made visible.

This is the full story of how the Remark got made. The audience can follow the reasoning chain from raw intel to final call — and see every character who participated.

---

## Conviction Visual

Conviction is not just a label — it scales the visual intensity of the Remark.

| Conviction | Visual Treatment |
|------------|-----------------|
| **Low** | Standard card. Muted border. Normal text weight. "Slight lean." |
| **Medium** | Orange border. Normal text weight. Standard Remark appearance. |
| **High** | Bold orange border. Slightly larger voice text. Subtle glow. Conviction tag pulses. The card demands attention. |

High conviction Remarks are the ones the audience watches for. They're the bold calls that create the best entertainment — spectacular when right, memorable when wrong.

---

## Receipt Cards (Shareable)

When a Remark resolves, a receipt card is generated. This is a purpose-built shareable image optimised for screenshots, iMessage, Twitter, Instagram stories.

### Receipt Card Layout

The receipt card features **Jaromelu's character portrait** prominently — this is a meme-format shareable designed for group chats.

```
┌─────────────────────────────────────┐
│                                     │
│  ┌──────┐                          │
│  │      │  JAROMELU CALLED IT  ✓  │
│  │  👤  │  [smirking expression]   │
│  │      │                          │
│  └──────┘                          │
│                                     │
│  "Cleary is overpriced.             │
│   The Storm matchup is a trap."     │
│                                     │
│  SELL · Cleary · Round 6            │
│  Conviction: HIGH                   │
│                                     │
│  Result: Cleary scored 42    ✓     │
│                                     │
│  62% of the crowd disagreed.        │
│                                     │
│  jeromelu.com                       │
│                                     │
└─────────────────────────────────────┘
```

Jaromelu's avatar expression matches the result: smirk for correct, grimace/shrug for wrong.

### Wrong Call Receipt

```
┌─────────────────────────────────────┐
│                                     │
│  ┌──────┐                          │
│  │      │  JAROMELU MISSED    ✗   │
│  │  👤  │  [shrug expression]      │
│  │      │                          │
│  └──────┘                          │
│                                     │
│  "Cleary is overpriced."            │
│                                     │
│  SELL · Cleary · Round 6            │
│                                     │
│  Result: Cleary scored 95    ✗     │
│                                     │
│  "Variance. The process remains     │
│   elite."                           │
│                                     │
│  jeromelu.com                       │
│                                     │
└─────────────────────────────────────┘
```

Both correct and wrong receipts are designed as **meme-format shareables** — Jaromelu's face + the call + the result. No additional context needed. A group chat member who has never visited the site understands it instantly.

### Design Requirements

- Fixed aspect ratio: 4:5 (Instagram-native) or 16:9 (Twitter/YouTube-native)
- Dark background (#0c0c0f), orange accent
- Readable at phone screenshot resolution
- Includes site URL but not aggressively branded
- The voice text is the hero — it should be the largest element
- Works as both a static image and an Open Graph card (for link previews)

---

## Remark Interactions

### Agree / Disagree

- Binary reaction. One tap. Can be changed before lock.
- Updates crowd sentiment bar in real time.
- Contributes to the user's personal Alignment Index score.
- After resolution: users who agreed/disagreed are told whether they were right.

### Share

- Generates a receipt card (see above).
- Pre-game (Open state): "Jaromelu is calling SELL on Cleary. Do you agree?"
- Post-game (Resolved state): "Jaromelu called it." / "Jaromelu missed."
- Copy link, or share directly to platform.

### Tap Subject

- Tapping a player/team/advisor/round name opens the Wiki drill-down panel.
- The Wiki panel shows everything the crew knows about that entity, with a link into the full wiki page.

### Tap Evidence Trail

- Expands the Remark card inline to show the full crew lineage.
- Collapsible. Defaults to collapsed.

### Ask About This Remark

- From the Interaction Bar, when viewing a Remark: "Ask about this call..."
- Questions are contextual — Jaromelu knows which Remark the user is referring to.
- Response appears as a Dialogue Card in the Stream, linked to the Remark.

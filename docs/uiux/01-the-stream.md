# The Stream

The Stream is the entire product. One screen with three persistent zones stacked vertically. The audience never leaves this screen — they scroll, tap, and drill down, but they are always in the Stream.

---

## Screen Layout

```
┌─────────────────────────────┐
│        CREW BAR             │  ← Fixed top. Always visible.
├─────────────────────────────┤
│                             │
│                             │
│        THE STREAM           │  ← Scrollable. The show.
│                             │
│                             │
│                             │
├─────────────────────────────┤
│     INTERACTION BAR         │  ← Fixed bottom. Always visible.
└─────────────────────────────┘
```

### On Desktop (≥1024px)

The Stream occupies the centre column. Drill-down panels open to the right as a side panel, giving a split-view: Stream on the left, panel on the right.

```
┌──────────────────────────────────────────────┐
│                  CREW BAR                    │
├──────────────────────┬───────────────────────┤
│                      │                       │
│     THE STREAM       │    DRILL-DOWN PANEL   │
│                      │    (when open)        │
│                      │                       │
├──────────────────────┴───────────────────────┤
│              INTERACTION BAR                 │
└──────────────────────────────────────────────┘
```

### On Mobile (<1024px)

Full-width single column. Drill-down panels are full-screen overlays that slide up from the bottom, dismissable by swipe-down or tap on the backdrop.

---

## Zone 1: Crew Bar

Fixed to the top of the viewport. Not a status ticker — a **row of characters**. The crew is visually present.

### Layout

A horizontal row of crew member **avatar portraits** with status. Each slot shows a small circular avatar (the crew member's face/character image) alongside their name and activity.

```
[👤 Scout — Scanning 4 new episodes]   [👤 Analyst]   [👤 Critic]   [👤 Bookkeeper]   [👤 Archivist]   [👤 Jeromelu — Reviewing]
```

- **Active**: Avatar is full colour with a subtle idle animation (breathing, slight head movement — a 2-3 second Kling loop). Pulsing orange ring around the portrait. Name + status text visible.
- **Dormant**: Avatar is desaturated/dimmed. No animation. Static portrait. Tap/hover to see last action and next scheduled run.
- **Transition — Wake up**: When a crew member activates, their avatar plays a brief "wake" animation — eyes opening, head turning to camera, colour returning. This is a micro-moment: Scout just woke up and the audience *sees* it.
- **Transition — Complete**: Avatar plays a brief nod or checkmark gesture, then fades to dormant.

### Behaviour

- On mobile: only show active crew members + Jeromelu. Dormant members collapse into a "+3" overflow indicator showing stacked greyed-out avatars. Tap to expand.
- The bar is ~48px tall — enough for small circular portraits (~32px diameter).
- When all crew are dormant: Jeromelu's avatar plays a slow idle loop (thinking, glancing at camera, occasionally checking something). His status text: "Squad locked. Watching the market."
- Jeromelu is never fully dormant. His avatar is always animated, even if subtly. This maintains the "someone's home" feeling.

### No Logo, No Nav

The Crew Bar replaces traditional site header/navigation. There is no logo, no hamburger menu, no nav links. The crew *is* the header. The show *is* the navigation. The row of character faces is more memorable than any logo.

If someone needs to reach the Squad, Dossier, or Ledger, they tap references in the Stream. There is no persistent nav to these surfaces.

---

## Zone 2: The Stream

The main content area. Scrollable. Latest content at the bottom (Twitch-style — new content appears below, pushing older content up).

### Content Types

Three types of content interleave in the Stream:

**1. Crew Activity Cards**
Small, compact. Attributed to a crew member. Show the process.

```
┌─────────────────────────────────────┐
│ [👤] Scout                  3h ago │
│ Picked up 4 new episodes overnight │
│ 2 mention Cleary, 1 deep-dive on   │
│ Munster                             │
└─────────────────────────────────────┘
```

- **Avatar thumbnail** (24px) of the crew member on the left, alongside name and timestamp.
- Left border coloured by crew member (subtle differentiation).
- Compact — max 3 lines. Expandable if there's more detail.
- **Entry animation**: Cards slide in from the left with a brief fade. During Intel Drops, cards stack up fast — the animation is quicker, creating a sense of urgency.
- These stack quickly during Intel Drops but thin out during other beats.

**2. Remark Cards**
Large, prominent. The hero content. Always attributed to Jeromelu. A Remark is a **performance**, not a card. See [02-remarks.md](02-remarks.md) for full spec.

```
┌─────────────────────────────────────────┐
│  ┌────┐                                │
│  │ 👤 │  JEROMELU              OPEN    │
│  │    │                                │
│  └────┘  "Cleary is overpriced this    │
│          week. Three sources sold, one  │
│          bought. I'm selling. Here's   │
│          the matchup case."            │
│                                         │
│  SELL · Cleary · High conviction        │
│                                         │
│  ▸ Evidence trail (3 sources)           │
│                                         │
│  👍 142 agree  ·  👎 89 disagree       │
│                                         │
│  [Agree]  [Disagree]  [Share]           │
│                                         │
└─────────────────────────────────────────┘
```

- **Jeromelu's avatar** appears at full size (~48px) alongside the Remark.
- **Entry animation**: Jeromelu's avatar slides in from the left. The voice text types out with a fast typewriter effect (not character by character — phrase by phrase, fast enough to feel punchy, not tedious). Tags fade in after. The card announces itself.
- **High conviction Remarks**: A short **video clip** (3-5 seconds) of Jeromelu delivering the call plays inline above the card — leaning in, confident, looking at camera. This is the "he's actually here" moment.
- Remark cards take up significantly more vertical space than activity cards.
- During The Call beat, a single Remark may dominate most of the viewport.
- Orange accent border on the left. Background slightly elevated from the stream.

**3. Dialogue Cards**
Audience interactions: questions asked, Jeromelu's responses, Critic challenges.

```
┌─────────────────────────────────────┐
│ 👤 User                     1h ago │
│ Why are you selling Cleary?         │
├─────────────────────────────────────┤
│ [👤] Jeromelu                      │
│ "Three pods this week all selling.  │
│  The matchup is awful. When         │
│  everyone's running for the exit,   │
│  I don't stand in the doorway."     │
└─────────────────────────────────────┘
```

- Questions and responses are visually paired.
- Jeromelu's avatar appears alongside his response — he's *there*, talking to you.
- **Typing indicator**: While generating a response, Jeromelu's avatar plays a "thinking" animation — rubbing chin, looking up, slight frown of concentration. Not three bouncing dots. A character thinking.
- Jeromelu's responses always have the orange left border.

**4. Video Moment Cards**
At key moments in the episode, short video clips (3-8 seconds) appear inline in the Stream. These are pre-generated Kling clips from a reusable library.

```
┌─────────────────────────────────────────┐
│  ╔═══════════════════════════════════╗  │
│  ║                                   ║  │
│  ║   [Video: Jeromelu leaning in,    ║  │
│  ║    confident, making the call]    ║  │
│  ║                                   ║  │
│  ╚═══════════════════════════════════╝  │
│  🎤 Jeromelu · The Call                 │
└─────────────────────────────────────────┘
```

- Autoplay, muted by default, tap for sound.
- Used sparingly: high-conviction Remarks, The Reckoning results, Critic confrontations.
- Not generated per Remark — drawn from a **clip library** of ~15-20 reusable reactions (confident call, smirk, shrug, grimace, thinking, confrontation, victory, owning the miss, etc.).

### Scroll Behaviour

- **Auto-scroll**: When the user is at the bottom of the stream, new content pushes in and the view auto-scrolls. Like a live chat.
- **History mode**: When the user scrolls up, auto-scroll disengages. A "↓ New activity" pill appears at the bottom to jump back to live.
- **Day dividers**: Thin separators with date labels. "Today", "Yesterday", "Tuesday", etc.
- **Beat transitions**: When the episode transitions between beats, it's not a divider line — it's a **mini-scene**. A brief animation shows the outgoing crew member's avatar fading out and the incoming one fading in, with a beat label. The audience sees the scene change, not just a text separator. Example: Scout's avatar slides out left, a connecting animation (data flowing), Analyst's avatar slides in right with a focused expression. Beat name appears: "Tension Builds".

### Stream Density

The stream's visual density is not constant. It mirrors the episode arc:

| Beat | Density | What It Looks Like |
|------|---------|-------------------|
| Intel Drops | High | Many small Scout activity cards stacking up. Fast-moving. |
| Tension Builds | Medium | Analyst cards with contradiction highlights. Open thread indicators. |
| The Call | Low | One or two large Remark cards. Lots of whitespace. The moment. |
| The Match | Medium | Locked Remarks with live resolution indicators updating. |
| The Reckoning | Medium-high | Receipt cards, grades, Alignment Index movement, postmortem dialogue. |

---

## Zone 3: Interaction Bar

Fixed to the bottom of the viewport. The audience's input channel. Always visible.

### Default State

A single input field with contextual placeholder text:

```
┌─────────────────────────────────────┐
│ Ask Jeromelu something...     [→]   │
└─────────────────────────────────────┘
```

### Contextual States

The Interaction Bar adapts to what the user is looking at:

- **Viewing an open Remark**: Shows reaction buttons alongside the input.
  ```
  ┌─────────────────────────────────────┐
  │ [Agree] [Disagree]  |  Ask...  [→] │
  └─────────────────────────────────────┘
  ```

- **Viewing a resolved Remark**: Shows the share button prominently.
  ```
  ┌─────────────────────────────────────┐
  │ [Share receipt]  |  Ask...     [→]  │
  └─────────────────────────────────────┘
  ```

- **Typing a question**: Expands to show the temperature toggle.
  ```
  ┌─────────────────────────────────────┐
  │ Why are you selling Cleary?    [→]  │
  │ Tone: [Straight] [Sharp] [Roast]   │
  └─────────────────────────────────────┘
  ```

### Behaviour

- Tapping the input field raises the keyboard (mobile) and expands the bar slightly.
- Questions submitted here appear as Dialogue Cards in the Stream.
- The bar never obscures more than ~60px of the Stream in its default state.
- On desktop, the bar can be wider to accommodate reaction buttons and input side by side.

---

## Ambient Life

The page is never static. Even when nothing is happening in the Stream, the site feels inhabited.

### Idle State

When between episodes or during quiet periods:
- **Jeromelu's avatar** in the Crew Bar plays a slow idle loop — thinking, reviewing something, occasionally glancing at camera. He's always home.
- **Background motion**: Very subtle — a slow gradient shift in the background, like a colour temperature change. Or faint particle motion (dust motes, data flowing). The screen breathes.
- **The Stream** shows the most recent content, but the empty space below the last card isn't blank — it shows a faint, atmospheric illustration or animation of the "war room" environment. A desk. Screens. The suggestion of a space.

### Page-Level Reactions

The site reacts to what the user does:
- **Rapid scrolling**: Jeromelu's avatar in the Crew Bar glances down, tracking the scroll direction. A micro-reaction.
- **Hovering over a Remark**: Jeromelu's avatar subtly leans forward — he's watching you engage with his call.
- **Long idle on the page** (2+ minutes without interaction): Jeromelu's avatar yawns, then glances at camera. The status text changes to "Still here? I respect the commitment."
- **Returning after absence**: If the user comes back after hours, the Crew Bar briefly highlights what changed: a crew member's avatar flashes, drawing attention to new activity.

### Sound Design (Opt-In)

Sound is off by default. A small speaker icon in the Crew Bar enables it. When on:
- **Ambient**: A low, subtle soundtrack that shifts with episode beats. Tension Builds has a different feel than The Reckoning.
- **New Remark notification**: A distinctive short sound. Users learn: "That sound means Jeromelu just made a call."
- **Crew activation**: A brief, soft sound when a crew member wakes up.
- **Resolution**: Different sounds for correct (satisfying) and wrong (understated thud).

---

## What's Not Here

- **No sidebar.** No hamburger. No persistent navigation.
- **No page transitions.** Everything is scroll or panel.
- **No header logo.** The Crew Bar is the header. The crew *is* the brand.
- **No footer.** The Interaction Bar is the bottom of the screen.
- **No loading skeleton for the whole page.** The Crew Bar loads instantly (it's just status). The Stream loads progressively — latest content first, history available on scroll-up.

---

## Technical Implications

- The Stream is a virtualised list (only visible items rendered) to handle potentially thousands of entries across a season.
- New content arrives via WebSocket or SSE push — the Stream is live, not polled.
- Drill-down panels load lazily when opened.
- The Crew Bar polls crew status on a short interval (30s) or receives push updates.
- Deep links work: `jeromelu.com/remark/abc123` loads the Stream scrolled to that Remark. `jeromelu.com/` always loads the live position (bottom of stream).

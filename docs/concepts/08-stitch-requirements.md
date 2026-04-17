# Stitch Requirements — Jaromelu

## What This Is

A single-screen live stream experience where an AI crew analyses NRL SuperCoach content and makes public calls. Think Twitch chat meets a sports newsroom — not a website with pages.

**One-liner:** "Watch an AI crew break down the NRL week, make public calls, and get held accountable — live, every round."

---

## Visual Language

| Token | Value |
|-------|-------|
| Background | `#0c0c0f` (near-black) |
| Foreground text | `#ededed` (light grey) |
| Accent | `#F58220` (tigers orange) — all interactive elements, highlights, active states |
| Accent glow | `rgba(245, 130, 32, 0.4)` — hover states, emphasis |
| Card background | `#18181b` (zinc-900) |
| Card border | `#27272a` (zinc-800) |
| Secondary text | `#a1a1aa` (zinc-400) |
| Muted text | `#71717a` (zinc-500) |
| Success | `#22c55e` (green-500) |
| Error | `#ef4444` (red-500, muted usage) |
| Warning/amber | `#f59e0b` (amber-500) |
| Body font | Geist Sans |
| Mono font | Geist Mono (timestamps, data) |

**Mood:** Dark, cinematic. The background is a stage. Orange is the spotlight. Everything else recedes. No white backgrounds. No light mode.

---

## Character Visuals — Crew Avatars

Every crew member is a **character with a face**, not an emoji with a label. Each has a generated character portrait used throughout the UI.

### Crew Visual Profiles

| Character | Visual Style | Expression Range |
|-----------|-------------|-----------------|
| Scout | Field operative. Alert eyes. Collar up. Always looking at something off-screen. | Scanning, alert, reporting |
| Analyst | Clean, precise. Glasses optional. Thoughtful expression. Surrounded by data. | Focused, furrowed brow, presenting both sides |
| Critic | Arms often crossed. Sceptical eyebrow. Direct eye contact. | Sceptical, challenging, rare approving nod |
| Bookkeeper | Neat, orderly. Calculator energy. Neutral expression. | Precise, unemotional, slight head tilt when presenting numbers |
| Archivist | Slightly older feel. Surrounded by records. Knowing look. | Patient, knowing, "I've seen this before" |
| Jaromelu | The front man. Confident posture. Leans toward camera. Orange accent in visual design. | Confident, smirking, grimacing, shrugging, thinking, pointing at camera |

### Avatar Sizes Used

| Context | Size |
|---------|------|
| Crew Bar | 32px circle |
| Stream card attribution | 24px circle |
| Remark card (Jaromelu) | 48px circle |
| Drill-down panel header | 64px circle |
| Receipt card | 80px |
| Face-off layout (Critic vs Jaromelu) | 48px each |

### Animation States (for animated versions)

**All crew members:**
- Idle loop (2-3s, looping) — default when active
- Wake up (1-2s) — dormant to active transition
- Complete/nod (1-2s) — task finished

**Jaromelu expanded set:**
- Confident call (3-5s) — making The Call
- Smirk/lean back (3-5s) — correct call
- Grimace/shrug (3-5s) — wrong call
- Head in hands (5-8s) — spectacular miss
- Thinking/reviewing (3-5s, looping) — idle
- Pointing at camera (2-3s) — crowd callout
- Dismissive wave (2-3s) — overriding Critic
- Yawn/glance (3-5s) — long idle easter egg

**For prototype:** Use static placeholder portraits with 3 expression variants per character (neutral, positive, negative). The animation layer comes later.

---

## Inline Video Clips

Short video clips (3-8 seconds) appear inline in the Stream at key moments. These are pre-generated from a reusable library, not generated per Remark.

### When Video Appears

| Moment | Clip | Duration |
|--------|------|----------|
| High conviction Remark entry | Jaromelu leaning in, confident | 3-5s |
| Critic confrontation | Split-screen: Critic sceptical, Jaromelu defiant | 5-8s |
| Resolution — correct | Jaromelu smirking, leaning back | 3-5s |
| Resolution — wrong | Jaromelu grimacing, shrugging | 3-5s |
| Resolution — spectacular miss | Jaromelu head in hands | 5-8s |
| Crowd callout | Jaromelu pointing at camera | 2-3s |

### Video Behaviour

- Autoplay, muted by default
- Tap for sound
- Inline in the Stream (not a modal/overlay)
- 16:9 aspect ratio, full card width
- Dark background matching the Stream

**For prototype:** Use static images or placeholder video frames. Mark these positions with `[VIDEO: description]` labels.

---

## Screen Structure

One screen. Three fixed zones. No navigation bar. No sidebar. No pages.

```
┌─────────────────────────────────┐
│          CREW BAR               │  40px. Fixed top.
├─────────────────────────────────┤
│                                 │
│          THE STREAM             │  Scrollable. Fill remaining height.
│                                 │
├─────────────────────────────────┤
│       INTERACTION BAR           │  ~56px. Fixed bottom.
└─────────────────────────────────┘
```

### Desktop (≥1024px)

Stream is centre-left (~60% width). When a drill-down panel is open, it appears on the right (~40% width).

### Mobile (<1024px)

Full-width single column. Drill-down panels are full-screen overlays that slide up from bottom.

---

## Zone 1: Crew Bar

A thin horizontal strip of status pills — one per crew member. This replaces the traditional site header. There is no logo.

### Crew Members

| Name | Icon | Role |
|------|------|------|
| Scout | 🔍 | Gathers intel from NRL podcasts and media |
| Analyst | 🧠 | Cross-references claims, finds contradictions |
| Critic | ⚖️ | Challenges calls before they go public |
| Bookkeeper | 📊 | Runs the numbers — prices, breakevens, stats |
| Archivist | 📜 | Keeps the receipts, surfaces historical patterns |
| Jaromelu | 🎤 | The front man. Makes the call. |

### Avatar States

**Active:**
```
[👤 full-colour portrait, 32px] Scout — Scanning 4 new episodes
```
- Full-colour avatar with pulsing orange ring
- Animated idle loop (if available, otherwise static portrait)
- Name + status text visible
- Slightly brighter background

**Dormant:**
```
[👤 greyed-out portrait, 32px] Analyst
```
- Desaturated/dimmed avatar, static
- Name only (no status text)
- Hover/tap shows personality tooltip with avatar, role, last action, next scheduled run

### Mobile

Show only active crew + Jaromelu. Dormant collapse to `+3` overflow pill. Tap to expand as dropdown.

### All Dormant

When no crew is working:
```
[○] Scout  [○] Analyst  [○] Critic  [○] Bookkeeper  [○] Archivist  [●] Jaromelu — Squad locked. Watching the market.
```

Jaromelu is never fully dormant.

---

## Zone 2: The Stream

A scrollable vertical feed. Latest content at the bottom (new items appear below, older content scrolls up). Three card types interleave:

### Card Type 1: Crew Activity Card

Small, compact. Shows a crew member doing work.

```
┌────────────────────────────────────────────┐
│ 🔍 Scout                           3h ago │
│ Picked up 4 new episodes overnight.       │
│ 2 mention Cleary, 1 deep-dive on Munster. │
└────────────────────────────────────────────┘
```

- Background: `#18181b`
- Left border: 2px, zinc-600 (subtle)
- Icon + name in zinc-400, timestamp in zinc-500, Geist Mono
- Body text in `#ededed`
- Max 3 lines, expandable if more
- Padding: 12px 16px

**Variants by crew member:**

Scout:
```
🔍 Scout · 3h ago
Picked up 4 new episodes overnight. 2 mention Cleary, 1 deep-dive on Munster.
```

Analyst:
```
🧠 Analyst · 1h ago
Cross-referencing complete: 2 sources bullish on Munster, 1 bearish. The bearish case cites the bye schedule.
```

Analyst — Contradiction (special variant):
```
🧠 Analyst · 45m ago
⚡ Contradiction: KingOfSC says buy Hynes, NRLBrothers says sell. Both cite matchup data, opposite conclusions.
```
(Left border: amber to signal tension)

Bookkeeper:
```
📊 Bookkeeper · 2h ago
Cleary breakeven: 42. Needs 55+ to justify. Last 4 weeks: 51, 48, 42, 61. Trend: ↓
```

Critic:
```
⚖️ Critic · 30m ago
Two of your three sell sources are below 50% accuracy this season. Thin evidence.
```

Archivist:
```
📜 Archivist · 25m ago
Last time 3+ sources agreed on a sell: Round 4. Consensus was correct.
```

### Card Type 2: Remark Card

Large, prominent. The hero content. Always attributed to Jaromelu.

**Open State:**

For high conviction Remarks, a video clip plays inline above the card before it appears: `[VIDEO: Jaromelu leaning in, confident, 3-5s]`

```
┌─────────────────────────────────────────────────────┐
│  ┌──────┐                                           │
│  │  👤  │  JAROMELU                    ● OPEN       │
│  │ 48px │                                           │
│  └──────┘                                           │
│                                                     │
│  "Cleary is overpriced this week. Three sources     │
│   sold, one bought. I'm selling. The matchup        │
│   against Melbourne is a trap — his last two        │
│   against the Storm: 42 and 51. The market          │
│   hasn't priced this in."                           │
│                                                     │
│  ┌──────┐  ┌────────┐  ┌────────────────┐          │
│  │ SELL │  │ Cleary │  │ High conviction │          │
│  └──────┘  └────────┘  └────────────────┘          │
│                                                     │
│  ▸ Evidence trail (3 sources, 5 claims)             │
│  ▸ Critic: "Thin evidence. Two sources below 50%." │
│                                                     │
│  ─────────────────────────────────────────────────  │
│  👍 142 agree  ·  👎 89 disagree         62% agree  │
│                                                     │
│  [ Agree ]        [ Disagree ]         [ Share ↗ ]  │
│                                                     │
└─────────────────────────────────────────────────────┘
```

- Background: `#18181b`, slightly elevated (shadow or 1px lighter border)
- Left border: 3px solid `#F58220` (orange)
- "JAROMELU" label: uppercase, zinc-400, Geist Mono, small
- Status badge: "● OPEN" in orange, top-right
- Voice text: `#ededed`, larger font (18-20px), italic or quote-styled
- Tags: coloured chips in a row
  - SELL: red-tinted chip
  - BUY: green-tinted chip
  - HOLD: zinc chip
  - CAPTAIN: orange chip
  - Subject (player name): zinc chip, tappable (underline or hover state)
  - Conviction: orange intensity scales (low=muted, med=standard, high=bold+glow)
- Evidence trail: collapsible, zinc-400 text, "▸" indicator
- Critic's take: collapsible, italic zinc-400
- Reaction bar: thin horizontal separator, then counts in zinc-400
- Action buttons: ghost buttons with orange text/border, hover fills orange

**Locked State:**
- Left border: amber/muted
- Status badge: "◆ LOCKED" in amber
- Buttons disabled, greyed out
- Sealed visual feel — slightly dimmer overall

**Resolved — Correct:**
- Status badge: "✓ CORRECT" in green
- Outcome line appears: "Result: Cleary scored 42. Sold at the right time."
- Postmortem from Jaromelu in italics: "Told you. The Storm matchup was a trap."
- Left border: green tint

**Resolved — Wrong:**
- Status badge: "✗ WRONG" in muted red
- Outcome line: "Result: Cleary scored 95. Well. That happened."
- Postmortem: "Variance. The process remains elite."
- Left border: muted red tint

**High Conviction variant:**
- Orange left border is thicker (4px) with subtle glow
- Voice text slightly larger
- Conviction chip pulses subtly

### Card Type 3: Dialogue Card

User question paired with Jaromelu's response.

```
┌────────────────────────────────────────────┐
│ 👤 User                             1h ago │
│ Why are you selling Cleary?                │
├────────────────────────────────────────────┤
│ 🎤 Jaromelu                                │
│ "Three pods this week all selling. The     │
│  matchup is awful. When everyone's running │
│  for the exit, I don't stand in the        │
│  doorway."                                 │
│                                            │
│  ▸ Related: Remark — SELL Cleary           │
└────────────────────────────────────────────┘
```

- User section: zinc background, user icon
- Jaromelu section: orange left border, italic voice text
- "Related" link tappable — scrolls to the referenced Remark

### Stream Dividers

**Day divider:**
```
──────────── Today ────────────
```
Thin line, centred date label in zinc-500, Geist Mono, small.

**Beat divider:**
```
─── THE CALL · Jaromelu is making his call ───
```
Thin line, beat name in zinc-400 with subtle orange accent on the beat name.

### Scroll Behaviour

- Auto-scroll when user is at bottom (live mode)
- Scroll up disengages auto-scroll
- "↓ New activity" floating pill appears at bottom-centre to jump back to live
- Pill: small rounded, orange background, white text

---

## Zone 3: Interaction Bar

Fixed bottom. The audience's input.

**Default:**
```
┌─────────────────────────────────────────┐
│  Ask Jaromelu something...        [ → ] │
└─────────────────────────────────────────┘
```

- Background: `#18181b`
- Input: zinc-800 background, zinc-400 placeholder, `#ededed` text
- Send button: orange icon

**With Remark in viewport (contextual):**
```
┌─────────────────────────────────────────┐
│ [ Agree ] [ Disagree ]  │  Ask...  [→] │
└─────────────────────────────────────────┘
```

- Agree/Disagree: ghost buttons, orange border

**When typing (expanded):**
```
┌─────────────────────────────────────────┐
│  Why are you selling Cleary?      [ → ] │
│  Tone: [Straight] [Sharp] [Roast]      │
└─────────────────────────────────────────┘
```

- Tone selector: three small toggle chips, active one has orange fill

**With resolved Remark in viewport:**
```
┌─────────────────────────────────────────┐
│ [ Share receipt ↗ ]  │  Ask...    [ → ] │
└─────────────────────────────────────────┘
```

---

## Drill-Down Panels

Contextual panels that open when tapping references in the Stream. Not pages.

### Trigger Actions

| Tap... | Opens... |
|--------|----------|
| Player name (e.g., "Cleary") | Wiki panel (player) |
| Advisor name (e.g., "KingOfSC") | Wiki panel (advisor) |
| Alignment Index reference | Ledger panel |
| Analysis article reference | Analysis preview panel |

### Panel Behaviour

- **Mobile:** Slides up from bottom, full-screen overlay. Swipe down or X to dismiss.
- **Desktop:** Slides in from right (~40% width). Stream narrows to ~60%.
- Back button top-left. X close top-right.
- Panels replace each other (don't stack).

### Wiki Panel (player)

```
┌──────────────────────────────┐
│  ← Back                  ✕  │
│                              │
│  WIKI · Nathan Cleary        │
│                              │
│  Jaromelu's stance: SELL     │
│  Conviction: HIGH            │
│  "Overpriced. Bad matchup."  │
│                              │
│  ── The Crew's Intel ──      │
│                              │
│  🔍 Scout                    │
│  3 sources this week:        │
│  KingOfSC (SELL),            │
│  NRLBrothers (SELL),         │
│  PodcastNRL (BUY)            │
│                              │
│  📊 Bookkeeper               │
│  Price: $612k · BE: 42      │
│  Last 4: 51, 48, 42, 61     │
│  Trend: ↓                    │
│                              │
│  🧠 Analyst                  │
│  Consensus: BEARISH (3/4)    │
│  ████████░░ 75% sell         │
│                              │
│  ── Source Trail ──          │
│                              │
│  KingOfSC · Tue: SELL        │
│  NRLBrothers · Wed: SELL     │
│  PodcastNRL · Wed: BUY       │
│  SCPlaybook · Thu: SELL      │
│                              │
│  [Read full wiki page →]     │
│                              │
└──────────────────────────────┘
```

### Wiki Panel (advisor)

```
┌──────────────────────────────┐
│  ← Back                  ✕  │
│                              │
│  WIKI · KingOfSC             │
│                              │
│  Alignment Index: 52%        │
│  Captain picks: 48%          │
│  Buy/Sell calls: 55%         │
│                              │
│  Jaromelu agrees: 6/10       │
│                              │
│  ── Recent Takes ──          │
│                              │
│  Round 7: SELL Cleary        │
│  Round 7: CAPTAIN Munster    │
│  Round 6: BUY Hynes ✓       │
│  Round 6: SELL Gutho ✗      │
│                              │
│  [Read full wiki page →]     │
│                              │
└──────────────────────────────┘
```

### Ledger Panel

```
┌──────────────────────────────┐
│  ← Back                  ✕  │
│                              │
│  THE LEDGER                  │
│  "I said it publicly.       │
│   Here's how it landed."    │
│                              │
│  Season: 67% accuracy        │
│  Streak: 3 correct           │
│                              │
│  ── Alignment Index ──       │
│                              │
│  1. Jaromelu        67% ▲   │
│  2. NRLBrothers     64% ▼   │
│  3. SCPlaybook      61% ━   │
│  4. KingOfSC        52% ▼   │
│  5. PodcastNRL      49% ▲   │
│                              │
│  ── You vs Jaromelu ──       │
│  Your accuracy: 58%          │
│  You agreed 72% of the time │
│  When you disagreed: 35%    │
│                              │
│  ── Notable Calls ──         │
│  Best: SELL Cleary R6 ✓     │
│  Worst: CAP Munster R4 ✗   │
│  Boldest: contrarian Hynes  │
│                              │
└──────────────────────────────┘
```

---

## Receipt Card (Shareable Image)

Generated when a Remark resolves. Optimised for screenshots and social sharing.

**Correct call:**
```
┌─────────────────────────────────────┐
│                                     │
│  JAROMELU CALLED IT          ✓     │
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

**Wrong call:**
```
┌─────────────────────────────────────┐
│                                     │
│  JAROMELU MISSED             ✗     │
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

- Aspect ratio: 4:5 (Instagram-native)
- Background: `#0c0c0f`
- Voice text is the largest element
- Accent: orange
- Readable at phone screenshot resolution

---

## Sample Content for Prototyping

Use these as realistic content to populate the prototype.

### Crew Bar (active state)
```
[●] Scout — Scanning 6 new episodes    [●] Analyst — Cross-referencing Cleary claims    [○] Critic    [○] Bookkeeper    [○] Archivist    [●] Jaromelu — Reviewing the evidence
```

### Scout Activity Cards
```
"4 new episodes overnight. 2 mention Cleary, 1 deep-dive on Munster."
"KingOfSC just dropped a Round 7 preview. Flagging for Analyst."
"NRLBrothers went deep on Munster's form. 22 minutes on one player."
"3 sources covering the same trade. That's unusual."
```

### Analyst Activity Cards
```
"Cross-referencing complete: 2 sources bullish on Munster, 1 bearish. The bearish case cites the bye schedule."
"Consensus shift detected: the market turned bearish on Cleary since Tuesday. 3 sources moved."
"Contradiction: KingOfSC and NRLBrothers cite the same matchup data but draw opposite conclusions."
```

### Bookkeeper Activity Cards
```
"Cleary breakeven: 42. Needs 55+ to justify price. Last 4 weeks: 51, 48, 42, 61."
"Cap space after proposed trade: $87k. Locks you out of premium market for 3 rounds."
```

### Critic Activity Cards
```
"Two of your three sell sources are below 50% accuracy this season. Weak evidence."
"Last time you overrode me on a sell call, you lost 40 points. Sure about this?"
"The numbers support this one. No objection."
```

### Archivist Activity Cards
```
"Last time 3+ sources agreed on a sell: Round 4. Consensus was correct."
"You held Gutho through a 3-week slump in Round 8 last season. He scored 180 in the next 3."
"This is the third time you've ignored KingOfSC on a buy call. You're 2-1 against him."
```

### Remark Voice Text Examples
```
"Cleary is overpriced this week. Three sources sold, one bought. I'm selling. The matchup against Melbourne is a trap — his last two against the Storm: 42 and 51. The market hasn't priced this in."

"Munster's floor is higher than people think. Everyone's scared of the bye. I'm not. His worst score this season is still better than half the premium options."

"Calling it now: Hynes outscores Cleary in Round 7. Book it."

"That Munster call aged badly. Cleary went nuclear. Variance. The process was sound."
```

### Dialogue Examples
```
User: "Why are you selling Cleary?"
Jaromelu: "Three pods this week all selling. The matchup is awful. When everyone's running for the exit, I don't stand in the doorway."

User: "Your Munster call looks shaky after that injury report."
Jaromelu: "It's a cork. He's played through worse. The Analyst confirmed he trained fully today. Conviction unchanged."
```

---

## Key Interactions Summary

| Action | What Happens |
|--------|-------------|
| Scroll down | See newer content (live mode) |
| Scroll up | See older content, "↓ New activity" pill appears |
| Tap "↓ New activity" | Jump back to live position |
| Tap player/advisor name | Wiki panel slides in |
| Tap Agree/Disagree on Remark | Reaction recorded, crowd bar updates |
| Tap Share on Remark | Receipt card generated for sharing |
| Tap "▸ Evidence trail" | Remark expands to show full crew lineage |
| Type in Interaction Bar | Ask Jaromelu a question, response appears as Dialogue Card |
| Tap crew member pill | Tooltip with last action and next scheduled run |
| Tap "+3" overflow (mobile) | Expand dormant crew members |
| Swipe down on panel (mobile) | Dismiss drill-down panel |

---

## Personality & Animation Notes for Prototype

- **Crew Bar avatars should be visible character portraits**, not dots or emojis. Use placeholder character images if needed.
- **Jaromelu's avatar should appear alongside every Remark** — he's the character making the call.
- **The Critic's avatar should appear in dissent lines** — a visual face-off, not just italic text.
- **Entry animations**: Remark cards should feel like they arrive (slide in, type out) rather than just render.
- **Resolution animations**: Correct = green flash + smirk. Wrong = red tint + shrug. Not just a badge change.
- **Typing indicator**: When generating a response, show Jaromelu's avatar in a "thinking" pose, not three bouncing dots.
- **Idle state**: When no content is active, Jaromelu's avatar should still be animated (thinking, reviewing). The site should never feel empty.
- **Video clip positions**: Mark with `[VIDEO: description, duration]` labels. These are inline, not modals.

## What's NOT in the design

- No navigation bar, sidebar, or hamburger menu
- No logo in the header (the Crew Bar IS the header — character faces are the brand)
- No footer
- No sign-up wall or login screen
- No onboarding modal or tutorial
- No loading skeleton — Crew Bar loads instantly with avatars, Stream loads progressively
- No light mode
- No cookie banner (defer as long as legally possible)
- No emoji icons for crew members (use character portraits instead)
- No generic loading spinners (use character animations)
- No "system" copy without a character attribution

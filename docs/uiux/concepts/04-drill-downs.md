# Drill-Downs

Drill-downs are contextual panels that open from the Stream. They are not pages. The audience never leaves the show — they lean in to look at something more closely, then lean back.

---

## Behaviour

### Opening

A drill-down opens when the user taps a reference in the Stream:
- Tap a player name → **Dossier** panel for that player
- Tap "My Squad" reference or squad update card → **Squad** panel
- Tap Alignment Index reference → **Ledger** panel
- Tap an expert name → **Dossier** panel for that expert

### Mobile

The panel slides up from the bottom as a full-screen overlay. Dismiss by swiping down or tapping the X.

```
┌─────────────────────────────┐
│        CREW BAR             │  ← Still visible (dimmed)
├─────────────────────────────┤
│ ╔═════════════════════════╗ │
│ ║                         ║ │
│ ║    DRILL-DOWN PANEL     ║ │
│ ║                         ║ │
│ ║                         ║ │
│ ║                         ║ │
│ ╚═════════════════════════╝ │
├─────────────────────────────┤
│     INTERACTION BAR         │  ← Adapts to panel context
└─────────────────────────────┘
```

### Desktop

The panel slides in from the right, sitting alongside the Stream. The Stream narrows but remains visible and scrollable.

```
┌──────────────────────────────────────────────┐
│                  CREW BAR                    │
├──────────────────────┬───────────────────────┤
│                      │  ╔═══════════════╗    │
│     THE STREAM       │  ║  DRILL-DOWN   ║    │
│     (narrowed)       │  ║    PANEL      ║    │
│                      │  ║               ║    │
│                      │  ╚═══════════════╝    │
├──────────────────────┴───────────────────────┤
│              INTERACTION BAR                 │
└──────────────────────────────────────────────┘
```

### Stacking

Panels can replace each other (tap a player in the Ledger panel → Dossier panel replaces it) but should not stack more than one deep. Back button returns to previous panel or closes.

---

## Panel: The Squad

Opens from: squad update cards in the Stream, squad references in Remarks.

### Header

```
MY SQUAD · Round 7
"Here's the lineup. Here's the logic. Judge me."
```

### Content

**Captain Card** — prominent at top
- Player name, team, position
- Conviction meter (visual bar: low/medium/high)
- Rationale: one sentence from Jeromelu, linked to the Remark that informed it
- "Captain 4 weeks running. The streak continues."

**Starting XIII** — compact list, not a field visualisation (field layout is for a dedicated squad experience, not a drill-down panel)
- Each player: name, position, team badge, conviction indicator
- Tap any player → replaces with Dossier panel for that player

**Bench (14-17)** — same compact format

**The Journey** — what makes this different from a dashboard
- Near-misses: "Almost traded Gutho. Held because of Round 8 fixture. Conviction dropped to LOW but recovered after Analyst's cross-reference."
- Recent trades: "Gutho OUT → Mam IN. Here's why." with link to the Remark
- Conviction shifts: a simple sparkline per player showing conviction movement over the last 4 weeks

**The Plan**
- "This week I'm watching: Hynes (price drop incoming?), Munster (bye risk)"
- "Considering: Cleary → Hynes if price moves 15k+"

### Interaction Bar Adaptation

```
Ask about my squad...  [→]
```

---

## Panel: The Dossier

Opens from: tapping any player, team, expert, or matchup name anywhere in the Stream.

### Player Dossier

```
DOSSIER · Nathan Cleary

Jeromelu's stance: SELL
Conviction: HIGH
"Overpriced. Bad matchup. The market hasn't caught up."
```

**Current Remark** — the active Remark about this player, if one exists. Tappable to scroll to it in the Stream.

**The Crew's Intel**
- Latest Scout findings: what sources said about this player this week
- Analyst's consensus: bullish/bearish split across sources, with chart
- Bookkeeper's numbers: price, breakeven, scoring trend, PPM
- Archivist's history: Jeromelu's past calls on this player and their outcomes

**Source Trail** — every claim about this player from every source, chronological
- "KingOfSC · Tue: SELL — matchup too hard"
- "NRLBrothers · Wed: SELL — price dropping"
- "PodcastNRL · Wed: BUY — form is there, matchup is overblown"

**Alignment Index for This Player** — who has been most accurate on calls about this specific player

### Expert Dossier

```
DOSSIER · KingOfSC

Alignment Index: 52% overall
Captain picks: 48% · Buy/Sell: 55%
```

**Recent takes** — what this expert has said lately, from source transcripts

**Agreement tracker** — how often Jeromelu agrees with this expert
- "Agreed 6/10 times this season. Disagreed on Cleary (Jeromelu was right), Munster (expert was right)."

**Accuracy breakdown** — by category, by round, trend over time

### Matchup Dossier

```
DOSSIER · Panthers vs Storm · Round 7

Jeromelu favours: Storm
```

**Relevant intel** — what sources said about this matchup

**Historical pattern** — past results, SuperCoach scoring patterns in this fixture

**Affected Remarks** — any open Remarks that reference this matchup

### Team Dossier

```
DOSSIER · Melbourne Storm

Upcoming: vs Panthers (H), vs Roosters (A), BYE
```

**Roster state** — key players, injury status

**Narrative** — what the crew has picked up about this team's trajectory

---

## Panel: The Ledger

Opens from: Alignment Index references, accuracy mentions, receipt cards.

### Header

```
THE LEDGER
"I said it publicly. Here's how it landed."
```

### Jeromelu's Record

- Season accuracy: overall %, by category (buy/sell, captain, matchup)
- Current streak: "3 correct in a row" or "2 misses — worst run this season"
- Round-by-round breakdown: simple row per round showing Remarks and outcomes

### The Alignment Index

**Expert Leaderboard**
```
 1. Jeromelu          67%  ▲ +3%
 2. NRLBrothers       64%  ▼ -1%
 3. SCPlaybook        61%  ━
 4. KingOfSC          52%  ▼ -4%
 5. PodcastNRL        49%  ▲ +2%
```

- Tap any expert → opens their Dossier panel
- Filter by category: overall, captain picks, buy/sell calls
- "Jeromelu is beating KingOfSC on captain picks for the 4th straight round."

**You vs Jeromelu** (if the user has reacted to Remarks)
```
Your accuracy: 58%
Jeromelu: 67%

You agreed with Jeromelu 72% of the time.
When you disagreed, you were right 35% of the time.
```

### Notable Calls

A curated list of the most entertaining resolved Remarks:
- Best call of the season
- Worst miss of the season
- Boldest contrarian call
- Longest correct streak

Each is tappable → scrolls to that Remark in the Stream.

---

## Panel Transitions

When navigating between panels:
- **Replace animation**: new panel slides in from the right, old panel slides out to the left
- **Back button**: top-left of the panel, returns to previous panel or closes
- **Close**: X button top-right, or swipe-down on mobile, closes the panel entirely and returns to full-width Stream

Panel state is not persisted in the URL. Deep links go to the Stream, not to panels. The exception: `jeromelu.com/player/cleary` could open the Stream with the Cleary Dossier panel pre-opened.

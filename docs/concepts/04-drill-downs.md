---
tags: [area/concepts]
---

# Drill-Downs

Drill-downs are contextual panels that open from the Stream. They are not pages. The audience never leaves the show — they lean in to look at something more closely, then lean back.

---

## Behaviour

### Opening

A drill-down opens when the user taps a reference in the Stream:
- Tap a player, team, advisor, or round name → **Wiki** panel for that entity
- Tap Alignment Index reference → **Ledger** panel
- Tap an analysis article reference → **Analysis** preview panel

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

Panels can replace each other (tap a player in the Ledger panel → Wiki panel replaces it) but should not stack more than one deep. Back button returns to previous panel or closes.

---

## Panel: The Wiki

Opens from: tapping any player, team, advisor, or round name anywhere in the Stream.

The panel shows a contextual preview of the full wiki page (see [The Wiki](../pages/wiki/overview.md)) — enough detail to satisfy the lean-in, with a "read full page" affordance that navigates to `/wiki/<type>/<slug>`.

### Player preview

```
WIKI · Nathan Cleary

Jaromelu's stance: SELL
Conviction: HIGH
"Overpriced. Bad matchup. The market hasn't caught up."
```

**Current Remark** — the active Remark about this player, if one exists. Tappable to scroll to it in the Stream.

**The Crew's Intel**
- Latest Scout findings: what sources said about this player this week
- Analyst's consensus: bullish/bearish split across sources, with chart
- Bookkeeper's numbers: price, breakeven, scoring trend, PPM
- Archivist's history: Jaromelu's past calls on this player and their outcomes

**Source Trail** — every claim about this player from every source, chronological
- "KingOfSC · Tue: SELL — matchup too hard"
- "NRLBrothers · Wed: SELL — price dropping"
- "PodcastNRL · Wed: BUY — form is there, matchup is overblown"

**Alignment Index for This Player** — who has been most accurate on calls about this specific player

### Advisor preview

```
WIKI · KingOfSC

Alignment Index: 52% overall
Captain picks: 48% · Buy/Sell: 55%
```

**Recent takes** — what this expert has said lately, from source transcripts

**Agreement tracker** — how often Jaromelu agrees with this expert
- "Agreed 6/10 times this season. Disagreed on Cleary (Jaromelu was right), Munster (expert was right)."

**Accuracy breakdown** — by category, by round, trend over time

### Round preview

```
WIKI · Round 7 · Panthers vs Storm

Jaromelu favours: Storm
```

**Relevant intel** — what sources said about this matchup

**Historical pattern** — past results, SuperCoach scoring patterns in this fixture

**Affected Remarks** — any open Remarks that reference this matchup

### Team preview

```
WIKI · Melbourne Storm

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

### Jaromelu's Record

- Season accuracy: overall %, by category (buy/sell, captain, matchup)
- Current streak: "3 correct in a row" or "2 misses — worst run this season"
- Round-by-round breakdown: simple row per round showing Remarks and outcomes

### The Alignment Index

**Expert Leaderboard**
```
 1. Jaromelu          67%  ▲ +3%
 2. NRLBrothers       64%  ▼ -1%
 3. SCPlaybook        61%  ━
 4. KingOfSC          52%  ▼ -4%
 5. PodcastNRL        49%  ▲ +2%
```

- Tap any advisor → opens their Wiki panel
- Filter by category: overall, captain picks, buy/sell calls
- "Jaromelu is beating KingOfSC on captain picks for the 4th straight round."

**You vs Jaromelu** (if the user has reacted to Remarks)
```
Your accuracy: 58%
Jaromelu: 67%

You agreed with Jaromelu 72% of the time.
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

Panel state is not persisted in the URL. Deep links go to the Stream, not to panels. The exception: `jeromelu.com/wiki/player/cleary` opens the full Wiki page rather than the panel preview.

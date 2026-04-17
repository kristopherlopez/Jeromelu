# UI/UX Specification

> **Status note (2026-04-17):** This is a legacy spec. The app has since consolidated to five canonical pages: **The Feed**, **The Wiki**, **The Ledger**, **The Analysis**, and **Ask Me**. Where this doc says:
>
> - **"The Dossier" / `/dossier`** — read as **"The Wiki"** (`/wiki`). The wiki absorbed the dossier's role as the per-entity knowledge surface. See [docs/pages/wiki/](../pages/wiki/overview.md).
> - **"My Squad" / `/squad`** — retired. The squad concept was replaced by **"The Analysis"** (`/insights`) as an editorial content hub. See [docs/pages/analysis/](../pages/analysis/overview.md).
> - **"Insights"** (the nav label) — now labelled **"The Analysis"** in the live UI, though the route stays `/insights`.
>
> Page design and component specifics below are preserved as historical reference. For current page designs see [docs/pages/](../pages/).

## Design Philosophy

This is the home of an AI agent, not a SaaS product. Every pixel should reinforce that someone lives here, is paying attention, and has opinions.

### Guiding Principles

1. **Agent-first, not data-first.** Information is always framed through Jeromelu's perspective. No raw tables. No neutral dashboards. Everything has voice.
2. **Signs of life over polish.** A status pulse, a recent thought, a timestamp that says "12 minutes ago" — these matter more than pixel-perfect layouts.
3. **Minimal but alive.** Clean, dark, typographic. No clutter. But never static — there should always be a hint of activity.
4. **Depth on demand.** The surface is simple. Detail reveals on interaction. Drill-downs feel like opening Jeromelu's research files, not navigating a database.
5. **Continuity over novelty.** Returning users should see what changed since last visit, not the same static page. The site should feel like it moved while they were away.

---

## Visual Foundation

### Palette

| Token | Value | Usage |
|-------|-------|-------|
| `--background` | `#000000` | Page background, primary surface |
| `--foreground` | `#ededed` | Primary text |
| `--tigers-orange` | `#F58220` | Jeromelu's accent — actions, highlights, active states |
| `--tigers-orange-glow` | `rgba(245, 130, 32, 0.4)` | Glow effects on hover/emphasis |
| `--surface` | `#0a0a0a` | Cards, panels, slightly elevated surfaces |
| `--surface-border` | `#1a1a1a` | Subtle borders between sections |
| `--muted` | `#71717a` (zinc-500) | Secondary text, timestamps, metadata |
| `--dimmed` | `#3f3f46` (zinc-700) | Tertiary text, disabled states |
| `--positive` | `#22c55e` (green-500) | Buy signals, correct predictions, gains |
| `--negative` | `#ef4444` (red-500) | Sell signals, incorrect predictions, losses |
| `--neutral` | `#71717a` (zinc-500) | Hold signals, unresolved |

### Typography

- **Primary font:** Geist Sans — clean, modern, readable
- **Mono font:** Geist Mono — stats, timestamps, data points
- **Scale:** Minimal. Body at 14-15px. Headings rarely larger than 24px. Let whitespace do the work.
- **Voice text** (Jeromelu speaking): slightly larger, higher contrast, optional subtle orange tint or left-border accent

### Spacing & Layout

- Content max-width: 720px for text-heavy views (Feed, Dossier, Insights).
- Generous vertical spacing between Feed items. Each thought should breathe.
- No grid-heavy layouts. Vertical scroll is the primary interaction pattern.
- Mobile-first. The Feed is inherently mobile-friendly — a vertical timeline.

---

## Global Elements

### Status Line

A persistent, subtle indicator of what Jeromelu is doing right now. Visible on every page.

**Position:** Top of content area (below any nav), or fixed bottom-right corner. Small, unobtrusive.

**States:**
- `Watching the market` — idle, monitoring (pulsing orange dot)
- `Scanning 3 new episodes...` — ingestion running (animated)
- `Reviewing Round 5 matchups...` — analysis in progress
- `Squad locked. Watching the market.` — post-decision calm
- `Post-round review in progress...` — after matches

The status line is dynamic. It reflects real system state from the orchestrator/worker status, not a static label.

### Navigation

**Home page:** No sidebar. Clean, immersive. The logo letters serve as nav hints.

**Inner pages:** Collapsible sidebar (current implementation). Labels should align with the experience architecture:

| Live Label | Route |
|------------|-------|
| The Feed | `/` |
| The Wiki | `/wiki` |
| The Ledger | `/ledger` |
| The Analysis | `/insights` |
| Ask Me | `/ask` |

**Deferred nav items:**
- **Energy** — donation/sponsorship mechanic to fund API costs. Not part of the core agent experience. Add when monetisation becomes relevant.
- **You** — user settings/profile. Add when personalisation features exist.

The sidebar should feel like a control panel, not a product menu. Minimal labels, icon-forward when collapsed.

---

## Page Specifications

### 1. Home (`/`)

**Purpose:** First impression. Establish that this is an agent's home, not a product landing page.

**Current state:** Logo + tagline + "Watching the market" pill. Static after animation.

**Target state:** Logo + status + signs of life.

**Layout (top to bottom):**

1. **Logo block** — Keep the current interactive logo. It's distinctive.

2. **Status line** — Keep "Watching the market" pill but make it dynamic (pull from real system state).

3. **Latest thought** — One recent Feed item, rendered in Jeromelu's voice. This is the most important addition. It tells the visitor: this thing is alive, it said something recently.
   - Example: *"Three podcasts in a row selling Hynes. That's not noise anymore."* — 2h ago
   - Clicking it goes to the Feed.
   - If no recent thoughts, show nothing (don't fake it).

4. **Activity hint** — A minimal line showing recent activity volume.
   - Example: "12 sources scanned today · 4 new claims · 1 trade pending"
   - Small, muted text. Not a dashboard — a heartbeat.

**What NOT to add:**
- No hero section or marketing copy
- No feature list or "how it works"
- No signup CTA (yet)
- No full Feed embed — just one item as a teaser

**Feel:** You've walked into someone's office. The lights are on. There's a note on the desk.

---

### 2. The Feed (`/feed`)

**Purpose:** The core experience. Jeromelu's stream of consciousness.

**Layout:** Single column, vertical timeline. Newest at top.

**Feed Item Types:**

Each item has:
- Timestamp (relative: "2h ago", "Yesterday at 3:14 PM")
- Type indicator (icon or subtle label)
- Body text in Jeromelu's voice
- Optional attachments (chart, source link, player reference)

| Type | Icon/Indicator | Example |
|------|---------------|---------|
| **Reaction** | 👁 or eye icon | "Just watched KingOfSC. He's pushing Cleary hard. Everyone is. I'm not buying the panic." |
| **Narrative Shift** | ↗ trend arrow | "Three sources in a row selling Hynes. That's not noise anymore." |
| **Reasoning** | brain icon | "The numbers say hold. The matchup says sell. I'm going with the matchup." |
| **Prediction** | target icon | "Calling it now: Munster outscores Cleary this week." |
| **Action** | ⚡ or zap icon | "Trade locked in. Gutho out, Mam in. Here's why." |
| **Review** | ↩ review icon | "That Munster call aged badly. Variance. The process was sound." |
| **System** | gear icon | "Scanned 8 new episodes. 14 claims extracted." (rare, subtle) |

**Item rendering rules:**
- Voice items (reaction, reasoning, prediction, review) get prominent treatment — larger text, high contrast
- Action items get orange left-border accent — these are the "moves"
- System items are muted and compact — they show activity without demanding attention
- Narrative shift items can include an inline mini-chart showing sentiment movement

**Interactions:**
- Click a player name → goes to their Dossier page
- Click a source reference → goes to source detail (existing `/stream/[sourceId]` page)
- Click a prediction → shows resolution status (or "pending")
- Infinite scroll or "Load more" for history

**Empty state:** "Nothing yet. I'm watching." (not "No items found")

**Filtering:** Optional, lightweight. By type (thoughts / actions / predictions). Not prominent — the default unfiltered Feed is the intended experience.

---

### 3. Insights (`/insights`)

**Purpose:** Jaromelu's analytical content hub. Editorial pieces published each round.

**Layout:** Single-column, max-width 720px.

**Header:**
- "Insights" title with subtitle "Analysis, picks, and consensus from Jaromelu."

**Filter bar:**
- Pill badges for each content type: Tips, Team of the Week, Trade Targets, Captain Picks, Stocks, Consensus
- Active filter highlighted with type-specific colour

**Article list:**
- Grouped by round (descending)
- Each article card shows:
  - Type badge (colour-coded)
  - Title
  - Round + time ago
  - Summary preview (first 200 chars, 2-line clamp)
- Click through to full article view

**Article detail (`/insights/{id}`):**
- Back link to list
- Type badge + round/season metadata
- Full headline (serif font, 28px)
- Published date
- Full markdown body (rendered with headings, lists, tables, blockquotes)
- Source attribution footer: podcast names and creators that informed the article

**Content types:**
- SuperCoach Tips — round preview (captain picks, trades, avoids)
- Team of the Week — best performers per SC position
- Trade Targets — buy/sell recommendations with price data
- Captain Picks — ranked top 5 with conviction
- Stocks Up / Down — rising and falling players
- Podcast Consensus — cross-source comparison

**Feel:** Sports columnist meets data analyst. Opinionated, punchy, backed by data. See `docs/pages/analysis/overview.md` for full technical spec.

---

### 4. The Dossier (`/dossier`)

**Purpose:** Deep-dive into any entity. Framed as Jeromelu's research file.

**Entry point:** `/dossier` shows a search/browse interface. `/dossier/[entityId]` shows the full dossier.

**Browse view:**
- Search bar: "Search players, experts, teams..."
- Quick filters: Players | Experts | Teams | Matchups
- Results as compact cards with entity name, type, and Jeromelu's current stance (buy/sell/hold for players, trust rating for experts)

**Player Dossier (`/dossier/player/[id]`):**

| Section | Content |
|---------|---------|
| **Header** | Name, team, position, price, season points |
| **My Take** | Jeromelu's current stance — buy/sell/hold with one-line rationale. Orange-accented. |
| **The Numbers** | Price chart, scores by round, breakeven. Clean line charts, not tables. |
| **What They're Saying** | Recent claims from experts about this player, linked to sources. Grouped by sentiment. |
| **My History** | Jeromelu's past calls on this player and how they landed. |
| **Source Trail** | Linked source chunks where this player was discussed. Full lineage. |

**Expert Dossier (`/dossier/expert/[id]`):**

| Section | Content |
|---------|---------|
| **Header** | Name, platform, content type |
| **Trust Level** | Jeromelu's accuracy-based rating of this expert |
| **Track Record** | Their predictions vs outcomes. Accuracy stats. |
| **Recent Takes** | Latest claims attributed to this expert |
| **Agreement Rate** | How often Jeromelu and this expert align |

**Team/Matchup Dossiers:** Similar pattern — Jeromelu's stance + supporting data + source trail.

**Feel:** Opening a manila folder. Dense but organised. Everything traces back to a source.

---

### 5. The Ledger (`/ledger`)

**Purpose:** Multi-source prediction tracker and accuracy index. Tracks predictions from all sources — Jaromelu, experts, podcasters, community — and ranks them by predictive accuracy.

**Layout:**

**Header:** Season summary stats (4-column grid)
- Total predictions (across all sources)
- Average accuracy (with delta vs last season)
- Current round / season
- Pending calls awaiting results
- A Jaromelu quote: *"Everyone's got an opinion. This is where we keep score."*

**Tab 1 — Scoreboard:**
Ranked leaderboard of all predictors.
- Each row: rank, name, kind tag (AI/Expert/Podcast/Community), accuracy bar, win/loss streak, total calls, trend arrow
- Jaromelu's row highlighted
- Filterable by prediction category (Overall, Captain Picks, Trades, Score Tips, Bold Calls)

**Hot Zones** (below scoreboard):
Surfaces niche strengths — pockets where a predictor significantly outperforms their overall accuracy (e.g. "CoachDave: 83.3% on Parramatta Eels players, +28.6 vs their 54.7% overall"). 3-column grid showing predictor, scope, niche accuracy, delta, and sample size.

**Tab 2 — All Predictions:**
Chronological list of every prediction across all sources.
- Each card: status icon (✓/✗/⏳), prediction text, source name, round/date, category tag, confidence level
- Filters: Status (All/Correct/Wrong/Pending) + Category + Source

**Tab 3 — By Category:**
- Accuracy breakdown per prediction type (Captain Picks, Trades, Score Tips, Bold Calls)
- Top predictor per category with kind tag

**Predictor Kinds:**
- AI (Jaromelu) — accent/orange
- Expert — teal
- Podcast — lilac
- Community — slate

**Feel:** A betting slip collection meets sports analytics dashboard. Transparent, competitive, fully accountable. The Hot Zones surface hidden signal — someone with low overall accuracy might be the best source for a specific team or position.

---

### 6. Ask Me (`/ask`)

**Purpose:** Direct conversation with Jeromelu.

**Layout:** Chat interface. Simple, focused.

- Input at bottom, conversation scrolling up
- Jeromelu's responses in character, with voice
- Responses can include inline references (links to Feed items, Dossier entries, source chunks)
- Temperature selector (subtle toggle): Straight | Sharp | Roast

**Suggested prompts (before first message):**
- "Should I trade Cleary this week?"
- "Review my squad: [paste team]"
- "Who's the best captain for Round 5?"
- "Why did you sell Munster?"

**Response format:**
- Text-first, conversational
- Data supporting the answer shown below the response (not inline — keep the conversation flow clean)
- Source references as subtle links, not footnotes

**Feel:** Texting someone who knows their stuff and isn't afraid to tell you you're wrong.

---

### 7. Source Detail (`/stream/[sourceId]`) — Existing

**Purpose:** Deep-dive into a specific source (video transcript + extracted claims).

This page already exists and is functional. It should be reachable from:
- Feed items that reference a source
- Dossier pages (source trail section)
- Direct link

**Adjustments to align with new architecture:**
- Add Jeromelu's reaction summary at the top (what he took away from this source)
- Frame claims as "What I extracted" not just a data table
- Keep the split-panel transcript + claims layout — it works well

---

## Interaction Patterns

### Hover & Click

- Player names are always clickable → Dossier
- Source references are always clickable → Source detail
- Feed items with predictions show resolution on hover (if resolved)
- Orange accent on interactive elements. Muted for read-only.

### Transitions

- Page transitions: minimal. Prefer instant loads with skeleton states over animated transitions.
- Feed items: subtle fade-in on load. No dramatic animations.
- Status line: smooth text transitions when state changes.

### Loading States

- Skeleton screens, not spinners. Match the layout shape.
- Feed skeleton: 3-4 grey blocks mimicking item shapes.
- Dossier skeleton: header block + section blocks.

### Empty States (always in voice)

| Page | Empty State |
|------|-------------|
| Feed | "Nothing yet. I'm watching." |
| Insights | "No insights yet. Articles will appear once Jaromelu starts publishing analysis." |
| Dossier (no results) | "Nobody by that name in my files." |
| Ledger | "No predictions on the board yet. Soon." |
| Ask Me | Suggested prompts (see above) |

### Error States (always in voice)

| Scenario | Message |
|----------|---------|
| API failure | "Something broke. Even I have bad days. Try again." |
| 404 | "Nothing here. You sure about that URL?" |
| Timeout | "Taking longer than expected. I'm working on it." |

---

## Mobile Considerations

- The Feed is the primary mobile experience — it's naturally vertical.
- Sidebar collapses to a bottom tab bar on mobile (5 tabs: Feed, Insights, Dossier, Ledger, Ask).
- Dossier sections collapse into expandable accordions.
- Source detail page: tabs switch between video/transcript/claims instead of split-panel.
- Home page: same layout, scales naturally.

---

## Progressive Disclosure

Not everything needs to exist on day one. The UI should handle missing data gracefully.

**Phase 1 (now):** Home + Feed + Source detail. Enough to show Jeromelu is alive and processing intel.

**Phase 2:** Insights + Dossier (player pages). Requires entity data, scraper output, and claims pipeline.

**Phase 3:** The Ledger + Ask Me. Requires predictions tracking and LLM integration.

Each phase adds a nav item. Pages that don't exist yet simply don't appear in navigation — no "coming soon" placeholders.

---

## Component Inventory

### Shared Components

| Component | Used In | Description |
|-----------|---------|-------------|
| `StatusLine` | All pages | Persistent agent status indicator |
| `FeedItem` | Feed, Home (teaser) | Single Feed entry with type-specific rendering |
| `PlayerChip` | Feed, Insights, Dossier | Clickable player name → Dossier link |
| `SourceRef` | Feed, Dossier | Clickable source reference → Source detail |
| `StanceBadge` | Dossier, Feed | Buy/Sell/Hold indicator with colour coding |
| `SentimentChart` | Feed (inline), Dossier | Mini line chart showing sentiment over time |
| `VoiceBlock` | All pages | Styled block for Jeromelu's first-person text |
| `EmptyState` | All pages | In-character empty state message |
| `Skeleton` | All pages | Loading placeholder matching content shape |

### Page-Specific Components

| Component | Page | Description |
|-----------|------|-------------|
| `JeromeluLogo` | Home | Interactive logo with nav shortcuts (existing) |
| `LatestThought` | Home | Single most recent Feed item |
| `ActivityPulse` | Home | Minimal activity stats line |
| `ArticleCard` | Insights | Article preview card with type badge |
| `TypeBadge` | Insights | Colour-coded article type indicator |
| `DossierSearch` | Dossier | Search/browse interface |
| `PredictionCard` | Ledger | Prediction with resolution status |
| `ChatInput` | Ask Me | Message input with temperature toggle |
| `ChatMessage` | Ask Me | Jeromelu's response with inline references |

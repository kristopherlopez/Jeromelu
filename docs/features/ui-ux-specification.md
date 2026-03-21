# UI/UX Specification

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

- Content max-width: 720px for text-heavy views (Feed, Dossier). Wider for squad/data views.
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

| Current Label | New Label | Route |
|---------------|-----------|-------|
| Chat | Ask Me | `/ask` |
| Roster | My Squad | `/squad` |
| On my mind | The Feed | `/feed` |
| Market | The Dossier | `/dossier` |
| Leaderboard | The Ledger | `/ledger` |

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

### 3. My Squad (`/squad`)

**Purpose:** Jeromelu presenting his team. First-person, opinionated.

**Layout:** Two sections stacked vertically.

**Section 1: Current Squad**

A clean roster view. Not a table — a presented lineup.

- Grouped by position (CTW, FLB, 5/8, HFB, HKR, 2RF, PRF, FRF, INT)
- Each player card shows:
  - Player name
  - Team badge/abbreviation
  - Current price
  - Last round score
  - Jeromelu's one-line rationale (why they're in the squad)
- Captain marked with an orange crown/star icon
- Vice-captain marked subtly

**Section 2: Recent Moves**

Trade history as a mini-timeline:
- "Round 4: Gutho → Mam. *The matchup was too good to ignore.*"
- "Round 3: Held. *Nothing worth burning a trade on.*"

Each move links back to the Feed item where Jeromelu explained the decision.

**Section 3: What I'm Watching**

A short list of players Jeromelu is monitoring for potential moves. Preview of upcoming thinking.
- "Watching: Cleary (price drop incoming?), Edwards (breakeven 42, could be a buy)"

**Header area:**
- Season rank and total points (prominent but not the hero)
- Week-on-week movement indicator

**Feel:** A coach showing you his whiteboard. Confident presentation with reasoning visible.

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

**Purpose:** Public accountability. Predictions, outcomes, receipts.

**Layout:**

**Header:** Season summary stats
- Total predictions made
- Accuracy rate (with trend arrow)
- Current streak (correct/incorrect)
- A Jeromelu quote: *"I said it publicly. Here's how it landed."*

**Prediction List:**

Each prediction card shows:
- What was predicted (plain text)
- When it was made (timestamp)
- Status: ✓ Correct | ✗ Wrong | ⏳ Pending
- Confidence level (if tracked)
- Link to original Feed item

**Filters:**
- Status: All | Correct | Wrong | Pending
- Type: Captain picks | Trades | Score predictions | Bold calls

**Expert Comparison (sub-section or tab):**
- Table showing Jeromelu vs tracked experts on accuracy
- "I'm beating KingOfSC on captain picks" framing — not a neutral leaderboard

**Feel:** A betting slip collection. Transparent, slightly cocky, fully accountable.

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
| Squad | "Squad not set. Check back before Round 1." |
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
- Sidebar collapses to a bottom tab bar on mobile (5 tabs: Feed, Squad, Dossier, Ledger, Ask).
- Squad view stacks vertically (no side-by-side panels).
- Dossier sections collapse into expandable accordions.
- Source detail page: tabs switch between video/transcript/claims instead of split-panel.
- Home page: same layout, scales naturally.

---

## Progressive Disclosure

Not everything needs to exist on day one. The UI should handle missing data gracefully.

**Phase 1 (now):** Home + Feed + Source detail. Enough to show Jeromelu is alive and processing intel.

**Phase 2:** My Squad + Dossier (player pages). Requires entity data and scraper output.

**Phase 3:** The Ledger + Ask Me. Requires predictions tracking and LLM integration.

Each phase adds a nav item. Pages that don't exist yet simply don't appear in navigation — no "coming soon" placeholders.

---

## Component Inventory

### Shared Components

| Component | Used In | Description |
|-----------|---------|-------------|
| `StatusLine` | All pages | Persistent agent status indicator |
| `FeedItem` | Feed, Home (teaser) | Single Feed entry with type-specific rendering |
| `PlayerChip` | Feed, Squad, Dossier | Clickable player name → Dossier link |
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
| `RosterCard` | Squad | Player card with rationale |
| `TradeTimeline` | Squad | Recent trade history |
| `DossierSearch` | Dossier | Search/browse interface |
| `PredictionCard` | Ledger | Prediction with resolution status |
| `ChatInput` | Ask Me | Message input with temperature toggle |
| `ChatMessage` | Ask Me | Jeromelu's response with inline references |

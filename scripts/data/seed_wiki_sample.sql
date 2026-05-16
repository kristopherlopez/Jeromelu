-- Seed wiki with sample data: 2 players, 2 teams, 2 advisors
-- Uses existing entity IDs where possible, creates advisor entities fresh

BEGIN;

-- ─────────────────────────────────────────────────────────────
-- 1. Set slugs on existing entities
-- ─────────────────────────────────────────────────────────────
UPDATE entities SET slug = 'tom-trbojevic'  WHERE entity_id = '9cb4a1e2-20c6-4e90-ac44-d9cd7c6ca356';
UPDATE entities SET slug = 'nathan-cleary'  WHERE entity_id = '4471c483-ee67-4ead-940a-9ecd97af32a2';
UPDATE entities SET slug = 'panthers'       WHERE entity_id = 'd8be0ff9-0572-43f6-8f96-a28429ee95e6';
UPDATE entities SET slug = 'storm'          WHERE entity_id = 'faaf8f95-b3b8-4da7-a2f1-fd1f049ee7d7';

-- ─────────────────────────────────────────────────────────────
-- 2. Create advisor entities
-- ─────────────────────────────────────────────────────────────
INSERT INTO entities (entity_id, entity_type, canonical_name, slug, aliases, metadata_json)
VALUES
  ('a0000001-0000-0000-0000-000000000001', 'advisor', 'SC Playbook', 'sc-playbook',
   ARRAY['SC Playbook NRL', 'SC Playbook NRL Podcast'], '{"platform": "youtube"}'::jsonb),
  ('a0000001-0000-0000-0000-000000000002', 'advisor', 'The SuperCoach NRL Podcast', 'the-supercoach-nrl-podcast',
   ARRAY['SuperCoach NRL Podcast', 'SCNRL Pod'], '{"platform": "youtube"}'::jsonb)
ON CONFLICT (slug) WHERE slug IS NOT NULL DO NOTHING;

-- ─────────────────────────────────────────────────────────────
-- 3. Wiki pages
-- ─────────────────────────────────────────────────────────────

-- Player: Tom Trbojevic
INSERT INTO wiki_pages (entity_id, page_type, slug, title, summary, status, content) VALUES (
  '9cb4a1e2-20c6-4e90-ac44-d9cd7c6ca356', 'player', 'tom-trbojevic',
  'Tom Trbojevic',
  'Premium fullback for Manly. Elite ceiling but extensive injury history makes him a high-risk, high-reward SuperCoach asset.',
  'published',
  '## Overview

Tom Trbojevic is one of the most devastating attacking fullbacks in the NRL when fit. Playing for the [[sea-eagles]], he combines elite speed, footballing instincts, and an ability to create something from nothing. In SuperCoach, he sits in the premium fullback bracket — capable of 100+ scores on his day, but rarely available for a full season.

> **Callout:** Turbo is the definition of a risk-reward pick. When he plays, he''s arguably the best fullback in the game. The problem is he averages 14 games a season over the last four years.

## Current Form

Through the opening rounds of 2026, Trbojevic has looked sharp when on the field. His running metres are up, his try involvements are strong, and Manly''s attack clearly flows through him. The concern, as always, is durability.

| Metric | Value | Rank (FLB) |
|--------|-------|------------|
| Avg SC Points | 74.3 | 4th |
| Price | $487,200 | Mid-premium |
| Breakeven | 61 | Comfortable |
| Games Played | 4/5 | Missed Rd 3 |

## Price Analysis

His price bottomed mid-season last year after missing eight straight rounds. Anyone who bought the dip and held would have seen a $150k rise through the finals. The pattern is predictable: injury → price crash → recovery → price spike.

> **Mechanism:** Trbojevic''s SuperCoach pricing follows a boom-bust cycle driven by availability, not form. When he plays, his scores keep his breakeven manageable. When he misses time, his price craters — creating a buy window for coaches willing to accept the risk.

## Expert Opinions

The advisory community is split on Turbo this season:

- [[sc-playbook]] have been consistently `[BULLISH]` — they argue the discount is too steep to ignore and that Manly''s system is built to protect him
- [[the-supercoach-nrl-podcast]] are more cautious, rating him `[HOLD]` — they flag the hamstring history and prefer [[nathan-cleary]] as the premium fullback pick

> **Verdict:** If you can stomach the bye-round planning and have a strong backup option on your bench, Trbojevic at his current price represents genuine value. But he is not a season-long set-and-forget.

## Injury History

This is where it gets uncomfortable. The hamstring has been a recurring theme since 2021:

- **2025:** Missed 10 games (hamstring, then shoulder)
- **2024:** Missed 8 games (hamstring)
- **2023:** Missed 12 games (knee reconstruction)
- **2022:** Played 20 games — his healthiest season in four years

> **Warning:** Three of the last four seasons have seen Trbojevic miss 8+ games. Any purchase must be made with a contingency plan for extended absence.

## SuperCoach Verdict

`[BUY]` at current price if you have bench cover. `[AVOID]` if you need reliability from your fullback slot. He is not a middle-ground pick — commit to the upside or steer clear entirely.'
) ON CONFLICT (slug) DO NOTHING;

-- Player: Nathan Cleary
INSERT INTO wiki_pages (entity_id, page_type, slug, title, summary, status, content) VALUES (
  '4471c483-ee67-4ead-940a-9ecd97af32a2', 'player', 'nathan-cleary',
  'Nathan Cleary',
  'Penrith halfback and SuperCoach royalty. The safest premium in the game — enormous floor, captaincy upside, and the best team around him.',
  'published',
  '## Overview

Nathan Cleary is the heartbeat of the [[panthers]] and the benchmark halfback in SuperCoach. Playing behind the best forward pack in the NRL, Cleary has the luxury of time, field position, and a team that manufactures points even on off nights. He''s been the #1 ranked halfback in three of the last four seasons.

> **Callout:** There is no safer premium in SuperCoach. Cleary''s floor is other players'' ceilings. The only question is whether you captain him or someone with a higher ceiling on any given week.

## Current Form

Cleary has started 2026 in ominous fashion. Five straight 70+ scores, two tons, and he''s barely out of second gear. The Panthers'' early-season dominance means he''s getting through games without needing to force anything — which, paradoxically, is when he''s most dangerous.

| Metric | Value | Rank (HFB) |
|--------|-------|------------|
| Avg SC Points | 82.1 | 1st |
| Price | $612,400 | Top premium |
| Breakeven | 72 | Needs monitoring |
| Games Played | 5/5 | Full availability |

## Price Analysis

Cleary is expensive and his breakeven is creeping up — but that''s the cost of owning the best. His price ceiling is north of $700k if he maintains this output. The risk isn''t a crash; it''s stagnation. If his scores dip even slightly toward 65 PPG, you''re holding an expensive asset that''s losing money.

> **Mechanism:** Premium halfbacks in SuperCoach follow a different pricing logic to other positions. Their consistency compresses breakevens — a high price with a high breakeven is sustainable if the floor stays above 65. Cleary''s floor is the highest in the game.

## Expert Opinions

Universal consensus across the advisory community:

- [[sc-playbook]] rate him `[CAPTAIN]` material every single week — "If you don''t know who to captain, it''s Cleary"
- [[the-supercoach-nrl-podcast]] agree on `[BUY]` and flag him as essential — "You can''t win SuperCoach without him at some point in the season"

There is virtually no bearish take on Cleary across any major podcast or analyst. The only debate is *when* to bring him in, not *whether*.

## Captaincy Value

This is where Cleary separates from the pack. As a captain option, his consistency is unmatched:

- **2025 captain scores (top 5):** 87, 92, 78, 104, 81
- **Lowest captain score:** 58 (only once below 65 all season)
- **Captain ROI vs field:** +12.3 PPG average advantage

> **Verdict:** Cleary is the safest captain pick in any given round. You won''t always win the captaincy battle with him, but you will almost never lose it badly. That floor protection is worth more than chasing ceiling plays week to week.

## SuperCoach Verdict

`[BUY]` — essential at some point. The only question is timing. If you don''t own him, you need a plan to get him. If you do own him, he''s a season-long hold with weekly captaincy upside.'
) ON CONFLICT (slug) DO NOTHING;

-- Team: Panthers
INSERT INTO wiki_pages (entity_id, page_type, slug, title, summary, status, content) VALUES (
  'd8be0ff9-0572-43f6-8f96-a28429ee95e6', 'team', 'panthers',
  'Penrith Panthers',
  'The NRL''s dominant force. Four straight grand finals, three premierships. A SuperCoach factory built on system, depth, and relentless forward pressure.',
  'published',
  '## Overview

The Penrith Panthers have been the NRL''s benchmark club since 2020. Under Ivan Cleary, they''ve built a system so deep that losing Origin players barely registers. For SuperCoach purposes, the Panthers are the gift that keeps giving — their forward pack produces elite base stats, their halves control games, and even their bench players score above replacement level.

> **Callout:** If you''re building a SuperCoach team and you don''t have at least two Panthers in your squad, you''re making life harder than it needs to be.

## Playing Style

The Panthers play a forward-dominated, field-position game. They complete at elite rates (~82%), defend their own line ferociously, and then score in clusters when the opposition fatigues. This translates directly to SuperCoach:

- **Forwards** accumulate massive base stats through high completion rates and long sets
- **Halves** ([[nathan-cleary]] and Jarome Luai''s replacement) benefit from constant attacking field position
- **Outside backs** get clean ball late in sets and finish at a high rate

> **Mechanism:** The Panthers'' SuperCoach value comes from their system, not individual brilliance. Their forwards average 15% more tackles and 10% more running metres than the league average, purely because they complete more sets and spend more time in the opposition half.

## Key SuperCoach Assets

| Player | Position | SC Avg | Verdict |
|--------|----------|--------|---------|
| [[nathan-cleary]] | HFB | 82.1 | `[BUY]` — essential premium |
| Isaah Yeo | 2RF | 71.4 | `[BUY]` — safest forward in the game |
| James Fisher-Harris | FRF | 68.2 | `[HOLD]` — elite but expensive |
| Moses Leota | FRF | 54.8 | `[BREAKOUT]` — underpriced workhorse |

## Schedule Outlook

The Panthers'' draw is front-loaded with away games through the Origin period, then a favourable home stretch post-Origin. For SuperCoach coaches planning trades:

- **Rounds 6-10:** Tough stretch (Roosters, Storm, Sharks away)
- **Rounds 15-20:** Soft draw with three home games against bottom-8 teams
- **Finals:** The Panthers will be there. They always are.

## SuperCoach Verdict

Stack Panthers. Their system-driven consistency means even mid-range Panthers players outperform equivalents at other clubs. The forward pack is the best in the game for base stats, and [[nathan-cleary]] is the single most important player in SuperCoach.'
) ON CONFLICT (slug) DO NOTHING;

-- Team: Storm
INSERT INTO wiki_pages (entity_id, page_type, slug, title, summary, status, content) VALUES (
  'faaf8f95-b3b8-4da7-a2f1-fd1f049ee7d7', 'team', 'storm',
  'Melbourne Storm',
  'The perennial contenders. Post-Bellamy transition underway but the system still churns out SuperCoach value across every position.',
  'published',
  '## Overview

The Melbourne Storm have been a SuperCoach powerhouse for over a decade. Even as the post-Craig Bellamy era begins, the Storm''s system continues to produce reliable fantasy assets. Their defence-first mentality generates tackle counts, their structured attack creates consistent try-scoring opportunities, and their culture means players rarely underperform their ability.

> **Callout:** Melbourne is the one club where you can buy almost any starting player and know you''re getting close to their ceiling. The system doesn''t allow passengers.

## Playing Style

The Storm play a disciplined, high-completion, defence-oriented game. Their SuperCoach value comes from:

- **Elite tackle counts** — Storm forwards regularly top 40 tackles per game in grinding contests
- **Structured try-scoring** — they score through set plays and repeat sets rather than broken-field brilliance
- **Player accountability** — minutes are earned, not given. Players who produce keep their spot; those who don''t get replaced quickly

> **Mechanism:** The Storm''s coaching system extracts maximum SuperCoach output per minute played. Their bench rotation is aggressive — starters get 55-65 minutes but produce at higher intensity. This compresses scoring into a shorter window but maintains per-minute rates that rival anyone in the NRL.

## Key SuperCoach Assets

| Player | Position | SC Avg | Verdict |
|--------|----------|--------|---------|
| Jahrome Hughes | HFB | 75.8 | `[BUY]` — consistent premium half |
| Harry Grant | HOK | 71.2 | `[BUY]` — best hooker in SC |
| Nelson Asofa-Solomona | FRF | 58.4 | `[HOLD]` — minute-limited but impactful |
| Ryan Papenhuyzen | FLB | 68.9 | `[HOLD]` — explosive but injury-prone |

## Key Concern: Transition

The elephant in the room is the coaching transition. The Storm''s system has been Bellamy''s system for 20 years. Early signs suggest continuity, but there''s a non-zero chance the defensive structures that generate elite tackle counts start to erode.

> **Warning:** Monitor completion rates and tackle counts through rounds 6-10. If the Storm''s defensive metrics slip below 80% completion rate, the SuperCoach value proposition for their forwards changes significantly.

## SuperCoach Verdict

Still a strong source of fantasy value across multiple positions. Harry Grant and Jahrome Hughes are near-essential. The forward pack offers value at multiple price points. But watch the defensive metrics — the post-Bellamy transition is the biggest unknown in NRL fantasy this season.'
) ON CONFLICT (slug) DO NOTHING;

-- Advisor: SC Playbook
INSERT INTO wiki_pages (entity_id, page_type, slug, title, summary, status, content) VALUES (
  'a0000001-0000-0000-0000-000000000001', 'advisor', 'sc-playbook',
  'SC Playbook',
  'One of the most popular SuperCoach podcasts. Known for bold calls, strong opinions, and detailed statistical breakdowns.',
  'published',
  '## Overview

SC Playbook is one of the most-listened-to NRL SuperCoach podcasts, publishing multiple episodes per week during the season. They''re known for taking strong positions on players, backing their calls publicly, and providing detailed statistical breakdowns to support their recommendations.

> **Callout:** SC Playbook doesn''t hedge. When they say buy, they mean it. When they say sell, they''ll tell you exactly why. This makes them easy to track and easy to hold accountable — which is exactly what Jeromelu does.

## Style & Approach

SC Playbook leans heavily on:

- **Statistical analysis** — breakevens, PPM (points per minute), rolling averages
- **Matchup context** — they factor in opposition defensive records, not just player form
- **Bold calls** — they''re willing to call players busts or must-buys earlier than most

They tend to be `[BULLISH]` on premium players and aggressive on early-season trades. Their philosophy is that waiting costs you money — if the data says move, move now.

## Notable Calls This Season

### Hits
- Called [[tom-trbojevic]] as a buy in round 2 at $452k — he''s risen $35k since
- Identified Moses Leota as a `[BREAKOUT]` forward before anyone else

### Misses
- Backed Bradman Best as a top-6 CTW — he''s averaged 48 through 5 rounds
- Called Parramatta''s forward pack as underrated — they''ve been bottom-4

## Track Record

| Metric | 2026 (so far) | 2025 |
|--------|--------------|------|
| Buy calls correct | 7/11 (64%) | 58% |
| Sell calls correct | 4/6 (67%) | 62% |
| Captain picks | 3/5 best option | 41% hit rate |

> **Verdict:** SC Playbook is a reliable source for statistical analysis and early-mover calls. Their hit rate on buys is above average. Their captain picks are middling. Best used for identifying value targets early, not for weekly captaincy guidance.

## How Jeromelu Uses This Source

SC Playbook is weighted as a `[SOLID]` source for player analysis and price movement predictions. Their buy/sell calls feed into the consensus engine with a reliability weighting based on their rolling 10-round accuracy.'
) ON CONFLICT (slug) DO NOTHING;

-- Advisor: The SuperCoach NRL Podcast
INSERT INTO wiki_pages (entity_id, page_type, slug, title, summary, status, content) VALUES (
  'a0000001-0000-0000-0000-000000000002', 'advisor', 'the-supercoach-nrl-podcast',
  'The SuperCoach NRL Podcast',
  'The OG SuperCoach pod. Conservative, measured, and deeply experienced. Prefer proven assets over speculative punts.',
  'published',
  '## Overview

The SuperCoach NRL Podcast has been running since the early days of NRL SuperCoach. They bring years of experience and a conservative, measured approach to player analysis. Where other podcasts chase the latest breakout, this pod focuses on proven performers and risk management.

> **Callout:** If SC Playbook is the aggressive trader, the SuperCoach NRL Podcast is the patient holder. Their philosophy is that SuperCoach is won by avoiding mistakes, not by chasing upside. Over a full season, that philosophy has merit.

## Style & Approach

Their analysis emphasises:

- **Proven track records** — they want to see 3+ weeks of form before committing
- **Risk management** — bench cover, bye planning, and downside protection
- **Season-long thinking** — they rarely recommend moves for short-term gain

They tend to be `[NEUTRAL]` on unproven players and `[BEARISH]` on injury-prone premiums unless the discount is extreme. This makes them a natural counterweight to more aggressive sources.

## Notable Calls This Season

### Hits
- Warned against early investment in Parramatta players — correct, they''ve underperformed
- Called [[nathan-cleary]] as essential from round 1 — he''s been the #1 half

### Misses
- Were too slow on the Moses Leota breakout — recommended waiting until round 4, missed the price rise
- Called Harry Grant overpriced at the start — he''s justified his price tag

## Track Record

| Metric | 2026 (so far) | 2025 |
|--------|--------------|------|
| Buy calls correct | 5/8 (63%) | 61% |
| Sell calls correct | 5/7 (71%) | 65% |
| Captain picks | 2/5 best option | 38% hit rate |

> **Verdict:** The SuperCoach NRL Podcast is strongest on sell calls and risk identification. Their conservative approach means they miss some upside, but they also avoid more busts than aggressive sources. Best used as a sanity check against bolder calls from other advisors.

## How Jeromelu Uses This Source

Weighted as a `[SOLID]` source for sell signals and risk assessment. Their conservative lens provides a natural counterbalance to more aggressive sources in the consensus engine. When both SC Playbook and this pod agree on a call, it''s a high-conviction signal.'
) ON CONFLICT (slug) DO NOTHING;

-- ─────────────────────────────────────────────────────────────
-- 4. Set slugs on the Sea Eagles entity (referenced in wiki-links)
-- ─────────────────────────────────────────────────────────────
UPDATE entities SET slug = 'sea-eagles' WHERE entity_id = '8e6be847-28dc-48ca-84bf-e1ac5519edca';

-- ─────────────────────────────────────────────────────────────
-- 5. Create wiki stubs for referenced entities that don't have pages
-- ─────────────────────────────────────────────────────────────
INSERT INTO wiki_pages (entity_id, page_type, slug, title, summary, status, content) VALUES (
  '8e6be847-28dc-48ca-84bf-e1ac5519edca', 'team', 'sea-eagles',
  'Manly Sea Eagles',
  'Home of Tom Trbojevic. Rebuilding contenders with a potent backline when healthy.',
  'stub', ''
) ON CONFLICT (slug) DO NOTHING;

-- ─────────────────────────────────────────────────────────────
-- 6. Create revisions for all pages
-- ─────────────────────────────────────────────────────────────
INSERT INTO wiki_revisions (page_id, summary, source_trigger)
SELECT page_id, 'Initial page created with full content', 'seed_wiki_sample.sql'
FROM wiki_pages WHERE status = 'published';

INSERT INTO wiki_revisions (page_id, section_heading, summary, source_trigger)
SELECT page_id, 'Current Form', 'Updated form stats through Round 5', 'round_results:5'
FROM wiki_pages WHERE slug IN ('tom-trbojevic', 'nathan-cleary');

INSERT INTO wiki_revisions (page_id, section_heading, summary, source_trigger)
SELECT page_id, 'Expert Opinions', 'Added SC Playbook and SuperCoach NRL Podcast takes', 'source_ingest'
FROM wiki_pages WHERE slug IN ('tom-trbojevic', 'nathan-cleary');

INSERT INTO wiki_revisions (page_id, section_heading, summary, source_trigger)
SELECT page_id, 'Notable Calls This Season', 'Updated hit/miss tracking through Round 5', 'round_results:5'
FROM wiki_pages WHERE slug IN ('sc-playbook', 'the-supercoach-nrl-podcast');

COMMIT;

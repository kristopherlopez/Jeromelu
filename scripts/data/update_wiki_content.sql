-- Update wiki content to use custom block syntax for rich components

BEGIN;

-- ── Tom Trbojevic ──
UPDATE wiki_pages SET content = '## Overview

Tom Trbojevic is one of the most devastating attacking fullbacks in the NRL when fit. Playing for the [[sea-eagles]], he combines elite speed, footballing instincts, and an ability to create something from nothing. In SuperCoach, he sits in the premium fullback bracket — capable of 100+ scores on his day, but rarely available for a full season.

> **Callout:** Turbo is the definition of a risk-reward pick. When he plays, he''s arguably the best fullback in the game. The problem is he averages 14 games a season over the last four years.

## Current Form

Through the opening rounds of 2026, Trbojevic has looked sharp when on the field. His running metres are up, his try involvements are strong, and Manly''s attack clearly flows through him. The concern, as always, is durability.

:::stats
| Label | Value | Sub |
|-------|-------|-----|
| Avg SC Points | 74.3 | Ranked 4th (FLB) |
| Price | $487k | Mid-premium |
| Breakeven | 61 | Comfortable |
| Games Played | 4/5 | Missed Rd 3 |
:::

## Price Analysis

His price bottomed mid-season last year after missing eight straight rounds. Anyone who bought the dip and held would have seen a $150k rise through the finals. The pattern is predictable: injury → price crash → recovery → price spike.

> **Mechanism:** Trbojevic''s SuperCoach pricing follows a boom-bust cycle driven by availability, not form. When he plays, his scores keep his breakeven manageable. When he misses time, his price craters — creating a buy window for coaches willing to accept the risk.

## Expert Opinions

The advisory community is split on Turbo this season:

:::trust
| Rating | Name | Description |
|--------|------|-------------|
| Bullish | SC Playbook | Consistently bullish — they argue the discount is too steep to ignore and that Manly''s system is built to protect him. Called him a buy in round 2 at $452k. |
| Hold | The SuperCoach NRL Podcast | More cautious — they flag the hamstring history and prefer Nathan Cleary as the premium fullback pick. Recommend waiting for a full clean run. |
:::

> **Verdict:** If you can stomach the bye-round planning and have a strong backup option on your bench, Trbojevic at his current price represents genuine value. But he is not a season-long set-and-forget.

## Injury History

This is where it gets uncomfortable. The hamstring has been a recurring theme since 2021:

:::timeline
| Year | Color | Title | Description | Signal |
|------|-------|-------|-------------|--------|
| ''25 | red | 2025 Season | Missed <strong>10 games</strong> — hamstring, then shoulder | Returned for finals but looked underdone in elimination loss |
| ''24 | red | 2024 Season | Missed <strong>8 games</strong> — recurring hamstring | Started strong, broke down in Origin period |
| ''23 | red | 2023 Season | Missed <strong>12 games</strong> — knee reconstruction | Season-ending injury in Round 10 |
| ''22 | green | 2022 Season | Played <strong>20 games</strong> — his healthiest season in four years | This is the ceiling: what Turbo looks like with a full preseason |
:::

> **Warning:** Three of the last four seasons have seen Trbojevic miss 8+ games. Any purchase must be made with a contingency plan for extended absence.

## SuperCoach Verdict

:::final-verdict
`[BUY]` at current price if you have bench cover. `[AVOID]` if you need reliability from your fullback slot. He is not a middle-ground pick — commit to the upside or steer clear entirely.
:::'
WHERE slug = 'tom-trbojevic';

-- ── Nathan Cleary ──
UPDATE wiki_pages SET content = '## Overview

Nathan Cleary is the heartbeat of the [[panthers]] and the benchmark halfback in SuperCoach. Playing behind the best forward pack in the NRL, Cleary has the luxury of time, field position, and a team that manufactures points even on off nights. He''s been the #1 ranked halfback in three of the last four seasons.

> **Callout:** There is no safer premium in SuperCoach. Cleary''s floor is other players'' ceilings. The only question is whether you captain him or someone with a higher ceiling on any given week.

## Current Form

Cleary has started 2026 in ominous fashion. Five straight 70+ scores, two tons, and he''s barely out of second gear. The Panthers'' early-season dominance means he''s getting through games without needing to force anything — which, paradoxically, is when he''s most dangerous.

:::stats
| Label | Value | Sub |
|-------|-------|-----|
| Avg SC Points | 82.1 | Ranked 1st (HFB) |
| Price | $612k | Top premium |
| Breakeven | 72 | Needs monitoring |
| Games Played | 5/5 | Full availability |
:::

## Price Analysis

Cleary is expensive and his breakeven is creeping up — but that''s the cost of owning the best. His price ceiling is north of $700k if he maintains this output. The risk isn''t a crash; it''s stagnation.

> **Mechanism:** Premium halfbacks in SuperCoach follow a different pricing logic to other positions. Their consistency compresses breakevens — a high price with a high breakeven is sustainable if the floor stays above 65. Cleary''s floor is the highest in the game.

## Expert Opinions

Universal consensus across the advisory community:

:::trust
| Rating | Name | Description |
|--------|------|-------------|
| Captain | SC Playbook | Rate him captain material every single week — "If you don''t know who to captain, it''s Cleary" |
| Buy | The SuperCoach NRL Podcast | Agree on essential status — "You can''t win SuperCoach without him at some point in the season" |
:::

There is virtually no bearish take on Cleary across any major podcast or analyst. The only debate is *when* to bring him in, not *whether*.

## Captaincy Value

This is where Cleary separates from the pack. As a captain option, his consistency is unmatched:

:::stats
| Label | Value | Sub |
|-------|-------|-----|
| Best Captain Score | 104 | Round 4, 2025 |
| Lowest Captain Score | 58 | Only once below 65 |
| Captain ROI vs Field | +12.3 PPG | Average advantage |
| Top-5 Rate | 68% | In top 5 captain scores |
:::

> **Verdict:** Cleary is the safest captain pick in any given round. You won''t always win the captaincy battle with him, but you will almost never lose it badly. That floor protection is worth more than chasing ceiling plays week to week.

## SuperCoach Verdict

:::final-verdict
`[BUY]` — essential at some point. The only question is timing. If you don''t own him, you need a plan to get him. If you do own him, he''s a season-long hold with weekly captaincy upside.
:::'
WHERE slug = 'nathan-cleary';

COMMIT;

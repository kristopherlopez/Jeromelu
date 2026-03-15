# Supercoach & NRL API Research

## Supercoach API

**Auth:** OAuth2 with `LegacyApplicationClient` (oauthlib). Reference: [edgecate/Supercoach](https://github.com/edgecate/Supercoach).

- Token endpoint pattern: `/{year}/api/{sport}/classic/v1/access_token`
- NRL variant likely: `https://supercoach.dailytelegraph.com.au/{year}/api/nrl/classic/v1/access_token` (or migrated to `codesports.com.au`)
- Requires `client_id`, username, password
- Token appended as query param on subsequent requests
- Stats centre: `/{sport}/draft/statscentre?access_token={token}`
- Response: JSON with player names, positions, prices, scores by round, breakevens, averages
- **Action needed:** Log into Supercoach, inspect XHR in DevTools to confirm exact 2026 endpoints

## NRL API (nrl.com)

No official public docs. Endpoints discoverable via browser DevTools.

- Draw: `https://www.nrl.com/draw/` (underlying JSON via XHR)
- Draw Hub: `https://draw-hub.nrl.com/`
- Stats: `https://www.nrl.com/stats/`
- Match Centre: `https://www.nrl.com/draw/nrl-premiership/{year}/round-{n}/{match-slug}/`
- **No auth required** for public nrl.com endpoints

## NRL Fantasy (fantasy.nrl.com)

- 5-6 JSON files served on page load (discoverable via network tab)
- Contains player data, team data, stadium data
- Historically **unauthenticated** (as of 2022, may have changed)
- Reference: [Morgan Potter blog](https://morgan-potter.github.io/2022/05/24/NRL-Fantasy-Data.html)

## Community GitHub Repos

| Repo | Lang | What | Source |
|------|------|------|--------|
| [edgecate/Supercoach](https://github.com/edgecate/Supercoach) | Python | OAuth2 auth + scraping (AFL, pattern applies to NRL) | Supercoach API |
| [beauhobba/NRL-Data](https://github.com/beauhobba/NRL-Data) | Python | Selenium scraper for player stats by round, includes ML | nrl.com |
| [DanielTomaro13/nrlR](https://github.com/DanielTomaro13/nrlR) | R | Ladders, fixtures, player/team stats, 1998+ | nrl.com, rugbyleagueproject.org |
| [uselessnrlstats](https://github.com/uselessnrlstats/uselessnrlstats) | Python+R | Scraper + analysis, CSV data included | rugbyleagueproject.org |

## Community Data Sites

| Site | URL | Offers |
|------|-----|--------|
| NRL Supercoach Stats | nrlsupercoachstats.com | Scores, averages, PPMs, prices, breakevens |
| SuperCoach Data | supercoachdata.com/scnrl/ | NRL SuperCoach analytics |
| SC Playbook | scplaybook.com.au | News, analysis, team list breakdowns |
| Footy Statistics | footystatistics.com | Breakevens, price history |
| Rugby League Project | rugbyleagueproject.org | Historical data (primary source for scrapers) |
| Fixture Download | fixturedownload.com | Fixtures as CSV, XLSX, ICS, JSON |

## Recommended Approach

1. **Supercoach data (prices, breakevens, SC scores):** Reverse-engineer endpoints via browser DevTools. Use edgecate OAuth2 pattern for auth.
2. **NRL match stats:** Use nrl.com XHR endpoints (no auth) or beauhobba/NRL-Data Selenium approach.
3. **NRL Fantasy JSON:** Hit fantasy.nrl.com endpoints directly (check if still unauthenticated).
4. **Historical backfill:** rugbyleagueproject.org + fixturedownload.com for fixtures.

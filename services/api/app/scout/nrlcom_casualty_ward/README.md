# Scout / nrl.com Casualty Ward

Daily snapshot of the official league-wide injury roll.

| Field | Value |
|---|---|
| Source | `nrl.com/casualty-ward/data?season=Y` |
| Cadence | Daily (state changes weekly+) |
| Historical reach | Current season only — no historical query param |
| Pipeline label | `nrlcom-casualty-ward` |
| Endpoint | `POST /api/admin/scout/nrlcom-casualty-ward[?season=Y]` |
| Make target | `make scout-nrlcom-casualty-ward [SEASON=2026]` |
| S3 archive | `scout/nrlcom/casualty-ward/{comp}/{YYYYMMDD}.json` (timestamped — preserves daily history) |
| DB extraction | **Deferred** — downstream extractor reads S3 → writes `injuries` |

Each casualty entry: `firstName, lastName, teamNickname, injury, expectedReturn, imageUrl, theme, url`. ~98 entries currently.

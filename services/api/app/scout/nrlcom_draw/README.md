# Scout / nrl.com Draw

Captures fixture data per round.

| Field | Value |
|---|---|
| Source | `nrl.com/draw/data?competition=&season=&round=` |
| Cadence | Daily (current+lookahead); also backfill for historical seasons |
| Historical reach | 1908 (filterSeasons has 119 entries) |
| Pipeline label | `nrlcom-draw` |
| Endpoint | `POST /api/admin/scout/nrlcom-draw?competition=N&season=Y[&round=N]` |
| Make target | `make scout-nrlcom-draw COMPETITION=111 SEASON=2026 [ROUND=N]` |
| S3 archive | `scout/nrlcom/draw/{comp}/{season}/round-{NN}.json` |
| DB extraction | **Deferred** — downstream extractor reads S3 → writes `matches`, `rounds` |

NRL premiership = competition `111`. NRLW / NSW Cup / QLD Cup have other comp IDs.

If `round` is omitted, the response contains the *current* round's fixtures + all filter metadata.

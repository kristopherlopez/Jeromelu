# Scout / nrl.com Ladder

Per-round team standings + 22 per-team metrics (form, streak, points-for/against, home/away/day/night records, average margins, betting odds).

| Field | Value |
|---|---|
| Source | `nrl.com/ladder/data?competition=&season=[&round=]` |
| Cadence | Per-round post-FullTime |
| Historical reach | ~1990s (29 seasons in filter) |
| Pipeline label | `nrlcom-ladder` |
| Endpoint | `POST /api/admin/scout/nrlcom-ladder?competition=N&season=Y[&round=N]` |
| Make target | `make scout-nrlcom-ladder COMPETITION=111 SEASON=2026 [ROUND=N]` |
| S3 archive | `scout/nrlcom/ladder/{comp}/{season}/round-{NN}.json` |
| DB extraction | **Deferred** — Phase 4: writes `team_standings` (new table) |

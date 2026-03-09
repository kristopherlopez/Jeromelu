# 3.1 API Endpoints

**Phase:** 3 — API & Frontend
**Priority:** 6 (feed), 9 (remaining)
**Service:** `services/api`

## Tasks
- [ ] `GET /feed` — paginated live feed events
- [ ] `GET /feed/latest` — latest events (for polling/SSE)
- [ ] `GET /team` — current squad state
- [ ] `GET /team/history` — trade history, captain choices
- [ ] `GET /predictions` — prediction ledger
- [ ] `GET /predictions/{id}` — prediction detail with evidence
- [ ] `GET /consensus/{player_id}` — player consensus data
- [ ] `GET /entities/players` — player list with search
- [ ] `GET /entities/players/{id}` — player profile with claims, predictions
- [ ] `GET /entities/experts` — expert list with accuracy scores
- [ ] `GET /sources` — source list
- [ ] `POST /chat` — Ask Jeromelu (chat interface)
- [ ] Authentication/API key middleware
- [ ] Rate limiting
- [ ] Error handling and validation

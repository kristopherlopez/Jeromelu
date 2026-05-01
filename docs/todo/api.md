---
tags: [area/todo, status/planning]
---

# 3.1 API Endpoints

**Phase:** 3 — API & Frontend
**Priority:** 6 — First public-facing feature (feed endpoint)
**Service:** `services/api`

## Tasks

### Read endpoints

- [ ] `GET /feed` — paginated live feed events
- [ ] `GET /feed/latest` — latest events (polling/SSE)
- [ ] `GET /team` — current squad state
- [ ] `GET /team/history` — trade history, captain choices
- [ ] `GET /predictions` — prediction ledger
- [ ] `GET /predictions/{id}` — prediction detail with evidence
- [ ] `GET /consensus/{player_id}` — player consensus data
- [ ] `GET /entities/players` — player list with search
- [ ] `GET /entities/players/{id}` — player profile with claims, predictions
- [ ] `GET /entities/experts` — expert list with accuracy scores
- [ ] `GET /sources` — source list

### Write endpoints

- [ ] `POST /chat` — Ask Jaromelu (chat interface)

### Cross-cutting

- [ ] Authentication / API key middleware
- [ ] Rate limiting
- [ ] Error handling and validation

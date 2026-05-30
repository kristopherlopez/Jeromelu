# Miner Package Layout

Miner is the API-side acquisition boundary. Everything here should either
capture external data or support that capture. Downstream interpretation
belongs to Analyst, Bookkeeper, Archivist, or feature routers.

## Top Level

| Path | Purpose |
|---|---|
| `routes.py` | Aggregates all Miner admin pipeline routers for `app.main`. |
| `common/` | Shared deterministic-pipeline plumbing: audit rows, archive detail flags, raw-response S3 archive writer. |
| `source_discovery/` | Deterministic YouTube discovery plus agentic web/off-platform discovery. |
| `presenter_research/` | Agentic presenter/person research for one known channel. |
| `youtube/` | YouTube Data API client plus refresh/metrics/coverage jobs. |
| `media/` | YouTube audio acquisition plus legacy/debug persistent video helpers and CLIs. |

## Pipeline Folders

Each deterministic feed pipeline keeps its owned code together:

```text
<pipeline>/
  __init__.py      # router export
  fetcher.py       # upstream HTTP/source call
  models.py        # strict Pydantic models when the pipeline has a D8 contract
  routes.py        # POST /api/admin/miner/<pipeline>
  README.md        # source, cadence, archive path, drift notes
```

The current `nrlcom_*` pure-capture folders without `models.py` intentionally
archive raw snapshots only. Add strict models and fixture-backed tests before
using those payloads for DB extraction.

## Tests

Tests mirror the source packages:

```text
tests/unit/api/miner/<pipeline>/test_models.py
tests/integration/miner/<pipeline>/test_response_shape.py
tests/fixtures/miner/<pipeline>/canonical_response.json
```

Shared Miner tests live under `tests/unit/api/miner/`; package-specific tests
should follow the package name when a folder grows enough to need it.

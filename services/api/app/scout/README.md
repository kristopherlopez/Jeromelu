# Scout Package Layout

Scout is the API-side acquisition boundary. Everything here should either
capture external data or support that capture. Downstream interpretation
belongs to Analyst, Bookkeeper, Archivist, or feature routers.

## Top Level

| Path | Purpose |
|---|---|
| `routes.py` | Aggregates all Scout admin pipeline routers for `app.main`. |
| `common/` | Shared deterministic-pipeline plumbing: audit rows, archive detail flags. |
| `loop.py`, `tools.py`, `prompt.py`, `cli.py` | Agentic YouTube source discovery. |
| `presenters.py`, `presenters_cli.py` | Agentic presenter discovery for one channel. |
| `refresh.py`, `youtube_api.py` | Deterministic YouTube API refresh and metrics helpers. |
| `audio.py`, `video.py` plus `*_cli.py` | YouTube media acquisition helpers. |
| `_s3_archive.py` | Shared raw-response S3 archive writer. |

## Pipeline Folders

Each deterministic feed pipeline keeps its owned code together:

```text
<pipeline>/
  __init__.py      # router export
  fetcher.py       # upstream HTTP/source call
  models.py        # strict Pydantic models when the pipeline has a D8 contract
  routes.py        # POST /api/admin/scout/<pipeline>
  README.md        # source, cadence, archive path, drift notes
```

The current `nrlcom_*` pure-capture folders without `models.py` intentionally
archive raw snapshots only. Add strict models and fixture-backed tests before
using those payloads for DB extraction.

## Tests

Tests mirror the source packages:

```text
tests/unit/api/scout/<pipeline>/test_models.py
tests/integration/scout/<pipeline>/test_response_shape.py
tests/fixtures/scout/<pipeline>/canonical_response.json
```

Root-level Scout modules such as `refresh.py` keep root-level tests under
`tests/unit/api/scout/`.

# Tests

Three tiers, separated by what they need to run.

## Layout

```
tests/
  unit/              # default tier — fast, no IO, no env vars
    shared/          # packages/shared/jeromelu_shared
      test_agent_audit.py     # cost math, run-id, _truncate
      test_scraping_nrl.py    # team codes, names, parsers, JQGRID map
      players/                # placeholder — supercoach roster, name resolution
      db/                     # placeholder — session, model helpers
    api/             # services/api/app
      routers/
        test_admin_helpers.py # _stitch_segments, _chunk_segments, _normalize
      scout/
        test_refresh_helpers.py  # _video_id_from_url, _parse_published_at
        <pipeline>/
          test_models.py         # strict Scout fixture/model contracts
      analyst/
        test_transcribe_helpers.py  # imports from transcribe_helpers.py —
                                    # NEVER import transcribe.py directly
                                    # (drags in pyannote/torch)
    gpu/
      test_deploy_helpers.py  # ECR URI, model/config name constructors
    scripts/         # placeholder — scripts/data/* helpers
  integration/       # needs a real DB / S3 / external infra
    scout/<pipeline>/
      test_response_shape.py     # env-flagged live drift checks
  evals/             # LLM-graded RAG evals via DeepEval (costs $$)
```

Web pure helpers (`getHighestStage`, `funnelClass`, `formatDate` in
`services/web/src/app/admin/`) are **not yet covered** — `services/web`
has no test runner installed. Adding Vitest + a tsconfig path is its
own setup task; pick it up when the frontend grows enough logic to
justify the harness.

Mirror the source tree when adding tests so the home for any new test is
obvious. If a folder has a `.gitkeep` and no tests, it's a placeholder
waiting for coverage in that area.

## Running

```bash
# Unit tests only (default — fast, deterministic, no env vars)
make test

# DeepEval suite — needs OPENAI_API_KEY and DATABASE_URL
make test-eval
```

## CI

`tests/unit/` runs on every PR and on push to master via
`.github/workflows/tests.yml`. The workflow installs only
`requirements-test.txt` — a lightweight subset that **deliberately
excludes** the ML stack (torch, pyannote, deepgram, insightface,
opencv, anthropic, openai, temporalio). Total install + run is well
under a minute.

The pyannote/torch boundary is preserved by splitting `transcribe.py`
into two modules: `transcribe.py` (the pipeline, heavy deps) and
`transcribe_helpers.py` (pure functions, lightweight). Tests import
from `transcribe_helpers` so CI never has to install torch.

CI is currently warning-only — failing tests show a red status check
but do NOT block `deploy.yml`. Promote to a hard gate by adding
`needs: tests` to the deploy job once the workflow has proven stable.

Or invoke pytest directly:

```bash
pytest                              # unit only (per pytest.ini testpaths)
pytest tests/unit/shared            # one area
pytest tests/unit -k stitch         # one function across the suite
pytest tests/evals                  # eval tier (must export keys first)
```

## What goes where

- **unit** — pure functions, table-driven cases, no `Session()`, no HTTP, no
  `boto3.client(...)`, no `.env`. If you'd need to mock more than one thing
  to run it, it probably belongs in `integration/`.
- **integration** — anything that touches the DB schema, MinIO/S3, or a
  live external API. Expect to need `make up` first.
- **evals** — LLM quality / behaviour. Slow, non-deterministic, costs money
  per run. Run on CI weekly, not per-commit.

## Adding a unit test

1. Find the matching folder under `tests/unit/` (or create it next to its
   peers if the source area is new).
2. File name: `test_<module>.py`. Function name: `test_<behaviour>()`.
3. Import directly from the source — `pythonpath` is already set in
   `pytest.ini` so `from app.routers.admin import _stitch_segments` and
   `from jeromelu_shared.scraping.nrl import normalize_team` both work.
4. No fixtures unless the test needs them. Pure-function tests don't.

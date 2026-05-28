---
tags: [area/operations, area/build]
---

# Engineering Quality Hardening

This backlog captures coding and delivery best practices that are not yet
fully enforced in the repo. It complements the existing process rules in
[`CLAUDE.md`](../../CLAUDE.md), [`docs/build/META.md`](../build/META.md),
[`tests/README.md`](../../tests/README.md), and
[`docs/ops/ci-cd.md`](../ops/ci-cd.md).

The intent is to turn repeated review concerns into mechanical checks where
that is cheap, and into clear project invariants where automation would be
too noisy at first.

## Current Baseline

- Python unit tests run in CI via `pytest`.
- Web type checking runs in CI via `npm run typecheck`.
- Terraform has `fmt`, `validate`, and `plan` CI.
- Scout scraper drift tests exist as a strong subsystem pattern.
- Web already has `services/web/eslint.config.mjs`; ESLint is configured but
  not run in CI.
- `.env`, `.env.local`, and `.env.production` are ignored by git.
- Deploy is documented as not yet gated by the test workflow.

## Tier 1 - High Leverage, Low Cost

### 1. Python lint and format

**Gap:** No repo-level Python lint/format configuration is enforced.

**Do:**
- Add Ruff configuration, preferably in a root `pyproject.toml`.
- Use Ruff for linting, formatting, and import sorting.
- Add `make lint-python` and `make format-python` targets.
- Add a CI job that runs Ruff against `services/`, `packages/`, `scripts/`,
  and `tests/`.

**Why:** Catches unused imports, unused variables, many datetime mistakes,
obvious bug patterns, and import-order churn before review.

### 2. Python type checking

**Gap:** The web has `tsc --noEmit`; Python has no equivalent check.

**Do:**
- Add Pyright or mypy for `services/api`, `packages/shared`, key workers, and
  high-value scripts.
- Start as warning-only or with a narrow include set.
- Tighten over time as noisy modules are fixed.

**Why:** The repo has many cross-module contracts: Pydantic models, SQLAlchemy
models, agent helpers, scraper payloads, and data extractors. Type drift is
likely to become expensive.

### 3. Frontend lint in CI

**Gap:** ESLint config exists, but CI does not run `npm run lint`.

**Do:**
- Add `npm run lint` to `.github/workflows/tests.yml`.
- Optionally add a local pre-push branch for web lint next to typecheck.

**Why:** Next.js already provides the lint rules. This is cheap coverage for
React, hooks, accessibility-adjacent rules, and import mistakes.

### 4. Datetime and timezone invariant

**Gap:** There is no explicit project rule for timezone-safe datetime use.

**Do:**
- Add an invariant to `docs/build/META.md`: use timezone-aware datetimes; store
  and compare UTC at DB/API boundaries; avoid `datetime.utcnow()`.
- Enable relevant Ruff datetime rules where practical.
- Prefer `datetime.now(timezone.utc)` in Python.

**Why:** The domain depends on published times, match kickoffs, rounds,
scheduled jobs, transcript timestamps, and cross-region infrastructure.
Naive datetime bugs will be subtle.

### 5. Secret hygiene

**Gap:** `.env` is ignored, but secret-handling rules are not stated as a
project invariant and no repo-level secret scanner is configured.

**Do:**
- Add a short invariant: never commit `.env*`, tokens, keys, or prod secrets;
  redact secrets from logs, issues, comments, and run reports.
- Add Gitleaks or detect-secrets in CI.
- Add Dependabot secret-scanning/security notes if using GitHub-native
  features outside repo code.

**Why:** The project uses AWS, S3, LLM providers, Deepgram, HuggingFace, admin
keys, and self-hosted deployment. A single leaked key has high blast radius.

### 6. Gate deploy on quality checks

**Gap:** `tests.yml` does not currently gate `deploy.yml`.

**Do:**
- Once `pytest`, web typecheck, and lint jobs are stable, make deploy depend on
  them.
- Keep manual migration application separate.

**Why:** Red tests or broken TypeScript should not automatically ship to
Lightsail.

## Tier 2 - Meaningful, More Friction

### 7. Scraper and external API error-handling convention

**Gap:** Fetchers choose their own retry, exception, logging, and user-facing
error behavior.

**Do:**
- Define when to retry, when to fail fast, and when to classify a failure as
  upstream drift.
- Standardize exception names per pipeline, for example
  `<Pipeline>FetchError` and `<Pipeline>DriftError` where useful.
- Standardize status codes for admin endpoints wrapping upstream APIs.
- Decide whether transient retry policy lives in shared helpers.

**Why:** Scout and Analyst both depend on external services. Inconsistent
failure behavior makes cron and operator recovery harder.

### 8. Idempotency for all cron and worker writes

**Gap:** Scout documents idempotent natural-key upserts well, but the rule is
not repo-wide.

**Do:**
- Promote idempotency to a general invariant for cron jobs, workers, backfills,
  and admin-triggered refreshes.
- Document natural keys for each new write path.
- Require a dry-run mode or a fixture-backed pure extraction seam for risky
  backfills.

**Why:** Production jobs will be retried. Re-runs must not duplicate, corrupt,
or downgrade data.

### 9. Dependency hygiene

**Gap:** Dependency files are split across root, service, and package levels.

**Do:**
- Decide which dependency file owns each runtime.
- Add Dependabot or Renovate for Python and npm.
- Add a rule: new dependencies need a reason, runtime owner, and test impact.

**Why:** Dependency sprawl slows CI, bloats images, increases CVE surface, and
makes local setup brittle.

### 10. Migration safety rules

**Gap:** The repo says to apply migrations via `make migrate`, but does not
define online-safe migration patterns.

**Do:**
- Document two-step migrations for risky changes:
  add nullable column -> backfill -> enforce NOT NULL later.
- Avoid destructive drops in the same deploy that removes code reads.
- Prefer indexes that do not block large tables where PostgreSQL supports it.
- Document rollback expectations for each non-trivial migration.

**Why:** This matters more as production data grows and deploys become less
forgiving.

### 11. API response conventions

**Gap:** FastAPI endpoints do not appear to share one documented convention
for error envelopes, pagination, status-code choices, or schema placement.

**Do:**
- Define pagination shape for list endpoints.
- Define common error response style for admin/public APIs.
- Document where request/response Pydantic schemas should live.
- Apply to new endpoints first; migrate old endpoints opportunistically.

**Why:** The API surface is growing across public pages, admin operations, and
agent pipelines.

### 12. Test seams and fakes

**Gap:** Test tiers are well documented, but mocking/faking guidance is thin
outside Scout drift tests.

**Do:**
- Prefer pure extraction helpers for parser/mapper logic.
- Use checked-in fixtures for upstream payload shapes.
- Use fakes over mocks when exercising multi-step behavior.
- Keep live API, DB, and S3 tests in integration, never unit.

**Why:** This preserves fast unit tests while still letting pipelines be tested
against realistic payloads.

## Tier 3 - Useful Later

### 13. Frontend component conventions

Define when components should be server vs client components, where data
fetching should live, and how route-level data modules should be organized.

### 14. Accessibility baseline

Add minimum expectations for keyboard navigation, focus states, labels, color
contrast, and semantic HTML. Run lint/a11y checks where practical.

### 15. SQLAlchemy performance expectations

Document when to use eager loading, how to avoid N+1 queries, and how to review
query count for high-traffic endpoints.

### 16. Deprecation and removal protocol

Document how to remove stale endpoints, scripts, jobs, migrations, and
backwards-compatibility shims without leaving dead references in docs, CI, or
deployment scripts.

### 17. File and function size guidance

Add lightweight guidance only if modules start becoming consistently difficult
to review. Avoid hard line-count rules unless they are solving a real problem.

## Suggested Implementation Order

1. Add Ruff config and CI.
2. Add web lint to CI.
3. Add deploy gating after tests and lint are stable.
4. Add Pyright or mypy in a narrow, warning-first mode.
5. Add secret scanning and Dependabot/Renovate.
6. Update `docs/build/META.md` with timezone, secret hygiene, idempotency,
   dependency, and migration-safety invariants.
7. Standardize scraper error handling and API conventions as new endpoints are
   touched.

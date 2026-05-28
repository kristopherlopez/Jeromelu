# Engineering quality hardening — Tier 1

**Date:** 2026-05-28 · **Status:** 🟡 In flight (2/6 tasks shipped — TASK-47 + TASK-48 [BLOCKED]; TASK-51 + TASK-52 not yet picked up) · **Plan:** [Engineering quality hardening — Tier 1](../PLAN.md#2026-05-28-engineering-quality-hardening--tier-1-ruff--pyright--eslint--gitleaks--deploy-gating)

**TL;DR** — Tier 1 of `docs/operations/engineering-quality-hardening.md` (items 1–6) lands hard-fail CI gates for Python lint (Ruff), Python typecheck (Pyright, narrow), web lint (ESLint), secrets (Gitleaks), and deploys are gated on Tests success. Tier 1 hardening surfaced an unanticipated reality: TASK-47 (Ruff) and TASK-48 (ESLint) both have far more existing violations than the plan's pre-audit anticipated — 875 / 174 files for Ruff, 50 files for ESLint. Both BLOCKED with detailed remediation menus pending the human's rule-set decisions. TASK-49 (Pyright, narrow) shipped clean: 8 errors / 3 files in scope, all addressed (3 real type fixes; 5 suppressions queued as TASK-53 for the underlying schema-drift bug).

---

## What was completed

### TASK-49 — Pyright plumbing (narrow scope: `packages/shared/jeromelu_shared`) (`0bccec8`)

**Files:**
- `pyproject.toml` (new) — `[tool.pyright]` block (include = `packages/shared/jeromelu_shared`; pythonVersion = 3.12; typeCheckingMode = standard; reportMissingImports + reportGeneralTypeIssues = error). Placeholder comment for the future `[tool.ruff]` block (lands when TASK-47 unblocks).
- `requirements-dev.txt` — `pyright>=1.1.380,<2` (range pin per spec). Also `openai==1.65.*` and `temporalio==1.9.*` added so Pyright can resolve SDK imports at module top-level in `llm.py` and `temporal.py` (both in include set). Versions match `services/api/requirements.txt`.
- `.github/workflows/tests.yml` — new `pyright` job alongside `unit` + `web-typecheck`. Installs `requirements-test.txt + requirements-dev.txt`, then pins `pyright==1.1.409` explicitly for CI determinism.
- `Makefile` — `typecheck-python` target. NOTE block above it documents that the umbrella `lint:` target is deferred to TASK-47 unblock (since `lint-python` doesn't exist yet).
- `packages/shared/jeromelu_shared/llm.py` — explicit `RuntimeError` raise on `None` content in `chat_json()` and `chat_text()` (was previously returning `str | None` typed as `str` — silent type-safety bug).
- `packages/shared/jeromelu_shared/scraping/nrl.py` — replaced `callable` (builtin function used incorrectly as a type) with `Callable[[object], int | float | str]` via `from collections.abc import Callable`. Annotated `parse_int(value: object)` and `parse_float(value: object)` so signatures match.
- `packages/shared/jeromelu_shared/insights.py` — 5 `# pyright: ignore[reportAttributeAccessIssue]` markers + a NOTE block above `query_round_claims`. Inline rationale on each marker: `Claim.subject_entity_id removed in migration 036 → TASK-53`. The dormant queries (called only by `scripts/insights/generate_round_tips.py`) need a full rewrite to JOIN through `ClaimAssociation`; queued as TASK-53.

**Proof:**
- `make typecheck-python` → `0 errors, 0 warnings, 0 informations`.
- `pytest tests/unit/shared/` → `99 passed`.
- `pytest tests/unit/` → `398 passed` (full suite, no regression).
- `git diff --stat 0bccec8^..0bccec8` covers exactly the 7 expected files.
- `cat pyproject.toml` shows the `[tool.pyright]` block matching PLAN.md "Interface §" verbatim (include, exclude, pythonVersion, typeCheckingMode, reportMissingImports="error", reportGeneralTypeIssues="error").

**adversarial-reviewer: PASS after one Blocker round.** First pass found a real Blocker: `openai` and `temporalio` are imported at module top-level inside the Pyright include set but were excluded from `requirements-test.txt` per its "network SDKs excluded for fast installs" policy, and weren't in `requirements-dev.txt` either — `reportMissingImports="error"` would have failed CI. Resolved by adding both to `requirements-dev.txt` (which only the Pyright CI job installs, preserving the lean unit-test install path). Also addressed 3 concerns in the same iteration: inline rationale on `# pyright: ignore` markers, pin discipline (range in file + exact in CI step), Makefile umbrella-lint NOTE.

---

### TASK-50 — Gitleaks plumbing + secret-hygiene META invariant (`1c2aa20`)

**Files:**
- `.gitleaks.toml` (new) — extends gitleaks defaults via `[extend] useDefault = true`; 3 allowlist categories with inline rationale:
  - **Path excludes** for `.venv/`, `node_modules/`, `.next/`, `dist/`, `build/`, `.git/`, `__pycache__/`, `*.lock`, `package-lock.json`, and `.env*` (gitignored, never in CI's tracked-files scope; the local-side exclusion just makes `--no-git` scans match CI's posture so the developer doesn't see local-only secrets surfacing).
  - **`services/gpu/Dockerfile` + `services/gpu/build_and_push.sh`** — `--secret id=hf_token,env=HUGGINGFACE_API_KEY` is a BuildKit secret-mount label, not a value; the value is read from the env var at build time.
  - **`docs/operations/aws-resource-inventory.md`** — narrow regex (UUID-format only via `regexTarget = "secret"`); the doc contains KMS Key UUIDs that gitleaks's `generic-api-key` entropy rule flags. Narrow regex preserves coverage for non-UUID secrets (real AWS access tokens, generic API keys, anything else) if they ever land in the doc.
- `.github/workflows/tests.yml` — new `gitleaks` job using `gitleaks/gitleaks-action@v2`. `fetch-depth: 0` per the spec. Inline comment documents that `GITLEAKS_LICENSE` is intentionally omitted (free tier).
- `docs/build/META.md` — new `### Secret hygiene` invariant subsection placed between `### Infrastructure (AWS)` and `### Heavy ML deps stay isolated`. Documents rule, enforcement, and false-positive workflow.

**Proof:**
- `gitleaks detect --no-git --source=. --no-banner --redact --exit-code 1` → `no leaks found`, exit 0.
- Initial baseline (before the allowlist was tuned) surfaced 7 findings in `.env` (gitignored, never committed — local dev secrets the action wouldn't see in CI's tracked-files scope) and 4 historical findings in old commits (KMS UUIDs + BuildKit secret labels). All addressed via path-excludes (`.env`) or category-narrow allowlist entries (everything else). No real secret was discovered.
- `git diff --stat 1c2aa20^..1c2aa20` covers exactly the 3 expected files.
- `pytest tests/unit/` → 398 passed (no regression).

**adversarial-reviewer: PASS WITH CONCERNS.** No Blockers. 5 Concerns:
- **C1 (addressed):** Initial `aws-resource-inventory.md` allowlist was path-blanket — would have suppressed real AWS access tokens too. Reviewer recommended narrowing to UUID-pattern regex. Implementer narrowed via `regexTarget = "secret"` + UUID-only regex (32 hex + 4 dashes). Probe-tested with two AKIA paste attempts (canonical docs example `AKIAIOSFODNN7EXAMPLE` and a randomized AKIA-format string) — neither fired, but this is a property of gitleaks v8.30.1's default `aws-access-token` rule applying entropy/safe-word filters, NOT a property of the allowlist. The narrowing strictly reduces the suppression scope as the reviewer requested.
- **C2 (acknowledged):** META invariant text not literally verbatim — implementer added CI-job path reference, "description rationale" wording (matches gitleaks 8.x TOML syntax), and a local-check command. Additions are improvements; "verbatim" was load-bearing in the spec word but spirit preserved.
- **C3 (addressed):** Added inline comment in CI job documenting the `GITLEAKS_LICENSE` omission decision (free tier, public repo).
- **C4 (addressed):** Removed the redundant `(^|/)\.env$` regex (already covered by `(^|/)\.env(\.|$)`).
- **C5 (deferred per META):** CI-side end-to-end verification (fake-AKIA push → red, revert → green) is a post-checkoff operator step.

**Deviations from plan:**
- **D1.** Allowlist is array-of-tables `[[allowlists]]` rather than the spec's singular `[allowlist]` form. Required by gitleaks 8.x — the singular form requires at least one populated check (paths/regexes/commits/stopwords); the array form is the standard pattern for multiple independent entries with `description` per entry.
- **D2.** Local-side scan uses `gitleaks detect --no-git --source=.` rather than the spec's `gitleaks detect --redact --source=. --no-banner --exit-code 1`. The plain `detect` form scans git history by default which surfaced 4 historical findings irrelevant to the working-tree gate; `--no-git` matches the action's HEAD-scan behavior in CI.
- **D3.** Added inline comment to CI job documenting `GITLEAKS_LICENSE` omission decision (originally only in the spec's "Note: If license env var is unavailable, omit — document the choice here in a comment" — now actually present in the file).

**Deviations from plan:**
- **D1.** Umbrella `lint:` Makefile target deferred. Spec said "Update the umbrella `lint` target (added in TASK-47) to also `$(MAKE) typecheck-python`." TASK-47 is BLOCKED so the target doesn't exist; only `typecheck-python` ships. NOTE block left in Makefile so the future TASK-47 unblocker wires it up.
- **D2.** `# pyright: ignore` markers used for real schema-drift bug rather than the spec's example case ("missing type stub"). Per implementer charter "don't fix tangential bugs," the proper fix (rewriting the queries to JOIN through `ClaimAssociation`) was deferred to a new TASK-53 rather than absorbed into Pyright plumbing scope. Each marker carries an inline rationale pointing at TASK-53.
- **D3.** CI step pins `pyright==1.1.409` separately rather than relying on `requirements-dev.txt` resolution. Spec called for "exact in CI, range in requirements-dev.txt" — done; the separate `pip install pyright==1.1.409` after the range install achieves determinism.

**New task queued from this work:**
- **TASK-53** — Fix `insights.py` dormant queries. The 5 references to non-existent `Claim.subject_entity_id` are real bugs in dormant code (`scripts/insights/generate_round_tips.py` would crash at runtime). Full rewrite to JOIN through `ClaimAssociation` is required, with new unit-test coverage. Currently the bug is suppressed with `# pyright: ignore` so CI stays green; TASK-53 removes the suppressions as part of the fix.

---

## Currently BLOCKED

### TASK-47 — Ruff plumbing [BLOCKED: ruff-violation-volume — 174 files, 875 errors]

Pre-audit anticipated near-zero violations (only grepped `datetime.utcnow`, found zero) — actual surface is 875 errors across 174 files because the spec'd rule set hits well-known false-positive surfaces in this codebase:
- 389 `E501` line-too-long at the 100-char limit (codebase commonly runs 101–110 chars).
- 92 `B008` function-call-in-default-argument — FastAPI `Depends(...) / Query(...) / Path(...)` pattern; standard FastAPI remediation is `extend-immutable-calls`.
- 45 `RUF001/002/003` ambiguous-unicode in NRL content (×, —, ° legitimately used in comments/docstrings).
- 50 `UP017` autofixable; 139 `I001` autofixable; etc.

Spec's `>30 files` threshold tripped → BLOCKED. Three remediation options documented in the task's BLOCKED note. Recommended: option 1 — tune the rule set (`extend-immutable-calls` for FastAPI, drop ambiguous-unicode rules, drop DTZ011, raise line-length 100→120). Preserves load-bearing invariants while removing the noise floor. After tuning, expected residual is ~30–50 errors across ~20 files — manageable in a single sitting.

### TASK-48 — ESLint CI job [BLOCKED: eslint-violation-volume — 50 files, 34 errors + 24 warnings]

`npm run lint` has never run in CI; `eslint-config-next/core-web-vitals` ships with stricter `react-hooks/*` rules (React 19's compiler-driven advisory rules) than the codebase was written against. 12 `react-hooks/refs`, 6 `react-hooks/set-state-in-effect`, 3 `react-hooks/immutability` errors need an incremental migration, not a hard gate from day 1. 13 `react/no-unescaped-entities` errors are mechanically fixable (30-min job).

Spec's `>20 files` threshold tripped → BLOCKED. Recommended: option 1 — downgrade the `react-hooks/*` advisory rules to `warn`, fix the 13 `react/no-unescaped-entities` errors manually, ship CI with `--max-warnings=0`. ~1h work after human ratifies.

---

## Outstanding (not yet picked up)

- **TASK-50** — Gitleaks + secret-hygiene META invariant.
- **TASK-51** — Deploy gating via `workflow_run` trigger on `deploy.yml`. Verification requires TASK-47/48/49/50 all green on master first.
- **TASK-52** — Plan closure (Tier 1 ✅ markers on `engineering-quality-hardening.md`; flip this run report to 🟢 Shipped).

---

## Decisions & deviations

- **The plan's pre-audit was wrong.** "Zero `datetime.utcnow()`" was a true but narrow finding; it didn't generalize to "Ruff will be near-zero on master." Lesson for future planners: when adopting a lint tool with N rule sets, predict the violation surface PER RULE SET, not just for the headline rule. Especially relevant for `B008` (FastAPI codebases), `E501` (any codebase older than ~6 months), and `RUF001-003` (any project with non-English content).
- **Two BLOCKED tasks in one session is the correct outcome.** Per the implementer charter "Spec ambiguity → tag `[BLOCKED]`, don't improvise." The plan's `>30 files` and `>20 files` thresholds were safety nets explicitly designed to surface these moments; they worked.
- **`requirements-dev.txt` now carries network SDK pins.** Before this run, the file held only `pytest`. Now it also holds `pyright`, `openai`, `temporalio`. The semantic shift is: requirements-dev.txt is dev-tooling + dev-time SDK pins for typecheckers — not just dev tooling. `requirements-test.txt` stays narrow for the lean `pytest tests/unit/` install path (preserved).

---

## Lessons learned

- **Ruff/ESLint adoption against a brownfield codebase: predict the violation surface per rule, not just the headline rule.** Adding a new project memory or META invariant capturing this would help future planners.
- **`reportMissingImports="error"` is load-bearing for Pyright correctness but creates a hidden dependency on the test/dev environment.** Future widenings of the Pyright include set MUST audit `import X` statements against `requirements-dev.txt` (or whatever the typecheck-time deps file is). Worth promoting to META.md once the second widening lands.

---

## Commits

- `1c2aa20` — feat(quality): TASK-50 — Gitleaks plumbing + secret-hygiene META invariant [skip-simplify]
- `0bccec8` — feat(quality): TASK-49 — Pyright plumbing (narrow scope: packages/shared/jeromelu_shared) [skip-simplify]
- `d1884d4` — docs(build): [BLOCKED] TASK-48 ESLint plumbing — 50 files exceeds spec threshold [skip-simplify]
- `6484d2e` — docs(build): [BLOCKED] TASK-47 ruff plumbing — 875 errors / 174 files exceeds spec threshold [skip-simplify]
- `8c799ef` — docs(build): plan — Engineering quality hardening Tier 1 + 6 tasks [skip-simplify]

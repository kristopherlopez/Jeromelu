# Engineering quality hardening — Tier 1

**Date:** 2026-05-28 · **Status:** 🟡 In flight (4/6 tasks shipped — TASK-51 + TASK-52 not yet picked up) · **Plan:** [Engineering quality hardening — Tier 1](../PLAN.md#2026-05-28-engineering-quality-hardening--tier-1-ruff--pyright--eslint--gitleaks--deploy-gating)

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

---

### TASK-47 — Ruff plumbing (Option 1 rule-set tuning) (`6e9c227`)

Unblocked 2026-05-28 by human picking Option 1 from the BLOCKED note's remediation menu. Pre-audit had anticipated near-zero violations (only grepped `datetime.utcnow`, found zero) — actual surface with the plan-verbatim rule set was 875 errors across 174 files because the rule set hit well-known false-positive surfaces (E501 at 100-char, B008 on FastAPI Depends, RUF001/2/3 on NRL content). Option 1 tuned the rule set rather than absorbing the noise.

**Files (config + CI + META):**
- `pyproject.toml` — `[tool.ruff]` block with Option 1 tunings: line-length = 120; `extend-immutable-calls` for 8 FastAPI helpers (Depends, Query, Path, Body, Header, Form, File, Cookie); `ignore = ["DTZ011", "RUF001", "RUF002", "RUF003"]`; per-file-ignores `E501` for 8 prompt/HTML-content files (3 LLM-prompt files + 5 SES report scripts); per-file ignore `["DTZ", "B011"]` for tests. Pyright block from TASK-49 preserved.
- `requirements-dev.txt` — `ruff>=0.15,<1` range; CI pins exact (`ruff==0.15.14`).
- `Makefile` — added `lint-python`, `format-python`, `lint` (umbrella chaining lint-python + typecheck-python; `lint-web` lands with TASK-48). `.PHONY` updated.
- `.github/workflows/tests.yml` — new `ruff` job before `pyright`. Pins `ruff==0.15.14` in a separate step after `pip install -r requirements-dev.txt` (matches Pyright's pin pattern).
- `docs/build/META.md` — new `### Datetime / timezone` invariant subsection. Text uses `datetime.now(UTC)` form (matches reality after Ruff's UP017 autofix swept the codebase).

**Source-tree changes (~190 files, 4730/-3666 across 196 files staged):**
- **337 safe autofixes** via `ruff check --fix` — import-sort, datetime modernization (`timezone.utc` → `UTC`), unused-import removal, deprecated-import migration, f-string cleanup, etc.
- **24 unsafe autofixes** via `--unsafe-fixes` — RUF046 `int(round(...))` → `round(...)`; RUF059 `_`-prefix on unused-unpacked variables. Both classes are semantically safe.
- **142 files reformatted** via `ruff format` — line wrapping at the 120-char limit, trailing-comma normalization, spacing.
- **Manual fixes** (carefully audited):
  - **F821 real bug** in `services/worker-publishing/app/activities/update_consensus.py:125`: `len(entity_claims)` → `len(person_claims)`. `entity_claims` was undefined — would have crashed with `NameError` at runtime if the snapshot-flip log path ever fired. **Ruff caught a production bug.**
  - **33 B904 raise-from-inside-except** — batch-fixed via a one-shot helper script (`scripts/_fix_b904.py`, created/run/deleted in-session) that walked backwards from each raise to find the enclosing `except ... as Y:` and appended `from Y`. 31 of 33 fixed by the script; 2 unbound `except ValueError:` cases (`insights.py:84`, `lineup.py:288`) hand-fixed to `from None` (input-validation paths where the original error is uninteresting).
  - **2 B008** in `voice_cluster_hdbscan.py:94` + `voice_cluster_runner.py:59`: `params: VoiceClusterParams = VoiceClusterParams()` got `# noqa: B008` with rationale "frozen dataclass — immutable, safely shareable across calls" (verified by reading the `@dataclass(frozen=True)` declaration).
  - **1 B007** in `scripts/reconcile_orphan_channels.py:108` — `url` → `_url` (intentionally unused unpacked variable).
  - **1 RUF034** in `packages/shared/jeromelu_shared/scraping/nrl.py:186` — `parsed if parsed != 0 else parsed` (no-op ternary) → `parsed` with comment update ("explicit zeros preserved by the parser").
  - **5 E402** in `scripts/transcripts/clean_transcript.py` + `scripts/video/upload_clips_to_s3.py` — `# noqa: E402` markers with rationale "sys.path manipulation above must run first".
  - **10 E501 inline `# noqa: E501`** markers on legitimate long lines: SQL CHECK constraint string, single-line docstrings, chained-zip expressions, f-string error messages with full-keys diagnostic, FastAPI Query `description=`, logger format strings.

**Proof:**
- `make lint-python` → `All checks passed!` + `267 files already formatted`.
- `make typecheck-python` → 0 errors, 0 warnings, 0 informations.
- `pytest tests/unit/` → **398 passed** (zero regression from autofix/format/manual changes).
- `git grep -n "datetime\.utcnow" services packages scripts` → 0 matches.

**adversarial-reviewer: PASS WITH CONCERNS.** No Blockers. 4 Concerns:
- **C1 (acknowledged):** META text uses `datetime.now(UTC)` rather than the spec's `datetime.now(timezone.utc)`. Landed text matches reality after the UP017 autofix swept the codebase. Worth noting; not a bug.
- **C2 (addressed):** Tightened the `# noqa: B008` rationale from "dataclass with only scalar defaults — safely shareable across calls" to "frozen dataclass — immutable, safely shareable across calls" per the reviewer's verification that the class is `@dataclass(frozen=True)`.
- **C3 (post-checkoff):** Run report update is happening here, per META ritual.
- **C4 (recorded):** F821 catching a real production bug (`len(entity_claims)` → would have NameError'd if the snapshot-flip log fired) is a load-bearing data point for the value of Ruff plumbing. Promoting to Lessons learned below.

**Deviations from plan:**
- **D1.** Spec said `select = ["E", "F", "I", "B", "DTZ", "UP", "RUF"]` and `ignore = []`. Landed `ignore = ["DTZ011", "RUF001", "RUF002", "RUF003"]` per Option 1.
- **D2.** Spec said `line-length = 100`. Landed `line-length = 120` per Option 1.
- **D3.** Spec said `[tool.ruff.lint.per-file-ignores]` only for `tests/**/*.py` and `**/conftest.py`. Landed 8 additional per-file-ignore entries for E501 in prompt / HTML-content files (LLM system prompts, SES email bodies, seed-mock-articles).
- **D4.** New `[tool.ruff.lint.flake8-bugbear]` `extend-immutable-calls` block — 8 FastAPI helpers added per Option 1.
- **D5.** B904 batch fix via one-shot helper script (`scripts/_fix_b904.py`, created/run/deleted) rather than hand-editing each of 33 instances.

---

### TASK-48 — ESLint CI job + `lint-web` Make target (Option 1 rule downgrades) (`e65544f`)

Unblocked 2026-05-28 by human picking Option 1 from the BLOCKED note. Initial baseline (`npm run lint` on master HEAD before Option 1) was 58 problems (34 errors, 24 warnings) across 50 files. Option 1 downgraded React 19's stricter advisory rules to `warn` and hand-fixed the 13 `react/no-unescaped-entities` errors.

**Files:**
- `services/web/eslint.config.mjs` — override object added after the `...nextVitals, ...nextTs` spreads (later objects win in flat-config). Sets `react-hooks/set-state-in-effect`, `react-hooks/refs`, `react-hooks/immutability`, `react-hooks/incompatible-library` to `"warn"`. Inline rationale documents the React 19 incremental-migration premise.
- `services/web/src/app/components/AlignmentPanel.tsx` — 9 entity replacements: 2× `"` → `&quot;` (line 225), 7× `'` → `&apos;` (lines 228, 433, 434, 435, 706, 1097, 1098). Semantic preserved (entities render as same characters).
- `services/web/src/app/components/AssignRunModal.tsx` — 1 `'` → `&apos;` (line 332).
- `services/web/src/app/components/AssignVoiceModal.tsx` — 1 `'` → `&apos;` (line 292).
- `services/web/src/app/components/VoicesPanel.tsx` — 2 `'` → `&apos;` (lines 259, 434).
- `.github/workflows/tests.yml` — new `web-lint` job placed between `web-typecheck` and `ruff`. Standard shape (`actions/checkout@v6`, `actions/setup-node@v6 node-version: "20"`, npm cache, `npm ci`, `npm run lint`). Inline comment documents the downgraded-rules context.
- `Makefile` — new `lint-web` target (`cd services/web && npm run lint`); umbrella `lint:` target now chains `lint-python + lint-web + typecheck-python`. `.PHONY` updated.

**Proof:**
- `make lint-web` → `0 errors, 45 warnings`, exit 0. Warnings: 4 downgraded react-hooks rules (22) + `@next/next/no-img-element` (13) + `@typescript-eslint/no-unused-vars` (8) + `react-hooks/exhaustive-deps` (2).
- `make lint-python` → `All checks passed!` (TASK-47 stays clean).
- `pytest tests/unit/` → **398 passed** (no regression).

**adversarial-reviewer: PASS WITH CONCERNS.** No Blockers. 3 Concerns:
- **C1 (captured below as D1):** The BLOCKED note's `--max-warnings=0` bullet is internally contradictory. Shipped without the flag per the "hard-fail on error-severity" interpretation.
- **C2 (applied):** Session-scoped staging — `CLAUDE.md`, `scripts/data/populate/phase_aux.py`, `tests/unit/scripts/data/populate/test_phase_aux.py` left unstaged per other-session ownership.
- **C3 (post-checkoff, per TASK-49/50 precedent):** End-to-end CI verification (push deliberate-error → red, revert → green) is deferred to the post-merge operator window. The gate's mechanism is verified by local-side `npm run lint` exit codes; the CI-side proof is captured when an actual broken PR surfaces (or as part of TASK-51's deploy-gate dry run, which already requires the same observability).

**Deviations from plan:**
- **D1.** Spec said "Add CI with `--max-warnings=0`". Landed without the flag because the spec's adjacent "warnings become informational" wording and the umbrella "hard-fail on error-severity" property contradict it. The only coherent reading was: hard-fail on errors, warnings show but don't fail. `npm run lint`'s default behavior matches that — no flag needed.
- **D2.** Initial baseline (audit) showed 34 errors / 24 warnings / 50 files. Post-downgrade-only state was 13 errors / 45 warnings / 50 files. Post-fix state is 0 errors / 45 warnings / 50 files (45 warnings instead of the spec's predicted ~24 because the rule downgrades convert errors into warnings rather than silencing them).
- **D3.** `&apos;` chosen over `&#39;` as the entity replacement (both render identically; `&apos;` is more readable in source).

---

**Deviations from plan:**
- **D1.** Umbrella `lint:` Makefile target deferred. Spec said "Update the umbrella `lint` target (added in TASK-47) to also `$(MAKE) typecheck-python`." TASK-47 is BLOCKED so the target doesn't exist; only `typecheck-python` ships. NOTE block left in Makefile so the future TASK-47 unblocker wires it up.
- **D2.** `# pyright: ignore` markers used for real schema-drift bug rather than the spec's example case ("missing type stub"). Per implementer charter "don't fix tangential bugs," the proper fix (rewriting the queries to JOIN through `ClaimAssociation`) was deferred to a new TASK-53 rather than absorbed into Pyright plumbing scope. Each marker carries an inline rationale pointing at TASK-53.
- **D3.** CI step pins `pyright==1.1.409` separately rather than relying on `requirements-dev.txt` resolution. Spec called for "exact in CI, range in requirements-dev.txt" — done; the separate `pip install pyright==1.1.409` after the range install achieves determinism.

**New task queued from this work:**
- **TASK-53** — Fix `insights.py` dormant queries. The 5 references to non-existent `Claim.subject_entity_id` are real bugs in dormant code (`scripts/insights/generate_round_tips.py` would crash at runtime). Full rewrite to JOIN through `ClaimAssociation` is required, with new unit-test coverage. Currently the bug is suppressed with `# pyright: ignore` so CI stays green; TASK-53 removes the suppressions as part of the fix.

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
- **TASK-47 caught a real production bug.** Ruff's F821 in `worker-publishing/.../update_consensus.py:125` (`len(entity_claims)` referencing an undefined name) would have raised `NameError` at runtime if the snapshot-flip log path ever fired. This is the load-bearing case for Ruff plumbing being a net-positive even when initial violation volume is high: even a "noisy" lint pass surfaces real bugs that would otherwise crash in production.
- **Batch-fixing mechanical violations via a one-shot helper script is faster + safer than 33 individual Edit calls** for AST-shaped patterns like B904. The helper-script-then-delete pattern (no committed scripts) preserves clean implementer history.

---

## Commits

- `e65544f` — feat(quality): TASK-48 — ESLint CI job + lint-web Make target (Option 1 rule downgrades) [skip-simplify]
- `6e9c227` — feat(quality): TASK-47 — Ruff plumbing (Option 1 rule-set tuning) [skip-simplify]
- `1c2aa20` — feat(quality): TASK-50 — Gitleaks plumbing + secret-hygiene META invariant [skip-simplify]
- `0bccec8` — feat(quality): TASK-49 — Pyright plumbing (narrow scope: packages/shared/jeromelu_shared) [skip-simplify]
- `d1884d4` — docs(build): [BLOCKED] TASK-48 ESLint plumbing — 50 files exceeds spec threshold [skip-simplify]
- `6484d2e` — docs(build): [BLOCKED] TASK-47 ruff plumbing — 875 errors / 174 files exceeds spec threshold [skip-simplify]
- `8c799ef` — docs(build): plan — Engineering quality hardening Tier 1 + 6 tasks [skip-simplify]

---
tags: [area/agents, subarea/system, status/live]
---

# Presenter Scout

| | |
|---|---|
| **Package** | `services/api/app/scout/presenters.py` |
| **Trigger** | `make scout-presenters CHANNEL_ID=…` (CLI) or `POST /api/admin/presenters/scout/{channel_id}` (admin UI) |
| **Crew counterpart** | [Scout](../crew/scout.md) — research/discovery mode, scoped to one channel |
| **ETL role** | **Extract only.** Files candidates; promotion happens via human review. |
| **Status** | Phase 1 ✅ + Phase 2 ✅ shipped 2026-05-05. Phase 3 (priors integration with Lineup) backlog. |

Given one channel (a YouTube channel, podcast, or website), Presenter Scout researches who the regular presenters are via Anthropic-hosted web tools, files findings into `scout_presenter_candidates`, and stops. Reviewers confirm/reject in the admin "Presenters" tab; confirmation creates a `people` row (or links to an existing one) and writes a `source_presenters` association.

**Why it exists.** Cold-starting a new channel today means: someone Googles the show, manually creates `people` rows for the hosts, then enrolls voice/face spans. Steps 1 and 2 are what an agent with web tools should do for us. Step 3 (enrollment) compounds — once Phase 3 lands, confirmed presenters become priors that soften the matching thresholds for first appearance.

---

## Architecture

```
channel_id ──► run_presenter_scout()
                    │
                    ▼
      Anthropic Messages API ◀── system prompt (cached, ~2.3k tokens)
            │                ◀── tools: web_search, web_fetch,
            │                          lookup_existing_people,
            │                          persist_presenter_candidate
            │                ◀── user brief (channel name, url, platform,
            │                          description, already-confirmed list)
            ▼
      Multi-turn streaming loop (presenters.py: run_presenter_scout)
            │
            ├── server-side tools (web_search ≤3, web_fetch ≤3 per run)
            │
            └── client-side tools:
                  lookup_existing_people     → SELECT against people / aliases
                  persist_presenter_candidate → validates evidence mentions
                                                the name; INSERT into
                                                scout_presenter_candidates
                                                (status='pending');
                                                idempotent on
                                                (channel_id, lower(name))
                                                while pending
            │
            ▼
      PresenterScoutResult (turns, tool_calls, candidates_filed, est. cost)
```

`agent_audit` plumbing is identical to the main Scout — same `agent_runs` row, same per-event `agent_events`, same JSONL forensic upload to `s3://jeromelu-clean-documents/agent-logs/presenter_scout/…`.

---

## Files

| File | Purpose |
|---|---|
| `app/scout/presenters.py` | Tool definitions + handlers + system prompt + run loop |
| `app/scout/presenters_cli.py` | `make scout-presenters` entry point; accepts `--channel-id` or `--source-id` |
| `app/routers/presenters.py` | `/api/admin/presenters/*` endpoints (trigger / list / confirm / reject) |
| `services/web/src/app/admin/PresentersPanel.tsx` | Admin "Presenters" tab |

## Data

| Table | Role |
|---|---|
| `scout_presenter_candidates` | Staging inbox. Agent writes here; status `pending` → `confirmed` / `rejected` on review. |
| `source_presenters` | Confirmed `(channel_id, person_id, role)` association. Created on confirm. |

Schema details: [data-catalogue § scout_presenter_candidates](../../operations/data-catalogue.md#scout_presenter_candidates). Migration: `052_source_presenters.sql`.

---

## Bounds

Tighter than the discovery Scout — one channel is a small task, a runaway loop is a bug.

```python
DEFAULT_BOUNDS = AgentBounds(
    max_turns=8,
    max_tool_calls=20,
    max_wall_seconds=300,
    max_budget_usd=0.30,
)
```

In practice a clean run takes ~7 turns, ~$0.15, ~30s wall time. Verified on the `Bloke In A Bar` channel (2026-05-05): 3 candidates filed (Denan Kemp host + Tyson Jackson and Blake Austin regulars), 7 turns, 6 tool calls, $0.148, 4× web_search, 1× web_fetch.

---

## Roles

The agent picks one of four typed roles per filed candidate. Reviewers can override on confirm.

| Role | When |
|---|---|
| `host` | The show is theirs. Named in the show title or "Hosted by …". |
| `co-host` | Named on every / nearly every episode alongside the host. Equal billing. |
| `regular` | Recurring panel member; in many but not all episode titles. |
| `frequent-guest` | Recurring presence but clearly not part of the core panel. |

Prompt instructs: when in doubt, downgrade. Reviewers prefer "regular" upgraded to "co-host" over "co-host" demoted to "regular".

---

## Hand-off contract

**Inputs:**
- `channel_id` (UUID) — required. The CLI also accepts `--source-id` and resolves it to its channel server-side.

**Outputs:**
- ≥0 rows in `scout_presenter_candidates` with `status='pending'`. Each row carries:
  - `name`, `role`, `evidence_json` (≥1 `{url, snippet}` — snippet must mention the name; auto-validation rejects filings that don't satisfy this)
  - `llm_confidence` 0.0–1.0
  - `existing_person_id` (best-effort dupe hint — set when `lookup_existing_people` returned a clean match)
- One `agent_runs` row keyed on `run_id` with `agent_id='presenter_scout'`, full token + cost rollup.
- One JSONL forensic bundle at `s3://jeromelu-clean-documents/agent-logs/presenter_scout/{YYYY}/{MM}/{DD}/{run_id}.jsonl`.

**Idempotence:**
- Re-running for the same channel will not double-file a still-pending name (partial unique index on `(channel_id, lower(name)) WHERE status='pending'`).
- A previously rejected name *can* re-surface on a re-run — intentional; rejection might have been wrong, or the role might have changed.
- Confirmation writes a `source_presenters` row guarded by `UNIQUE (channel_id, person_id)`. Re-confirming the same candidate returns `already-confirmed` without duplicating.

---

## Running

CLI:
```bash
make scout-presenters CHANNEL_ID=<uuid>
make scout-presenters SOURCE_ID=<uuid>          # resolves to channel server-side
make scout-presenters CHANNEL_ID=<uuid> DRY_RUN=1
make scout-presenters CHANNEL_ID=<uuid> MODEL=claude-opus-4-7
```

Admin UI: `/admin` → **Presenters** tab → pick channel → **Run Presenter Scout**. Synchronous (~30s); spinner while it runs.

API:
```bash
# Trigger
curl -X POST http://localhost:8000/api/admin/presenters/scout/<channel-uuid>

# List
curl 'http://localhost:8000/api/admin/presenters/by-channel/<channel-uuid>'

# Confirm — creates a new Person from candidate.name
curl -X POST http://localhost:8000/api/admin/presenters/candidates/<id>/confirm \
     -H 'content-type: application/json' -d '{"reviewed_by":"alice"}'

# Confirm — link to existing Person
curl -X POST http://localhost:8000/api/admin/presenters/candidates/<id>/confirm \
     -H 'content-type: application/json' \
     -d '{"existing_person_id":"<uuid>","reviewed_by":"alice"}'

# Reject
curl -X POST http://localhost:8000/api/admin/presenters/candidates/<id>/reject \
     -H 'content-type: application/json' -d '{"note":"actually a guest","reviewed_by":"alice"}'
```

---

## Backlog (Phase 3)

- **Lineup priors.** Surface the confirmed `(channel_id, person_id)` set to the visual_id / voice_id matchers. When a source's channel has confirmed presenters, soften match thresholds for those people — first appearance auto-resolves instead of needing manual enrolment.
- **Auto-trigger on first ingestion.** Last step of `make collect-audio` for any new source whose channel has zero confirmed presenters: queue a Presenter Scout run in the background. Reviewer wakes up to a populated inbox.
- **Person merge tool.** When two reviewers confirm the same name on different channels and create two `people` rows, a merge UI consolidates them. v1 leaves duplicates as an acceptable risk.

See [docs/todo/source-presenters.md](../../todo/source-presenters.md) for the full plan.

---

## Related

- [Scout (source discovery)](source-discovery.md) — sibling agent; same loop shape, different scope
- [Speaker Identification](speaker-identification.md) — the matchers that will consume confirmed presenters as priors (Phase 3)
- [Agent Audit](agent-audit.md) — the observability trail every agent writes

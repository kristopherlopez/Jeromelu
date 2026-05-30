---
tags: [area/operations, data-lineage]
---

# Lineage: miner_presenter_candidates

[Schema: data-catalogue/miner_presenter_candidates.md](../data-catalogue/miner_presenter_candidates.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| Presenter Miner agent | — (web search; no S3 archive) | **Primary** — agent finds people who present a known channel |

Presenter Miner uses web search tools (per `docs/agents/system/presenter-miner.md`) to discover hosts/co-hosts/regulars/guests for a known channel. Each finding includes evidence URLs + snippets that mention the name.

## Writers

- `services/api/app/miner/presenter_research/agent.py` — Presenter Research agent; INSERTs candidates with `status='pending'`
- **Admin "Presenters" review tab** — humans confirm/reject; confirmation triggers a [people](people.md) row (created or linked) and a [source_presenters](source_presenters.md) row

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `id` | derived | UUID, DB-side default |
| `channel_id` | scope | FK → channels (CASCADE); the show this candidate is associated with |
| `name` | agent | "Denan Kemp" |
| `role` | agent | `host`, `co-host`, `regular`, `frequent-guest` |
| `evidence_json` | agent | Array of `{url, snippet}`. Snippet must mention the name (auto-validated at INSERT) |
| `llm_confidence` | agent | Agent's own 0.0–1.0 score |
| `notes` | agent + review | Free-form agent commentary; reviewer notes appended on reject |
| `existing_person_id` | agent (`lookup_existing_people` tool) | Best-effort dupe hint |
| `status` | review | `pending` → `confirmed`/`rejected` |
| `reviewed_at`, `reviewed_by` | review | |
| `confirmed_person_id` | review | FK → people; set on confirm — the Person this candidate became |
| `run_id` | agent | Groups candidates from one Presenter Miner run |
| `discovered_at` | derived | DB default `now()` |

## Notes

- Distinct from [miner_candidates](miner_candidates.md) — that one discovers *channels* and *videos*; this one discovers *people who present* a known channel.
- Partial unique on `(channel_id, lower(name)) WHERE status='pending'` — re-runs don't double-file pending names but a previously-rejected name CAN re-surface (it might have been wrongly rejected).
- See migration 052.

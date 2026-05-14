---
tags: [area/operations, data-catalogue]
---

# source_presenters

[← Data Catalogue](README.md) · Layer 3 — Content & claims

Confirmed `(channel_id, person_id, role)` association. Anchored at channel level — presenters are a property of the show, not the episode. Created by `POST /api/admin/presenters/candidates/{id}/confirm`. See migration 052.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| id | UUID | PK | uuid4 | |
| channel_id | UUID | no | | FK → channels (CASCADE) |
| person_id | UUID | no | | FK → people (CASCADE) |
| role | text | no | | `host`, `co-host`, `regular`, `frequent-guest`. May differ from the originating candidate's role if the reviewer overrode on confirm. |
| is_regular | bool | no | true | Convenience flag — true for host/co-host/regular, false for frequent-guest |
| since_ts | timestamptz | yes | | Optional join date if known |
| confirmed_at | timestamptz | no | now() | |
| confirmed_by | text | yes | | Reviewer identity |
| candidate_id | UUID | yes | | FK → scout_presenter_candidates (SET NULL). Provenance pointer. |

**Unique:** (channel_id, person_id) — one row per (show, person). Re-confirming the same candidate is idempotent on this constraint.
**Indexes:** person_id (for "what shows is X on?" queries).
**FK:** channel_id → channels (CASCADE); person_id → people (CASCADE); candidate_id → scout_presenter_candidates (SET NULL).

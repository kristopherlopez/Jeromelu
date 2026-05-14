---
tags: [area/operations, data-catalogue]
---

# match_team_lists

[← Data Catalogue](README.md) · Layer 2 — Structured world

Versioned named-17 announcements per match per team. Each new public lineup
(Tuesday list, Thursday list, late changes) appends a row with an
incremented `list_version` rather than mutating the prior row.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| list_id | UUID | PK | uuid4 | |
| match_id | UUID | no | | FK → matches (CASCADE) |
| team_id | UUID | no | | FK → teams (RESTRICT) |
| player_id | UUID | no | | FK → people (RESTRICT) |
| jersey_number | int | yes | | 1..30 (allows reserves) |
| named_position | text | yes | | `fullback`, `wing`, `centre`, `five-eighth`, `halfback`, `hooker`, `prop`, `second-row`, `lock`, `interchange`, `reserve` |
| sc_position | text | yes | | SC position string (HOK/HFB/CTW/FRF/2RF/MID/FLB/FLX) — populated when the SC API is the source |
| is_captain | bool | no | false | Per-match-per-player captain flag (mig 036). |
| list_version | int | no | 1 | Monotonically increasing per (match, team) |
| status | text | no | `named` | `named`, `late_change_in`, `late_change_out`, `19th_man`, `reserve`, `withdrawn` |
| announced_at | timestamptz | yes | | |
| source | text | no | `nrl_com` | |
| metadata_json | jsonb | no | {} | |
| created_at | timestamptz | no | now() | |

**Unique:** (match_id, team_id, player_id, list_version)
**Indexes:** match_id, team_id, player_id, (match_id, team_id, list_version DESC)
**FK:** match_id → matches (CASCADE); team_id → teams (RESTRICT); player_id → people (RESTRICT)

Live current state for a fixture: filter by (match_id, team_id) and pick `list_version` DESC.

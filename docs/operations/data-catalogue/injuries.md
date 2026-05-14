---
tags: [area/operations, data-catalogue]
---

# injuries

[← Data Catalogue](README.md) · Layer 2 — Structured world

Append-on-change timeline of player injury / suspension state. Each daily
casualty-ward sweep writes a new row only when a player's status has
actually changed (or appeared for the first time).

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| injury_id | UUID | PK | uuid4 | |
| player_id | UUID | no | | FK → people (CASCADE) |
| team_id | UUID | yes | | FK → teams (SET NULL) |
| status | text | no | | `training`, `test`, `1_week`, `2_4_weeks`, `4_8_weeks`, `indefinite`, `season`, `suspended`, `cleared` |
| body_part | text | yes | | `hamstring`, `knee_acl`, `head`, `ankle`, ... |
| mechanism | text | yes | | `collision`, `non_contact`, `illness`, `concussion_protocol`, `suspension`, `unknown` |
| description | text | yes | | Raw text from the source |
| expected_return_round | int | yes | | |
| expected_return_date | date | yes | | |
| severity | text | yes | | `low`, `moderate`, `high`, `season` |
| reported_at | timestamptz | no | | When the source published the change |
| resolved_at | timestamptz | yes | | Set on the prior open row when status flips to `cleared` |
| source | text | no | | `nrl_com_casualty`, `zerotackle`, `nrl_physio_twitter`, `manual` |
| source_url | text | yes | | |
| metadata_json | jsonb | no | {} | |
| created_at | timestamptz | no | now() | |

**Indexes:** (player_id, reported_at DESC), (team_id, status) WHERE resolved_at IS NULL, reported_at
**FK:** player_id → people (CASCADE); team_id → teams (SET NULL)

"Latest known status for player X": ORDER BY reported_at DESC LIMIT 1.

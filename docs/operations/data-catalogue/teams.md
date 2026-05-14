---
tags: [area/operations, data-catalogue]
---

# teams

[← Data Catalogue](README.md) · [Lineage](../data-lineage/teams.md) · Layer 2 — Structured world

Canonical roster of every team across all grades feeding into NRL — NRL,
NRLW, NSW Cup, QLD Cup (Hostplus Cup), and the junior pathway grades
(Jersey Flegg, Mal Meninga, SG Ball, Cyril Connell, Harold Matthews —
schema-allowed; not yet seeded). `parent_team_id` self-references to link
a feeder team to its senior NRL/NRLW side.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| team_id | UUID | PK | uuid4 | |
| slug | text | no | | UNIQUE; e.g. `brisbane_broncos`, `norths_devils`, `brisbane_broncos_nrlw` |
| name | text | no | | Full team name |
| short_name | text | yes | | e.g. `Broncos` |
| aliases | text[] | no | `{}` | Lower-grade rows may be empty |
| grade | text | no | | `nrl`, `nrlw`, `nsw_cup`, `qld_cup`, `jersey_flegg`, `mal_meninga`, `sg_ball`, `cyril_connell`, `harold_matthews` |
| competition | text | yes | | e.g. `NRL Premiership`, `NSW Cup` |
| parent_team_id | UUID | yes | | FK → teams (senior team this feeds into; NULL for top grades) |
| founded_year | int | yes | | |
| logo_url | text | yes | | |
| metadata_json | jsonb | no | {} | Long-tail: nicknames, fan_club_url, naming_history, optional home_venue_id, optional primary_colour / secondary_colour, expansion-team `enters_competition_year`, etc. |
| active | bool | no | true | |
| created_at | timestamptz | no | now() | |
| updated_at | timestamptz | no | now() | Auto-updates |

**Unique:** slug
**Indexes:** grade, parent_team_id, active
**FK:** parent_team_id → teams (ON DELETE SET NULL)

Baseline seed for prod and local lives in migration `039_seed_teams_2026.sql` — 19 NRL (incl. Perth Bears 2027 and Papua New Guinea 2028 expansion sides flagged via `metadata_json.enters_competition_year`), 12 NRLW, 12 NSW Cup, 15 Hostplus Cup. Idempotent (`ON CONFLICT (slug) DO UPDATE`). Pathway grades (Jersey Flegg, SG Ball, Mal Meninga, Cyril Connell, Harold Matthews) are schema-allowed but not yet seeded — populate via a follow-up migration once a downstream consumer needs them.

Incremental top-ups (e.g. when PNG's team name is announced, or when a feeder affiliation changes) go via the admin endpoint `POST /api/admin/teams/seed` (`make prod-seed-teams`) which takes a yaml-shaped JSON payload and runs the same idempotent upsert against `jeromelu_shared.teams.seed_teams()`.

## Historical lineage — potential future update

Today's `teams` schema captures *current* clubs. As historical content lights up (defunct sides like North Sydney Bears NRL 1908–1999, Newtown Jets NRL pre-1983, Adelaide Rams, Western Reds, etc.; mergers like Balmain + Western Suburbs → Wests Tigers; competition renames NSWRFL → NSWRL → ARL → NRL), three concerns surface:

- **Defunct clubs** — currently expressed via `active=false` only.
- **Mergers** — predecessor / successor relationships have no first-class home.
- **Competition rename** — `teams.competition` is a single text label and assumes one comp per club for all time.

**Interim convention** (until a downstream feature actually queries this): use `metadata_json` keys on existing rows.
- `lifespan: [{competition: "NRL", from: 1908, to: 1999}, {competition: "NSW Cup", from: 2007}]` — array of stints in chronological order.
- `predecessor_slugs: ["balmain_tigers", "western_suburbs_magpies"]` on the merged-into row.
- `successor_slugs: ["wests_tigers"]` on the merged-out rows.
- Treat `NSWRFL → NSWRL → ARL → NRL` as a small hardcoded constant in code; store the contemporaneous comp name inside `lifespan[].competition` rather than upgrading the schema.

**Upgrade path** when the interim shape stops paying its way: introduce a temporal SCD-2 `team_competitions` table (team_id, competition_id, effective_from, effective_to) plus a `competitions` reference (id, name, founded, ended, succeeded_by) seeded with NSWRFL, NSWRL, ARL, NRL, NRLW, NSW Cup, QLD Cup. Triggers for the upgrade: a feature that queries "teams active in NRL season X", >50 historical rows where typo tolerance matters, or any UI showing year-by-year competition membership. At that point `teams.competition` retires (becomes derivable as the current `team_competitions` row).

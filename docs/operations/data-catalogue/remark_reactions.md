---
tags: [area/operations, data-catalogue, status/planned]
---

# remark_reactions — planned (not yet built)

[← Data Catalogue](README.md) · [Lineage](../data-lineage/remark_reactions.md) · Layer 4 — Reasoning & output

> **Status:** described below as planned design — depends on [remarks](remarks.md).

Audience reactions to open/locked Remarks.

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| reaction_id | UUID | PK | uuid4 | |
| remark_id | UUID | no | | FK → remarks |
| user_id | UUID | yes | | |
| reaction_type | text | no | | `agree`, `disagree` |
| created_at | timestamptz | no | now() | |

**FK:** remark_id → remarks

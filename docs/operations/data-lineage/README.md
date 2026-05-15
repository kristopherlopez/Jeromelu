---
tags: [area/operations, data-lineage]
---

# Data Lineage

Per-table mapping from upstream sources → DB columns. Sits in the trinity:

- [data-sources/](../data-sources/README.md) — what's in S3 (upstream JSON profiles)
- [data-catalogue/](../data-catalogue/README.md) — what's in DB (column-level schema)
- **data-lineage/** *(this folder)* — the mapping between them

Each file mirrors a [data-catalogue](../data-catalogue/README.md) file by name. Open `data-lineage/matches.md` to see exactly which `nrl.com/match-centre` JSON path feeds `matches.attendance`, which extractor does the work, and what UPSERT/COALESCE semantics apply.

For the conceptual L1 (external) → L2 (S3) → L3 (DB) overview and identity-resolution narrative, see [docs/architecture/data-lineage.md](../../architecture/data-lineage.md).

---

## Per-table lineage

### Layer 1 — Identity

- [people](people.md) · [player_attributes](player_attributes.md) · [people_roles](people_roles.md) · [rounds](rounds.md)

### Layer 2 — Structured world

- [teams](teams.md) · [venues](venues.md) · [matches](matches.md) · [match_team_lists](match_team_lists.md) · [match_officials](match_officials.md) · [match_timeline](match_timeline.md)
- [player_match_stats](player_match_stats.md) · [team_standings](team_standings.md) · [stat_leaderboards](stat_leaderboards.md)
- [injuries](injuries.md) · [player_rounds](player_rounds.md) · [sc_settings](sc_settings.md)

### Layer 3 — Content & claims

- [scout_candidates](scout_candidates.md) · [scout_presenter_candidates](scout_presenter_candidates.md) · [source_presenters](source_presenters.md)
- [channels](channels.md) · [channel_metrics](channel_metrics.md) · [sources](sources.md) · [video_metrics](video_metrics.md)
- [source_documents](source_documents.md) · [source_chunks](source_chunks.md) · [source_speakers](source_speakers.md) · [source_chapters](source_chapters.md)
- [source_face_detections](source_face_detections.md) · [source_face_clusters](source_face_clusters.md) · [person_voiceprints](person_voiceprints.md) · [person_face_embeddings](person_face_embeddings.md)
- [quotes](quotes.md) · [claims](claims.md) · [claim_chunks](claim_chunks.md) · [claim_associations](claim_associations.md)

### Layer 4 — Reasoning & output

- [predictions](predictions.md) · [prediction_associations](prediction_associations.md) · [consensus_snapshots](consensus_snapshots.md)
- [decisions](decisions.md) · [decision_associations](decision_associations.md) · [outcomes](outcomes.md)
- [events](events.md) · [plans](plans.md)
- [remarks](remarks.md) · [remark_reactions](remark_reactions.md) · [alignment_scores](alignment_scores.md) — planned
- [knowledge_base](knowledge_base.md) · [wiki_pages](wiki_pages.md) · [wiki_revisions](wiki_revisions.md)
- [squad_slots](squad_slots.md) — planned

### Layer 5 — Agent audit

- [agent_runs](agent_runs.md) · [agent_events](agent_events.md)

---

## File shape

Each lineage file has:

1. **Sources** — upstream pipelines (with link to their data-sources profile) and what role each plays
2. **Extractor / Writer** — the code path that does the mapping
3. **Field mapping** — per-column source / source field / notes; constants and "not extracted" rows are explicit
4. **UPSERT semantics** — for tables with non-trivial conflict handling (which columns get overwritten vs `COALESCE`d vs `||` merged)
5. **Notes** — gotchas, planned future work, drift to the catalogue

Marker conventions:
- `derived` source means DB-side default (UUID, `now()`, generated column)
- `constant` source means hardcoded in the writer
- `S3 key` source means parsed from the archive's path, not its payload
- `not extracted` means schema-allowed but no current writer populates it

---

## Drift policy

When you change an extractor or migration:

1. Update the per-table lineage file in this folder
2. If a column was added/removed, update [data-catalogue](../data-catalogue/README.md) too
3. If an upstream feed shape changed, regenerate the affected [data-sources](../data-sources/README.md) profile

Treat all three folders as one unit — a PR that touches an extractor without touching its lineage file is incomplete.

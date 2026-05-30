---
tags: [area/operations, data-lineage]
---

# Lineage: claim_chunks

[Schema: data-catalogue/claim_chunks.md](../data-catalogue/claim_chunks.md)

## Sources

| Pipeline | Profile | Role |
|---|---|---|
| `process-transcript` / `upload-transcript` skills | — | Written together with claims |

## Writer

`scripts/transcripts/extraction/writer.py` — driven by the `upload-transcript` skill. For each [claims](claims.md) row, writes one `claim_chunks` row per [source_chunks](source_chunks.md) chunk that the claim was extracted from. SC notes path uses the same writer via `services/api/app/miner/supercoach_roster/notes_extractor.py`.

## Field mapping

| DB column | Source | Notes |
|---|---|---|
| `claim_id` | upload-transcript | Composite PK with chunk_id; FK → claims (CASCADE delete) |
| `chunk_id` | upload-transcript | Composite PK with claim_id; FK → source_chunks (CASCADE delete) |
| `ordinal` | upload-transcript | Order of chunks for this claim; defaults `0` |

## Notes

- N:M junction. A claim spanning multiple consecutive chunks gets multiple rows; a claim from a single chunk gets one.
- Cascade delete from either side keeps the junction tidy automatically.

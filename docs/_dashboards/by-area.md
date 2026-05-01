---
tags: [area/root, dashboard]
aliases: [Coverage, By Area]
---

# Vault Coverage by Area

Doc count and recency by area tag. Useful for spotting under-documented areas.

## Doc count by area

```dataview
TABLE WITHOUT ID
  rows.area AS "Area",
  length(rows) AS "Docs"
FROM ""
FLATTEN filter(file.tags, (t) => startswith(t, "#area/")) AS area
GROUP BY area
SORT length(rows) DESC
```

## Most-recently edited (top 20)

```dataview
TABLE WITHOUT ID
  file.link AS "Doc",
  filter(file.tags, (t) => startswith(t, "#area/"))[0] AS "Area",
  file.mtime AS "Last edit"
FROM ""
WHERE !contains(file.path, "_dashboards") AND !contains(file.path, "_templates")
SORT file.mtime DESC
LIMIT 20
```

## Stalest docs (oldest mtime, top 20)

```dataview
TABLE WITHOUT ID
  file.link AS "Doc",
  filter(file.tags, (t) => startswith(t, "#area/"))[0] AS "Area",
  file.mtime AS "Last edit"
FROM ""
WHERE !contains(file.path, "_dashboards") AND !contains(file.path, "_templates") AND !contains(file.path, "archive")
SORT file.mtime ASC
LIMIT 20
```

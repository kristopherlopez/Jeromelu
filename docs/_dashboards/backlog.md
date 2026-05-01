---
tags: [area/root, dashboard]
aliases: [Backlog, What's Next]
---

# Backlog

Everything not yet built or still in planning. Pulls from `status/not-built` and `status/planning` tags across the vault.

## Designed but not built

```dataview
TABLE WITHOUT ID
  file.link AS "Doc",
  filter(file.tags, (t) => startswith(t, "#area/"))[0] AS "Area"
FROM ""
WHERE contains(file.tags, "#status/not-built")
SORT file.path ASC
```

## Planning (todo/)

```dataview
TABLE WITHOUT ID
  file.link AS "Item",
  file.mtime AS "Last touched"
FROM "todo"
WHERE contains(file.tags, "#status/planning")
SORT file.mtime DESC
```

## Skeletons (started, not real)

```dataview
LIST
FROM ""
WHERE contains(file.tags, "#status/skeleton")
SORT file.path ASC
```

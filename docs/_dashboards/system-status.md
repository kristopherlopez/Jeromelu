---
tags: [area/root, dashboard]
aliases: [System Status, Agent Status Board]
---

# System Agent Status

Live status of every agent under `agents/system/`. Pulls from frontmatter `status/*` tags. Edit a doc's frontmatter and this updates on next view.

## Status board

```dataview
TABLE WITHOUT ID
  file.link AS "Agent",
  filter(file.tags, (t) => startswith(t, "#status/"))[0] AS "Status"
FROM "agents/system"
WHERE file.name != "README"
SORT file.name ASC
```

## By status

### Live

```dataview
LIST
FROM "agents/system"
WHERE contains(file.tags, "#status/live")
SORT file.name ASC
```

### Skeleton

```dataview
LIST
FROM "agents/system"
WHERE contains(file.tags, "#status/skeleton")
SORT file.name ASC
```

### Partial

```dataview
LIST
FROM "agents/system"
WHERE contains(file.tags, "#status/partial")
SORT file.name ASC
```

### Not built

```dataview
LIST
FROM "agents/system"
WHERE contains(file.tags, "#status/not-built")
SORT file.name ASC
```

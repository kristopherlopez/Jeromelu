---
tags: [area/root, meta]
aliases: [Vault Conventions, Conventions]
---

# Vault Conventions

This vault is the `docs/` folder of the Jaromelu repo, opened directly in Obsidian. The same files are also read by GitHub and Claude Code, so conventions stay portable.

## Link Style

**Use standard markdown links: `[text](relative/path.md)`** — works in Obsidian, GitHub, and Claude Code.

Do **not** use `[[wikilinks]]` — they break GitHub rendering and Claude Code's link resolution. Obsidian's backlinks pane and graph view work fine with markdown links anyway (Obsidian auto-resolves them).

## Frontmatter

Every doc has a YAML frontmatter block at the top with at least a `tags:` key. Example:

```yaml
---
tags: [area/architecture]
---
```

Only the entry-point notes (Home, vault-conventions, folder READMEs) carry `aliases:`.

## Tag Taxonomy

### Area (always present)

One per file, based on the top-level folder.

| Tag | Folder |
|---|---|
| `area/architecture` | `architecture/` |
| `area/concepts` | `concepts/` |
| `area/agents` | `agents/` |
| `area/pages` | `pages/` |
| `area/operations` | `operations/`, `ops/` |
| `area/sources` | `sources/` |
| `area/avatar` | `avatar/` |
| `area/design-system` | `design-system/` |
| `area/todo` | `todo/` |
| `area/archive` | `archive/` |
| `area/root` | `docs/` (Home, conventions, root-level notes) |

### Subarea (where useful)

| Tag | Path |
|---|---|
| `subarea/crew` | `agents/crew/` |
| `subarea/system` | `agents/system/` |
| `subarea/skills` | `agents/skills/` |
| `subarea/feed` | `pages/feed/` |
| `subarea/wiki` | `pages/wiki/` |
| `subarea/analysis` | `pages/analysis/` |
| `subarea/ledger` | `pages/ledger/` |
| `subarea/pulse` | `pages/pulse/` |
| `subarea/ask-me` | `pages/ask-me/` |

### Status

For docs that describe something with a build state. Folder defaults apply to `archive/` and `todo/`.

| Tag | Meaning |
|---|---|
| `status/live` | Running in production (or local equivalent) |
| `status/partial` | Partly built, not feature-complete |
| `status/skeleton` | File/code exists but no real implementation yet |
| `status/not-built` | Designed but no code |
| `status/planning` | Backlog item (default for `todo/`) |
| `status/archived` | Historical, superseded (default for `archive/`) |

## File Naming

- `kebab-case.md`
- Numbered prefixes (e.g., `01-venture-thesis.md`) signal reading order; preserve when adding to a numbered series.
- Folder index files are `README.md` — Obsidian indexes them fine.

## Adding a New Doc

1. Create the file under the right folder
2. Add the frontmatter block with at least one `area/` tag
3. Add `subarea/` and `status/` if applicable
4. Link it from the relevant folder `README.md` (the folder MOC)
5. If it's a major new entry point, link it from [Home](Home.md)

## Updating Tags in Bulk

Frontmatter was added in bulk via a one-off script (see commit history). To re-run or extend:
- The script is idempotent — files that already have `---` on line 1 are skipped
- Manual status overrides live in the script itself, not in this doc

## Vault Infrastructure (`_*` folders)

Folders prefixed with `_` are vault infrastructure, not project content. They sort to the top of the file explorer.

| Folder | Contents |
|---|---|
| `_dashboards/` | Dataview dashboards, Kanban boards, Canvas dashboards. Read-only views of vault state. |
| `_templates/` | Templater templates. Activated by folder rules (see [_obsidian-setup](_obsidian-setup.md)). New `agents/system/*.md` auto-fills from `system-agent.md`, etc. |
| `_assets/snippets/` | CSS snippets. Versioned in git here as the source of truth; Obsidian reads them from `.obsidian/snippets/` (gitignored), so copy them across once per machine. |

## Dashboards & Plugins

Dashboards rely on plugins documented in [_obsidian-setup](_obsidian-setup.md):
- **Dataview** queries read `tags:` and `file.tags` — that's why the bulk frontmatter pass was load-bearing
- **Kanban** plugin renders the agent status as a board from `_dashboards/agents-kanban.md`
- **Canvas** is a core plugin — `_dashboards/Project Home.canvas` is the visual project map

When you add a new system agent or change its status:
1. Update the doc's frontmatter (`status/live`, `status/skeleton`, etc.)
2. Move the line in `_dashboards/agents-kanban.md` to the new column
3. Dataview-driven dashboards (Home, system-status, backlog, by-area) update automatically

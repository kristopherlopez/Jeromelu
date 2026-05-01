---
tags: [area/root, meta]
aliases: [Obsidian Setup, Plugin Setup]
---

# Obsidian Setup

One-time setup for the plugins this vault is built around. Settings live in `.obsidian/` (gitignored, per-machine), so re-do this if you open the vault on a new machine.

## Open the vault

Point Obsidian at `C:\Users\krist\ClaudeProjects\Jeromelu\docs`. **Not** the repo root — only `docs/` should be the vault, otherwise Obsidian indexes code.

## Plugins to install (Settings → Community plugins → Browse)

| Plugin | Purpose | Tier |
|---|---|---|
| **Dataview** | Live dashboards from frontmatter (status boards, backlog, coverage) | 1 |
| **Excalidraw** | Hand-drawn diagrams embedded in arch/concept docs | 1 |
| **Iconize** | Folder & file icons in the file explorer | 1 |
| **Templater** | Pre-fill frontmatter when creating new docs | 2 |
| **Kanban** | Renders status-grouped markdown as a board | 2 |

Canvas is a *core* plugin (already enabled). Just confirm it's on under Settings → Core plugins.

## Plugin configuration

### Dataview
- Settings → Dataview → **Enable JavaScript Queries**: on (used by some dashboards).
- Settings → Dataview → **Enable Inline Queries**: on.

### Templater
- Settings → Templater → **Template folder location**: `_templates`
- Settings → Templater → **Trigger Templater on new file creation**: on
- Settings → Templater → **Folder Templates**:
  - `agents/system` → `_templates/system-agent.md`
  - `architecture` → `_templates/architecture-doc.md`
  - `concepts` → `_templates/concept.md`
  - `todo` → `_templates/todo.md`

### Iconize
- Settings → Iconize → set folder icons:
  - `architecture` → 🏛️ or `lucide-building-2`
  - `agents` → 🤖 or `lucide-bot`
  - `concepts` → 💡 or `lucide-lightbulb`
  - `pages` → 🖥️ or `lucide-monitor`
  - `operations` → ⚙️ or `lucide-settings`
  - `sources` → 📥 or `lucide-inbox`
  - `avatar` → 🎭 or `lucide-drama`
  - `todo` → ✅ or `lucide-list-todo`
  - `archive` → 📦 or `lucide-archive`

### CSS Snippet (status badges)
1. Open the vault folder in your file manager → navigate to `.obsidian/snippets/` (create the folder if it doesn't exist).
2. Copy `_assets/snippets/status-badges.css` from this vault into `.obsidian/snippets/`.
3. Settings → Appearance → **CSS snippets** → toggle `status-badges` on.

After that, every `#status/live`, `#status/not-built` etc. tag renders as a coloured pill.

## Where things live

| Folder | What |
|---|---|
| `_dashboards/` | Dataview dashboards, the project canvas, the agents kanban |
| `_templates/` | Templater templates for new docs |
| `_assets/snippets/` | CSS snippets (copy into `.obsidian/snippets/`) |

The `_` prefix sorts these to the top of the file explorer and signals "vault infrastructure, not project content."

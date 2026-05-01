"""One-off: prepend Obsidian-friendly YAML frontmatter to docs/*.md.

Idempotent: skips files whose first line is already `---`.

Run from repo root:
    python scripts/add_obsidian_frontmatter.py            # dry run
    python scripts/add_obsidian_frontmatter.py --apply    # write changes
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

DOCS = Path("docs")

AREA_BY_FOLDER = {
    "architecture": "area/architecture",
    "concepts": "area/concepts",
    "agents": "area/agents",
    "pages": "area/pages",
    "operations": "area/operations",
    "ops": "area/operations",
    "sources": "area/sources",
    "avatar": "area/avatar",
    "design-system": "area/design-system",
    "todo": "area/todo",
    "archive": "area/archive",
}

SUBAREA_BY_PATH = {
    "agents/crew": "subarea/crew",
    "agents/system": "subarea/system",
    "agents/skills": "subarea/skills",
    "pages/feed": "subarea/feed",
    "pages/wiki": "subarea/wiki",
    "pages/analysis": "subarea/analysis",
    "pages/ledger": "subarea/ledger",
    "pages/pulse": "subarea/pulse",
    "pages/ask-me": "subarea/ask-me",
}

# Folder-level status defaults
FOLDER_STATUS = {
    "archive": "status/archived",
    "todo": "status/planning",
}

# Per-file status overrides (relative to docs/, posix-style)
FILE_STATUS = {
    "agents/system/orchestrator.md": "status/skeleton",
    "agents/system/ingestion.md": "status/live",
    "agents/system/publishing.md": "status/live",
    "agents/system/scraper.md": "status/partial",
    "agents/system/extraction.md": "status/not-built",
    "agents/system/decision.md": "status/not-built",
    "agents/system/source-discovery.md": "status/live",
    "agents/system/agent-audit.md": "status/live",
    "agents/system/player-roster.md": "status/live",
    "agents/system/daily-intel-sweep.md": "status/live",
}

# Root-level files that need an explicit area
ROOT_AREA = {
    "Home.md": None,  # already has frontmatter
    "_vault-conventions.md": None,  # already has frontmatter
    "content-production-pipeline.md": "area/avatar",
    "temporal-notes.md": "area/architecture",
}


def tags_for(rel_path: Path) -> list[str]:
    """Compute tag list for a doc path relative to docs/."""
    posix = rel_path.as_posix()
    parts = rel_path.parts
    tags: list[str] = []

    if len(parts) == 1:
        # Root-level file
        area = ROOT_AREA.get(parts[0])
        if area:
            tags.append(area)
    else:
        top = parts[0]
        area = AREA_BY_FOLDER.get(top)
        if area:
            tags.append(area)

        # Sub-area for two-level paths under agents/ or pages/
        if len(parts) >= 2:
            two = f"{parts[0]}/{parts[1]}"
            sub = SUBAREA_BY_PATH.get(two)
            if sub:
                tags.append(sub)

    # Status: per-file override beats folder default
    if posix in FILE_STATUS:
        tags.append(FILE_STATUS[posix])
    elif parts and parts[0] in FOLDER_STATUS:
        tags.append(FOLDER_STATUS[parts[0]])

    return tags


def has_frontmatter(text: str) -> bool:
    return text.lstrip("﻿").startswith("---\n") or text.lstrip("﻿").startswith("---\r\n")


def build_frontmatter(tags: list[str]) -> str:
    if not tags:
        return ""
    tag_list = ", ".join(tags)
    return f"---\ntags: [{tag_list}]\n---\n\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Write changes (default: dry run)")
    args = ap.parse_args()

    if not DOCS.is_dir():
        print(f"docs/ not found from cwd={Path.cwd()}", file=sys.stderr)
        return 2

    skipped_existing = 0
    skipped_no_tags = 0
    written = 0
    would_write = 0

    for md in sorted(DOCS.rglob("*.md")):
        rel = md.relative_to(DOCS)
        text = md.read_text(encoding="utf-8")

        if has_frontmatter(text):
            skipped_existing += 1
            continue

        tags = tags_for(rel)
        if not tags:
            skipped_no_tags += 1
            print(f"  [no tags] {rel.as_posix()}")
            continue

        block = build_frontmatter(tags)
        new_text = block + text

        if args.apply:
            md.write_text(new_text, encoding="utf-8")
            written += 1
        else:
            would_write += 1
            print(f"  [+] {rel.as_posix()}  ->  {tags}")

    print()
    print(f"Skipped (already had frontmatter): {skipped_existing}")
    print(f"Skipped (no tags computed):       {skipped_no_tags}")
    if args.apply:
        print(f"Wrote frontmatter to:              {written}")
    else:
        print(f"Would write frontmatter to:        {would_write}")
        print("\n(dry run — re-run with --apply to write changes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

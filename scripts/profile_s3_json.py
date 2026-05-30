"""Profile JSON archives at an S3 prefix.

Samples N objects, walks each JSON tree, and emits a markdown shape report:
top-level structure tree + per-path table (type, presence, nullability,
cardinality, example values). Designed to run against any miner/* prefix
to ground per-table lineage docs in the actual upstream shape.

Usage:
    python scripts/profile_s3_json.py miner/nrlcom/match-centre/111/2026/round-07/
    python scripts/profile_s3_json.py miner/nrlcom/match-centre/ --samples 20
    python scripts/profile_s3_json.py <prefix> --out docs/architecture/profiles/nrlcom/match-centre.md
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from typing import Any

import boto3

DEFAULT_BUCKET = "jeromelu-clean-documents"
EXAMPLE_STR_CAP = 60


def list_keys(bucket: str, prefix: str) -> list[str]:
    client = boto3.client("s3")
    keys: list[str] = []
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []) or []:
            keys.append(obj["Key"])
    return keys


def read_json(bucket: str, key: str) -> Any:
    client = boto3.client("s3")
    resp = client.get_object(Bucket=bucket, Key=key)
    return json.loads(resp["Body"].read())


def walk(node: Any, path: str, out: dict[str, list[Any]]) -> None:
    """Recursively collect (jsonpath -> [values]) from a JSON tree.

    Arrays use `[*]` in the path; per-element values aggregate under that
    same key. Array length is recorded under `<path>.__len__`.
    """
    if isinstance(node, dict):
        # record empty objects too so we know the shape exists
        if not node:
            out[path].append({})
        for k, v in node.items():
            walk(v, f"{path}.{k}", out)
    elif isinstance(node, list):
        out[f"{path}.__len__"].append(len(node))
        for v in node:
            walk(v, f"{path}[*]", out)
    else:
        out[path].append(node)


def type_of(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    if isinstance(v, dict):
        return "object"
    if isinstance(v, list):
        return "array"
    return type(v).__name__


def truncate(s: str, cap: int = EXAMPLE_STR_CAP) -> str:
    return s if len(s) <= cap else s[: cap - 1] + "…"


def example_repr(v: Any) -> str:
    if isinstance(v, str):
        return truncate(json.dumps(v))
    return truncate(json.dumps(v, default=str))


def summarise(profiles: list[dict[str, list[Any]]]) -> list[dict[str, Any]]:
    presence: Counter[str] = Counter()
    all_paths: dict[str, list[Any]] = defaultdict(list)
    n = len(profiles)
    for p in profiles:
        for path, vs in p.items():
            presence[path] += 1
            all_paths[path].extend(vs)

    rows: list[dict[str, Any]] = []
    for path in sorted(all_paths):
        vs = all_paths[path]
        types = Counter(type_of(v) for v in vs)
        non_null = [v for v in vs if v is not None]
        # de-dupe examples by repr; keep up to 3 distinct
        seen: set[str] = set()
        examples: list[str] = []
        for v in non_null:
            r = example_repr(v)
            if r in seen:
                continue
            seen.add(r)
            examples.append(r)
            if len(examples) >= 3:
                break
        cardinality = len({json.dumps(v, default=str) for v in non_null})
        rows.append(
            {
                "path": path,
                "type": " \\| ".join(t for t, _ in types.most_common()),
                "presence": f"{presence[path]}/{n}",
                "nullable": "yes" if "null" in types else "no",
                "cardinality": cardinality,
                "examples": examples,
            }
        )
    return rows


def render_tree(rows: list[dict[str, Any]]) -> str:
    """Top 2 levels of the structure: top-level keys + their immediate children.

    Container paths (`object`, `array`) are reconstructed from leaf-path
    prefixes so `awayTeam`, `timeline`, etc. show up alongside their leaves.
    """
    type_at: dict[str, str] = {}

    def normalise(p: str) -> str:
        return p.replace("[*]", "")

    def add_container(path: str, kind: str) -> None:
        if path not in type_at:
            type_at[path] = kind

    for r in rows:
        p = r["path"]
        if p.endswith(".__len__"):
            parent = p[: -len(".__len__")]
            add_container(normalise(parent), "array")
            parts = parent.split(".")
            for i in range(1, len(parts)):
                add_container(normalise(".".join(parts[:i])), "object")
            continue
        type_at[normalise(p)] = r["type"]
        parts = p.split(".")
        for i in range(1, len(parts)):
            seg = parts[i - 1]
            kind = "array" if "[*]" in seg else "object"
            add_container(normalise(".".join(parts[:i])), kind)

    def depth(path: str) -> int:
        return path.count(".")

    shown = sorted(p for p in type_at if 1 <= depth(p) <= 2)
    lines = ["```", "$"]
    for p in shown:
        d = depth(p)
        indent = "│   " * (d - 1)
        leaf = p.rsplit(".", 1)[-1]
        lines.append(f"{indent}├── {leaf}: {type_at[p]}")
    lines.append("```")
    return "\n".join(lines)


def render_markdown(bucket: str, prefix: str, sample_keys: list[str], rows: list[dict[str, Any]]) -> str:
    out: list[str] = []
    out.append("---")
    out.append("tags: [area/architecture, data-lineage, profile]")
    out.append("---")
    out.append("")
    out.append(f"# Profile: `{prefix}`")
    out.append("")
    out.append(
        f"_Generated by `scripts/profile_s3_json.py`. Bucket: `{bucket}`. Sample size: {len(sample_keys)} objects._"
    )
    out.append("")
    out.append("## Sample objects")
    out.append("")
    for k in sample_keys:
        out.append(f"- `{k}`")
    out.append("")
    out.append("## Top-level structure")
    out.append("")
    out.append(render_tree(rows))
    out.append("")
    out.append("## Field profile")
    out.append("")
    out.append("| Path | Type | Presence | Nullable | Cardinality | Examples |")
    out.append("|---|---|---|---|---|---|")
    for r in rows:
        ex = ", ".join(r["examples"]) if r["examples"] else "—"
        ex = ex.replace("|", "\\|")
        path_str = r["path"].replace("|", "\\|")
        out.append(f"| `{path_str}` | {r['type']} | {r['presence']} | {r['nullable']} | {r['cardinality']} | {ex} |")
    out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("prefix", help="S3 prefix under the bucket")
    ap.add_argument("--bucket", default=DEFAULT_BUCKET)
    ap.add_argument("--samples", type=int, default=10)
    ap.add_argument(
        "--strategy",
        choices=("last", "first", "spread"),
        default="last",
        help="Which N keys to sample: last (most recent by sort), first, or spread (evenly).",
    )
    ap.add_argument("--out", default=None, help="Write markdown to this path (default: stdout)")
    args = ap.parse_args()

    keys = list_keys(args.bucket, args.prefix)
    if not keys:
        print(f"No objects under prefix: {args.prefix}", file=sys.stderr)
        return 1
    keys.sort()
    if args.strategy == "last":
        sample = keys[-args.samples :]
    elif args.strategy == "first":
        sample = keys[: args.samples]
    else:
        if args.samples >= len(keys):
            sample = keys
        else:
            step = len(keys) / args.samples
            sample = [keys[int(i * step)] for i in range(args.samples)]

    profiles: list[dict[str, list[Any]]] = []
    for k in sample:
        payload = read_json(args.bucket, k)
        prof: dict[str, list[Any]] = defaultdict(list)
        walk(payload, "$", prof)
        profiles.append(prof)

    rows = summarise(profiles)
    md = render_markdown(args.bucket, args.prefix, sample, rows)
    if args.out:
        import os

        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"Wrote {args.out} ({len(rows)} field rows, {len(sample)} samples)")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())

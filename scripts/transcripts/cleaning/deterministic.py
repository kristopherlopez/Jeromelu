"""Layer 1: Deterministic exact-match corrections from corrections.yaml."""

from pathlib import Path

import yaml

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def load_corrections(path: Path | None = None) -> list[tuple[str, str]]:
    """Load corrections.yaml and return as sorted (old, new) pairs.

    Sorted longest-first so longer matches take priority.
    Filters out entries shorter than 5 chars or identity mappings.
    """
    if path is None:
        path = DATA_DIR / "corrections.yaml"

    with open(path, encoding="utf-8") as f:
        raw: dict[str, str] = yaml.safe_load(f)

    pairs = [
        (old, new)
        for old, new in raw.items()
        if len(old) >= 5 and old != new
    ]
    pairs.sort(key=lambda x: -len(x[0]))
    return pairs


def apply_deterministic(
    segments: list[dict],
    corrections: list[tuple[str, str]],
) -> list[dict]:
    """Apply exact-match corrections to segment text fields.

    Returns list of correction records for reporting.
    """
    records = []
    for seg_idx, seg in enumerate(segments):
        text = seg["text"]
        for old, new in corrections:
            if old in text:
                text = text.replace(old, new)
                records.append({
                    "segment_idx": seg_idx,
                    "original": old,
                    "corrected": new,
                    "confidence": "HIGH",
                    "method": "deterministic",
                })
        seg["text"] = text
    return records

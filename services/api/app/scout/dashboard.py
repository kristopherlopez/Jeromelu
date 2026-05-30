"""Read-only Scout dashboard backed by ``agent_runs``."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query
from jeromelu_shared.db import AgentRun
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ..deps import get_db

SCOUT_AGENT_ID = "scout"
UNCLASSIFIED_PIPELINE = "unclassified"
FAILURE_STATUSES = frozenset({"failed", "aborted"})
MAX_DETAIL_DEPTH = 3
MAX_DETAIL_KEYS = 30

router = APIRouter()


def _isoformat(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _detail_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _pipeline_name(detail: Mapping[str, Any]) -> str:
    raw = detail.get("pipeline")
    if isinstance(raw, str):
        pipeline = raw.strip()
        if pipeline:
            return pipeline
    return UNCLASSIFIED_PIPELINE


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, str | int | float | bool | Decimal)


def _scalar(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    return value


def _summarise_detail(detail: Mapping[str, Any], *, depth: int = 0) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    visible_items = tuple(detail.items())[:MAX_DETAIL_KEYS]
    for key, value in visible_items:
        key_text = str(key)
        if key_text == "pipeline":
            continue

        if _is_scalar(value):
            summary[key_text] = _scalar(value)
        elif isinstance(value, Mapping):
            if depth >= MAX_DETAIL_DEPTH:
                summary[f"{key_text}_keys"] = len(value)
                continue
            nested = _summarise_detail(value, depth=depth + 1)
            if nested:
                summary[key_text] = nested
        elif isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
            summary[f"{key_text}_count"] = len(value)

    hidden_count = len(detail) - len(visible_items)
    if hidden_count > 0:
        summary["detail_keys_truncated"] = hidden_count

    return summary


def _run_cost(row: Any) -> float | None:
    return _float_or_none(getattr(row, "total_cost_usd", None))


def _base_pipeline_row(row: Any, pipeline: str, detail: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "pipeline": pipeline,
        "last_run_id": getattr(row, "run_id", None),
        "status": getattr(row, "status", None),
        "started_at": _isoformat(getattr(row, "started_at", None)),
        "ended_at": _isoformat(getattr(row, "ended_at", None)),
        "summary": getattr(row, "summary", "") or "",
        "detail": _summarise_detail(detail),
        "total_cost_usd": _run_cost(row),
        "run_count": 0,
        "status_counts": {},
        "recent_failure_count": 0,
        "recent_total_cost_usd": 0.0,
    }


def build_scout_dashboard(rows: Sequence[Any], *, limit: int) -> dict[str, Any]:
    """Group recent Scout ``agent_runs`` rows by ``detail_json.pipeline``.

    ``rows`` must be newest-first. The endpoint deliberately summarises nested
    lists as counts so large per-channel/per-source audit details do not leak
    into dashboard payloads.
    """

    pipelines: dict[str, dict[str, Any]] = {}
    pipeline_order: list[str] = []

    for row in rows:
        detail = _detail_dict(getattr(row, "detail_json", None))
        pipeline = _pipeline_name(detail)
        entry = pipelines.get(pipeline)
        if entry is None:
            entry = _base_pipeline_row(row, pipeline, detail)
            pipelines[pipeline] = entry
            pipeline_order.append(pipeline)

        entry["run_count"] += 1
        status = getattr(row, "status", None) or "unknown"
        entry["status_counts"][status] = entry["status_counts"].get(status, 0) + 1
        if status in FAILURE_STATUSES:
            entry["recent_failure_count"] += 1

        cost = _run_cost(row)
        if cost is not None:
            entry["recent_total_cost_usd"] += cost

    for entry in pipelines.values():
        entry["recent_total_cost_usd"] = round(entry["recent_total_cost_usd"], 6)

    return {
        "ok": True,
        "window": {
            "limit": limit,
            "row_count": len(rows),
            "pipeline_count": len(pipelines),
        },
        "pipeline_order": pipeline_order,
        "pipelines": pipelines,
    }


def _recent_scout_runs(db: Session, *, limit: int) -> list[AgentRun]:
    return (
        db.query(AgentRun)
        .filter(AgentRun.agent_id == SCOUT_AGENT_ID)
        .order_by(desc(AgentRun.started_at))
        .limit(limit)
        .all()
    )


@router.get("/admin/scout/dashboard")
def scout_dashboard(
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    """Recent Scout pipeline health grouped by ``detail_json.pipeline``."""

    rows = _recent_scout_runs(db, limit=limit)
    return build_scout_dashboard(rows, limit=limit)

"""Shared audit helpers for deterministic Scout pipelines.

The feed-acquisition routes all follow the same pattern: create one
``agent_runs`` row, do deterministic fetch/archive/parse/upsert work, then
stamp completion or failure. This module keeps that wiring consistent without
owning the actual pipeline logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jeromelu_shared.agent_audit import (
    AgentBounds,
    make_run_id,
    record_agent_ended,
    record_agent_started,
)
from sqlalchemy.orm import Session

SCOUT_AGENT_ID = "scout"
SCOUT_AGENT_NAME = "Scout"
DETERMINISTIC_MODEL = "deterministic"


def _bounds_dict(bounds: AgentBounds) -> dict[str, Any]:
    return {
        "max_turns": bounds.max_turns,
        "max_tool_calls": bounds.max_tool_calls,
        "max_wall_seconds": bounds.max_wall_seconds,
        "max_budget_usd": bounds.max_budget_usd,
    }


@dataclass
class DeterministicScoutRun:
    db: Session
    run_id: str
    pipeline: str
    detail: dict[str, Any]
    model: str = DETERMINISTIC_MODEL

    def complete(self, summary_text: str) -> None:
        record_agent_ended(
            self.db,
            run_id=self.run_id,
            status="completed",
            summary_text=summary_text,
            model=self.model,
            detail=self.detail,
        )

    def fail(self, exc: Exception, summary_text: str) -> None:
        self.detail["error"] = f"{type(exc).__name__}: {exc}"
        record_agent_ended(
            self.db,
            run_id=self.run_id,
            status="failed",
            summary_text=summary_text,
            model=self.model,
            detail=self.detail,
        )


def start_deterministic_run(
    db: Session,
    *,
    pipeline: str,
    brief: str,
    detail: dict[str, Any] | None = None,
    max_wall_seconds: int = 60,
) -> DeterministicScoutRun:
    run_id = make_run_id(SCOUT_AGENT_ID)
    bounds = AgentBounds(
        max_turns=0,
        max_tool_calls=0,
        max_wall_seconds=max_wall_seconds,
        max_budget_usd=0.0,
    )
    run_detail: dict[str, Any] = {"pipeline": pipeline}
    run_detail.update(detail or {})

    record_agent_started(
        db,
        agent_id=SCOUT_AGENT_ID,
        agent_name=SCOUT_AGENT_NAME,
        run_id=run_id,
        model=DETERMINISTIC_MODEL,
        brief=brief,
        bounds={**_bounds_dict(bounds), **run_detail},
    )
    return DeterministicScoutRun(
        db=db,
        run_id=run_id,
        pipeline=pipeline,
        detail=run_detail,
    )


def set_archive_detail(detail: dict[str, Any], archive_key: str | None) -> None:
    detail["s3_archive_key"] = archive_key
    if archive_key is None:
        detail["s3_archive_failed"] = True

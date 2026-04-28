"""Standardised audit trail for Claude-Agent-SDK-based agents.

Every agent built on the Anthropic Messages API + custom tools loop should use
this module so observability, cost tracking, and forensic logs look the same
across the system.

Three layers per run, all joinable on `run_id`:
  1. `agent_runs` rows (start + end)           — DB run-level summary
  2. `agent_events` rows                       — DB per-event trace, queryable
                                                 live while the run is in flight
  3. JSONL bundle uploaded to S3 at run end    — long-term forensics

The S3 key is stamped into the end `agent_runs.detail_json.s3_log_key`, so
a single SQL query goes from "this run" to its forensic transcript.

S3 key format:
  {settings.s3_agent_logs_bucket}/agent-logs/{agent_id}/{YYYY}/{MM}/{DD}/{run_id}.jsonl

Usage skeleton (see services/api/app/scout/loop.py for the reference impl):

    from jeromelu_shared.agent_audit import (
        AgentAuditLog, AgentBounds, MODEL_PRICING,
        estimate_token_cost, make_run_id,
        record_agent_started, record_agent_ended,
    )

    run_id = make_run_id("scout")
    audit = AgentAuditLog(
        session=session, agent_id="scout", run_id=run_id,
        s3_bucket=settings.s3_agent_logs_bucket,
    )
    record_agent_started(session, agent_id="scout", agent_name="Scout",
                         run_id=run_id, model=..., brief=..., bounds=asdict(bounds))
    audit.run_started(model=..., brief=..., bounds=asdict(bounds))

    # ... per turn: audit.turn_started / .text / .tool_use / .tool_result / .turn_complete ...
    # ... on bound hit: audit.bound_hit(...) ...
    # ... on exception: audit.error(...) ...

    audit.run_ended(status=..., summary={...})
    s3_key = audit.flush_to_s3()
    record_agent_ended(session, agent_id="scout", agent_name="Scout",
                       run_id=run_id, status=..., summary_text=...,
                       detail={..., "s3_log_key": s3_key,
                               "agent_events_count": audit.event_count})

When adding a new agent (e.g. 'critic'): also extend the agent_runs
agent_id CHECK constraint via a new migration before first run, otherwise
record_agent_started will fail.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from jeromelu_shared.db import AgentEvent, AgentRun

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Standard bounds
# ---------------------------------------------------------------------------

@dataclass
class AgentBounds:
    """Hard caps every agent should respect.

    Budget gates, not goals — agents should typically finish well before any
    of these trip. If a run regularly hits a bound, that's a sign the prompt
    or tools need work.
    """
    max_turns: int = 20
    max_tool_calls: int = 60
    max_wall_seconds: int = 900            # 15 min
    max_budget_usd: float = 3.00


# ---------------------------------------------------------------------------
# Cost estimation — used for budget gates, not invoicing.
# Verify against current Anthropic pricing on each run-loop edit.
# ---------------------------------------------------------------------------

MODEL_PRICING: dict[str, dict[str, float]] = {
    # USD per million tokens
    "claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write_5m": 3.75,
    },
    "claude-opus-4-7": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_write_5m": 18.75,
    },
    "claude-haiku-4-5-20251001": {
        "input": 1.00,
        "output": 5.00,
        "cache_read": 0.10,
        "cache_write_5m": 1.25,
    },
}


def estimate_token_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_write_tokens: int,
) -> float:
    """Rough USD cost for a run's token usage. Falls back to Sonnet 4.6 pricing
    for unknown models so the budget gate still trips."""
    p = MODEL_PRICING.get(model, MODEL_PRICING["claude-sonnet-4-6"])
    return (
        (input_tokens / 1_000_000) * p["input"]
        + (output_tokens / 1_000_000) * p["output"]
        + (cache_read_tokens / 1_000_000) * p["cache_read"]
        + (cache_write_tokens / 1_000_000) * p["cache_write_5m"]
    )


# Server-side tools are billed separately from tokens. Verify periodically.
SERVER_TOOL_PRICING_USD: dict[str, float] = {
    "web_search": 0.01,    # $10 per 1,000 searches (Anthropic-managed)
    "web_fetch": 0.00,     # token cost only — no per-fetch charge
}


def estimate_server_tool_cost(tool_counts: dict[str, int]) -> float:
    """USD cost for server-side tool usage (web_search, web_fetch).

    Pass a dict like {"web_search": 12, "web_fetch": 3}. Unknown tool names
    contribute 0 — better to under-report than to crash a run on a new tool.
    """
    return sum(
        n * SERVER_TOOL_PRICING_USD.get(name, 0.0)
        for name, n in (tool_counts or {}).items()
    )


# ---------------------------------------------------------------------------
# Run identity
# ---------------------------------------------------------------------------

def make_run_id(agent_id: str) -> str:
    """Uniform run id across agents: '{agent_id}-{YYYYMMDDTHHMMSS}-{nonce}'.

    The agent prefix lets you grep logs / S3 keys / DB rows by agent without
    parsing JSON. The timestamp keeps runs sortable by name. The nonce avoids
    collisions from same-second triggers.
    """
    return f"{agent_id}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:6]}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truncate(value: Any, limit: int = 5000) -> Any:
    """Trim large values to keep stored events manageable."""
    if isinstance(value, str) and len(value) > limit:
        return value[:limit] + f"... [truncated {len(value) - limit} chars]"
    if isinstance(value, dict):
        return {k: _truncate(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_truncate(v, limit) for v in value]
    return value


# ---------------------------------------------------------------------------
# AgentAuditLog — DB-backed event trail with S3 bundle at end
# ---------------------------------------------------------------------------

class AgentAuditLog:
    """Per-event audit log. Writes each event into `agent_events` (queryable
    live) and buffers in memory; on `flush_to_s3()` serialises the buffer to
    a single JSONL object and uploads it for long-term forensics.

    DB write failures are logged but do not abort the run — the in-memory
    buffer remains complete and the S3 upload is the safety net.

    Standard event types:
      run_started, turn_started, text, tool_use, tool_result, server_block,
      turn_complete, bound_hit, error, run_ended
    """

    def __init__(
        self,
        *,
        session: Session,
        agent_id: str,
        run_id: str,
        s3_bucket: str | None = None,
    ) -> None:
        self.session = session
        self.agent_id = agent_id
        self.run_id = run_id
        self.s3_bucket = s3_bucket or None
        self._buffer: list[dict[str, Any]] = []
        self.event_count = 0

    # ------------------------------------------------------------------
    # Internal: write one event (DB row + buffer append)
    # ------------------------------------------------------------------
    def _write(self, event_type: str, **fields: Any) -> None:
        sequence = self.event_count
        now = datetime.now(timezone.utc)
        turn = fields.get("turn")  # convenience denorm; stays in payload too

        # Truncate payload values to keep rows small. event_type/turn are
        # already columns; everything else lands in payload.
        payload = {k: _truncate(v) for k, v in fields.items() if k != "turn"}

        # Buffer entry: same shape as the row we'll write. Used for the JSONL.
        record = {
            "t": now.isoformat(),
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "sequence": sequence,
            "type": event_type,
            "turn": turn,
            "payload": payload,
        }
        self._buffer.append(record)
        self.event_count = sequence + 1

        # Persist to DB. Any failure is logged and swallowed so the run
        # continues — S3 buffer is the safety net.
        try:
            row = AgentEvent(
                run_id=self.run_id,
                agent_id=self.agent_id,
                sequence=sequence,
                t=now,
                type=event_type,
                turn=turn,
                payload=payload,
            )
            self.session.add(row)
            self.session.commit()
        except Exception:
            logger.exception(
                "AgentAuditLog DB write failed agent=%s run=%s seq=%s type=%s",
                self.agent_id, self.run_id, sequence, event_type,
            )
            try:
                self.session.rollback()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Standard recording API — one method per event type
    # ------------------------------------------------------------------
    def run_started(self, *, model: str, brief: str, bounds: dict[str, Any]) -> None:
        self._write("run_started", model=model, brief=brief, bounds=bounds)

    def turn_started(self, *, turn: int) -> None:
        self._write("turn_started", turn=turn)

    def text(self, *, turn: int, text: str) -> None:
        if not text:
            return
        self._write("text", turn=turn, text=text)

    def tool_use(self, *, turn: int, name: str, id: str, input: dict[str, Any]) -> None:
        self._write("tool_use", turn=turn, name=name, id=id, input=input)

    def tool_result(
        self,
        *,
        turn: int,
        name: str,
        tool_use_id: str,
        result: Any,
        is_error: bool = False,
    ) -> None:
        self._write(
            "tool_result",
            turn=turn,
            name=name,
            tool_use_id=tool_use_id,
            is_error=is_error,
            result=result,
        )

    def server_block(self, *, turn: int, btype: str, payload: dict[str, Any]) -> None:
        """Catch-all for server-side content blocks (server_tool_use,
        web_search_tool_result, web_fetch_tool_result, etc.)."""
        self._write("server_block", turn=turn, block_type=btype, block=payload)

    def turn_complete(
        self,
        *,
        turn: int,
        stop_reason: str,
        usage: dict[str, Any],
        message_id: str | None = None,
        model: str | None = None,
        latency_ms: int | None = None,
        tool_counts: dict[str, int] | None = None,
    ) -> None:
        """Record end-of-turn metadata.

        Required: turn, stop_reason, usage (Anthropic Usage shape).
        Optional but recommended:
          message_id   — Anthropic message id (for cross-reference / support)
          model        — server-pinned model id (may differ from requested)
          latency_ms   — wall-clock for this turn's stream call
          tool_counts  — server-side tool invocations this turn
                         (e.g. {"web_search": 3, "web_fetch": 1}). Used by
                         estimate_server_tool_cost for accurate budget gating.
        """
        self._write(
            "turn_complete",
            turn=turn,
            stop_reason=stop_reason,
            usage=usage,
            message_id=message_id,
            model=model,
            latency_ms=latency_ms,
            tool_counts=tool_counts or {},
        )

    def bound_hit(self, *, bound: str, value: Any) -> None:
        self._write("bound_hit", bound=bound, value=value)

    def error(self, *, where: str, message: str) -> None:
        self._write("error", where=where, message=message)

    def run_ended(self, *, status: str, summary: dict[str, Any]) -> None:
        self._write("run_ended", status=status, summary=summary)

    # ------------------------------------------------------------------
    # Finalisation
    # ------------------------------------------------------------------
    def flush_to_s3(self) -> str | None:
        """Upload the buffered JSONL log to S3. Returns the S3 key, or None
        if no bucket configured / the upload failed.

        Key format: agent-logs/{agent_id}/{YYYY}/{MM}/{DD}/{run_id}.jsonl
        """
        if not self.s3_bucket:
            logger.info(
                "Agent audit %s: no S3 bucket configured; events live in agent_events DB only",
                self.agent_id,
            )
            return None

        try:
            from jeromelu_shared.s3 import get_s3_client
        except Exception:
            logger.exception("Agent audit %s: failed to import S3 client", self.agent_id)
            return None

        body_str = "\n".join(
            json.dumps(rec, default=str, ensure_ascii=False) for rec in self._buffer
        )
        body = body_str.encode("utf-8")

        now = datetime.now(timezone.utc)
        key = f"agent-logs/{self.agent_id}/{now:%Y/%m/%d}/{self.run_id}.jsonl"
        try:
            client = get_s3_client()
            client.put_object(
                Bucket=self.s3_bucket,
                Key=key,
                Body=body,
                ContentType="application/jsonl",
            )
            logger.info(
                "Agent audit %s: uploaded %d events (%d bytes) to s3://%s/%s",
                self.agent_id, self.event_count, len(body), self.s3_bucket, key,
            )
            return key
        except Exception:
            logger.exception(
                "Agent audit %s: S3 upload failed; events still in agent_events DB",
                self.agent_id,
            )
            return None


# ---------------------------------------------------------------------------
# AgentRun helpers — agent-agnostic run-level summary rows
# ---------------------------------------------------------------------------

def record_agent_started(
    session: Session,
    *,
    agent_id: str,
    agent_name: str,
    run_id: str,
    model: str,
    brief: str,
    bounds: dict[str, Any],
) -> None:
    """Insert a 'started' agent_runs row at the top of an agent run.

    Caller is responsible for ensuring `agent_id` is in the AgentRun
    CHECK constraint (extend via migration before adding a new agent).
    """
    row = AgentRun(
        run_id=run_id,
        agent_id=agent_id,
        agent_name=agent_name,
        activity_type="started",
        summary=(
            f"{agent_name} run started — model={model}, "
            f"budget=${bounds.get('max_budget_usd', '?')}"
        ),
        detail_json={
            "model": model,
            "brief_preview": brief[:500],
            "bounds": bounds,
        },
    )
    session.add(row)
    session.commit()


def record_agent_ended(
    session: Session,
    *,
    agent_id: str,
    agent_name: str,
    run_id: str,
    status: str,
    summary_text: str,
    detail: dict[str, Any],
) -> None:
    """Insert a 'completed' or 'failed' agent_runs row at run end.

    `status` is the agent's logical status; maps to AgentRun.activity_type:
      'completed' | 'aborted' -> 'completed'  (status preserved in detail_json)
      'failed'                -> 'failed'
    """
    activity_type = "failed" if status == "failed" else "completed"
    enriched = dict(detail)
    enriched["status"] = status

    row = AgentRun(
        run_id=run_id,
        agent_id=agent_id,
        agent_name=agent_name,
        activity_type=activity_type,
        summary=summary_text,
        detail_json=enriched,
    )
    session.add(row)
    session.commit()

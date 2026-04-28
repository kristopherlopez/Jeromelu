"""Scout's multi-turn streaming agent loop.

Manual implementation — no high-level helper exists for autonomous agent
loops with streaming + custom tools in the Anthropic SDK today. We:
  1. Send the messages with stream()
  2. Print text deltas live (the theatre)
  3. After streaming completes, inspect content blocks
  4. Execute any client-side tool_use blocks
  5. Feed tool_result blocks back; loop until end_turn or a bound trips
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from anthropic import Anthropic
from sqlalchemy.orm import Session

from jeromelu_shared.agent_audit import (
    AgentAuditLog,
    AgentBounds,
    estimate_token_cost,
    make_run_id,
    record_agent_ended,
    record_agent_started,
)
from jeromelu_shared.config import settings

from app.scout.prompt import SCOUT_SYSTEM_PROMPT, build_user_brief
from app.scout.tools import CUSTOM_TOOL_HANDLERS, all_tools, summarise_known_sources

# Scout's identity for the standard agent_audit machinery
AGENT_ID = "scout"
AGENT_NAME = "Scout"

logger = logging.getLogger(__name__)


# Bounds + cost estimation come from the shared agent_audit module so all
# agents share the same bounds shape and pricing table. Back-compat alias for
# anything importing ScoutBounds from this module (notably cli.py).
ScoutBounds = AgentBounds


@dataclass
class ScoutRunResult:
    run_id: str
    model: str
    started_at: datetime
    ended_at: datetime
    turns_used: int
    tool_calls: int
    candidates_filed: int
    duplicates_skipped: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    estimated_cost_usd: float
    stop_reason: str
    status: str                             # 'completed' | 'aborted' | 'failed'
    notes: list[str] = field(default_factory=list)


def _content_block_for_send(block: Any) -> dict[str, Any]:
    """Serialise an SDK response content block to the shape the API accepts on
    the round-trip. The SDK's `model_dump()` includes fields it auto-populates
    on parse (notably a stray `text` on `server_tool_use`,
    `web_search_tool_result`, `web_fetch_tool_result`, etc.) that the API
    rejects on send. Strip `text` from anything that isn't an actual text block.
    """
    payload = block.model_dump()
    if payload.get("type") != "text":
        payload.pop("text", None)
    return payload


def _summarise_tool_input(name: str, payload: dict[str, Any]) -> str:
    """Compact one-line summary of a tool call for console theatre."""
    if name == "web_search":
        return f"web_search({payload.get('query', '?')!r})"
    if name == "web_fetch":
        return f"web_fetch({payload.get('url', '?')})"
    if name == "dedupe_check":
        return f"dedupe_check({payload.get('kind', '?')}, {payload.get('url', '?')})"
    if name == "dedupe_check_bulk":
        items = payload.get("items", [])
        return f"dedupe_check_bulk({len(items)} items)"
    if name == "persist_candidate":
        return (
            f"persist_candidate({payload.get('kind', '?')} | "
            f"{payload.get('title', '')[:60]} | score={payload.get('score', '?')})"
        )
    return f"{name}({list(payload.keys())})"


def run_scout(
    session: Session,
    *,
    brief: str | None = None,
    model: str = "claude-sonnet-4-6",
    bounds: AgentBounds | None = None,
    dry_run: bool = False,
) -> ScoutRunResult:
    """Run one Scout sweep. Synchronous — call from a CLI or background task."""
    bounds = bounds or AgentBounds()
    run_id = make_run_id(AGENT_ID)
    start_ts = time.time()
    started_at = datetime.now(timezone.utc)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in environment")

    client = Anthropic(api_key=api_key)

    # Standard agent audit log: each event lands in agent_events (queryable
    # live) and is buffered for a JSONL bundle uploaded to S3 at run end.
    audit = AgentAuditLog(
        session=session,
        agent_id=AGENT_ID,
        run_id=run_id,
        s3_bucket=settings.s3_agent_logs_bucket,
    )

    system = [
        {
            "type": "text",
            "text": SCOUT_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    tools = all_tools()

    # Per-run dynamic context: the known set goes in the user message (NOT the
    # system prompt) so the system-prompt cache stays warm across runs.
    known_set = summarise_known_sources(session)
    user_brief = f"{known_set}\n\n---\n\n{build_user_brief(brief)}"
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": user_brief}
    ]

    turns = 0
    tool_calls = 0
    candidates_filed = 0
    duplicates_skipped = 0
    in_tok = out_tok = cache_r = cache_w = 0
    stop_reason = "unknown"
    status = "completed"
    notes: list[str] = []

    print(f"\n=== Scout run {run_id} (model={model}, dry_run={dry_run}) ===\n")
    print(f"[brief]\n{user_brief}\n")

    # Run-level audit start: crew_activity DB row + JSONL log header.
    bounds_dict = asdict(bounds)
    record_agent_started(
        session,
        agent_id=AGENT_ID,
        agent_name=AGENT_NAME,
        run_id=run_id,
        model=model,
        brief=user_brief,
        bounds=bounds_dict,
    )
    audit.run_started(model=model, brief=user_brief, bounds=bounds_dict)

    while turns < bounds.max_turns:
        turns += 1
        print(f"\n--- turn {turns} ---")
        audit.turn_started(turn=turns)

        try:
            with client.messages.stream(
                model=model,
                max_tokens=4096,
                system=system,
                tools=tools,
                messages=messages,
            ) as stream:
                # Stream text deltas to console for live theatre.
                # Tool-call summaries get printed after the message resolves
                # (we only know the full input once content_block_stop arrives).
                for event in stream:
                    if event.type == "content_block_delta":
                        delta_type = getattr(event.delta, "type", None)
                        if delta_type == "text_delta":
                            print(event.delta.text, end="", flush=True)
                final = stream.get_final_message()
                print()  # newline after any streamed text
        except Exception as e:
            status = "failed"
            notes.append(f"turn {turns} api error: {e}")
            audit.error(where=f"turn {turns} api", message=str(e))
            logger.exception("Scout API error")
            break

        # Track usage
        u = final.usage
        in_tok += u.input_tokens
        out_tok += u.output_tokens
        cache_r += getattr(u, "cache_read_input_tokens", 0) or 0
        cache_w += getattr(u, "cache_creation_input_tokens", 0) or 0
        stop_reason = final.stop_reason or "unknown"

        # Append assistant message verbatim, stripping fields the SDK adds on
        # parse but the API rejects on the round-trip.
        messages.append(
            {
                "role": "assistant",
                "content": [_content_block_for_send(block) for block in final.content],
            }
        )

        # Walk every content block for the audit trail; only client-side
        # tool_use blocks need a tool_result fed back next turn.
        tool_results: list[dict[str, Any]] = []
        for block in final.content:
            btype = getattr(block, "type", "unknown")

            if btype == "text":
                audit.text(turn=turns, text=getattr(block, "text", "") or "")
                continue

            if btype != "tool_use":
                # server_tool_use, web_search_tool_result, web_fetch_tool_result, etc.
                # All run on Anthropic's side — log the block for forensics.
                try:
                    payload = block.model_dump()
                except Exception:
                    payload = {"repr": repr(block)}
                audit.server_block(turn=turns, btype=btype, payload=payload)
                continue

            # Client-side tool call
            name = block.name
            tool_calls += 1

            print(f"[tool] {_summarise_tool_input(name, block.input)}")
            audit.tool_use(
                turn=turns, name=name, id=block.id, input=dict(block.input)
            )

            if name not in CUSTOM_TOOL_HANDLERS:
                continue

            handler = CUSTOM_TOOL_HANDLERS[name]
            try:
                if dry_run and name == "persist_candidate":
                    result = {
                        "ok": True,
                        "status": "dry-run",
                        "would_have_filed": block.input.get("title"),
                    }
                else:
                    kwargs = dict(block.input)
                    if name == "persist_candidate":
                        kwargs["run_id"] = run_id
                    result = handler(session, **kwargs)

                if name == "persist_candidate" and isinstance(result, dict):
                    if result.get("status") == "filed":
                        candidates_filed += 1
                    elif result.get("status") == "duplicate":
                        duplicates_skipped += 1

                print(f"[tool-result] {json.dumps(result, default=str)[:300]}")
                audit.tool_result(
                    turn=turns,
                    name=name,
                    tool_use_id=block.id,
                    result=result,
                    is_error=False,
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, default=str),
                    }
                )
            except Exception as e:
                logger.exception("Custom tool %s failed", name)
                notes.append(f"tool {name} failed: {e}")
                audit.tool_result(
                    turn=turns,
                    name=name,
                    tool_use_id=block.id,
                    result={"error": str(e)},
                    is_error=True,
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"error": str(e)}),
                        "is_error": True,
                    }
                )

        # Per-turn audit summary
        audit.turn_complete(
            turn=turns,
            stop_reason=stop_reason,
            usage={
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
                "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
                "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
            },
        )

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        # Stop conditions
        if stop_reason == "end_turn":
            break
        if stop_reason == "max_tokens":
            notes.append(f"turn {turns} hit max_tokens; stopping")
            audit.bound_hit(bound="max_tokens", value=turns)
            status = "aborted"
            break

        # Bounds
        elapsed = time.time() - start_ts
        cost_so_far = estimate_token_cost(model, in_tok, out_tok, cache_r, cache_w)

        if elapsed > bounds.max_wall_seconds:
            notes.append(f"wall-clock bound hit at {elapsed:.0f}s")
            audit.bound_hit(bound="max_wall_seconds", value=round(elapsed, 1))
            status = "aborted"
            break
        if tool_calls >= bounds.max_tool_calls:
            notes.append(f"max_tool_calls ({bounds.max_tool_calls}) hit")
            audit.bound_hit(bound="max_tool_calls", value=tool_calls)
            status = "aborted"
            break
        if cost_so_far >= bounds.max_budget_usd:
            notes.append(f"budget ${cost_so_far:.3f} >= cap ${bounds.max_budget_usd}")
            audit.bound_hit(bound="max_budget_usd", value=round(cost_so_far, 4))
            status = "aborted"
            break

    ended_at = datetime.now(timezone.utc)
    final_cost = estimate_token_cost(model, in_tok, out_tok, cache_r, cache_w)

    result = ScoutRunResult(
        run_id=run_id,
        model=model,
        started_at=started_at,
        ended_at=ended_at,
        turns_used=turns,
        tool_calls=tool_calls,
        candidates_filed=candidates_filed,
        duplicates_skipped=duplicates_skipped,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cache_read_tokens=cache_r,
        cache_write_tokens=cache_w,
        estimated_cost_usd=round(final_cost, 4),
        stop_reason=stop_reason,
        status=status,
        notes=notes,
    )

    summary_dict = {
        "turns_used": turns,
        "tool_calls": tool_calls,
        "candidates_filed": candidates_filed,
        "duplicates_skipped": duplicates_skipped,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "cache_read_tokens": cache_r,
        "cache_write_tokens": cache_w,
        "estimated_cost_usd": round(final_cost, 4),
        "stop_reason": stop_reason,
        "notes": notes,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
    }

    audit.run_ended(status=status, summary=summary_dict)
    s3_log_key = audit.flush_to_s3()

    summary_text = (
        f"Scout run {status} — {candidates_filed} filed, {duplicates_skipped} dupes, "
        f"{turns} turns, {tool_calls} tool calls, ${final_cost:.3f}"
    )
    record_agent_ended(
        session,
        agent_id=AGENT_ID,
        agent_name=AGENT_NAME,
        run_id=run_id,
        status=status,
        summary_text=summary_text,
        detail={
            **summary_dict,
            "model": model,
            "s3_log_key": s3_log_key,
            "s3_log_bucket": settings.s3_agent_logs_bucket if s3_log_key else None,
            "agent_events_count": audit.event_count,
        },
    )

    print(f"\n=== Scout run done ===")
    print(f"  status: {status}")
    print(f"  turns: {turns}, tool_calls: {tool_calls}")
    print(f"  filed: {candidates_filed}, duplicates: {duplicates_skipped}")
    print(f"  tokens: in={in_tok} out={out_tok} cache_read={cache_r} cache_write={cache_w}")
    print(f"  est. cost: ${final_cost:.4f}")
    print(f"  events: {audit.event_count} rows in agent_events (run_id={run_id})")
    if s3_log_key:
        print(f"  bundle: s3://{settings.s3_agent_logs_bucket}/{s3_log_key}")
    if notes:
        print(f"  notes: {notes}")
    print()

    return result

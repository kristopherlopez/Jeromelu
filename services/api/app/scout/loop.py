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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from anthropic import Anthropic
from sqlalchemy.orm import Session

from app.scout.prompt import SCOUT_SYSTEM_PROMPT, build_user_brief
from app.scout.tools import CUSTOM_TOOL_HANDLERS, all_tools

logger = logging.getLogger(__name__)


# Pricing in USD per million tokens. Verify against current Anthropic pricing.
# Used only for the budget gate — rough is fine.
_PRICING = {
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
}


@dataclass
class ScoutBounds:
    max_turns: int = 20
    max_tool_calls: int = 60
    max_wall_seconds: int = 900            # 15 min
    max_budget_usd: float = 3.00


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


def _estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_write_tokens: int,
) -> float:
    p = _PRICING.get(model, _PRICING["claude-sonnet-4-6"])
    return (
        (input_tokens / 1_000_000) * p["input"]
        + (output_tokens / 1_000_000) * p["output"]
        + (cache_read_tokens / 1_000_000) * p["cache_read"]
        + (cache_write_tokens / 1_000_000) * p["cache_write_5m"]
    )


def _summarise_tool_input(name: str, payload: dict[str, Any]) -> str:
    """Compact one-line summary of a tool call for console theatre."""
    if name == "web_search":
        return f"web_search({payload.get('query', '?')!r})"
    if name == "web_fetch":
        return f"web_fetch({payload.get('url', '?')})"
    if name == "dedupe_check":
        return f"dedupe_check({payload.get('kind', '?')}, {payload.get('url', '?')})"
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
    bounds: ScoutBounds | None = None,
    dry_run: bool = False,
) -> ScoutRunResult:
    """Run one Scout sweep. Synchronous — call from a CLI or background task."""
    bounds = bounds or ScoutBounds()
    run_id = f"scout-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}-{uuid4().hex[:6]}"
    start_ts = time.time()
    started_at = datetime.now(timezone.utc)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in environment")

    client = Anthropic(api_key=api_key)

    system = [
        {
            "type": "text",
            "text": SCOUT_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    tools = all_tools()
    messages: list[dict[str, Any]] = [
        {"role": "user", "content": build_user_brief(brief)}
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
    print(f"[brief] {build_user_brief(brief)}\n")

    while turns < bounds.max_turns:
        turns += 1
        print(f"\n--- turn {turns} ---")

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
            logger.exception("Scout API error")
            break

        # Track usage
        u = final.usage
        in_tok += u.input_tokens
        out_tok += u.output_tokens
        cache_r += getattr(u, "cache_read_input_tokens", 0) or 0
        cache_w += getattr(u, "cache_creation_input_tokens", 0) or 0
        stop_reason = final.stop_reason or "unknown"

        # Append assistant message verbatim (Anthropic SDK content blocks)
        messages.append(
            {
                "role": "assistant",
                "content": [block.model_dump() for block in final.content],
            }
        )

        # Walk the content for client-side tool_use blocks
        tool_results: list[dict[str, Any]] = []
        for block in final.content:
            if block.type != "tool_use":
                continue
            name = block.name
            tool_calls += 1

            print(f"[tool] {_summarise_tool_input(name, block.input)}")

            # Built-in tools (web_search, web_fetch) execute server-side; we don't
            # see them as tool_use blocks — the API returns server_tool_use /
            # web_search_tool_result blocks and continues. Only our custom tools
            # need handling here.
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
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"error": str(e)}),
                        "is_error": True,
                    }
                )

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        # Stop conditions
        if stop_reason == "end_turn":
            break
        if stop_reason == "max_tokens":
            notes.append(f"turn {turns} hit max_tokens; stopping")
            status = "aborted"
            break

        # Bounds
        elapsed = time.time() - start_ts
        cost_so_far = _estimate_cost(model, in_tok, out_tok, cache_r, cache_w)

        if elapsed > bounds.max_wall_seconds:
            notes.append(f"wall-clock bound hit at {elapsed:.0f}s")
            status = "aborted"
            break
        if tool_calls >= bounds.max_tool_calls:
            notes.append(f"max_tool_calls ({bounds.max_tool_calls}) hit")
            status = "aborted"
            break
        if cost_so_far >= bounds.max_budget_usd:
            notes.append(f"budget ${cost_so_far:.3f} >= cap ${bounds.max_budget_usd}")
            status = "aborted"
            break

    ended_at = datetime.now(timezone.utc)
    final_cost = _estimate_cost(model, in_tok, out_tok, cache_r, cache_w)

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

    print(f"\n=== Scout run done ===")
    print(f"  status: {status}")
    print(f"  turns: {turns}, tool_calls: {tool_calls}")
    print(f"  filed: {candidates_filed}, duplicates: {duplicates_skipped}")
    print(f"  tokens: in={in_tok} out={out_tok} cache_read={cache_r} cache_write={cache_w}")
    print(f"  est. cost: ${final_cost:.4f}")
    if notes:
        print(f"  notes: {notes}")
    print()

    return result

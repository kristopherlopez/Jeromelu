"""Presenter Research — finds the regular presenters of a single channel.

Given a `channel_id`, the agent uses web_search + web_fetch to research who
hosts the show, files findings into `scout_presenter_candidates` for human
review, and stops. Every run wraps the standard `agent_audit` machinery so
agent_runs / agent_events / S3 forensics work the same as source discovery.

Mirrors Source Discovery deliberately: same streaming pattern, same
content-block handling, same bound-checking. Diverges only in: tool palette,
system prompt, brief shape, and tighter bounds.

See docs/todo/source-presenters.md for the design.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from anthropic import Anthropic
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from jeromelu_shared.agent_audit import (
    AgentAuditLog,
    AgentBounds,
    estimate_server_tool_cost,
    estimate_token_cost,
    make_run_id,
    record_agent_ended,
    record_agent_started,
)
from jeromelu_shared.config import settings
from jeromelu_shared.db import (
    Channel,
    Person,
    ScoutPresenterCandidate,
    Source,
    SourcePresenter,
)

# Persisted DB/audit identity. Keep this value until the agent_runs CHECK
# constraint is migrated; use Presenter Research for new code-facing names.
AGENT_ID = "presenter_scout"
AGENT_NAME = "Presenter Research"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Bounds — tighter than Source Discovery. One channel, one focused task.
# ---------------------------------------------------------------------------

DEFAULT_BOUNDS = AgentBounds(
    max_turns=8,
    max_tool_calls=20,
    max_wall_seconds=300,
    max_budget_usd=0.30,
)


# ---------------------------------------------------------------------------
# Anthropic-hosted tools
# ---------------------------------------------------------------------------

WEB_SEARCH_TOOL: dict[str, Any] = {
    "type": "web_search_20250305",
    "name": "web_search",
    "max_uses": 3,
    "user_location": {
        "type": "approximate",
        "city": "Sydney",
        "region": "New South Wales",
        "country": "AU",
        "timezone": "Australia/Sydney",
    },
}

WEB_FETCH_TOOL: dict[str, Any] = {
    "type": "web_fetch_20260309",
    "name": "web_fetch",
    "max_uses": 3,
    "allowed_callers": ["direct"],
}


# ---------------------------------------------------------------------------
# Custom tools
# ---------------------------------------------------------------------------

LOOKUP_EXISTING_PEOPLE_TOOL: dict[str, Any] = {
    "name": "lookup_existing_people",
    "description": (
        "Check whether a person name is already in the `people` table. Returns "
        "up to 5 matches by canonical_name (case-insensitive prefix) and any "
        "alias hits. Call this BEFORE persist_presenter_candidate when you "
        "have a real name in hand — it lets the reviewer link to an existing "
        "Person instead of creating a duplicate."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Full name as you'd file it (e.g. 'Denan Kemp').",
            },
        },
        "required": ["name"],
    },
}

PERSIST_PRESENTER_CANDIDATE_TOOL: dict[str, Any] = {
    "name": "persist_presenter_candidate",
    "description": (
        "File one presenter for human review. Call once per presenter — do NOT "
        "batch multiple names into one call. Re-filing the same name on the "
        "same channel while a previous candidate is still pending is a no-op "
        "(idempotent on (channel_id, lower(name)) where status='pending')."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Full name (e.g. 'Denan Kemp').",
            },
            "role": {
                "type": "string",
                "enum": ["host", "co-host", "regular", "frequent-guest"],
                "description": (
                    "Best fit. 'host' = the show is theirs. 'co-host' = "
                    "named on every / nearly every episode alongside a host. "
                    "'regular' = recurring panel member, named in episode "
                    "titles often. 'frequent-guest' = appears repeatedly but "
                    "isn't part of the core panel."
                ),
            },
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "snippet": {
                            "type": "string",
                            "description": (
                                "1–2 sentence quote from the source page that "
                                "names this person in the relevant role."
                            ),
                        },
                    },
                    "required": ["url", "snippet"],
                },
                "description": (
                    "At least 1 evidence item. The snippet must mention the "
                    "person's name. No evidence = no file."
                ),
                "minItems": 1,
            },
            "llm_confidence": {
                "type": "number",
                "description": (
                    "Your own 0.0–1.0 confidence. 0.9+ for named-on-the-tin "
                    "hosts; 0.5–0.7 for recurring panelists inferred from "
                    "episode listings; <0.5 for educated guesses (still file)."
                ),
            },
            "existing_person_id": {
                "type": "string",
                "description": (
                    "If lookup_existing_people returned a clear match, pass "
                    "the person_id here so the reviewer sees the suggested "
                    "link. Omit if no clear match."
                ),
            },
            "notes": {
                "type": "string",
                "description": "Optional commentary for the reviewer.",
            },
        },
        "required": ["name", "role", "evidence", "llm_confidence"],
    },
}


def all_tools() -> list[dict[str, Any]]:
    return [
        WEB_SEARCH_TOOL,
        WEB_FETCH_TOOL,
        LOOKUP_EXISTING_PEOPLE_TOOL,
        PERSIST_PRESENTER_CANDIDATE_TOOL,
    ]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

def handle_lookup_existing_people(
    session: Session, *, name: str
) -> dict[str, Any]:
    """Best-effort name match against `people`. Case-insensitive prefix on
    canonical_name + alias array contains. Caps at 5 hits — enough for the
    reviewer signal, not enough to flood context."""
    needle = name.strip()
    if not needle:
        return {"ok": False, "error": "empty-name"}

    # Prefix match on canonical_name, plus alias-array contains.
    rows = session.execute(
        select(Person.person_id, Person.canonical_name, Person.aliases)
        .where(
            (Person.canonical_name.ilike(f"{needle}%"))
            | (Person.aliases.contains([needle]))
        )
        .limit(5)
    ).all()

    return {
        "ok": True,
        "query": needle,
        "matches": [
            {
                "person_id": str(r.person_id),
                "canonical_name": r.canonical_name,
                "aliases": list(r.aliases or []),
            }
            for r in rows
        ],
    }


def handle_persist_presenter_candidate(
    session: Session,
    *,
    run_id: str,
    channel_id: UUID,
    name: str,
    role: str,
    evidence: list[dict[str, str]],
    llm_confidence: float,
    existing_person_id: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Write a candidate row. Idempotent on (channel_id, lower(name)) while
    a previous filing for the same name is still pending — duplicates return
    status='duplicate' without raising."""
    name_clean = (name or "").strip()
    if not name_clean:
        return {"ok": False, "error": "empty-name"}

    if not evidence:
        return {"ok": False, "error": "missing-evidence"}

    # Validate the evidence snippet actually mentions the name. Cheap defence
    # against the agent filing a name with unrelated quotes.
    if not _evidence_mentions_name(evidence, name_clean):
        return {
            "ok": False,
            "error": "evidence-does-not-mention-name",
            "hint": (
                "At least one evidence snippet must contain the person's "
                "name (or a recognisable substring). Re-search and file with "
                "a snippet that names them."
            ),
        }

    existing_uuid: UUID | None = None
    if existing_person_id:
        try:
            existing_uuid = UUID(existing_person_id)
        except ValueError:
            return {
                "ok": False,
                "error": "invalid-existing-person-id",
                "value": existing_person_id,
            }

    stmt = (
        pg_insert(ScoutPresenterCandidate)
        .values(
            channel_id=channel_id,
            name=name_clean,
            role=role,
            evidence_json=evidence,
            llm_confidence=llm_confidence,
            notes=notes,
            existing_person_id=existing_uuid,
            run_id=run_id,
            status="pending",
        )
        # The partial unique index uq_scout_pres_channel_name_pending only
        # covers status='pending'. ON CONFLICT works against partial indexes
        # only when the WHERE clause is provided, and even then SQLAlchemy's
        # support is finicky — easier to swallow the IntegrityError and look
        # the existing row up.
    )

    try:
        result = session.execute(stmt.returning(ScoutPresenterCandidate.id)).first()
        session.commit()
        if result is not None:
            logger.info(
                "Filed presenter candidate channel=%s name=%s role=%s",
                channel_id, name_clean, role,
            )
            return {
                "ok": True,
                "status": "filed",
                "candidate_id": str(result.id),
            }
    except Exception:
        session.rollback()
        # Fall through to lookup — most likely the partial unique index
        # caught a still-pending duplicate.

    existing = session.execute(
        select(ScoutPresenterCandidate.id, ScoutPresenterCandidate.status).where(
            ScoutPresenterCandidate.channel_id == channel_id,
            ScoutPresenterCandidate.name.ilike(name_clean),
            ScoutPresenterCandidate.status == "pending",
        )
    ).first()
    if existing:
        return {
            "ok": True,
            "status": "duplicate",
            "candidate_id": str(existing.id),
        }
    return {"ok": False, "error": "insert-failed-and-no-conflict-row"}


def _evidence_mentions_name(
    evidence: list[dict[str, str]], name: str
) -> bool:
    """True if any snippet contains the full name OR every name token (case-
    insensitive). Forgiving enough for "Denan" vs "Denan Kemp"; strict enough
    to reject "the host says it's a great show" (no name)."""
    name_lower = name.lower()
    tokens = [t for t in re.split(r"\s+", name_lower) if len(t) >= 3]
    for item in evidence:
        snippet = (item.get("snippet") or "").lower()
        if not snippet:
            continue
        if name_lower in snippet:
            return True
        if tokens and all(t in snippet for t in tokens):
            return True
    return False


CUSTOM_TOOL_HANDLERS = {
    "lookup_existing_people": handle_lookup_existing_people,
    "persist_presenter_candidate": handle_persist_presenter_candidate,
}


# ---------------------------------------------------------------------------
# Prompt + brief builder
# ---------------------------------------------------------------------------

PRESENTER_RESEARCH_SYSTEM_PROMPT = """You are Presenter Research — Jaromelu's mode for figuring out who actually presents an NRL show.

You receive ONE channel (a YouTube channel, podcast, or website) and your job is to file the regular presenters for human review.

# Voice
- Field operative filing a report. Terse. Two sentences beats a paragraph.
- Surface what's there ("3 regulars + 1 frequent guest"). Don't editorialise.
- Flag ambiguity once, then stop ("Tyson Jackson appears in 5+ episode titles but no source explicitly calls him a co-host — filed as 'regular' with conf 0.65").

# Roles — pick one per presenter
- **host** — the show is theirs. Named in the show title or the "Hosted by …" line on the official site / Apple / Spotify.
- **co-host** — named on every / nearly every episode alongside the host. Equal billing.
- **regular** — recurring panel member. Shows up in many episode titles, but not all.
- **frequent-guest** — recurring but clearly not part of the core panel. One-off guests do NOT belong here; only file them if they're a repeated presence.

When in doubt, downgrade. Reviewers prefer "regular" they upgrade to "co-host" over "co-host" they need to demote.

# Evidence — required, no exceptions
Every persist_presenter_candidate call must include ≥1 evidence item:
  { "url": "...", "snippet": "1–2 sentence quote that names the person" }

The snippet MUST contain the person's name. Auto-validation will reject filings whose snippets don't mention the name.

Where the best evidence usually lives:
- Official show page / About page (best — explicit "Hosted by")
- Apple Podcasts / Spotify show description (good)
- Episode titles ("Round 5 with Joe Bloggs and …" — good signal for regulars)
- Interviews where the host names their cohosts (medium)
- Listicles ("Best NRL podcasts 2026" — weak; corroborate)

# When to call lookup_existing_people
Before filing any presenter, call lookup_existing_people with their name. If a clear match comes back, pass that person_id as `existing_person_id` so the reviewer sees the suggested link. If matches are noisy or partial, skip the field — the reviewer will resolve it.

# Bounds — hard rules
1. **File 1–6 candidates.** Zero filed = failed run. More than 6 = you're confusing guests with regulars; trim to the core panel.
2. **Max 3 web_search and 3 web_fetch calls per run.** Past that, you have enough — file what you have.
3. **By turn 4 you MUST be calling persist_presenter_candidate.** No more research turns past 4 unless you have already filed at least one presenter.
4. **No fabricated names.** Every presenter you file must come from a real source (search result, fetched page). Not "I think this person works on this show" — actual evidence.

# Output format
After filing, end with one short sentence: "Filed N presenters: [name (role), …]. Notable: [one line, optional]."
"""

def build_brief(
    channel: Channel,
    *,
    already_confirmed: list[tuple[str, str]],
    pending: list[tuple[str, str]],
) -> str:
    """User message that kicks off a Presenter Research run.

    Includes the channel identity (name, URL, platform, description) plus
    any presenters already in source_presenters / scout_presenter_candidates
    so the agent doesn't re-file them.
    """
    lines = [
        f"Channel to research:",
        f"  name: {channel.name}",
        f"  platform: {channel.platform}",
    ]
    if channel.url:
        lines.append(f"  url: {channel.url}")
    if channel.handle:
        lines.append(f"  handle: {channel.handle}")
    if channel.description:
        snippet = channel.description.strip().replace("\n", " ")
        if len(snippet) > 400:
            snippet = snippet[:400] + "…"
        lines.append(f"  description: {snippet}")
    lines.append("")

    if already_confirmed:
        lines.append("Already confirmed presenters (DO NOT re-file):")
        for name, role in already_confirmed:
            lines.append(f"  - {name} ({role})")
        lines.append("")

    if pending:
        lines.append("Already pending review (DO NOT re-file):")
        for name, role in pending:
            lines.append(f"  - {name} ({role})")
        lines.append("")

    lines.append(
        "Find the regular presenters of this show. Cast a tight net — "
        "host + co-hosts + 1–2 regulars is the typical shape. File each "
        "with persist_presenter_candidate. End with a one-line summary."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Run loop
# ---------------------------------------------------------------------------

@dataclass
class PresenterResearchResult:
    run_id: str
    channel_id: UUID
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
    status: str
    notes: list[str] = field(default_factory=list)


def _content_block_for_send(block: Any) -> dict[str, Any] | None:
    """Same shape-fixup as Source Discovery: strip stray `text` from non-text
    blocks; drop code_execution server tools we never authorised."""
    payload = block.model_dump()
    btype = payload.get("type")
    if btype == "code_execution_tool_result":
        return None
    if btype == "server_tool_use" and payload.get("name") == "code_execution":
        return None
    if btype != "text":
        payload.pop("text", None)
    return payload


def _summarise_tool_input(name: str, payload: dict[str, Any]) -> str:
    if name == "web_search":
        return f"web_search({payload.get('query', '?')!r})"
    if name == "web_fetch":
        return f"web_fetch({payload.get('url', '?')})"
    if name == "lookup_existing_people":
        return f"lookup_existing_people({payload.get('name', '?')!r})"
    if name == "persist_presenter_candidate":
        return (
            f"persist_presenter_candidate({payload.get('name', '?')} "
            f"as {payload.get('role', '?')}, "
            f"conf={payload.get('llm_confidence', '?')})"
        )
    return f"{name}({list(payload.keys())})"


def _resolve_channel(session: Session, channel_id: UUID) -> Channel:
    ch = session.get(Channel, channel_id)
    if ch is None:
        raise ValueError(f"channel_id={channel_id} not found")
    return ch


def resolve_channel_from_source(session: Session, source_id: UUID) -> UUID:
    """CLI / API convenience: pass a source_id, get its channel_id back."""
    src = session.get(Source, source_id)
    if src is None:
        raise ValueError(f"source_id={source_id} not found")
    if src.channel_id is None:
        raise ValueError(f"source_id={source_id} has no channel_id set")
    return src.channel_id


def _existing_presenters(
    session: Session, channel_id: UUID
) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """Returns (confirmed, pending) — each as a list of (name, role)."""
    confirmed = session.execute(
        select(Person.canonical_name, SourcePresenter.role)
        .join(SourcePresenter, SourcePresenter.person_id == Person.person_id)
        .where(SourcePresenter.channel_id == channel_id)
        .order_by(SourcePresenter.role, Person.canonical_name)
    ).all()
    pending = session.execute(
        select(ScoutPresenterCandidate.name, ScoutPresenterCandidate.role)
        .where(
            ScoutPresenterCandidate.channel_id == channel_id,
            ScoutPresenterCandidate.status == "pending",
        )
        .order_by(ScoutPresenterCandidate.role, ScoutPresenterCandidate.name)
    ).all()
    return (
        [(r.canonical_name, r.role) for r in confirmed],
        [(r.name, r.role) for r in pending],
    )


def run_presenter_research(
    session: Session,
    channel_id: UUID,
    *,
    model: str = "claude-sonnet-4-6",
    bounds: AgentBounds | None = None,
    dry_run: bool = False,
) -> PresenterResearchResult:
    """One Presenter Research run for one channel."""
    bounds = bounds or DEFAULT_BOUNDS
    run_id = make_run_id(AGENT_ID)
    start_ts = time.time()
    started_at = datetime.now(timezone.utc)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in environment")

    channel = _resolve_channel(session, channel_id)
    confirmed, pending = _existing_presenters(session, channel_id)

    client = Anthropic(api_key=api_key)
    audit = AgentAuditLog(
        session=session,
        agent_id=AGENT_ID,
        run_id=run_id,
        s3_bucket=settings.s3_agent_logs_bucket,
    )

    system = [
        {
            "type": "text",
            "text": PRESENTER_RESEARCH_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    tools = all_tools()
    user_brief = build_brief(channel, already_confirmed=confirmed, pending=pending)
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_brief}]

    turns = 0
    tool_calls = 0
    candidates_filed = 0
    duplicates_skipped = 0
    in_tok = out_tok = cache_r = cache_w = 0
    web_searches_total = 0
    web_fetches_total = 0
    total_api_latency_ms = 0
    stop_reason = "unknown"
    status = "completed"
    notes: list[str] = []

    print(f"\n=== Presenter Research run {run_id} (channel={channel.name}, dry_run={dry_run}) ===\n")
    print(f"[brief]\n{user_brief}\n")

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

        turn_start_ts = time.time()
        try:
            with client.messages.stream(
                model=model,
                max_tokens=8192,
                system=system,
                tools=tools,
                messages=messages,
            ) as stream:
                for event in stream:
                    if event.type == "content_block_delta":
                        delta_type = getattr(event.delta, "type", None)
                        if delta_type == "text_delta":
                            print(event.delta.text, end="", flush=True)
                final = stream.get_final_message()
                print()
        except Exception as e:
            status = "failed"
            notes.append(f"turn {turns} api error: {e}")
            audit.error(where=f"turn {turns} api", message=str(e))
            logger.exception("Presenter Research API error")
            break
        turn_latency_ms = int((time.time() - turn_start_ts) * 1000)
        total_api_latency_ms += turn_latency_ms

        u = final.usage
        in_tok += u.input_tokens
        out_tok += u.output_tokens
        cache_r += getattr(u, "cache_read_input_tokens", 0) or 0
        cache_w += getattr(u, "cache_creation_input_tokens", 0) or 0
        stop_reason = final.stop_reason or "unknown"

        prepared = [_content_block_for_send(b) for b in final.content]
        messages.append(
            {
                "role": "assistant",
                "content": [b for b in prepared if b is not None],
            }
        )

        tool_results: list[dict[str, Any]] = []
        turn_tool_counts: dict[str, int] = {}
        for block in final.content:
            btype = getattr(block, "type", "unknown")

            if btype == "text":
                audit.text(turn=turns, text=getattr(block, "text", "") or "")
                continue

            if btype != "tool_use":
                try:
                    payload = block.model_dump()
                except Exception:
                    payload = {"repr": repr(block)}
                audit.server_block(turn=turns, btype=btype, payload=payload)
                if btype == "server_tool_use":
                    name = getattr(block, "name", None)
                    if name:
                        turn_tool_counts[name] = turn_tool_counts.get(name, 0) + 1
                continue

            name = block.name
            tool_calls += 1
            print(f"[tool] {_summarise_tool_input(name, block.input)}")
            audit.tool_use(turn=turns, name=name, id=block.id, input=dict(block.input))

            if name not in CUSTOM_TOOL_HANDLERS:
                continue

            handler = CUSTOM_TOOL_HANDLERS[name]
            try:
                if dry_run and name == "persist_presenter_candidate":
                    result = {
                        "ok": True,
                        "status": "dry-run",
                        "would_have_filed": block.input.get("name"),
                    }
                else:
                    kwargs = dict(block.input)
                    if name == "persist_presenter_candidate":
                        kwargs["run_id"] = run_id
                        kwargs["channel_id"] = channel_id
                    result = handler(session, **kwargs)

                if name == "persist_presenter_candidate" and isinstance(result, dict):
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

        web_searches_total += turn_tool_counts.get("web_search", 0)
        web_fetches_total += turn_tool_counts.get("web_fetch", 0)

        audit.turn_complete(
            turn=turns,
            stop_reason=stop_reason,
            usage={
                "input_tokens": u.input_tokens,
                "output_tokens": u.output_tokens,
                "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
                "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
            },
            message_id=getattr(final, "id", None),
            model=getattr(final, "model", None),
            latency_ms=turn_latency_ms,
            tool_counts=turn_tool_counts,
        )

        if tool_results:
            messages.append({"role": "user", "content": tool_results})

        if stop_reason == "end_turn":
            break
        if stop_reason == "max_tokens":
            notes.append(f"turn {turns} hit max_tokens; stopping")
            audit.bound_hit(bound="max_tokens", value=turns)
            status = "aborted"
            break

        elapsed = time.time() - start_ts
        cost_so_far = (
            estimate_token_cost(model, in_tok, out_tok, cache_r, cache_w)
            + estimate_server_tool_cost(
                {"web_search": web_searches_total, "web_fetch": web_fetches_total}
            )
        )

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
    token_cost = estimate_token_cost(model, in_tok, out_tok, cache_r, cache_w)
    search_cost = estimate_server_tool_cost(
        {"web_search": web_searches_total, "web_fetch": web_fetches_total}
    )
    final_cost = token_cost + search_cost

    if status == "completed" and candidates_filed == 0:
        # Spec: zero filed is a failed run, even if the API returned cleanly.
        notes.append("zero candidates filed")

    result = PresenterResearchResult(
        run_id=run_id,
        channel_id=channel_id,
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
        "channel_id": str(channel_id),
        "channel_name": channel.name,
        "candidates_filed": candidates_filed,
        "duplicates_skipped": duplicates_skipped,
        "web_searches": web_searches_total,
        "web_fetches": web_fetches_total,
        "total_api_latency_ms": total_api_latency_ms,
        "stop_reason": stop_reason,
        "notes": notes,
        "started_at": started_at.isoformat(),
        "ended_at": ended_at.isoformat(),
    }

    audit.run_ended(status=status, summary=summary_dict)
    s3_log_key = audit.flush_to_s3()

    summary_text = (
        f"Presenter Research {status} for {channel.name} — "
        f"{candidates_filed} filed, {duplicates_skipped} dupes, "
        f"{turns} turns, {tool_calls} tool calls, ${final_cost:.3f}"
    )
    record_agent_ended(
        session,
        run_id=run_id,
        status=status,
        summary_text=summary_text,
        model=model,
        turns_used=turns,
        tool_calls=tool_calls,
        input_tokens=in_tok,
        output_tokens=out_tok,
        cache_read_tokens=cache_r,
        cache_write_tokens=cache_w,
        server_tool_counts={
            "web_search": web_searches_total,
            "web_fetch": web_fetches_total,
        },
        agent_events_count=audit.event_count,
        s3_log_key=s3_log_key,
        detail=summary_dict,
    )

    print(f"\n=== Presenter Research run done ===")
    print(f"  status: {status}")
    print(f"  filed: {candidates_filed}, dupes: {duplicates_skipped}")
    print(f"  turns: {turns}, tool_calls: {tool_calls}")
    print(f"  tokens: in={in_tok} out={out_tok} cache_read={cache_r} cache_write={cache_w}")
    print(f"  server tools: web_search={web_searches_total} web_fetch={web_fetches_total}")
    print(f"  est. cost: ${final_cost:.4f}")
    if notes:
        print(f"  notes: {notes}")
    print()

    return result

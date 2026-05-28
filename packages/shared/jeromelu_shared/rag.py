"""RAG module for Ask Me — retrieves KB entries and generates answers in JeromeLu's voice."""

import logging
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from jeromelu_shared.db import KnowledgeBase, Person, Source
from jeromelu_shared.llm import chat_text, get_embeddings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts per temperature mode
# ---------------------------------------------------------------------------

BASE_PROMPT = """\
You are JeromeLu, an NRL SuperCoach AI analyst. You answer questions about \
NRL SuperCoach strategy: trades, captains, squad structure, player analysis.

Voice rules:
- First person ("I", "I'm", "my"). Short, punchy sentences.
- Opinionated — take a side. Never say "it depends" without then picking one.
- Use SuperCoach jargon naturally: breakeven, PPM, base stats, ceiling, floor, price movement.
- Reference specific data from your knowledge base when available.
- Cite sources naturally ("I saw on KingOfSC...", "via NRLSCTalk...").
- If you don't have info, say so honestly but in character ("That's not in my files yet").
- Do NOT make up stats, scores, or prices. Only use data from the context below.

KNOWLEDGE BASE:
{context}
"""

TEMPERATURE_ADDONS = {
    "straight": "Be helpful and direct. Give clear recommendations with reasoning.",
    "sharp": "Be confident and cutting. Strong opinions. Mock bad takes.",
    "roast": "Be savage. Roast bad decisions. Maximum entertainment value. Still accurate though.",
}


def embed_query(text_input: str) -> list[float]:
    """Embed a single query string."""
    return get_embeddings([text_input])[0]


def retrieve_kb(
    db: Session,
    query_embedding: list[float],
    limit: int = 10,
    kb_types: list[str] | None = None,
) -> list[KnowledgeBase]:
    """Find the most relevant KB entries via cosine similarity."""
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    filters = ["embedding IS NOT NULL", "(expires_at IS NULL OR expires_at > now())"]
    params: dict = {"emb": embedding_str, "lim": limit}

    if kb_types:
        filters.append("kb_type = ANY(:kb_types)")
        params["kb_types"] = kb_types

    where_clause = " AND ".join(filters)

    sql = text(f"""
        SELECT kb_id
        FROM knowledge_base
        WHERE {where_clause}
        ORDER BY embedding <=> cast(:emb AS vector)
        LIMIT :lim
    """)

    rows = db.execute(sql, params).fetchall()
    kb_ids = [row[0] for row in rows]

    if not kb_ids:
        return []

    return db.query(KnowledgeBase).filter(KnowledgeBase.kb_id.in_(kb_ids)).all()


def build_context(kb_entries: list[KnowledgeBase]) -> str:
    """Format KB entries into a context block for the LLM."""
    if not kb_entries:
        return "(No relevant knowledge found)"

    sections = []
    for entry in kb_entries:
        sections.append(f"[{entry.kb_type}] {entry.title}\n{entry.content}")

    return "\n\n---\n\n".join(sections)


def ask_jeromelu(
    db: Session,
    question: str,
    temperature_mode: str = "sharp",
) -> dict:
    """Full RAG pipeline: embed question → retrieve KB → generate answer."""
    # 1. Embed the question
    query_embedding = embed_query(question)

    # 2. Retrieve relevant KB entries
    kb_entries = retrieve_kb(db, query_embedding)

    # 3. Build context
    context = build_context(kb_entries)

    # 4. Build system prompt with temperature
    addon = TEMPERATURE_ADDONS.get(temperature_mode, TEMPERATURE_ADDONS["sharp"])
    system_prompt = BASE_PROMPT.format(context=context) + "\n\n" + addon

    # 5. Map temperature mode to LLM temperature
    temp_map = {"straight": 0.3, "sharp": 0.6, "roast": 0.8}
    llm_temp = temp_map.get(temperature_mode, 0.6)

    # 6. Generate response
    try:
        answer = chat_text(system_prompt, question, temperature=llm_temp)
    except Exception:
        logger.exception("LLM call failed for Ask Me")
        answer = "Something broke. Even I have bad days. Try again."

    # 7. Collect attribution data
    entity_ids: set[uuid.UUID] = set()
    source_claim_ids: set[uuid.UUID] = set()
    kb_entry_ids: list[str] = []

    for entry in kb_entries:
        kb_entry_ids.append(str(entry.kb_id))
        if entry.person_id:
            entity_ids.add(entry.person_id)
        if entry.source_claim_ids:
            source_claim_ids.update(entry.source_claim_ids)

    # Load people for response (KB.person_id only ever points at players today)
    players = []
    if entity_ids:
        for e in db.query(Person).filter(Person.person_id.in_(entity_ids)).all():
            players.append({"entity_id": str(e.person_id), "name": e.canonical_name})

    # Load sources referenced by KB entries
    sources = []
    source_ids_from_meta = set()
    for entry in kb_entries:
        sid = (entry.metadata_json or {}).get("source_id")
        if sid:
            source_ids_from_meta.add(uuid.UUID(sid))

    if source_ids_from_meta:
        for s in db.query(Source).filter(Source.source_id.in_(source_ids_from_meta)).all():
            sources.append(
                {
                    "source_id": str(s.source_id),
                    "title": s.title,
                    "creator_name": s.creator_name,
                }
            )

    return {
        "answer": answer,
        "sources": sources,
        "players": players,
        "kb_entries_used": kb_entry_ids,
    }

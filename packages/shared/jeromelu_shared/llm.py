from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from jeromelu_shared.config import settings

if TYPE_CHECKING:
    # `openai` is a network SDK deliberately excluded from requirements-test.txt
    # so unit-test collection stays lean. It is imported lazily inside the client
    # getters below; this TYPE_CHECKING import keeps the type annotations resolvable
    # for pyright (which installs openai via requirements-dev.txt) without forcing a
    # runtime dependency at import time.
    from openai import OpenAI

logger = logging.getLogger(__name__)

_chat_client: OpenAI | None = None
_embedding_client: OpenAI | None = None

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def get_chat_client() -> OpenAI:
    """Get an OpenAI-compatible client for chat completions (routes via configured provider)."""
    from openai import OpenAI

    global _chat_client
    if _chat_client is None:
        if settings.llm_provider == "openrouter":
            _chat_client = OpenAI(
                api_key=settings.openrouter_api_key,
                base_url=OPENROUTER_BASE_URL,
            )
        else:
            _chat_client = OpenAI(api_key=settings.openai_api_key)
    return _chat_client


def get_embedding_client() -> OpenAI:
    """Get an OpenAI client for embeddings (always OpenAI direct — OpenRouter doesn't support embedding models reliably)."""  # noqa: E501  # single-line docstring
    from openai import OpenAI

    global _embedding_client
    if _embedding_client is None:
        _embedding_client = OpenAI(api_key=settings.openai_api_key)
    return _embedding_client


def chat_json(system_prompt: str, user_prompt: str, model: str | None = None) -> dict:
    """Call chat API and parse the response as JSON."""
    model = model or settings.llm_model
    client = get_chat_client()
    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )
    text = response.choices[0].message.content
    if text is None:
        raise RuntimeError("LLM returned no content for chat_json")
    return json.loads(text)


def chat_text(system_prompt: str, user_prompt: str, model: str | None = None, temperature: float = 0.7) -> str:
    """Call chat API and return raw text."""
    model = model or settings.llm_model
    client = get_chat_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )
    text = response.choices[0].message.content
    if text is None:
        raise RuntimeError("LLM returned no content for chat_text")
    return text


def get_embeddings(texts: list[str], model: str = "text-embedding-3-small") -> list[list[float]]:
    """Get embeddings for a list of texts (always via OpenAI direct)."""
    client = get_embedding_client()
    response = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]

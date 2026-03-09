import json
import logging

from openai import OpenAI

from jeromelu_shared.config import settings

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=settings.openai_api_key)
    return _client


def chat_json(system_prompt: str, user_prompt: str, model: str = "gpt-4o") -> dict:
    """Call OpenAI chat API and parse the response as JSON."""
    client = get_openai_client()
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
    return json.loads(text)


def chat_text(system_prompt: str, user_prompt: str, model: str = "gpt-4o", temperature: float = 0.7) -> str:
    """Call OpenAI chat API and return raw text."""
    client = get_openai_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
    )
    return response.choices[0].message.content


def get_embeddings(texts: list[str], model: str = "text-embedding-3-small") -> list[list[float]]:
    """Get embeddings for a list of texts."""
    client = get_openai_client()
    response = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]

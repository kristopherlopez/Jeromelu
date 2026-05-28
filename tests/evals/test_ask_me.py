"""DeepEval tests for the Ask Me chat feature.

Run with:
    deepeval test run tests/evals/test_ask_me.py

Requires:
    - OPENAI_API_KEY set (for DeepEval's evaluation LLM)
    - DATABASE_URL set (to query the knowledge base)
"""

from pathlib import Path

import pytest
import yaml
from deepeval import assert_test
from deepeval.metrics import (
    AnswerRelevancyMetric,
    FaithfulnessMetric,
    GEval,
    HallucinationMetric,
)
from deepeval.test_case import LLMTestCase
from jeromelu_shared.rag import ask_jeromelu, build_context, embed_query, retrieve_kb

# ---------------------------------------------------------------------------
# Load golden examples
# ---------------------------------------------------------------------------

GOLDEN_PATH = Path(__file__).parent / "golden" / "ask_me_golden.yaml"


def load_golden_examples() -> list[dict]:
    with open(GOLDEN_PATH) as f:
        return yaml.safe_load(f)


GOLDEN_EXAMPLES = load_golden_examples()

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

faithfulness = FaithfulnessMetric(threshold=0.7)
hallucination = HallucinationMetric(threshold=0.7)
relevancy = AnswerRelevancyMetric(threshold=0.7)

nrl_voice = GEval(
    name="NRL SuperCoach Voice",
    criteria=(
        "The response should sound like an opinionated NRL SuperCoach analyst. "
        "It should use first person, be concise, and use SuperCoach jargon "
        "(breakeven, PPM, base stats, ceiling, floor) where appropriate. "
        "It should take a clear stance rather than sitting on the fence."
    ),
    threshold=0.6,
)

no_fabrication = GEval(
    name="No Fabricated Stats",
    criteria=(
        "The response must not fabricate specific statistics, scores, prices, "
        "or breakevens that are not present in the provided context. "
        "If the context lacks data, the response should acknowledge this "
        "rather than making up numbers."
    ),
    threshold=0.8,
)

# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db():
    from jeromelu_shared.db import SessionLocal

    session = SessionLocal()
    yield session
    session.close()


@pytest.mark.parametrize(
    "example",
    GOLDEN_EXAMPLES,
    ids=[e["question"][:40] for e in GOLDEN_EXAMPLES],
)
def test_ask_me_faithfulness(example: dict, db):
    """Test that answers are grounded in KB context."""
    result = ask_jeromelu(db, example["question"], example.get("temperature", "sharp"))

    # Retrieve the context that was used
    query_emb = embed_query(example["question"])
    kb_types = [example["context_type"]] if example.get("context_type") else None
    kb_entries = retrieve_kb(db, query_emb, kb_types=kb_types)
    context = build_context(kb_entries)

    test_case = LLMTestCase(
        input=example["question"],
        actual_output=result["answer"],
        retrieval_context=[context],
    )

    assert_test(test_case, [faithfulness])


@pytest.mark.parametrize(
    "example",
    GOLDEN_EXAMPLES,
    ids=[e["question"][:40] for e in GOLDEN_EXAMPLES],
)
def test_ask_me_relevancy(example: dict, db):
    """Test that answers actually address the question."""
    result = ask_jeromelu(db, example["question"], example.get("temperature", "sharp"))

    test_case = LLMTestCase(
        input=example["question"],
        actual_output=result["answer"],
    )

    assert_test(test_case, [relevancy])


@pytest.mark.parametrize(
    "example",
    GOLDEN_EXAMPLES,
    ids=[e["question"][:40] for e in GOLDEN_EXAMPLES],
)
def test_ask_me_voice_and_accuracy(example: dict, db):
    """Test NRL voice and no fabricated stats."""
    result = ask_jeromelu(db, example["question"], example.get("temperature", "sharp"))

    query_emb = embed_query(example["question"])
    kb_entries = retrieve_kb(db, query_emb)
    context = build_context(kb_entries)

    test_case = LLMTestCase(
        input=example["question"],
        actual_output=result["answer"],
        retrieval_context=[context],
    )

    assert_test(test_case, [nrl_voice, no_fabrication])


@pytest.mark.parametrize(
    "example",
    [e for e in GOLDEN_EXAMPLES if e.get("must_not_contain")],
    ids=[e["question"][:40] for e in GOLDEN_EXAMPLES if e.get("must_not_contain")],
)
def test_ask_me_must_not_contain(example: dict, db):
    """Test that answers don't contain forbidden content."""
    result = ask_jeromelu(db, example["question"], example.get("temperature", "sharp"))

    for forbidden in example["must_not_contain"]:
        assert forbidden.lower() not in result["answer"].lower(), f"Answer contains forbidden term: {forbidden}"

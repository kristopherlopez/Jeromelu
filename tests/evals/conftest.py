"""DeepEval configuration for Ask Me evaluations."""

import os

import pytest

# DeepEval uses OpenAI for its evaluation metrics by default.
# Ensure OPENAI_API_KEY is set in the environment.


@pytest.fixture(scope="session")
def db_session():
    """Provide a DB session for tests that need to query KB context."""
    from jeromelu_shared.db import SessionLocal

    session = SessionLocal()
    yield session
    session.close()

"""Unit tests for jeromelu_shared.insights query helpers.

Specifically exercises the migration-036 rewrite of ``query_round_claims``
and ``query_claim_consensus`` to JOIN through ``ClaimAssociation`` on the
``'subject'`` role rather than the (now-removed) ``Claim.subject_entity_id``
column.

Uses an in-memory SQLite session with two narrow shims to make the real
declarative models build:
  - ``@compiles(JSONB, "sqlite")`` renders Postgres JSONB as plain JSON.
  - ``_strip_pg_only_ddl`` removes the Postgres-syntax CHECK constraint on
    ``ClaimAssociation`` (uses ``(col IS NOT NULL)::int`` casts SQLite
    can't parse).
FK references to non-existent tables (people, teams, …) are tolerated
because SQLite doesn't enforce FKs without ``PRAGMA foreign_keys = ON``.

Per TASK-53.
"""

from __future__ import annotations

import uuid

import pytest
from jeromelu_shared.db.models import Base, Claim, ClaimAssociation
from jeromelu_shared.insights import query_claim_consensus, query_round_claims
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker

# SQLite has no JSONB or UUID type. Render JSONB as plain JSON and the
# Postgres UUID as CHAR(32) when the engine is SQLite. Runtime values
# pass through unchanged — SQLAlchemy stores UUIDs as their string form
# under CHAR(32) and round-trips dicts through JSON. Postgres behavior
# is unchanged. Newer SQLAlchemy 2.0.x versions auto-fall-back UUID on
# SQLite; older ones (≤2.0.30-ish) don't, so we shim explicitly for
# determinism across the supported range.


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(_type, _compiler, **_kw) -> str:
    return "JSON"


@compiles(UUID, "sqlite")
def _compile_uuid_sqlite(_type, _compiler, **_kw) -> str:
    return "CHAR(32)"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db() -> Session:
    """Fresh in-memory SQLite session with only the two tables this module
    touches. Creating the full Base metadata fails because other tables
    (e.g. `people`, `channels`) use Postgres-specific ARRAY columns
    SQLite cannot render. The query helpers under test JOIN Claim ←
    ClaimAssociation only — they don't touch the people table — so
    inserting UUIDs directly for person_id is sufficient.

    The Claim/ClaimAssociation tables carry CHECK constraints with the
    `(col IS NOT NULL)::int + ...` Postgres syntax that SQLite can't
    parse. We save & restore the constraint sets around `create_all`
    so the in-process `Base.metadata` is unaffected for downstream
    tests / suites. FK constraints stay; SQLite tolerates references
    to non-existent tables without `PRAGMA foreign_keys = ON`.
    """
    from sqlalchemy import CheckConstraint

    claim_table = Claim.__table__
    assoc_table = ClaimAssociation.__table__
    saved = {
        claim_table: set(claim_table.constraints),
        assoc_table: set(assoc_table.constraints),
    }
    for table in (claim_table, assoc_table):
        table.constraints = {c for c in table.constraints if not isinstance(c, CheckConstraint)}

    try:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[claim_table, assoc_table])
        SessionLocal = sessionmaker(bind=engine)
        with SessionLocal() as session:
            yield session
    finally:
        for table, constraints in saved.items():
            table.constraints = constraints


def _make_claim(
    db: Session,
    *,
    claim_type: str,
    round_num: int = 5,
    season: int = 2026,
    claim_text: str = "test claim",
) -> Claim:
    """Insert and return a Claim row with sensible defaults."""
    claim = Claim(
        claim_id=uuid.uuid4(),
        claim_type=claim_type,
        claim_text=claim_text,
        effective_round=round_num,
        season=season,
        payload_json={},
    )
    db.add(claim)
    db.flush()
    return claim


def _link(db: Session, *, claim: Claim, person_id: uuid.UUID, role: str = "subject") -> None:
    """Insert a ClaimAssociation row linking a Claim to a Person via a role."""
    db.add(
        ClaimAssociation(
            association_id=uuid.uuid4(),
            claim_id=claim.claim_id,
            role=role,
            person_id=person_id,
        )
    )
    db.flush()


def _person_id() -> uuid.UUID:
    """Synthetic person_id. The query helpers don't join to people, so the
    UUID just needs to be stable for the test's lifetime."""
    return uuid.uuid4()


# ---------------------------------------------------------------------------
# query_round_claims
# ---------------------------------------------------------------------------


def test_query_round_claims_groups_by_person_id(db: Session) -> None:
    """Two claims about the same person are grouped under their person_id."""
    alice = _person_id()
    bob = _person_id()

    c1 = _make_claim(db, claim_type="buy", claim_text="alice rising")
    _link(db, claim=c1, person_id=alice)
    c2 = _make_claim(db, claim_type="captain", claim_text="alice captain")
    _link(db, claim=c2, person_id=alice)
    c3 = _make_claim(db, claim_type="sell", claim_text="bob fading")
    _link(db, claim=c3, person_id=bob)

    result = query_round_claims(db, round_num=5, season=2026)

    assert set(result.keys()) == {str(alice), str(bob)}
    assert len(result[str(alice)]) == 2
    assert {c["claim_type"] for c in result[str(alice)]} == {"buy", "captain"}
    assert len(result[str(bob)]) == 1
    assert result[str(bob)][0]["claim_type"] == "sell"


def test_query_round_claims_excludes_non_subject_roles(db: Session) -> None:
    """ClaimAssociation rows with role != 'subject' are excluded."""
    alice = _person_id()
    bob = _person_id()

    c1 = _make_claim(db, claim_type="buy")
    _link(db, claim=c1, person_id=alice, role="subject")
    _link(db, claim=c1, person_id=bob, role="opponent")  # off-role

    result = query_round_claims(db, round_num=5, season=2026)

    assert set(result.keys()) == {str(alice)}
    assert str(bob) not in result


def test_query_round_claims_excludes_team_only_associations(db: Session) -> None:
    """Subject-role associations with person_id IS NULL (team-only claims) excluded."""
    alice = _person_id()

    c1 = _make_claim(db, claim_type="buy")
    _link(db, claim=c1, person_id=alice)
    c2 = _make_claim(db, claim_type="buy")
    # No person link — only a team-id (in real schema). The helper skips
    # this because person_id IS NULL.
    db.add(
        ClaimAssociation(
            association_id=uuid.uuid4(),
            claim_id=c2.claim_id,
            role="subject",
            person_id=None,
            team_id=uuid.uuid4(),
        )
    )
    db.flush()

    result = query_round_claims(db, round_num=5, season=2026)

    assert set(result.keys()) == {str(alice)}


def test_query_round_claims_filters_by_round_and_season(db: Session) -> None:
    """Claims from a different round or season are excluded."""
    alice = _person_id()

    c1 = _make_claim(db, claim_type="buy", round_num=5, season=2026)
    _link(db, claim=c1, person_id=alice)
    c2 = _make_claim(db, claim_type="buy", round_num=6, season=2026)  # wrong round
    _link(db, claim=c2, person_id=alice)
    c3 = _make_claim(db, claim_type="buy", round_num=5, season=2025)  # wrong season
    _link(db, claim=c3, person_id=alice)

    result = query_round_claims(db, round_num=5, season=2026)

    assert len(result[str(alice)]) == 1
    assert result[str(alice)][0]["claim_text"] == "test claim"


def test_query_round_claims_optional_claim_types_filter(db: Session) -> None:
    """When claim_types is supplied, only those types appear."""
    alice = _person_id()

    c1 = _make_claim(db, claim_type="buy")
    _link(db, claim=c1, person_id=alice)
    c2 = _make_claim(db, claim_type="sell")
    _link(db, claim=c2, person_id=alice)
    c3 = _make_claim(db, claim_type="hold")
    _link(db, claim=c3, person_id=alice)

    result = query_round_claims(db, round_num=5, season=2026, claim_types=["buy", "hold"])

    types = {c["claim_type"] for c in result[str(alice)]}
    assert types == {"buy", "hold"}


def test_query_round_claims_empty_when_no_data(db: Session) -> None:
    """Empty DB → empty dict."""
    assert query_round_claims(db, round_num=5, season=2026) == {}


# ---------------------------------------------------------------------------
# query_claim_consensus
# ---------------------------------------------------------------------------


def test_query_claim_consensus_counts_per_claim_type(db: Session) -> None:
    """Per-person buy/sell/hold/captain/avoid counts come back correctly."""
    alice = _person_id()

    for _ in range(3):
        c = _make_claim(db, claim_type="buy")
        _link(db, claim=c, person_id=alice)
    for _ in range(2):
        c = _make_claim(db, claim_type="captain")
        _link(db, claim=c, person_id=alice)

    result = query_claim_consensus(db, round_num=5, season=2026)

    assert result == {
        str(alice): {"buy": 3, "sell": 0, "hold": 0, "captain": 2, "avoid": 0},
    }


def test_query_claim_consensus_excludes_non_subject_roles(db: Session) -> None:
    """Same role/null-person guards as query_round_claims."""
    alice = _person_id()
    bob = _person_id()

    c = _make_claim(db, claim_type="buy")
    _link(db, claim=c, person_id=alice, role="subject")
    _link(db, claim=c, person_id=bob, role="opponent")

    result = query_claim_consensus(db, round_num=5, season=2026)

    assert set(result.keys()) == {str(alice)}


def test_query_claim_consensus_ignores_unknown_claim_types(db: Session) -> None:
    """Claim types outside the buy/sell/hold/captain/avoid set are counted in
    the JOIN but skipped at result assembly — the row still creates a
    person entry but the unknown type is not added."""
    alice = _person_id()

    c1 = _make_claim(db, claim_type="buy")
    _link(db, claim=c1, person_id=alice)
    c2 = _make_claim(db, claim_type="injury_note")  # off-list
    _link(db, claim=c2, person_id=alice)

    result = query_claim_consensus(db, round_num=5, season=2026)

    assert result[str(alice)] == {
        "buy": 1,
        "sell": 0,
        "hold": 0,
        "captain": 0,
        "avoid": 0,
    }


def test_query_claim_consensus_empty_when_no_data(db: Session) -> None:
    """Empty DB → empty dict."""
    assert query_claim_consensus(db, round_num=5, season=2026) == {}

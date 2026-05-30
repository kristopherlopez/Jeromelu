from __future__ import annotations

import uuid

import pytest
from app.analyst import transcribe_drain_cli
from app.scout.media import drain
from app.scout.media.cli import drain_audio
from jeromelu_shared.db import Source


class QuerySpy:
    def __init__(self, rows):
        self.rows = rows
        self.criteria = []
        self.ordering = []
        self.limit_value = None
        self.lock_kwargs = None

    def filter(self, *criteria):
        self.criteria.extend(criteria)
        return self

    def order_by(self, *ordering):
        self.ordering.extend(ordering)
        return self

    def limit(self, limit):
        self.limit_value = limit
        return self

    def with_for_update(self, **kwargs):
        self.lock_kwargs = kwargs
        return self

    def all(self):
        return self.rows[: self.limit_value]


class SelectionSessionSpy:
    def __init__(self, rows):
        self.query_spy = QuerySpy(rows)
        self.query_args = None

    def query(self, *args):
        self.query_args = args
        return self.query_spy


def _criteria_sql(query: QuerySpy) -> str:
    return "\n".join(str(criteria) for criteria in query.criteria)


def test_select_pending_audio_source_ids_filters_and_limits():
    source_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    session = SelectionSessionSpy([(source_id,) for source_id in source_ids])

    selected = drain.select_pending_audio_source_ids(session, limit=2)

    assert selected == source_ids[:2]
    assert session.query_args == (Source.source_id,)
    assert session.query_spy.limit_value == 2
    assert session.query_spy.lock_kwargs == {"skip_locked": True, "of": Source}
    criteria = _criteria_sql(session.query_spy)
    assert "sources.approved_flag IS true" in criteria
    assert "sources.source_type = :source_type_1" in criteria
    assert "sources.ingestion_status = :ingestion_status_1" in criteria
    assert "sources.audio_s3_key IS NULL" in criteria
    assert len(session.query_spy.ordering) == 3


def test_select_collected_untranscribed_source_ids_filters_and_limits():
    source_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    session = SelectionSessionSpy([(source_id,) for source_id in source_ids])

    selected = drain.select_collected_untranscribed_source_ids(session, limit=1)

    assert selected == source_ids[:1]
    assert session.query_spy.limit_value == 1
    assert session.query_spy.lock_kwargs == {"skip_locked": True, "of": Source}
    criteria = _criteria_sql(session.query_spy)
    assert "sources.approved_flag IS true" in criteria
    assert "sources.ingestion_status = :ingestion_status_1" in criteria
    assert "sources.audio_s3_key IS NOT NULL" in criteria
    assert "sources.transcription_status IS NULL" in criteria
    assert "source_documents" in criteria
    assert "NOT (EXISTS" in criteria


@pytest.mark.parametrize("limit", [0, -1])
def test_selectors_reject_non_positive_limits(limit):
    session = SelectionSessionSpy([])

    with pytest.raises(ValueError, match="limit must be >= 1"):
        drain.select_pending_audio_source_ids(session, limit=limit)

    with pytest.raises(ValueError, match="limit must be >= 1"):
        drain.select_collected_untranscribed_source_ids(session, limit=limit)


class ProcessQuery:
    def __init__(self, source):
        self.source = source
        self.criteria = []
        self.lock_kwargs = None

    def options(self, *_options):
        return self

    def filter(self, *criteria):
        self.criteria.extend(criteria)
        return self

    def with_for_update(self, **kwargs):
        self.lock_kwargs = kwargs
        return self

    def one_or_none(self):
        return self.source


class ProcessSession:
    def __init__(self, source):
        self.source = source
        self.rollbacks = 0
        self.queries = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc_info):
        return False

    def query(self, *_args):
        query = ProcessQuery(self.source)
        self.queries.append(query)
        return query

    def rollback(self):
        self.rollbacks += 1


class ProcessSessionFactory:
    def __init__(self, sources):
        self.sources = list(sources)
        self.sessions = []

    def __call__(self):
        session = ProcessSession(self.sources[len(self.sessions)])
        self.sessions.append(session)
        return session


def test_drain_source_ids_isolates_per_source_failures():
    source_ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    sources = [type("SourceStub", (), {"source_id": source_id})() for source_id in source_ids]
    session_factory = ProcessSessionFactory(sources)
    processed = []

    def process_source(_session, source):
        processed.append(source.source_id)
        if source.source_id == source_ids[1]:
            raise RuntimeError("download blocked")

    result = drain.drain_source_ids(
        session_factory=session_factory,
        source_ids=source_ids,
        process_source=process_source,
    )

    assert processed == source_ids
    assert result.selected == 3
    assert result.succeeded == 2
    assert result.skipped == 0
    assert result.failed == 1
    assert result.failures[0].source_id == str(source_ids[1])
    assert result.failures[0].error == "download blocked"
    assert [session.rollbacks for session in session_factory.sessions] == [0, 1, 0]
    assert [session.queries[0].lock_kwargs for session in session_factory.sessions] == [
        {"skip_locked": True, "of": Source},
        {"skip_locked": True, "of": Source},
        {"skip_locked": True, "of": Source},
    ]


def test_drain_source_ids_rechecks_eligibility_and_skips_stale_selection():
    source_ids = [uuid.uuid4(), uuid.uuid4()]
    eligible_source = type("SourceStub", (), {"source_id": source_ids[1]})()
    session_factory = ProcessSessionFactory([None, eligible_source])
    processed = []

    def process_source(_session, source):
        processed.append(source.source_id)

    result = drain.drain_source_ids(
        session_factory=session_factory,
        source_ids=source_ids,
        process_source=process_source,
        eligibility_criteria=drain.pending_audio_source_criteria(),
    )

    assert processed == [source_ids[1]]
    assert result.selected == 2
    assert result.succeeded == 1
    assert result.skipped == 1
    assert result.failed == 0
    assert result.failures == ()

    first_query_sql = "\n".join(str(criteria) for criteria in session_factory.sessions[0].queries[0].criteria)
    assert "sources.source_id = :source_id_1" in first_query_sql
    assert "sources.approved_flag IS true" in first_query_sql
    assert "sources.source_type = :source_type_1" in first_query_sql
    assert "sources.ingestion_status = :ingestion_status_1" in first_query_sql
    assert "sources.audio_s3_key IS NULL" in first_query_sql


def test_audio_drain_cli_help_imports_without_download_stack(capsys):
    with pytest.raises(SystemExit) as exc:
        drain_audio.main(["--help"])

    assert exc.value.code == 0
    assert "--limit" in capsys.readouterr().out


def test_transcription_drain_cli_help_imports_without_deepgram_stack(capsys):
    with pytest.raises(SystemExit) as exc:
        transcribe_drain_cli.main(["--help"])

    assert exc.value.code == 0
    assert "--limit" in capsys.readouterr().out

"""Phase 5: unit tests for the hardened scout_backfill driver.

The driver was extended with --archive-only, --resume, --force, --bucket
flags. Tests use mocked httpx.Client + mocked boto3 S3 client so the loop
runs without real network or S3.

Six required cases per spec:
  1. URL params include archive_only=true when --archive-only is set.
  2. --resume + S3 head_object → 200 → POST is NOT issued.
  3. --resume + S3 head_object → 404 (raises) → POST IS issued.
  4. --resume --force → POST IS issued even when S3 already has the key.
  5. nrlcom-match-centre uses LIST-prefix resume (list_objects_v2 returning
     Contents non-empty → skip; empty → POST).
  6. Unknown --source exits with code 2.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scripts.data import scout_backfill


def _mock_httpx_client(return_code: int = 200, json_payload: dict | None = None):
    """Build a mocked httpx.Client whose `__enter__().post(...)` returns a
    fake Response. Returns the mock and the post-call accumulator."""
    fake_resp = MagicMock()
    fake_resp.status_code = return_code
    fake_resp.json.return_value = json_payload or {"run_id": "scout-fake-run"}
    fake_resp.text = "ok" if return_code == 200 else "fail"

    fake_client = MagicMock()
    fake_client.__enter__.return_value = fake_client
    fake_client.__exit__.return_value = False
    fake_client.post.return_value = fake_resp
    return fake_client


def _common_argv(source: str, *extra: str) -> list[str]:
    return [
        "--source", source,
        "--season-from", "2026",
        "--api", "http://localhost:8000",
        "--admin-key", "DUMMY",
        "--rate-limit", "0",  # zero sleep so tests run fast
        *extra,
    ]


def test_url_includes_archive_only_when_flag_set():
    """--archive-only appends archive_only=true to every POST's params."""
    fake_client = _mock_httpx_client()
    with patch("scripts.data.scout_backfill.httpx.Client", return_value=fake_client), \
         patch("scripts.data.scout_backfill.time.sleep"):
        exit_code = scout_backfill.main(
            _common_argv("nrlcom-stats", "--archive-only")
        )
    assert exit_code == 0
    # Only one POST for nrlcom-stats (no round dimension): 2026 only.
    assert fake_client.post.call_count == 1
    call_kwargs = fake_client.post.call_args.kwargs
    assert call_kwargs["params"]["archive_only"] == "true"
    assert call_kwargs["params"]["season"] == 2026
    assert call_kwargs["params"]["competition"] == 111


def test_archive_only_flag_omitted_by_default():
    """Default: no archive_only in params (daily-cron path)."""
    fake_client = _mock_httpx_client()
    with patch("scripts.data.scout_backfill.httpx.Client", return_value=fake_client), \
         patch("scripts.data.scout_backfill.time.sleep"):
        scout_backfill.main(_common_argv("nrlcom-stats"))
    call_kwargs = fake_client.post.call_args.kwargs
    assert "archive_only" not in call_kwargs["params"]


def test_resume_skips_when_s3_head_succeeds():
    """--resume + head_object returns OK → POST NOT issued; counted as skip."""
    fake_client = _mock_httpx_client()
    fake_s3 = MagicMock()
    fake_s3.head_object.return_value = {"ContentLength": 1234}  # success
    with patch("scripts.data.scout_backfill.httpx.Client", return_value=fake_client), \
         patch("scripts.data.scout_backfill._get_s3_client", return_value=fake_s3), \
         patch("scripts.data.scout_backfill.time.sleep"):
        scout_backfill.main(_common_argv("nrlcom-stats", "--resume"))
    # head_object called once for the single (2026, no-round) iteration
    assert fake_s3.head_object.call_count == 1
    # POST was skipped
    assert fake_client.post.call_count == 0


def test_resume_posts_when_s3_head_raises():
    """--resume + head_object raises (404) → POST IS issued."""
    fake_client = _mock_httpx_client()
    fake_s3 = MagicMock()
    fake_s3.head_object.side_effect = RuntimeError("404 Not Found")
    with patch("scripts.data.scout_backfill.httpx.Client", return_value=fake_client), \
         patch("scripts.data.scout_backfill._get_s3_client", return_value=fake_s3), \
         patch("scripts.data.scout_backfill.time.sleep"):
        scout_backfill.main(_common_argv("nrlcom-stats", "--resume"))
    assert fake_s3.head_object.call_count == 1
    # POST WAS issued (S3 said no)
    assert fake_client.post.call_count == 1


def test_force_overrides_resume():
    """--resume --force → POST IS issued even when head_object would say YES."""
    fake_client = _mock_httpx_client()
    fake_s3 = MagicMock()
    fake_s3.head_object.return_value = {"ContentLength": 1234}  # success
    with patch("scripts.data.scout_backfill.httpx.Client", return_value=fake_client), \
         patch("scripts.data.scout_backfill._get_s3_client", return_value=fake_s3), \
         patch("scripts.data.scout_backfill.time.sleep"):
        scout_backfill.main(_common_argv("nrlcom-stats", "--resume", "--force"))
    # head_object should NOT be called at all when --force is set (we never make a client either)
    assert fake_s3.head_object.call_count == 0
    # POST WAS issued unconditionally
    assert fake_client.post.call_count == 1


def test_match_centre_resume_uses_list_prefix():
    """nrlcom-match-centre uses LIST-prefix resume; non-empty Contents → skip."""
    fake_client = _mock_httpx_client()
    fake_s3 = MagicMock()
    fake_s3.list_objects_v2.return_value = {
        "Contents": [{"Key": "scout/nrlcom/match-centre/111/2026/round-12/foo.json"}],
    }
    with patch("scripts.data.scout_backfill.httpx.Client", return_value=fake_client), \
         patch("scripts.data.scout_backfill._get_s3_client", return_value=fake_s3), \
         patch("scripts.data.scout_backfill.time.sleep"):
        # Single round so we only iterate once
        scout_backfill.main(_common_argv(
            "nrlcom-match-centre",
            "--round-from", "12", "--round-to", "12",
            "--resume",
        ))
    # list_objects_v2 called once for (2026, round-12); POST not issued
    assert fake_s3.list_objects_v2.call_count == 1
    assert fake_client.post.call_count == 0
    # head_object NOT used for this source (match-centre uses LIST)
    assert fake_s3.head_object.call_count == 0


def test_match_centre_resume_list_empty_triggers_post():
    """nrlcom-match-centre LIST returning empty Contents → POST IS issued."""
    fake_client = _mock_httpx_client()
    fake_s3 = MagicMock()
    fake_s3.list_objects_v2.return_value = {"Contents": []}  # nothing under prefix
    with patch("scripts.data.scout_backfill.httpx.Client", return_value=fake_client), \
         patch("scripts.data.scout_backfill._get_s3_client", return_value=fake_s3), \
         patch("scripts.data.scout_backfill.time.sleep"):
        scout_backfill.main(_common_argv(
            "nrlcom-match-centre",
            "--round-from", "12", "--round-to", "12",
            "--resume",
        ))
    assert fake_s3.list_objects_v2.call_count == 1
    assert fake_client.post.call_count == 1


def test_unknown_source_exits_2():
    """Unknown --source value → exit code 2 (existing behaviour preserved)."""
    exit_code = scout_backfill.main(_common_argv("not-a-real-source"))
    assert exit_code == 2


def test_supercoach_roster_resume_is_noop():
    """SC siblings (no S3_KEY_FN entry) → --resume is a no-op; POST IS issued."""
    fake_client = _mock_httpx_client()
    fake_s3 = MagicMock()
    # head_object should NEVER be called for SC siblings (no key derivation).
    with patch("scripts.data.scout_backfill.httpx.Client", return_value=fake_client), \
         patch("scripts.data.scout_backfill._get_s3_client", return_value=fake_s3), \
         patch("scripts.data.scout_backfill.time.sleep"):
        scout_backfill.main(_common_argv("supercoach-roster", "--resume"))
    assert fake_s3.head_object.call_count == 0
    assert fake_s3.list_objects_v2.call_count == 0
    # POST WAS issued (resume is a no-op for this source)
    assert fake_client.post.call_count == 1

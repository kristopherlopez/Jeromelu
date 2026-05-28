"""Daily cron-health digest email.

Sister to scripts/cost_report.py. Where cost_report covers AWS spend, this
covers whether the scheduled jobs we depend on actually ran in the last
24h and what they produced.

Triggered by /etc/cron.d/jeromelu at 00:30 UTC (10:30 AEST) — late enough
for the worst-case `videos` refresh (kicks off 23:15 UTC, can take ~45
min) to have settled. Reports on the trailing 24h window.

Runs on the Lightsail box, not GitHub Actions. Reasons:
  - Needs Postgres access (DB heartbeats = "what did the job actually
    write"). The box has localhost docker exec into the postgres
    container.
  - Needs /var/log/jeromelu/*.log access ("did the process exit clean").
  - SES + S3 work from the box via the jeromelu-instance IAM user.

Dead-man's switch: if the box itself is down, no email arrives. That is
also true of the existing pg-backup.sh — same failure mode, separate
external monitoring catches it (Lightsail dashboard).

Permissions added in infra/terraform/iam.tf on the jeromelu-instance
user (ses:SendEmail scoped to the existing SES identities; the rest of
the AWS calls — s3:ListBucket, s3:HeadObject — were already permitted
by the existing S3App statement).

Env vars (sourced from /opt/jeromelu/.env by the wrapper):
  POSTGRES_USER, POSTGRES_DB    — for docker exec psql
  GITHUB_TOKEN                  — fine-grained PAT with actions:read on
                                  this repo. Without it the cost-report
                                  row falls back to status='unknown'.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import ClientError

# Windows-style stdout fix is harmless on Linux — keeps parity with cost_report.py.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---- Config ----------------------------------------------------------------

PRIMARY_REGION = "ap-southeast-2"
SENDER = "reports@jeromelu.ai"
RECIPIENT = "kristopher.lopez@gmail.com"

BACKUP_BUCKET = "jeromelu-public-assets"
BACKUP_PREFIX = "backups/postgres/"

SCOUT_LOG = "/var/log/jeromelu/scout-refresh.log"
PG_BACKUP_LOG = "/var/log/jeromelu/pg-backup.log"

GITHUB_REPO = "kristopherlopez/Jeromelu"
COST_REPORT_WORKFLOW = "cost-report.yml"

# Window for "did it run recently" — daily jobs get 25h of slack.
RUN_WINDOW = timedelta(hours=25)

OK = "ok"
WARN = "warn"
FAIL = "fail"

# Glyphs paired with each level. ✓/⚠/✗ render in plaintext and HTML
# without emoji fonts (which mail clients render inconsistently).
GLYPH = {OK: "✓", WARN: "⚠", FAIL: "✗"}
COLOR = {OK: "#1a7f37", WARN: "#bf8700", FAIL: "#cf222e"}


# ---- Data model ------------------------------------------------------------


@dataclass
class Row:
    """One row in the digest. Each scheduled job produces one Row."""

    name: str
    schedule: str  # human-readable, e.g. "23:00 UTC daily"
    status: str  # OK / WARN / FAIL
    last_run: str  # "2026-05-23T23:00:12Z" or "—"
    detail: str  # one-line summary of what the run did


# ---- Postgres helpers ------------------------------------------------------


def _psql(query: str) -> str:
    """Run a single SQL statement against the prod DB via docker exec.

    Returns the raw stdout (newline-separated rows, tab-separated cols).
    Empty string on success-with-no-rows. Raises on non-zero exit.
    """
    user = os.environ.get("POSTGRES_USER", "jeromelu_admin")
    db = os.environ.get("POSTGRES_DB", "jeromelu")
    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            "jeromelu-postgres",
            "psql",
            "-U",
            user,
            "-d",
            db,
            "-t",
            "-A",
            "-F",
            "\t",
            "-c",
            query,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def count_channel_metrics_24h(now: datetime) -> tuple[int, int]:
    """(total_rows, distinct_channels) over the last 24h."""
    out = _psql(
        "SELECT COUNT(*), COUNT(DISTINCT channel_id) "
        "FROM channel_metrics "
        "WHERE sampled_at > NOW() - INTERVAL '24 hours';"
    )
    if not out:
        return 0, 0
    total, distinct = out.split("\t")
    return int(total), int(distinct)


def count_video_metrics_24h(now: datetime) -> tuple[int, int, int]:
    """(metric_rows, distinct_videos, new_sources) over the last 24h.

    new_sources counts rows in `sources` with source_type='video' and
    ingested_at within the window — proxy for "discovered today".
    """
    metrics_out = _psql(
        "SELECT COUNT(*), COUNT(DISTINCT source_id) FROM video_metrics WHERE sampled_at > NOW() - INTERVAL '24 hours';"
    )
    # `created_at` is the discovery timestamp (NOT NULL, default now()).
    # `ingested_at` is later — set when transcription/audio fetch lands,
    # so it's the wrong field for "new videos discovered today".
    new_out = _psql(
        "SELECT COUNT(*) FROM sources WHERE source_type = 'youtube' AND created_at > NOW() - INTERVAL '24 hours';"
    )
    if not metrics_out:
        return 0, 0, int(new_out or 0)
    total, distinct = metrics_out.split("\t")
    return int(total), int(distinct), int(new_out or 0)


# ---- Log parsing -----------------------------------------------------------

# scout-refresh.log lines look like:
#   [2026-05-23T23:00:12Z] channel-stats status=200 body={"updated":12,...}
#   [2026-05-23T23:00:12Z] videos        curl_rc=28 err=...
SCOUT_LINE = re.compile(
    r"^\[(?P<ts>\S+)\]\s+(?P<job>\S+)\s+"
    r"(?:status=(?P<status>\d+)\s+body=(?P<body>.*)|curl_rc=(?P<rc>\d+)\s+err=(?P<err>.*))$"
)


def latest_scout_line(job: str, now: datetime) -> dict[str, Any] | None:
    """Return the latest log entry for `job` within RUN_WINDOW, or None.

    Reads bottom-up so the file size doesn't matter — typical log is
    one line per job per day, but cron retries during incidents can
    push it to dozens.
    """
    if not os.path.exists(SCOUT_LOG):
        return None
    cutoff = now - RUN_WINDOW
    with open(SCOUT_LOG, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    for line in reversed(lines):
        m = SCOUT_LINE.match(line.strip())
        if not m or m.group("job") != job:
            continue
        ts = _parse_log_ts(m.group("ts"))
        if ts is None or ts < cutoff:
            continue
        return {
            "ts": ts,
            "http_status": int(m.group("status")) if m.group("status") else None,
            "body": m.group("body") or "",
            "curl_rc": int(m.group("rc")) if m.group("rc") else None,
            "err": m.group("err") or "",
        }
    return None


def latest_pg_backup_log(now: datetime) -> datetime | None:
    """Return timestamp of the latest pg-backup log line in window, or None."""
    if not os.path.exists(PG_BACKUP_LOG):
        return None
    cutoff = now - RUN_WINDOW
    pat = re.compile(r"^\[(\S+)\]\s+backup ok:")
    with open(PG_BACKUP_LOG, encoding="utf-8", errors="replace") as f:
        for line in reversed(f.readlines()):
            m = pat.match(line.strip())
            if not m:
                continue
            ts = _parse_log_ts(m.group(1))
            if ts and ts >= cutoff:
                return ts
    return None


def _parse_log_ts(s: str) -> datetime | None:
    """Logs use date -u +%FT%TZ → 2026-05-23T23:00:12Z."""
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None


# ---- S3 / pg-backup --------------------------------------------------------


def latest_pg_backup_s3(now: datetime) -> dict[str, Any] | None:
    """Latest object under s3://{bucket}/{prefix} within RUN_WINDOW.

    More authoritative than the log file — the log can be rotated or
    truncated; the S3 object IS the deliverable. Return None if no
    backup landed in window.
    """
    s3 = boto3.client("s3", region_name=PRIMARY_REGION)
    resp = s3.list_objects_v2(Bucket=BACKUP_BUCKET, Prefix=BACKUP_PREFIX)
    contents = resp.get("Contents", [])
    if not contents:
        return None
    latest = max(contents, key=lambda o: o["LastModified"])
    if latest["LastModified"] < now - RUN_WINDOW:
        return None
    return {
        "key": latest["Key"],
        "size_bytes": latest["Size"],
        "last_modified": latest["LastModified"],
    }


# ---- GitHub Actions API ----------------------------------------------------


def latest_cost_report_run(now: datetime) -> dict[str, Any] | None:
    """Most recent run of cost-report.yml in window, via GH REST API.

    Returns {"status", "conclusion", "created_at", "html_url"} or None
    if no run in window. Returns the sentinel {"status": "unknown"} if
    GITHUB_TOKEN is unset — the row still appears, just without status.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return {"status": "unknown", "reason": "GITHUB_TOKEN not set"}

    url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{COST_REPORT_WORKFLOW}/runs?per_page=1"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.URLError as exc:
        return {"status": "unknown", "reason": f"GH API error: {exc}"}

    runs = data.get("workflow_runs", [])
    if not runs:
        return None
    run = runs[0]
    created_at = datetime.strptime(run["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    if created_at < now - RUN_WINDOW:
        return None
    return {
        "status": run["status"],  # queued / in_progress / completed
        "conclusion": run["conclusion"],  # success / failure / cancelled / ...
        "created_at": created_at,
        "html_url": run["html_url"],
    }


# ---- Per-job row builders --------------------------------------------------


def row_cost_report(now: datetime) -> Row:
    run = latest_cost_report_run(now)
    if run is None:
        return Row(
            name="GHA cost-report",
            schedule="22:00 UTC daily",
            status=FAIL,
            last_run="—",
            detail="No run found in last 25h",
        )
    if run.get("status") == "unknown":
        return Row(
            name="GHA cost-report",
            schedule="22:00 UTC daily",
            status=WARN,
            last_run="—",
            detail=run.get("reason", "status unknown"),
        )
    conclusion = run["conclusion"]
    if conclusion == "success":
        status = OK
    elif conclusion in ("in_progress", None):
        status = WARN
    else:
        status = FAIL
    return Row(
        name="GHA cost-report",
        schedule="22:00 UTC daily",
        status=status,
        last_run=run["created_at"].isoformat().replace("+00:00", "Z"),
        detail=f"conclusion={conclusion or 'pending'}",
    )


def row_channel_stats(now: datetime) -> Row:
    log = latest_scout_line("channel-stats", now)
    total, distinct = count_channel_metrics_24h(now)
    if log is None:
        return Row(
            name="Scout: channel-stats",
            schedule="23:00 UTC daily",
            status=FAIL,
            last_run="—",
            detail=f"No log entry in last 25h (DB has {total} rows)",
        )
    last_run = log["ts"].isoformat().replace("+00:00", "Z")
    if log["curl_rc"] is not None:
        return Row(
            name="Scout: channel-stats",
            schedule="23:00 UTC daily",
            status=FAIL,
            last_run=last_run,
            detail=f"curl_rc={log['curl_rc']}: {_truncate(log['err'], 80)}",
        )
    http = log["http_status"]
    # Every run snapshots every channel — zero rows means the endpoint
    # returned 2xx but did nothing useful.
    if http and 200 <= http < 300 and total > 0:
        status = OK
    elif http and 200 <= http < 300:
        status = WARN
    else:
        status = FAIL
    return Row(
        name="Scout: channel-stats",
        schedule="23:00 UTC daily",
        status=status,
        last_run=last_run,
        detail=f"HTTP {http} · {total} metric rows across {distinct} channels",
    )


def row_videos(now: datetime) -> Row:
    log = latest_scout_line("videos", now)
    total, distinct, new_sources = count_video_metrics_24h(now)
    if log is None:
        return Row(
            name="Scout: videos",
            schedule="23:15 UTC daily",
            status=FAIL,
            last_run="—",
            detail=f"No log entry in last 25h (DB has {total} rows, {new_sources} new)",
        )
    last_run = log["ts"].isoformat().replace("+00:00", "Z")
    if log["curl_rc"] is not None:
        return Row(
            name="Scout: videos",
            schedule="23:15 UTC daily",
            status=FAIL,
            last_run=last_run,
            detail=f"curl_rc={log['curl_rc']}: {_truncate(log['err'], 80)}",
        )
    http = log["http_status"]
    # Zero metric rows on a clean run is suspicious (job snapshots
    # existing videos too, not just new ones). Zero new_sources is
    # fine — most days there are no new videos.
    if http and 200 <= http < 300 and total > 0:
        status = OK
    elif http and 200 <= http < 300:
        status = WARN
    else:
        status = FAIL
    new_part = f", {new_sources} new" if new_sources else ""
    return Row(
        name="Scout: videos",
        schedule="23:15 UTC daily",
        status=status,
        last_run=last_run,
        detail=f"HTTP {http} · {total} metric snapshots across {distinct} videos{new_part}",
    )


def row_pg_backup(now: datetime) -> Row:
    s3_latest = latest_pg_backup_s3(now)
    log_ts = latest_pg_backup_log(now)
    if s3_latest is None:
        return Row(
            name="pg-backup",
            schedule="16:30 UTC daily",
            status=FAIL,
            last_run=log_ts.isoformat().replace("+00:00", "Z") if log_ts else "—",
            detail=f"No backup landed in s3://{BACKUP_BUCKET}/{BACKUP_PREFIX} in last 25h",
        )
    last_run = s3_latest["last_modified"].isoformat().replace("+00:00", "Z")
    size_mb = s3_latest["size_bytes"] / (1024 * 1024)
    key_short = s3_latest["key"].rsplit("/", 1)[-1]
    return Row(
        name="pg-backup",
        schedule="16:30 UTC daily",
        status=OK,
        last_run=last_run,
        detail=f"{key_short} ({size_mb:.1f} MB)",
    )


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


# ---- Rendering -------------------------------------------------------------


def render_text(today: datetime, rows: list[Row]) -> str:
    lines: list[str] = []
    lines.append(f"Jeromelu cron health — {today.date().isoformat()}")
    lines.append("=" * 60)
    lines.append("")
    counts = _status_counts(rows)
    lines.append(f"  {counts[OK]} ok · {counts[WARN]} warn · {counts[FAIL]} fail")
    lines.append("")
    for r in rows:
        lines.append(f"  {GLYPH[r.status]} {r.name}")
        lines.append(f"      schedule  {r.schedule}")
        lines.append(f"      last run  {r.last_run}")
        lines.append(f"      detail    {r.detail}")
        lines.append("")
    return "\n".join(lines)


def render_html(today: datetime, rows: list[Row]) -> str:
    counts = _status_counts(rows)
    header_color = COLOR[FAIL] if counts[FAIL] else COLOR[WARN] if counts[WARN] else COLOR[OK]
    row_html = "".join(_render_row_html(r) for r in rows)
    return f"""\
<!doctype html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:14px;color:#222">
<h2 style="margin:0 0 4px 0">Jeromelu cron health — {today.date().isoformat()}</h2>
<p style="margin:0 0 16px 0;color:{header_color};font-weight:600">
  {counts[OK]} ok · {counts[WARN]} warn · {counts[FAIL]} fail
</p>
<table style="border-collapse:collapse;width:100%;max-width:720px">
  <thead>
    <tr style="text-align:left;color:#666;font-size:12px;text-transform:uppercase;letter-spacing:.04em">
      <th style="padding:4px 12px 4px 0">Status</th>
      <th style="padding:4px 12px 4px 0">Job</th>
      <th style="padding:4px 12px 4px 0">Schedule</th>
      <th style="padding:4px 12px 4px 0">Last run</th>
      <th style="padding:4px 0">Detail</th>
    </tr>
  </thead>
  <tbody>{row_html}</tbody>
</table>
<p style="color:#888;font-size:12px;margin-top:24px">
  Generated by <code>scripts/cron_report.py</code> via
  <code>/etc/cron.d/jeromelu</code> on the Lightsail box.
  Dead-man's switch: if this email doesn't arrive, the box itself may be down.
</p>
</body></html>
"""


def _render_row_html(r: Row) -> str:
    return f"""
<tr style="border-top:1px solid #eee">
  <td style="padding:8px 12px 8px 0;color:{COLOR[r.status]};font-weight:600">
    {GLYPH[r.status]} {r.status}
  </td>
  <td style="padding:8px 12px 8px 0;font-weight:600">{r.name}</td>
  <td style="padding:8px 12px 8px 0;color:#666;white-space:nowrap">{r.schedule}</td>
  <td style="padding:8px 12px 8px 0;color:#666;white-space:nowrap;font-family:ui-monospace,Menlo,monospace;font-size:12px">{r.last_run}</td>
  <td style="padding:8px 0;color:#444">{r.detail}</td>
</tr>"""


def _status_counts(rows: list[Row]) -> dict[str, int]:
    counts = {OK: 0, WARN: 0, FAIL: 0}
    for r in rows:
        counts[r.status] += 1
    return counts


# ---- Send ------------------------------------------------------------------


def send_email(subject: str, html: str, text: str) -> None:
    ses = boto3.client("ses", region_name=PRIMARY_REGION)
    ses.send_email(
        Source=SENDER,
        Destination={"ToAddresses": [RECIPIENT]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Text": {"Data": text, "Charset": "UTF-8"},
                "Html": {"Data": html, "Charset": "UTF-8"},
            },
        },
    )


def _subject(today: datetime, rows: list[Row]) -> str:
    counts = _status_counts(rows)
    if counts[FAIL]:
        tag = f"✗ {counts[FAIL]} fail"
    elif counts[WARN]:
        tag = f"⚠ {counts[WARN]} warn"
    else:
        tag = f"{counts[OK]} ok"
    return f"[Jeromelu] Cron — {today.date().isoformat()} · {tag}"


def main() -> int:
    now = datetime.now(UTC)
    rows = [
        row_cost_report(now),
        row_channel_stats(now),
        row_videos(now),
        row_pg_backup(now),
    ]
    text = render_text(now, rows)
    html = render_html(now, rows)
    subject = _subject(now, rows)

    print(text)
    print("---sending---")
    try:
        send_email(subject=subject, html=html, text=text)
    except ClientError as exc:
        print(f"SES send failed: {exc}", file=sys.stderr)
        return 1
    print("sent OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

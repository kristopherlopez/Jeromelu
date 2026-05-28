"""Weekly capacity report.

Surfaces "are we close to filling something" before it bites. Three signals:

  1. Filesystem capacity — `df -h` on the root partition. The Lightsail
     small_3_2 box has 60GB SSD; Docker volumes + ECR cache + Postgres
     data all share it.
  2. Postgres database size — `pg_database_size('jeromelu')` plus the
     top tables by total size and by row count. Driven mostly by
     channel_metrics, video_metrics, source_chunks.
  3. Local log volume — `/var/log/jeromelu` size so we know if log
     rotation needs setting up.

Schedule: Mondays 22:30 UTC = Tuesday 08:30 AEST. Weekly because
storage doesn't move fast enough to warrant daily noise.
"""

from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PRIMARY_REGION = "ap-southeast-2"
SENDER = "reports@jeromelu.ai"
RECIPIENT = "kristopher.lopez@gmail.com"

# Thresholds for the headline colour.
WARN_PCT = 70
FAIL_PCT = 85


@dataclass
class DfRow:
    mount: str
    size: str
    used: str
    avail: str
    use_pct: int


@dataclass
class TableRow:
    name: str
    total_pretty: str
    total_bytes: int
    row_count: int


def df_root() -> DfRow:
    """Run `df -h /` and parse the single data row."""
    result = subprocess.run(
        ["df", "-h", "--output=target,size,used,avail,pcent", "/"],
        capture_output=True,
        text=True,
        check=True,
    )
    # Skip the header line.
    line = result.stdout.strip().splitlines()[-1].split()
    return DfRow(
        mount=line[0],
        size=line[1],
        used=line[2],
        avail=line[3],
        use_pct=int(line[4].rstrip("%")),
    )


def log_dir_size() -> str:
    """`du -sh /var/log/jeromelu` or '-' if missing."""
    path = "/var/log/jeromelu"
    if not os.path.isdir(path):
        return "-"
    result = subprocess.run(
        ["du", "-sh", path],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.split()[0] if result.returncode == 0 else "-"


def _psql(query: str) -> str:
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


def db_total_size() -> tuple[str, int]:
    """Returns (pretty, bytes) for the current database."""
    out = _psql("SELECT pg_size_pretty(pg_database_size(current_database())), pg_database_size(current_database());")
    pretty, bytes_str = out.split("\t")
    return pretty, int(bytes_str)


def top_tables_by_size(limit: int = 10) -> list[TableRow]:
    out = _psql(
        "SELECT c.relname, "
        "pg_size_pretty(pg_total_relation_size(c.oid)), "
        "pg_total_relation_size(c.oid), "
        "COALESCE(s.n_live_tup, 0) "
        "FROM pg_class c "
        "LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid "
        "JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE c.relkind = 'r' AND n.nspname = 'public' "
        "ORDER BY pg_total_relation_size(c.oid) DESC "
        f"LIMIT {limit};"
    )
    rows: list[TableRow] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 4:
            continue
        rows.append(
            TableRow(
                name=parts[0],
                total_pretty=parts[1],
                total_bytes=int(parts[2]),
                row_count=int(parts[3]),
            )
        )
    return rows


# ---- Rendering -------------------------------------------------------------


def _status_color(pct: int) -> str:
    if pct >= FAIL_PCT:
        return "#cf222e"
    if pct >= WARN_PCT:
        return "#bf8700"
    return "#1a7f37"


def render_text(
    today: datetime, df: DfRow, db_pretty: str, db_bytes: int, tables: list[TableRow], log_size: str
) -> str:
    lines = [
        f"Jeromelu capacity report — {today.date().isoformat()}",
        "=" * 60,
        "",
        "FILESYSTEM",
        f"  / — {df.used} of {df.size} used ({df.use_pct}%) · {df.avail} free",
        f"  /var/log/jeromelu — {log_size}",
        "",
        "DATABASE",
        f"  total — {db_pretty}",
        "",
        "TOP TABLES",
    ]
    for t in tables:
        lines.append(f"  {t.total_pretty:>10}  {t.row_count:>12,} rows  {t.name}")
    lines.append("")
    return "\n".join(lines)


def render_html(
    today: datetime, df: DfRow, db_pretty: str, db_bytes: int, tables: list[TableRow], log_size: str
) -> str:
    color = _status_color(df.use_pct)
    rows_html = "".join(
        f'<tr style="border-top:1px solid #eee">'
        f'<td style="padding:4px 12px 4px 0;font-family:ui-monospace,Menlo,monospace">{t.total_pretty}</td>'
        f'<td style="padding:4px 12px 4px 0;font-family:ui-monospace,Menlo,monospace;text-align:right">{t.row_count:,}</td>'
        f'<td style="padding:4px 0">{t.name}</td>'
        f"</tr>"
        for t in tables
    )
    return f"""\
<!doctype html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:14px;color:#222">
<h2 style="margin:0 0 4px 0">Jeromelu capacity — {today.date().isoformat()}</h2>
<p style="margin:0 0 16px 0;color:{color};font-weight:600">
  Root filesystem {df.use_pct}% full · DB {db_pretty}
</p>

<h3 style="margin:16px 0 4px 0">Filesystem</h3>
<table style="border-collapse:collapse">
  <tr><td style="padding:2px 16px 2px 0">/</td>
      <td>{df.used} of {df.size} ({df.use_pct}%) · <span style="color:#666">{df.avail} free</span></td></tr>
  <tr><td style="padding:2px 16px 2px 0">/var/log/jeromelu</td><td>{log_size}</td></tr>
</table>

<h3 style="margin:16px 0 4px 0">Postgres</h3>
<table style="border-collapse:collapse">
  <tr><td style="padding:2px 16px 2px 0">Total size</td><td><strong>{db_pretty}</strong></td></tr>
</table>

<h3 style="margin:16px 0 4px 0">Top tables</h3>
<table style="border-collapse:collapse;width:100%;max-width:600px">
  <thead>
    <tr style="text-align:left;color:#666;font-size:12px;text-transform:uppercase;letter-spacing:.04em">
      <th style="padding:4px 12px 4px 0">Size</th>
      <th style="padding:4px 12px 4px 0;text-align:right">Rows</th>
      <th style="padding:4px 0">Table</th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>

<p style="color:#888;font-size:12px;margin-top:24px">
  Generated weekly by <code>scripts/disk_report.py</code> on Tuesdays.
  Warn threshold {WARN_PCT}%, fail {FAIL_PCT}%.
</p>
</body></html>
"""


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


def main() -> int:
    now = datetime.now(UTC)
    df = df_root()
    db_pretty, db_bytes = db_total_size()
    tables = top_tables_by_size()
    log_size = log_dir_size()

    text = render_text(now, df, db_pretty, db_bytes, tables, log_size)
    html = render_html(now, df, db_pretty, db_bytes, tables, log_size)
    subject = f"[Jeromelu] Capacity — {now.date().isoformat()} · / {df.use_pct}% · DB {db_pretty}"

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

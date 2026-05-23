"""Daily app-error digest.

Cousin to scripts/cron_report.py — cron-report says "did the scheduled
jobs run". This says "is real user traffic erroring".

Source: `docker logs <container> --since 24h` for jeromelu-api and
jeromelu-web. Counts ERROR-level log lines and exception classes,
shows the latest few examples. No persistent log file is needed —
we scrape the container's stdout each morning.

Schedule: 00:35 UTC daily (10:35 AEST) — five min after cron-report so
the two arrive in the same morning batch.

Limitations:
  - If the container restarted in the last 24h, anything written
    before the restart is lost (docker keeps stdout in-memory until
    restart). Acceptable for V1 — restarts are infrequent and a
    restart itself is usually the cause of the errors anyway.
  - Caddy 5xx counts not included yet — Caddy is configured for
    `format console`, not JSON, so structured parsing is awkward.
"""

from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


PRIMARY_REGION = "ap-southeast-2"
SENDER = "reports@jeromelu.ai"
RECIPIENT = "kristopher.lopez@gmail.com"

CONTAINERS = ["jeromelu-api", "jeromelu-web"]
SINCE = "24h"

# Cap how many sample lines we keep per container so a single noisy
# error doesn't blow out the email.
MAX_SAMPLES_PER_CONTAINER = 5
MAX_TRACEBACK_LINES = 12

# A line counts as an error if it matches any of these patterns.
# Python logging default is `LEVEL:name:msg`. Uvicorn/FastAPI also emit
# `level - msg`. Next.js writes raw Error: messages and stack traces.
ERROR_PATTERN = re.compile(
    r"(?:^|[\s|])(?:ERROR|CRITICAL|FATAL|Error:|Exception:|Traceback)",
    re.IGNORECASE,
)
# Pulls "ModuleNotFoundError", "ValueError", etc. from a traceback's
# final line. Falls back to the first word of the message otherwise.
EXCEPTION_CLASS = re.compile(r"\b([A-Z][A-Za-z0-9_]*(?:Error|Exception|Warning))\b")


@dataclass
class ContainerReport:
    name: str
    available: bool                # docker exec succeeded
    error_count: int = 0
    class_counts: Counter = field(default_factory=Counter)
    samples: list[str] = field(default_factory=list)
    note: str = ""                 # e.g. "container not running"


def fetch_logs(container: str) -> tuple[bool, list[str], str]:
    """Returns (available, lines, note). lines is empty if unavailable."""
    try:
        result = subprocess.run(
            ["docker", "logs", container, "--since", SINCE],
            capture_output=True, text=True, timeout=60,
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return False, [], "docker logs timed out after 60s"
    if result.returncode != 0:
        # Container not running, doesn't exist, etc.
        err = (result.stderr or "").strip().splitlines()[-1:] or [""]
        return False, [], f"docker logs failed: {err[0][:120]}"
    # docker writes everything to stderr by default with --since;
    # combine both for robustness.
    combined = (result.stdout or "") + (result.stderr or "")
    return True, combined.splitlines(), ""


def analyze(lines: list[str]) -> tuple[int, Counter, list[str]]:
    """Walk lines once, tally errors and collect samples."""
    error_count = 0
    classes: Counter = Counter()
    samples: list[str] = []
    in_traceback = False
    traceback_buf: list[str] = []

    for raw in lines:
        line = raw.rstrip()
        if not line:
            in_traceback = False
            continue

        is_error_line = bool(ERROR_PATTERN.search(line))

        if line.startswith("Traceback (most recent call last)"):
            in_traceback = True
            traceback_buf = [line]
            continue

        if in_traceback:
            traceback_buf.append(line)
            # End of traceback = a line at column 0 that names the
            # exception (e.g. "ValueError: bad input").
            if line and not line.startswith(" ") and ":" in line:
                error_count += 1
                m = EXCEPTION_CLASS.search(line)
                cls = m.group(1) if m else line.split(":", 1)[0].strip()
                classes[cls] += 1
                if len(samples) < MAX_SAMPLES_PER_CONTAINER:
                    samples.append(_compact_traceback(traceback_buf))
                in_traceback = False
                traceback_buf = []
            elif len(traceback_buf) > MAX_TRACEBACK_LINES:
                # Runaway traceback (shouldn't happen, but guard).
                in_traceback = False
                traceback_buf = []
            continue

        if is_error_line:
            error_count += 1
            m = EXCEPTION_CLASS.search(line)
            cls = m.group(1) if m else "ERROR"
            classes[cls] += 1
            if len(samples) < MAX_SAMPLES_PER_CONTAINER:
                samples.append(line[:300])

    return error_count, classes, samples


def _compact_traceback(buf: list[str]) -> str:
    """Keep the first line and the last 3, drop the middle frames."""
    if len(buf) <= 4:
        return "\n".join(buf)
    return "\n".join([buf[0], "  ... (frames elided) ...", *buf[-3:]])


def collect() -> list[ContainerReport]:
    reports: list[ContainerReport] = []
    for name in CONTAINERS:
        avail, lines, note = fetch_logs(name)
        if not avail:
            reports.append(ContainerReport(name=name, available=False, note=note))
            continue
        count, classes, samples = analyze(lines)
        reports.append(ContainerReport(
            name=name, available=True,
            error_count=count, class_counts=classes, samples=samples,
        ))
    return reports


# ---- Rendering -------------------------------------------------------------

def render_text(today: datetime, reports: list[ContainerReport]) -> str:
    total = sum(r.error_count for r in reports)
    lines = [
        f"Jeromelu app errors — {today.date().isoformat()}",
        "=" * 60,
        "",
        f"  {total} error line(s) across {len(reports)} container(s) in last {SINCE}",
        "",
    ]
    for r in reports:
        lines.append(f"  {r.name}")
        if not r.available:
            lines.append(f"      ! {r.note}")
            lines.append("")
            continue
        if r.error_count == 0:
            lines.append("      no errors")
            lines.append("")
            continue
        lines.append(f"      {r.error_count} error(s)")
        if r.class_counts:
            top = r.class_counts.most_common(5)
            lines.append("      top classes:")
            for cls, n in top:
                lines.append(f"        {n:>4}  {cls}")
        if r.samples:
            lines.append("      latest:")
            for s in r.samples:
                for sl in s.splitlines():
                    lines.append(f"        {sl}")
                lines.append("")
        lines.append("")
    return "\n".join(lines)


def render_html(today: datetime, reports: list[ContainerReport]) -> str:
    total = sum(r.error_count for r in reports)
    color = "#1a7f37" if total == 0 else "#bf8700" if total < 20 else "#cf222e"
    sections = "".join(_render_container_html(r) for r in reports)
    return f"""\
<!doctype html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:14px;color:#222">
<h2 style="margin:0 0 4px 0">Jeromelu app errors — {today.date().isoformat()}</h2>
<p style="margin:0 0 16px 0;color:{color};font-weight:600">
  {total} error line(s) across {len(reports)} container(s) in last {SINCE}
</p>
{sections}
<p style="color:#888;font-size:12px;margin-top:24px">
  Generated by <code>scripts/error_report.py</code> via
  <code>/etc/cron.d/jeromelu</code> on the Lightsail box.
  Source: <code>docker logs --since {SINCE}</code>. Restarts within the
  window will truncate older lines.
</p>
</body></html>
"""


def _render_container_html(r: ContainerReport) -> str:
    if not r.available:
        return f"""
<div style="margin:0 0 20px 0;padding:12px;border:1px solid #ffd9b3;background:#fff8f0">
  <strong>{r.name}</strong><br>
  <span style="color:#cf222e">{r.note}</span>
</div>"""
    if r.error_count == 0:
        return f"""
<div style="margin:0 0 20px 0;padding:12px;border:1px solid #ddd">
  <strong>{r.name}</strong> · <span style="color:#1a7f37">no errors</span>
</div>"""
    rows = "".join(
        f'<tr><td style="padding:2px 12px 2px 0;text-align:right;font-family:ui-monospace,Menlo,monospace">{n}</td>'
        f'<td style="padding:2px 0">{_html_escape(cls)}</td></tr>'
        for cls, n in r.class_counts.most_common(5)
    )
    samples_html = ""
    if r.samples:
        sample_blocks = "".join(
            f'<pre style="margin:6px 0;padding:6px 8px;background:#f6f8fa;border:1px solid #d0d7de;border-radius:4px;font-size:12px;white-space:pre-wrap;overflow-wrap:anywhere">{_html_escape(s)}</pre>'
            for s in r.samples
        )
        samples_html = f"<div style='margin-top:8px'><div style='color:#666;font-size:12px;margin-bottom:4px'>Latest:</div>{sample_blocks}</div>"
    return f"""
<div style="margin:0 0 20px 0;padding:12px;border:1px solid #ddd">
  <strong>{r.name}</strong> · <span style="color:#bf8700">{r.error_count} error(s)</span>
  <table style="margin-top:8px;border-collapse:collapse">{rows}</table>
  {samples_html}
</div>"""


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


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


def _subject(today: datetime, reports: list[ContainerReport]) -> str:
    total = sum(r.error_count for r in reports)
    if total == 0:
        tag = "0 errors"
    else:
        tag = f"{total} errors"
    return f"[Jeromelu] Errors — {today.date().isoformat()} · {tag}"


def main() -> int:
    now = datetime.now(timezone.utc)
    reports = collect()
    text = render_text(now, reports)
    html = render_html(now, reports)
    subject = _subject(now, reports)
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

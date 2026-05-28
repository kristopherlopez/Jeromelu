"""Weekly content digest.

Different signal from the ops emails — this is the *you-as-product-owner*
report, not the you-as-operator one. Answers "what landed in the system
this week".

Sections (all over a 7-day trailing window):
  - Headline counts: new videos, claims extracted, predictions logged,
    week-over-week aggregate subscriber delta.
  - Top 10 newly-ingested videos by current view count.
  - Top 5 channels by 7-day subscriber growth.
  - Claims by type (count + a small sample).
  - Predictions resolved this week (count by status — usually empty
    until the resolution layer is wired up).

Schedule: Mondays 22:00 UTC = Tuesday 08:00 AEST. Lands after the
weekend's content has settled and before the new week starts.
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


# ---- Data structs ----------------------------------------------------------


@dataclass
class Headline:
    new_videos: int
    new_claims: int
    new_predictions: int
    sub_growth_total: int  # sum of WoW positive deltas across all channels


@dataclass
class VideoRow:
    title: str
    channel: str
    views: int


@dataclass
class ChannelDelta:
    name: str
    subs_now: int
    delta: int


@dataclass
class ClaimTypeRow:
    claim_type: str
    count: int


# ---- Queries ---------------------------------------------------------------


def fetch_headline() -> Headline:
    out = _psql("""
        SELECT
          (SELECT COUNT(*) FROM sources
              WHERE source_type='youtube' AND created_at > now() - interval '7 days'),
          (SELECT COUNT(*) FROM claims WHERE extracted_at > now() - interval '7 days'),
          (SELECT COUNT(*) FROM predictions WHERE created_at > now() - interval '7 days'),
          COALESCE((
            SELECT SUM(GREATEST(0, delta))::bigint FROM (
              SELECT
                (cm_now.metrics->>'subscribers')::int
                  - (cm_ago.metrics->>'subscribers')::int AS delta
              FROM channels c
              JOIN LATERAL (
                SELECT metrics FROM channel_metrics
                WHERE channel_id = c.channel_id
                ORDER BY sampled_at DESC LIMIT 1
              ) cm_now ON true
              JOIN LATERAL (
                SELECT metrics FROM channel_metrics
                WHERE channel_id = c.channel_id
                  AND sampled_at < now() - interval '6 days'
                ORDER BY sampled_at DESC LIMIT 1
              ) cm_ago ON true
              WHERE c.active = true
            ) sub
          ), 0);
    """)
    a, b, c, d = out.split("\t")
    return Headline(int(a), int(b), int(c), int(d))


def fetch_top_new_videos(limit: int = 10) -> list[VideoRow]:
    out = _psql(f"""
        SELECT s.title, COALESCE(c.name, '(no channel)'),
               COALESCE((vlm.metrics->>'views')::bigint, 0)
        FROM sources s
        LEFT JOIN channels c ON c.channel_id = s.channel_id
        LEFT JOIN video_latest_metrics vlm ON vlm.source_id = s.source_id
        WHERE s.source_type='youtube'
          AND s.created_at > now() - interval '7 days'
        ORDER BY COALESCE((vlm.metrics->>'views')::bigint, 0) DESC
        LIMIT {limit};
    """)
    rows: list[VideoRow] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        rows.append(VideoRow(parts[0], parts[1], int(parts[2])))
    return rows


def fetch_channel_velocity(limit: int = 5) -> list[ChannelDelta]:
    out = _psql(f"""
        SELECT c.name,
               (cm_now.metrics->>'subscribers')::int,
               (cm_now.metrics->>'subscribers')::int
                 - (cm_ago.metrics->>'subscribers')::int AS delta
        FROM channels c
        JOIN LATERAL (
          SELECT metrics FROM channel_metrics
          WHERE channel_id = c.channel_id
          ORDER BY sampled_at DESC LIMIT 1
        ) cm_now ON true
        JOIN LATERAL (
          SELECT metrics FROM channel_metrics
          WHERE channel_id = c.channel_id
            AND sampled_at < now() - interval '6 days'
          ORDER BY sampled_at DESC LIMIT 1
        ) cm_ago ON true
        WHERE c.active = true
        ORDER BY delta DESC
        LIMIT {limit};
    """)
    rows: list[ChannelDelta] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        rows.append(ChannelDelta(parts[0], int(parts[1]), int(parts[2])))
    return rows


def fetch_claims_by_type() -> list[ClaimTypeRow]:
    out = _psql("""
        SELECT claim_type, COUNT(*)::bigint
        FROM claims
        WHERE extracted_at > now() - interval '7 days'
        GROUP BY claim_type
        ORDER BY COUNT(*) DESC;
    """)
    rows: list[ClaimTypeRow] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        rows.append(ClaimTypeRow(parts[0], int(parts[1])))
    return rows


def fetch_predictions_resolved() -> list[tuple[str, int]]:
    out = _psql("""
        SELECT COALESCE(resolution_status, '(no status)'), COUNT(*)::bigint
        FROM predictions
        WHERE resolved_at > now() - interval '7 days'
        GROUP BY resolution_status
        ORDER BY COUNT(*) DESC;
    """)
    rows: list[tuple[str, int]] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) != 2:
            continue
        rows.append((parts[0], int(parts[1])))
    return rows


# ---- Rendering -------------------------------------------------------------


def _trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"


def render_text(
    today: datetime,
    h: Headline,
    videos: list[VideoRow],
    channels: list[ChannelDelta],
    claims: list[ClaimTypeRow],
    preds: list[tuple[str, int]],
) -> str:
    L: list[str] = [
        f"Jeromelu content digest — week ending {today.date().isoformat()}",
        "=" * 60,
        "",
        "HEADLINE",
        f"  {h.new_videos:>5}  new videos ingested",
        f"  {h.new_claims:>5}  claims extracted",
        f"  {h.new_predictions:>5}  predictions logged",
        f"  +{h.sub_growth_total:,} subscribers gained across active channels",
        "",
    ]
    L.append(f"TOP {len(videos)} NEW VIDEOS (by current view count)")
    if not videos:
        L.append("  (none)")
    for v in videos:
        L.append(f"  {v.views:>9,}  {_trunc(v.title, 60)}  — {_trunc(v.channel, 30)}")
    L.append("")

    L.append(f"TOP {len(channels)} CHANNEL VELOCITY (subscriber delta, 7d)")
    if not channels:
        L.append("  (none)")
    for c in channels:
        sign = "+" if c.delta >= 0 else ""
        L.append(f"  {sign}{c.delta:>7,}  {_trunc(c.name, 40)}  (now {c.subs_now:,})")
    L.append("")

    L.append("CLAIMS BY TYPE")
    if not claims:
        L.append("  (none this week)")
    for c in claims:
        L.append(f"  {c.count:>5}  {c.claim_type}")
    L.append("")

    L.append("PREDICTIONS RESOLVED")
    if not preds:
        L.append("  (none resolved this week)")
    for status, count in preds:
        L.append(f"  {count:>5}  {status}")
    L.append("")

    return "\n".join(L)


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_html(
    today: datetime,
    h: Headline,
    videos: list[VideoRow],
    channels: list[ChannelDelta],
    claims: list[ClaimTypeRow],
    preds: list[tuple[str, int]],
) -> str:
    def _kpi(num: str, label: str) -> str:
        return f"""
<div style="display:inline-block;margin-right:24px;vertical-align:top">
  <div style="font-size:24px;font-weight:600;color:#222">{num}</div>
  <div style="font-size:12px;color:#666;text-transform:uppercase;letter-spacing:.04em">{label}</div>
</div>"""

    videos_rows = (
        "".join(
            f'<tr style="border-top:1px solid #eee">'
            f'<td style="padding:4px 12px 4px 0;text-align:right;font-family:ui-monospace,Menlo,monospace">{v.views:,}</td>'
            f'<td style="padding:4px 12px 4px 0">{_esc(_trunc(v.title, 70))}</td>'
            f'<td style="padding:4px 0;color:#666">{_esc(_trunc(v.channel, 30))}</td>'
            f"</tr>"
            for v in videos
        )
        or '<tr><td colspan="3" style="padding:8px 0;color:#888">No new videos this week</td></tr>'
    )

    channel_rows = (
        "".join(
            f'<tr style="border-top:1px solid #eee">'
            f'<td style="padding:4px 12px 4px 0;text-align:right;font-family:ui-monospace,Menlo,monospace;color:{"#1a7f37" if c.delta >= 0 else "#cf222e"}">'
            f"{'+' if c.delta >= 0 else ''}{c.delta:,}</td>"
            f'<td style="padding:4px 12px 4px 0">{_esc(_trunc(c.name, 50))}</td>'
            f'<td style="padding:4px 0;color:#666">now {c.subs_now:,}</td>'
            f"</tr>"
            for c in channels
        )
        or '<tr><td colspan="3" style="padding:8px 0;color:#888">No channel-velocity data</td></tr>'
    )

    claims_rows = (
        "".join(
            f'<tr style="border-top:1px solid #eee">'
            f'<td style="padding:4px 12px 4px 0;text-align:right;font-family:ui-monospace,Menlo,monospace">{c.count}</td>'
            f'<td style="padding:4px 0">{_esc(c.claim_type)}</td>'
            f"</tr>"
            for c in claims
        )
        or '<tr><td colspan="2" style="padding:8px 0;color:#888">No claims extracted this week</td></tr>'
    )

    preds_rows = (
        "".join(
            f'<tr style="border-top:1px solid #eee">'
            f'<td style="padding:4px 12px 4px 0;text-align:right;font-family:ui-monospace,Menlo,monospace">{n}</td>'
            f'<td style="padding:4px 0">{_esc(s)}</td>'
            f"</tr>"
            for s, n in preds
        )
        or '<tr><td colspan="2" style="padding:8px 0;color:#888">None resolved this week</td></tr>'
    )

    return f"""\
<!doctype html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:14px;color:#222">
<h2 style="margin:0 0 16px 0">Jeromelu content digest — week ending {today.date().isoformat()}</h2>

<div style="margin:0 0 24px 0">
  {_kpi(f"{h.new_videos:,}", "new videos")}
  {_kpi(f"{h.new_claims:,}", "new claims")}
  {_kpi(f"{h.new_predictions:,}", "new predictions")}
  {_kpi(f"+{h.sub_growth_total:,}", "subs gained")}
</div>

<h3 style="margin:24px 0 4px 0">Top new videos (by view count)</h3>
<table style="border-collapse:collapse;width:100%;max-width:720px">
  <thead><tr style="text-align:left;color:#666;font-size:12px;text-transform:uppercase;letter-spacing:.04em">
    <th style="padding:4px 12px 4px 0;text-align:right">Views</th>
    <th style="padding:4px 12px 4px 0">Title</th>
    <th style="padding:4px 0">Channel</th>
  </tr></thead>
  <tbody>{videos_rows}</tbody>
</table>

<h3 style="margin:24px 0 4px 0">Channel velocity (7-day subscriber delta)</h3>
<table style="border-collapse:collapse;width:100%;max-width:720px">
  <thead><tr style="text-align:left;color:#666;font-size:12px;text-transform:uppercase;letter-spacing:.04em">
    <th style="padding:4px 12px 4px 0;text-align:right">Δ Subs</th>
    <th style="padding:4px 12px 4px 0">Channel</th>
    <th style="padding:4px 0">Current</th>
  </tr></thead>
  <tbody>{channel_rows}</tbody>
</table>

<h3 style="margin:24px 0 4px 0">Claims by type</h3>
<table style="border-collapse:collapse;width:100%;max-width:400px">
  <tbody>{claims_rows}</tbody>
</table>

<h3 style="margin:24px 0 4px 0">Predictions resolved</h3>
<table style="border-collapse:collapse;width:100%;max-width:400px">
  <tbody>{preds_rows}</tbody>
</table>

<p style="color:#888;font-size:12px;margin-top:24px">
  Generated weekly by <code>scripts/content_report.py</code> on Tuesdays.
  Window is the trailing 7 days.
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
    h = fetch_headline()
    videos = fetch_top_new_videos()
    channels = fetch_channel_velocity()
    claims = fetch_claims_by_type()
    preds = fetch_predictions_resolved()

    text = render_text(now, h, videos, channels, claims, preds)
    html = render_html(now, h, videos, channels, claims, preds)
    subject = (
        f"[Jeromelu] Content — {now.date().isoformat()} · "
        f"{h.new_videos} videos · {h.new_claims} claims · +{h.sub_growth_total:,} subs"
    )

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

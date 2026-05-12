"""Daily AWS spend + resource inventory email.

Triggered by .github/workflows/cost-report.yml at 22:00 UTC (08:00 AEST).
Pulls month-to-date spend by service from Cost Explorer, projects month-end
by linear extrapolation, describes the running resources we care about,
and ships an HTML+plaintext email via SES from reports@jeromelu.ai to
kristopher.lopez@gmail.com.

Permissions live in infra/terraform/iam.tf on the `jeromelu-cicd` user
(extends the existing CI policy with ce:GetCostAndUsage, a handful of
describe-* perms, and ses:SendEmail). SES identities are provisioned in
infra/terraform/ses.tf.

Stays in SES sandbox mode — one recipient, ~30 emails/month.
"""

from __future__ import annotations

import calendar
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any

import boto3
from botocore.exceptions import ClientError


# Windows-style stdout fix is harmless on Linux runners; keeps parity with
# services/gpu/deploy.py so a local run from a Windows shell doesn't crash
# on the em-dashes in print statements below.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---- Config ----------------------------------------------------------------

PRIMARY_REGION = "ap-southeast-2"
LINEUP_REGION = "us-east-1"
ENDPOINT_NAME = "jeromelu-lineup-async"
LIGHTSAIL_INSTANCE = "jeromelu"
SENDER = "reports@jeromelu.ai"
RECIPIENT = "kristopher.lopez@gmail.com"

# Min spend (USD) for a service to make the breakdown table.
SPEND_FLOOR = 0.005


# ---- Cost Explorer ---------------------------------------------------------

def fetch_mtd_by_service(today: date) -> tuple[float, list[tuple[str, float]]]:
    """Returns (mtd_total_usd, [(service, usd) sorted desc])."""
    ce = boto3.client("ce", region_name="us-east-1")
    month_start = today.replace(day=1).isoformat()
    end = (today + timedelta(days=1)).isoformat()  # CE end is exclusive
    resp = ce.get_cost_and_usage(
        TimePeriod={"Start": month_start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": "SERVICE"}],
    )
    if not resp["ResultsByTime"]:
        return 0.0, []
    groups = resp["ResultsByTime"][0]["Groups"]
    rows = [
        (g["Keys"][0], float(g["Metrics"]["UnblendedCost"]["Amount"]))
        for g in groups
    ]
    rows = [r for r in rows if r[1] >= SPEND_FLOOR]
    rows.sort(key=lambda x: -x[1])
    total = sum(usd for _, usd in rows)
    return total, rows


def fetch_last_month_total(today: date) -> float:
    """Returns prior-month total spend (USD). 0 if no data."""
    ce = boto3.client("ce", region_name="us-east-1")
    first_of_this_month = today.replace(day=1)
    last_month_end = first_of_this_month  # exclusive
    last_month_start = (first_of_this_month - timedelta(days=1)).replace(day=1)
    resp = ce.get_cost_and_usage(
        TimePeriod={
            "Start": last_month_start.isoformat(),
            "End": last_month_end.isoformat(),
        },
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
    )
    if not resp["ResultsByTime"]:
        return 0.0
    return float(resp["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"])


def project_month_end(mtd: float, today: date) -> float:
    """Linear extrapolation: MTD / days_elapsed * days_in_month.

    Noisy near month-start (Cost Explorer has ~24h lag, so early-month
    projections double-count or undercount intermittently). Good enough for
    a daily glance metric; not for budgeting.
    """
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_elapsed = max(today.day, 1)
    return mtd / days_elapsed * days_in_month


# ---- Resource descriptions -------------------------------------------------

def describe_lightsail() -> dict[str, Any]:
    ls = boto3.client("lightsail", region_name=PRIMARY_REGION)
    inst = ls.get_instance(instanceName=LIGHTSAIL_INSTANCE)["instance"]
    return {
        "bundle": inst["bundleId"],
        "state": inst["state"]["name"],
        "ram_gb": inst["hardware"]["ramSizeInGb"],
        "vcpus": inst["hardware"]["cpuCount"],
        "public_ip": inst.get("publicIpAddress", "-"),
    }


def describe_sagemaker_endpoint() -> dict[str, Any]:
    sm = boto3.client("sagemaker", region_name=LINEUP_REGION)
    try:
        ep = sm.describe_endpoint(EndpointName=ENDPOINT_NAME)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ValidationException":
            return {"status": "not-found"}
        raise

    cfg = sm.describe_endpoint_config(EndpointConfigName=ep["EndpointConfigName"])
    variant_cfg = cfg["ProductionVariants"][0]
    variant_runtime = ep["ProductionVariants"][0]

    asg = boto3.client("application-autoscaling", region_name=LINEUP_REGION)
    target_id = f"endpoint/{ENDPOINT_NAME}/variant/{variant_cfg['VariantName']}"
    targets = asg.describe_scalable_targets(
        ServiceNamespace="sagemaker",
        ResourceIds=[target_id],
    )["ScalableTargets"]
    min_cap = targets[0]["MinCapacity"] if targets else None
    max_cap = targets[0]["MaxCapacity"] if targets else None

    return {
        "status": ep["EndpointStatus"],
        "instance_type": variant_cfg["InstanceType"],
        "desired": variant_runtime["DesiredInstanceCount"],
        "current": variant_runtime["CurrentInstanceCount"],
        "min_capacity": min_cap,
        "max_capacity": max_cap,
    }


def describe_s3_buckets() -> list[str]:
    s3 = boto3.client("s3", region_name=PRIMARY_REGION)
    return sorted(b["Name"] for b in s3.list_buckets()["Buckets"])


# ---- Rendering -------------------------------------------------------------

def _fmt_money(usd: float) -> str:
    return f"${usd:,.2f}"


def render_text(
    today: date,
    mtd_total: float,
    mtd_breakdown: list[tuple[str, float]],
    last_month: float,
    projected: float,
    lightsail: dict[str, Any],
    sagemaker: dict[str, Any],
    s3_buckets: list[str],
) -> str:
    lines: list[str] = []
    lines.append(f"Jeromelu daily AWS report — {today.isoformat()}")
    lines.append("=" * 60)
    lines.append("")
    lines.append("SPEND")
    lines.append(f"  MTD          {_fmt_money(mtd_total)}")
    lines.append(f"  Projected    {_fmt_money(projected)}  (linear extrapolation)")
    lines.append(f"  Last month   {_fmt_money(last_month)}")
    lines.append("")
    lines.append("BY SERVICE (MTD)")
    for service, usd in mtd_breakdown:
        lines.append(f"  {_fmt_money(usd):>10}  {service}")
    lines.append("")
    lines.append("RESOURCES")
    lines.append(
        f"  Lightsail  {lightsail['bundle']} / {lightsail['ram_gb']}GB / "
        f"{lightsail['vcpus']}vCPU / {lightsail['state']} / {lightsail['public_ip']}"
    )
    if sagemaker.get("status") == "not-found":
        lines.append("  SageMaker  endpoint not found")
    else:
        scale = (
            f"min={sagemaker['min_capacity']} max={sagemaker['max_capacity']}"
            if sagemaker["min_capacity"] is not None
            else "no autoscaling target"
        )
        lines.append(
            f"  SageMaker  {sagemaker['instance_type']} / status={sagemaker['status']} / "
            f"desired={sagemaker['desired']} current={sagemaker['current']} / {scale}"
        )
    lines.append(f"  S3 buckets ({len(s3_buckets)}):")
    for name in s3_buckets:
        lines.append(f"    - {name}")
    lines.append("")
    return "\n".join(lines)


def render_html(
    today: date,
    mtd_total: float,
    mtd_breakdown: list[tuple[str, float]],
    last_month: float,
    projected: float,
    lightsail: dict[str, Any],
    sagemaker: dict[str, Any],
    s3_buckets: list[str],
) -> str:
    rows = "".join(
        f'<tr><td style="padding:2px 12px 2px 0">{service}</td>'
        f'<td style="padding:2px 0;text-align:right">{_fmt_money(usd)}</td></tr>'
        for service, usd in mtd_breakdown
    )
    if sagemaker.get("status") == "not-found":
        sm_line = "endpoint not found"
    else:
        scale = (
            f"min={sagemaker['min_capacity']} max={sagemaker['max_capacity']}"
            if sagemaker["min_capacity"] is not None
            else "no autoscaling target"
        )
        sm_line = (
            f"{sagemaker['instance_type']} · {sagemaker['status']} · "
            f"desired={sagemaker['desired']} current={sagemaker['current']} · {scale}"
        )
    buckets_li = "".join(f"<li>{n}</li>" for n in s3_buckets)
    return f"""\
<!doctype html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:14px;color:#222">
<h2 style="margin:0 0 12px 0">Jeromelu AWS report — {today.isoformat()}</h2>

<h3 style="margin:16px 0 4px 0">Spend</h3>
<table style="border-collapse:collapse">
  <tr><td style="padding:2px 16px 2px 0">MTD</td><td><strong>{_fmt_money(mtd_total)}</strong></td></tr>
  <tr><td style="padding:2px 16px 2px 0">Projected month-end</td><td>{_fmt_money(projected)} <span style="color:#888">(linear)</span></td></tr>
  <tr><td style="padding:2px 16px 2px 0">Last month total</td><td>{_fmt_money(last_month)}</td></tr>
</table>

<h3 style="margin:16px 0 4px 0">By service (MTD)</h3>
<table style="border-collapse:collapse">{rows}</table>

<h3 style="margin:16px 0 4px 0">Resources</h3>
<table style="border-collapse:collapse">
  <tr><td style="padding:2px 16px 2px 0;vertical-align:top">Lightsail</td>
      <td>{lightsail['bundle']} · {lightsail['ram_gb']} GB · {lightsail['vcpus']} vCPU · {lightsail['state']} · {lightsail['public_ip']}</td></tr>
  <tr><td style="padding:2px 16px 2px 0;vertical-align:top">SageMaker</td><td>{sm_line}</td></tr>
  <tr><td style="padding:2px 16px 2px 0;vertical-align:top">S3 buckets ({len(s3_buckets)})</td><td><ul style="margin:0;padding-left:20px">{buckets_li}</ul></td></tr>
</table>

<p style="color:#888;font-size:12px;margin-top:24px">
  Generated by <code>scripts/cost_report.py</code> via
  <code>.github/workflows/cost-report.yml</code>.
  Projection assumes a flat daily run-rate; ignore the figure in the first 3 days of the month.
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
    today = datetime.now(timezone.utc).date()

    mtd_total, mtd_breakdown = fetch_mtd_by_service(today)
    last_month = fetch_last_month_total(today)
    projected = project_month_end(mtd_total, today)
    lightsail = describe_lightsail()
    sagemaker = describe_sagemaker_endpoint()
    s3_buckets = describe_s3_buckets()

    text = render_text(
        today, mtd_total, mtd_breakdown, last_month, projected,
        lightsail, sagemaker, s3_buckets,
    )
    html = render_html(
        today, mtd_total, mtd_breakdown, last_month, projected,
        lightsail, sagemaker, s3_buckets,
    )

    subject = f"[Jeromelu] AWS — {today.isoformat()} · MTD {_fmt_money(mtd_total)} · proj {_fmt_money(projected)}"

    print(text)
    print("---sending---")
    send_email(subject=subject, html=html, text=text)
    print("sent OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())

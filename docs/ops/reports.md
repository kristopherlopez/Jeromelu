---
tags: [area/operations]
---

# Scheduled reports

Single source of truth for **every email Jeromelu sends to me**. Anything that arrives in `kristopher.lopez@gmail.com` from `reports@jeromelu.ai` is described here, including what data drives it and where to change it.

All emails ship through AWS SES (sandbox mode — verified sender + verified recipient). Domain identity (`jeromelu.ai`, DKIM via Route53) and email identity (`kristopher.lopez@gmail.com`) are provisioned in [`infra/terraform/ses.tf`](../../infra/terraform/ses.tf). Sending permissions are granted to two IAM users — see the matrix at the bottom.

## At a glance

| Report | Frequency | Lands at (AEST) | Source | Where it runs |
|---|---|---|---|---|
| AWS cost + inventory | Daily | 08:00 | Cost Explorer + describe-* APIs | GitHub Actions |
| Cron health digest | Daily | 10:30 | DB heartbeats + log files + S3 + GitHub Actions API | Lightsail cron |
| App errors | Daily | 10:35 | `docker logs --since 24h` on api + web | Lightsail cron |
| Content digest | Weekly (Tue) | 08:00 | Postgres queries — sources, claims, channel metrics | Lightsail cron |
| Capacity | Weekly (Tue) | 08:30 | `df -h`, `pg_database_size`, `pg_stat_user_tables` | Lightsail cron |

**Daily inbox load:** 3 emails. **Weekly extras:** 2 emails on Tuesday mornings (right after the dailies).

**Dead-man's-switch contract:** if any *daily* email is missing for two consecutive mornings, the box or SES is likely down — check Lightsail dashboard first, then SES sending statistics in the AWS console.

---

## Detailed view

### 1. AWS cost + inventory — `cost-report.yml`

| Aspect | Detail |
|---|---|
| Cadence | Daily, `0 22 * * *` UTC (08:00 AEST) |
| Trigger | [`.github/workflows/cost-report.yml`](../../.github/workflows/cost-report.yml) — GitHub Actions cron |
| Script | [`scripts/cost_report.py`](../../scripts/cost_report.py) |
| IAM identity | `jeromelu-cicd` (GHA secrets) — Cost Explorer, describe-* on Lightsail/SageMaker/S3, scoped SES send |
| Subject | `[Jeromelu] AWS — <date> · MTD $X · proj $Y` |

**Contents:** MTD spend, by-service breakdown, linear month-end projection from yesterday's daily rate, prior-month total, running Lightsail/SageMaker/S3 inventory.

**Why GHA, not the box:** Cost Explorer is account-scoped; no DB or local logs needed. Keeps the IAM cleanly scoped to the cicd user.

**Re-run manually:** `gh workflow run cost-report.yml`

### 2. Cron health digest — `cron_report.py`

| Aspect | Detail |
|---|---|
| Cadence | Daily, `30 0 * * *` UTC (10:30 AEST) |
| Trigger | [`scripts/cron.d/jeromelu`](../../scripts/cron.d/jeromelu) — Lightsail cron |
| Script | [`scripts/cron_report.py`](../../scripts/cron_report.py) via `cron-report.sh` |
| IAM identity | `jeromelu-instance` — SES send (statement `SESSendCronReport`) |
| Subject | `[Jeromelu] Cron — <date> · N ok` (or `· ⚠ N warn` / `· ✗ N fail`) |

**Contents:** One row per scheduled job covering the trailing 24h:

| Job | "Did it run?" | "What it did" |
|---|---|---|
| GHA cost-report | GitHub Actions REST API | Workflow conclusion |
| Scout: channel-stats | `scout-refresh.log` — `status=` and `curl_rc=` | DB: rows + distinct channels in `channel_metrics` |
| Scout: videos | Same file, `videos` lines | DB: rows + distinct videos in `video_metrics`, plus count of new `sources(source_type='youtube')` rows |
| pg-backup | S3 `list_objects_v2` on `backups/postgres/` — newest object | Backup key + size |

Status logic:

| Status | Means |
|---|---|
| `✓ ok` | Ran in window AND exit clean AND wrote rows |
| `⚠ warn` | Ran but exited non-clean, or wrote zero rows on a "should always write" job, or status couldn't be determined |
| `✗ fail` | No evidence of a run in the 25h window, or HTTP non-2xx |

**Required env** in `/opt/jeromelu/.env`:

| Var | Purpose | Required? |
|---|---|---|
| `POSTGRES_USER`, `POSTGRES_DB` | `docker exec ... psql` | Already present |
| `GITHUB_TOKEN` | Fine-grained PAT, `Actions: read` on this repo | Optional — without it the cost-report row degrades to `⚠ warn (status unknown)` |

### 3. App errors — `error_report.py`

| Aspect | Detail |
|---|---|
| Cadence | Daily, `35 0 * * *` UTC (10:35 AEST) |
| Script | [`scripts/error_report.py`](../../scripts/error_report.py) via `error-report.sh` |
| IAM identity | `jeromelu-instance` — SES send |
| Subject | `[Jeromelu] Errors — <date> · N errors` |

**Contents:** Per container, last 24h:
- Total ERROR-level log line count
- Top 5 exception classes by occurrence (parsed from tracebacks + `ERROR`/`Exception` patterns)
- Up to 5 sample lines (full traceback for exceptions, compacted to first + last 3 frames)

**Sources:** `docker logs jeromelu-api --since 24h` and `docker logs jeromelu-web --since 24h`. No persistent log file — relies on Docker's in-memory stdout buffer (cleared on container restart).

**Known limits:**
- Caddy 5xx counts not included — Caddy is configured for `format console`, not JSON. Add later by switching to `format json` and parsing access lines.
- A container restart during the 24h window truncates older lines.

### 4. Content digest — `content_report.py`

| Aspect | Detail |
|---|---|
| Cadence | Weekly Monday, `0 22 * * 1` UTC (Tuesday 08:00 AEST) |
| Script | [`scripts/content_report.py`](../../scripts/content_report.py) via `content-report.sh` |
| IAM identity | `jeromelu-instance` — SES send |
| Subject | `[Jeromelu] Content — <date> · N videos · M claims · +K subs` |

**Contents:** Trailing 7-day window:

| Section | Source query |
|---|---|
| Headline (new videos / claims / predictions / sub growth) | Counts on `sources`, `claims`, `predictions`, `channel_metrics` |
| Top 10 new videos | `sources` joined to `video_latest_metrics`, ordered by current views |
| Top 5 channel velocity | `channel_metrics` — latest vs 7d-ago lateral joins, ordered by subscriber delta |
| Claims by type | `claims` grouped by `claim_type` over the window |
| Predictions resolved | `predictions` grouped by `resolution_status` where `resolved_at > now() - 7d` |

The predictions section will usually be empty until the resolution-tracking layer is wired up — leaving it visible as a placeholder.

### 5. Capacity — `disk_report.py`

| Aspect | Detail |
|---|---|
| Cadence | Weekly Monday, `30 22 * * 1` UTC (Tuesday 08:30 AEST) |
| Script | [`scripts/disk_report.py`](../../scripts/disk_report.py) via `disk-report.sh` |
| IAM identity | `jeromelu-instance` — SES send |
| Subject | `[Jeromelu] Capacity — <date> · / X% · DB Y GB` |
| Status thresholds | `<70%` green · `70-85%` warn · `≥85%` fail |

**Contents:**
- Root filesystem usage (`df -h /`) — used/total/free/percent
- `/var/log/jeromelu` size
- Postgres database total size (`pg_database_size(current_database())`)
- Top 10 tables by total relation size (heap + indexes + TOAST), with row counts

**Why weekly, not daily:** Capacity moves slowly. Daily noise teaches you to ignore the signal that matters.

---

## Operational reference

### IAM matrix

| Email | IAM identity | Statement granting SES |
|---|---|---|
| Cost + inventory | `jeromelu-cicd` (GHA secrets) | `SESSendCostReport` in [`infra/terraform/iam.tf`](../../infra/terraform/iam.tf) |
| Cron health, App errors, Content, Capacity | `jeromelu-instance` (box-local AWS creds) | `SESSendCronReport` in same file |

Both grants are scoped to the existing `aws_ses_domain_identity.jeromelu` (sender) and `aws_ses_email_identity.kris` (recipient) ARNs in [`infra/terraform/ses.tf`](../../infra/terraform/ses.tf).

### Logs

Each cron writes its full stdout to a per-report file under `/var/log/jeromelu/`:

| Log file | Producer |
|---|---|
| `cron-report.log` | cron-report (text version of each digest sent) |
| `error-report.log` | error-report |
| `content-report.log` | content-report |
| `disk-report.log` | disk-report |
| `scout-refresh.log` | scout-refresh.sh runs (consumed by cron-report) |
| `pg-backup.log` | pg-backup runs |

No log rotation today. The disk-report will catch it when `/var/log/jeromelu` grows visibly.

### Test any report without waiting for cron

```bash
ssh jeromelu-prod
. /opt/jeromelu/.env
python3 /opt/jeromelu/scripts/<report>.py
```

Where `<report>` is `cron_report`, `error_report`, `content_report`, or `disk_report`. Cost report runs in GHA only — use `gh workflow run cost-report.yml` instead.

Every script prints its plaintext body to stdout, then `---sending---`, then `sent OK` (or the SES error). To dry-run without actually sending, comment out the `send_email(...)` call in `main()` — there is no `--dry-run` flag in any of the scripts.

### Adding a new report

The Lightsail-cron pattern is unsurprising — copy any of `error_report.py` + `error-report.sh` + the cron line. Heuristics:

- **Run on the box** when the report needs DB access or local logs. Add SES via the existing `SESSendCronReport` grant — no Terraform change needed.
- **Run in GHA** only when the data lives in AWS account-scoped APIs (Cost Explorer, IAM Access Analyzer, etc.).
- **Daily vs weekly:** match the cadence to how fast the signal moves. Operational stuff that can break overnight → daily. Aggregates that move on a weekly horizon → weekly. Default to weekly when in doubt; inbox noise erodes the value of the alert that actually matters.
- **Schedule slot:** avoid bunching. The current map is 22:00–22:30 UTC for weekend roll-ups (Mon nights), 00:30–00:35 UTC for daily ops, 22:00 UTC for GHA cost.

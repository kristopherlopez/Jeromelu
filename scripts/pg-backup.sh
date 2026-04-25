#!/usr/bin/env bash
# Nightly Postgres backup → S3.
#
# Install on Lightsail as a cron entry (runs 02:30 Sydney = 16:30 UTC):
#   30 16 * * * /opt/jeromelu/scripts/pg-backup.sh >> /var/log/jeromelu-backup.log 2>&1
#
# Retention: S3 lifecycle on jeromelu-public-assets/backups/ deletes after 30 days.
# Storage cost at 30d × ~5MB/day ≈ $0.003/mo.

set -euo pipefail

BUCKET="jeromelu-public-assets"
PREFIX="backups/postgres"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
KEY="${PREFIX}/jeromelu-${TS}.sql.gz"
TMP="/tmp/jeromelu-${TS}.sql.gz"

# Stream pg_dump from the running container; gzip; upload; delete tmp.
docker exec -t jeromelu-postgres \
	pg_dump -U jeromelu_admin -d jeromelu --format=plain --no-owner \
	| gzip -9 > "$TMP"

aws s3 cp "$TMP" "s3://${BUCKET}/${KEY}" \
	--region ap-southeast-2 \
	--storage-class STANDARD_IA

rm -f "$TMP"

echo "[$(date -u +%FT%TZ)] backup ok: s3://${BUCKET}/${KEY} ($(du -h "$TMP" 2>/dev/null | cut -f1 || echo n/a))"

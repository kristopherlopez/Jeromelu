#!/usr/bin/env bash
# Pull latest images and restart the prod compose stack on Lightsail.
#
# Runs on the Lightsail box itself. Invoked locally via:
#   ssh jeromelu-prod 'IMAGE_TAG=<sha> /opt/jeromelu/scripts/lightsail-deploy.sh'
# or by GitHub Actions over SSH.
#
# Expects:
#   - /opt/jeromelu          checkout of this repo (or just docker/ + scripts/)
#   - /opt/jeromelu/.env     runtime secrets (POSTGRES_PASSWORD, OPENAI_API_KEY, ...)
#   - aws CLI authenticated  for `aws ecr get-login-password`
#   - IMAGE_TAG              optional: pin to a specific git sha for rollback;
#                            defaults to "latest". CI does NOT pass a sha because
#                            path-filter builds only one of api/web per push, so
#                            a single SHA tag won't exist for the unchanged image.

set -euo pipefail

cd /opt/jeromelu/docker

export IMAGE_TAG="${IMAGE_TAG:-latest}"
export ECR_REGISTRY="111424988703.dkr.ecr.ap-southeast-2.amazonaws.com"

# Authenticate Docker with ECR (cred valid 12h)
aws ecr get-login-password --region ap-southeast-2 \
	| docker login --username AWS --password-stdin "$ECR_REGISTRY"

# Pull only the app images (postgres + caddy use public registry)
docker compose -f docker-compose.prod.yml --env-file /opt/jeromelu/.env pull web api

# Recreate web + api with new image; postgres + caddy stay running
docker compose -f docker-compose.prod.yml --env-file /opt/jeromelu/.env up -d web api

# Prune old images to free disk (keeps the current ones — they're tagged in compose)
docker image prune -f

# Sync the checked-in cron schedule into /etc/cron.d/. The `ubuntu` deploy
# user has NOPASSWD:ALL via cloud-init's /etc/sudoers.d/90-cloud-init-users,
# so this just works. -n forces non-interactive sudo — if the sudoers
# config is ever tightened, a missing rule will fail the deploy loudly
# rather than blocking on a prompt.
sudo -n install -m 0644 -o root -g root \
	/opt/jeromelu/scripts/cron.d/jeromelu \
	/etc/cron.d/jeromelu
chmod +x /opt/jeromelu/scripts/scout-refresh.sh /opt/jeromelu/scripts/pg-backup.sh

echo "deployed IMAGE_TAG=$IMAGE_TAG at $(date -u +%FT%TZ)"

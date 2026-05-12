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

# Roll services one at a time. The Lightsail box is a 1GB micro_3_2 — pulling
# three new images in parallel while three old containers still run peaks RAM
# over the cliff, the OS swaps to death, dockerd hangs, and the runner stops
# responding mid-deploy. Stopping the old container BEFORE the pull frees the
# memory the pull + extract needs. Brief per-service downtime (api ~30s, web
# ~60s for Next.js cold start, video-worker invisible) is the trade.
COMPOSE=(docker compose -f docker-compose.prod.yml --env-file /opt/jeromelu/.env)
for svc in api web video-worker; do
	echo ">>> rolling $svc ($(date -u +%FT%TZ))"
	"${COMPOSE[@]}" stop "$svc" || true
	"${COMPOSE[@]}" pull "$svc"
	"${COMPOSE[@]}" up -d --no-deps "$svc"
	# Free the just-replaced image promptly so the next service's pull has headroom.
	docker image prune -f
done

# Sync the checked-in cron schedule into /etc/cron.d/. The `ubuntu` deploy
# user has NOPASSWD:ALL via cloud-init's /etc/sudoers.d/90-cloud-init-users,
# so this just works. -n forces non-interactive sudo — if the sudoers
# config is ever tightened, a missing rule will fail the deploy loudly
# rather than blocking on a prompt.
sudo -n install -m 0644 -o root -g root \
	/opt/jeromelu/scripts/cron.d/jeromelu \
	/etc/cron.d/jeromelu
# Belt-and-braces: most scripts/*.sh are committed with mode 0755, but new
# files added from a Windows checkout default to 0644. Re-asserting the bit
# every deploy means a freshly added cron script never silently fails to run.
chmod +x /opt/jeromelu/scripts/*.sh

echo "deployed IMAGE_TAG=$IMAGE_TAG at $(date -u +%FT%TZ)"

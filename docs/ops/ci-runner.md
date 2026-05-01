---
tags: [area/operations]
---

# CI deploy runner

GitHub Actions deploys to prod by running the `deploy-lightsail` job on a
**self-hosted runner installed on the Lightsail box itself**, not via SSH
from a GitHub-hosted runner. This keeps Lightsail's port 22 locked to the
operator's IP and removes a moving-target firewall problem.

## Why self-hosted

The Lightsail firewall restricts port 22 to a single CIDR (the operator's
home IP) so the prod Postgres can be reached safely over an SSH tunnel.
GitHub-hosted runners use a churning pool of public IPs that we cannot
reasonably whitelist. A self-hosted runner connects **outbound** to GitHub
and pulls jobs, so no inbound port is needed.

## Topology

| Piece | Detail |
|---|---|
| Box | Lightsail instance `jeromelu` (Ubuntu 22.04 x86_64) |
| Install path | `/opt/actions-runner` |
| Runs as | system user `ubuntu` (member of `docker` group) |
| Service | systemd unit `actions.runner.kristopherlopez-Jeromelu.jeromelu-prod.service` |
| Labels | `self-hosted`, `linux`, `x64`, `jeromelu-prod` |
| Targeted by | `deploy-lightsail` job in `.github/workflows/deploy.yml` |

The runner runs as `ubuntu` rather than a fresh user because that account
already owns `/opt/jeromelu`, has docker socket access, and has working
AWS creds for `aws ecr get-login-password`. The deploy already executed
under this identity over SSH; the self-hosted runner is the same identity
with a different transport. This trade is acceptable because the repo is
private and single-author — anyone able to push to `master` already has
deploy capability.

## Initial setup

```bash
# 1. Mint a registration token (valid 1 hour) from a local machine with `gh` auth
gh api -X POST repos/kristopherlopez/Jeromelu/actions/runners/registration-token \
  --jq '.token'

# 2. On the box, install and register
ssh jeromelu-prod
sudo mkdir -p /opt/actions-runner && sudo chown ubuntu:ubuntu /opt/actions-runner
cd /opt/actions-runner
curl -fsSL -o runner.tar.gz \
  https://github.com/actions/runner/releases/download/v2.334.0/actions-runner-linux-x64-2.334.0.tar.gz
tar xzf runner.tar.gz && rm runner.tar.gz

./config.sh \
  --url https://github.com/kristopherlopez/Jeromelu \
  --token <TOKEN> \
  --name jeromelu-prod \
  --labels self-hosted,linux,x64,jeromelu-prod \
  --work _work \
  --unattended --replace

sudo ./svc.sh install ubuntu
sudo ./svc.sh start
```

## Operating

| Task | Command |
|---|---|
| Status | `sudo /opt/actions-runner/svc.sh status` |
| Restart | `sudo /opt/actions-runner/svc.sh stop && sudo /opt/actions-runner/svc.sh start` |
| Logs | `sudo journalctl -u actions.runner.kristopherlopez-Jeromelu.jeromelu-prod -f` |
| Confirm online (from anywhere) | `gh api repos/kristopherlopez/Jeromelu/actions/runners` |
| Upgrade | the runner self-updates when GitHub publishes a newer version |

## Removal / re-registration

If the runner needs to be torn down (e.g. moving boxes):

```bash
# On the box
sudo /opt/actions-runner/svc.sh stop
sudo /opt/actions-runner/svc.sh uninstall
cd /opt/actions-runner
./config.sh remove --token <REMOVE_TOKEN>   # mint via gh api .../remove-token
sudo rm -rf /opt/actions-runner
```

## Migrations

The `migrate` job in `.github/workflows/deploy.yml` is intentionally
notify-only — it does not auto-apply schema changes. After CI deploys
new code that depends on a migration, apply it from the box:

```bash
ssh jeromelu-prod
cd /opt/jeromelu
set -a; . ./.env; set +a
DATABASE_URL="postgresql://${POSTGRES_USER:-jeromelu_admin}:${POSTGRES_PASSWORD}@localhost:5432/${POSTGRES_DB:-jeromelu}" \
  bash packages/db/migrate.sh
```

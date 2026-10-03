#!/usr/bin/env bash
# One-time setup on a fresh Ubuntu 24.04 VPS. Run as a sudo user:
#   curl -fsSL https://raw.githubusercontent.com/... (private repo: copy this file over with scp)
#   bash bootstrap.sh git@github.com:dkmiller321/openingsoonfl.git
# Installs Docker, clones the repo, creates .env from the production template, starts the stack,
# and adds a nightly database backup. Re-running it is safe.
set -euo pipefail
REPO="${1:?usage: bootstrap.sh <git clone url>}"
DIR="$HOME/openingsoonfl"

if ! command -v docker >/dev/null; then
  sudo apt-get update -y
  sudo apt-get install -y ca-certificates curl git ufw
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
fi

sudo ufw allow OpenSSH >/dev/null
sudo ufw allow 80/tcp >/dev/null
sudo ufw allow 443/tcp >/dev/null
sudo ufw --force enable >/dev/null

if [ ! -d "$DIR/.git" ]; then
  git clone "$REPO" "$DIR"
fi
cd "$DIR"
git pull --ff-only

if [ ! -f .env ]; then
  cp deploy/env.production.example .env
  pg=$(openssl rand -hex 16)
  sess=$(openssl rand -base64 32 | tr -d '=+/')
  sed -i "s/^POSTGRES_PASSWORD=$/POSTGRES_PASSWORD=$pg/" .env
  sed -i "s/CHANGE-TO-POSTGRES_PASSWORD/$pg/" .env
  sed -i "s/^SESSION_SECRET=$/SESSION_SECRET=$sess/" .env
  echo "Created .env with generated database password and session secret."
  echo "Now fill the blanks (DOMAIN, ADMIN_PASSWORD, OPERATOR_*, RESEND_API_KEY, MAPBOX_TOKEN):"
  echo "  nano $DIR/.env   then re-run this script."
  exit 0
fi

for key in DOMAIN ADMIN_PASSWORD OPERATOR_EMAIL OPERATOR_POSTAL_ADDRESS RESEND_API_KEY; do
  if ! grep -Eq "^${key}=.+" .env; then echo "Fill ${key} in .env first."; exit 1; fi
done

sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

mkdir -p "$HOME/backups"
CRON="30 3 * * * cd $DIR && docker compose exec -T postgres pg_dump -U osfl -Fc osfl > $HOME/backups/osfl-\$(date +\%F).dump && find $HOME/backups -name 'osfl-*.dump' -mtime +14 -delete"
( crontab -l 2>/dev/null | grep -v 'osfl-' ; echo "$CRON" ) | crontab -

echo "Started. Check: https://$(grep ^DOMAIN= .env | cut -d= -f2)/health"
echo "First data load: sudo docker compose exec app osfl import-plan-review --county brevard && sudo docker compose exec app osfl import-weekly --county brevard"

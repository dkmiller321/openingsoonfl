# DEPLOY.md — running OpeningSoon FL on a VPS

One small Linux VPS runs everything: the app container (web admin, imports, digests, scheduler) and Postgres, behind Caddy for HTTPS. Expect about $6–12/month.

## 1. Prerequisites

- A VPS with 1 vCPU, 1–2 GB RAM and 20 GB disk (Ubuntu 24.04 LTS), for example Hetzner CX22, DigitalOcean Basic or Vultr.
- A domain, with an `A` record for the admin host pointing at the VPS (for example `app.openingsoonfl.com`).
- A sending domain verified in Resend (section 5).
- On the VPS, as a sudo user:

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-v2 git caddy
sudo usermod -aG docker $USER   # log out and back in
git clone <your repo url> openingsoonfl && cd openingsoonfl
```

## 2. Production `.env`

Copy `.env.example` to `.env` and change these values. Leave the rest at their defaults.

| Variable | Production value |
|---|---|
| `POSTGRES_PASSWORD` | A long random string. Also put it into `DATABASE_URL` (Compose overrides the host to `postgres`) |
| `ADMIN_PASSWORD` | A long random password. It's the only login |
| `SESSION_SECRET` | `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` |
| `OPERATOR_EMAIL` | Where alerts and test digests go |
| `OPERATOR_POSTAL_ADDRESS` | Your real mailing address (CAN-SPAM requires it in every digest) |
| `APP_BASE_URL` | `https://app.openingsoonfl.com` (used in unsubscribe links, and switches on secure cookies) |
| `SOURCE_MODE` | `live` |
| `FETCH_USER_AGENT` | `OpeningSoonFL/1.0 (+mailto:you@yourdomain.com)` |
| `EMAIL_MODE` | `resend` |
| `RESEND_API_KEY` | From resend.com, API Keys (sending access only) |
| `EMAIL_FROM` | `OpeningSoon FL <leads@yourdomain.com>`, on the verified domain |
| `SCHEDULER_ENABLED` | `1` |
| `TEST_ROUTES` | `0` (never `1` in production) |
| `APP_HOST_PORT` | `8010` (Caddy proxies to it; it stays bound to 127.0.0.1) |
| `MAX_VENDORS_PER_CATEGORY` | Your exclusivity promise, for example `3` |

Then start it:

```bash
docker compose up -d --build
curl -s http://127.0.0.1:8010/health          # {"status":"ok","db":"ok"}
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:8010/test/reset   # 404
```

Migrations run automatically when the container starts (`scripts/entrypoint.sh`).

## 3. Caddy reverse proxy with HTTPS

`/etc/caddy/Caddyfile`:

```
app.openingsoonfl.com {
    encode gzip
    reverse_proxy 127.0.0.1:8010
}
```

```bash
sudo systemctl reload caddy
```

Caddy gets and renews the TLS certificate automatically. Then open `https://app.openingsoonfl.com/login`.

## 4. Backups (`pg_dump` cron)

```bash
mkdir -p ~/backups
crontab -e
# daily 03:30 server time; keep 14 days
30 3 * * * cd ~/openingsoonfl && docker compose exec -T postgres pg_dump -U osfl -Fc osfl > ~/backups/osfl-$(date +\%F).dump && find ~/backups -name 'osfl-*.dump' -mtime +14 -delete
```

Restore: `docker compose exec -T postgres pg_restore -U osfl -d osfl --clean < ~/backups/osfl-YYYY-MM-DD.dump`. Copy the backups off the server too (for example with `rclone` to S3 or B2) every so often.

## 5. Resend domain verification (SPF/DKIM)

1. In Resend, go to Domains, add `yourdomain.com` (or a subdomain such as `mail.yourdomain.com`), and choose the closest region.
2. Add the DNS records Resend shows at your DNS host: the DKIM `TXT` record(s), the SPF `TXT`/`MX` records on the `send` subdomain, and optionally a DMARC record such as `_dmarc TXT "v=DMARC1; p=none; rua=mailto:you@yourdomain.com"`.
3. Wait until Resend marks the domain Verified. Then send yourself a test: Vendors, then Preview digest, then **Send test to me**.
4. Check the received email's headers for `spf=pass` and `dkim=pass`.

## 6. Checking the scheduler is running

The scheduler runs inside the app container with these jobs, all in ET:

| Job | When |
|---|---|
| plan-review import | 05:00 daily |
| licence import | 06:00 daily |
| daily digests | 07:00 daily |
| weekly digests | Monday 07:00 |
| health check | :15 past each hour |

- On start, the app logs each job's next run:

  ```bash
  docker compose logs app | grep scheduler
  # scheduler: import-weekly next run 2026-10-04T06:00:00-04:00 ...
  ```

- Each run is visible afterwards on `/sources` (trigger `scheduled`), and logged as `scheduled <job> -> {...}`.
- If a source fails, returns zero rows, changes its columns, or has had no good run for 8 days (licences) or 36 hours (plan reviews), you get an email: `[OpeningSoon FL] Source problem: ...`.
- Run a job by hand: `docker compose exec app osfl import-weekly --county brevard` (or `import-plan-review`, `send-digests --cadence weekly`, `check-health`).

## 7. Updating

```bash
git pull && docker compose up -d --build
```

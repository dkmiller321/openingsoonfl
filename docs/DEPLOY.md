# DEPLOY.md — running OpeningSoon FL on a VPS

One small Linux VPS runs everything: the app container (web admin, imports, digests, scheduler) and Postgres, behind Caddy for HTTPS. Expect about $6–12/month.

## 1. Prerequisites

- A VPS with 1 vCPU, 1–2 GB RAM and 20 GB disk (Ubuntu 24.04 LTS), for example Hetzner CX22, DigitalOcean Basic or Vultr.
- A domain, with an `A` record for the admin host pointing at the VPS (for example `app.openingsoonfl.com`).
- A sending domain verified in Resend (section 5).
- GitHub access from the server for the private repo: a read-only deploy key (repo, then Settings, then Deploy keys), or clone over HTTPS with a token.

## 2. One-script setup

Copy `deploy/bootstrap.sh` to the server, then run:

```bash
bash bootstrap.sh git@github.com:dkmiller321/openingsoonfl.git
```

- **First run:** it installs Docker and a firewall (SSH, 80, 443), clones the repo, and creates `.env` from `deploy/env.production.example` with a generated database password and session secret. Then it stops so you can fill the blanks:

  | Variable | Value |
  |---|---|
  | `DOMAIN`, `APP_BASE_URL` | Your admin host, for example `app.openingsoonfl.com` and `https://app.openingsoonfl.com` |
  | `ADMIN_PASSWORD` | A long random password (the only login) |
  | `OPERATOR_EMAIL`, `OPERATOR_POSTAL_ADDRESS` | Alerts and test sends; your real mailing address for the CAN-SPAM footer |
  | `RESEND_API_KEY`, `EMAIL_FROM` | From Resend, on the verified domain |
  | `MAPBOX_TOKEN` | Optional, for Mapbox basemaps |
  | `FETCH_USER_AGENT` | Include a real contact email |

- **Second run:** it starts the stack (`docker-compose.yml` + `docker-compose.prod.yml`: app, Postgres, Caddy with automatic HTTPS, scheduler on, test routes off) and adds the nightly backup.

The first data load (afterwards the scheduler takes over daily):

```bash
sudo docker compose exec app osfl import-plan-review --county brevard
sudo docker compose exec app osfl import-weekly --county brevard
```

Check `https://<DOMAIN>/health` → `{"status":"ok","db":"ok"}`, and that `POST /test/reset` returns 404.

## 3. HTTPS

Caddy runs as a Compose service (`deploy/Caddyfile`) and gets and renews the Let's Encrypt certificate for `DOMAIN` by itself. It also sets HSTS, nosniff and referrer-policy headers. Nothing to install on the host.

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
git pull && sudo docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

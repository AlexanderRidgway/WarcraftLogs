# crankguild.com Domain Setup — Design

**Status:** Approved
**Date:** 2026-03-01

## Goal

Connect the domain `crankguild.com` (registered at Cloudflare) to the guild website running on EC2.

## Architecture

```
User → crankguild.com → Cloudflare (HTTPS + CDN) → EC2 Elastic IP:80
                                                        ↓
                                                      Nginx (:80)
                                                        ↓
                                                    web-api (:8000)
                                                        ↓
                                                    PostgreSQL
```

- Cloudflare terminates HTTPS and provides CDN caching for static assets
- Cloudflare SSL mode: **Full** (HTTPS to visitors, HTTP to origin)
- Nginx reverse-proxies to the FastAPI `web-api` container
- No cert management needed on EC2

## Changes Required

### 1. Terraform — Elastic IP

Add `aws_eip` resource attached to the EC2 instance. Provides a stable IP address that persists across instance stop/start. Output the IP for Cloudflare DNS setup.

### 2. Terraform — Security Group

Add inbound rules for ports 80 (HTTP) and 443 (HTTPS) from `0.0.0.0/0`. Currently egress-only.

### 3. Nginx Container

Add an `nginx` service to `docker-compose.yml`:
- Listens on port 80
- Reverse-proxies to `web-api:8000`
- Sets `X-Forwarded-For`, `X-Real-IP`, `Host` headers
- Enables gzip for static assets

### 4. Nginx Config

Small `web/nginx.conf` file (~20 lines). Straightforward reverse proxy configuration.

### 5. Port Mapping

`web-api` stops exposing port 8000 externally. Only Nginx is publicly exposed on port 80.

### 6. Deployment Pipeline

Update `deploy.yml` and `user-data.sh` to build and run the full docker-compose stack (bot + web + nginx + postgres + sync-worker) instead of a single bot container.

### 7. Cloudflare DNS (Manual)

After `terraform apply`, add DNS records in Cloudflare dashboard:
- `crankguild.com` → A record → Elastic IP (Proxied)
- `www.crankguild.com` → CNAME → `crankguild.com` (Proxied)
- SSL mode: Full

## Cost Impact

- Elastic IP: Free while EC2 instance is running (~$3.60/mo if instance is stopped)
- Cloudflare: Free tier covers everything needed
- No additional AWS services required

## Decisions

- **Cloudflare Full SSL** over Full Strict — avoids needing a cert on EC2 for no real benefit at guild scale
- **Nginx over direct FastAPI exposure** — standard production setup, handles request buffering, gzip, and is designed for public-facing traffic
- **Same EC2 instance** — keeps costs minimal, sufficient for guild-scale traffic

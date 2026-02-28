# AWS Migration & CI/CD — Design Document

**Date:** 2026-02-28
**Context:** Migrate the WarcraftLogs Discord bot from local development to a production AWS deployment with Infrastructure as Code (Terraform) and GitHub Actions CI/CD.

---

## Goal

Run the bot on AWS with infrastructure defined in Terraform, secrets managed securely, config.yaml persisted in S3, and automated deploys triggered by pushes to the HR/Testing branch.

---

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| IaC tool | Terraform | Industry standard, cloud-agnostic, large community |
| Compute | EC2 (t3.micro) | Cheapest option for a long-running Discord bot (~$7.50/mo) |
| Container runtime | Docker on EC2 | Reproducible builds, easy rollbacks, clean CI/CD |
| Config persistence | S3 with sync | Survives instance termination; config.yaml is writable at runtime |
| Secrets | AWS Secrets Manager | Purpose-built, supports rotation, ~$0.40/secret/mo |
| Image registry | ECR | Native AWS, IAM-integrated, minimal cost |
| CI/CD | GitHub Actions | Already using GitHub; two workflows (CI + deploy) |
| Environments | Production only | Single guild bot, not enterprise — keep it simple |
| Deploy mechanism | SSM Run Command | No SSH keys needed; Amazon Linux 2023 includes SSM agent |

---

## Architecture

```
GitHub Actions CI/CD
  ├── On push/PR:
  │     1. Run pytest (73 tests)
  │
  ├── On push to HR/Testing:
  │     1. Build Docker image
  │     2. Push to ECR (tagged with git SHA + "latest")
  │     3. SSM Run Command → EC2 pulls new image, restarts container
  │
AWS Account
  ├── ECR                    — Docker image repository
  ├── EC2 (t3.micro)         — Runs the bot container (Amazon Linux 2023)
  │     ├── Docker           — Installed via user data script
  │     ├── SSM Agent        — Pre-installed, enables remote commands
  │     └── CloudWatch Agent — Ships container logs
  ├── S3 bucket              — config.yaml persistence
  ├── Secrets Manager        — Discord token, WCL client ID/secret, guild config
  ├── IAM Role               — EC2 instance profile
  │     ├── ecr:GetAuthorizationToken, ecr:BatchGetImage, ecr:GetDownloadUrlForLayer
  │     ├── s3:GetObject, s3:PutObject (config bucket only)
  │     ├── secretsmanager:GetSecretValue (bot secrets only)
  │     ├── ssm:* (for SSM agent)
  │     └── logs:CreateLogStream, logs:PutLogEvents
  ├── Security Group         — Egress only (HTTPS to Discord + WCL APIs)
  └── CloudWatch Log Group   — Container stdout/stderr
```

**Estimated monthly cost:** ~$8-12 (t3.micro ~$7.50, Secrets Manager ~$1.20, S3/ECR/CloudWatch pennies)

---

## Terraform Structure

```
infra/
├── main.tf              — Provider config, S3 backend for state
├── variables.tf         — Input variables (region, instance type, etc.)
├── ec2.tf               — EC2 instance, security group, key pair (optional)
├── iam.tf               — IAM role, instance profile, policies
├── ecr.tf               — ECR repository
├── s3.tf                — S3 bucket for config.yaml + Terraform state
├── secrets.tf           — Secrets Manager secret (structure only)
├── cloudwatch.tf        — CloudWatch Log Group
├── outputs.tf           — Instance IP, ECR URL, S3 bucket name
├── user-data.sh         — EC2 startup script
├── terraform.tfvars     — Environment-specific values (in .gitignore)
└── bootstrap/
    └── bootstrap.sh     — One-time script to create S3 state bucket + DynamoDB lock table
```

**Terraform state:** Stored in a dedicated S3 bucket with DynamoDB locking. A bootstrap script creates these resources before the first `terraform init`.

---

## Docker Setup

**Dockerfile** (at repo root):

- Base: `python:3.11-slim`
- Install production deps only (`requirements.txt` — no pytest)
- Copy `src/`, `config.yaml`, `entrypoint.sh`
- Entrypoint: `entrypoint.sh`

**entrypoint.sh** flow:
1. Pull secrets from Secrets Manager → export as environment variables
2. Download `config.yaml` from S3 (if exists, else use bundled default)
3. Start the bot: `exec python -m src.bot`

**requirements.txt split:**
- `requirements.txt` — production only (discord.py, aiohttp, pyyaml, python-dotenv, boto3)
- `requirements-dev.txt` — adds pytest, pytest-asyncio (for CI and local dev)

**.dockerignore:** tests/, docs/, .env, .git/, __pycache__/, *.pyc, .pytest_cache/

---

## GitHub Actions Workflows

### `.github/workflows/ci.yml`

Trigger: push to any branch, pull_request

```
Steps:
  1. Checkout
  2. Set up Python 3.11
  3. pip install -r requirements.txt -r requirements-dev.txt
  4. python -m pytest -v
```

### `.github/workflows/deploy.yml`

Trigger: push to HR/Testing (needs: ci)

```
Steps:
  1. Checkout
  2. Configure AWS credentials (GitHub secrets)
  3. Login to ECR
  4. Build + push Docker image (tags: git SHA, latest)
  5. SSM Run Command to EC2:
     - docker pull <ecr-url>:latest
     - docker stop warcraftlogs-bot || true
     - docker rm warcraftlogs-bot || true
     - docker run -d --name warcraftlogs-bot --restart unless-stopped <ecr-url>:latest
```

**GitHub repository secrets:**
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `AWS_ACCOUNT_ID`

---

## Config Sync (S3)

**Changes to `src/config/loader.py`:**

1. Add `boto3` import
2. Add `_sync_from_s3()` — downloads config.yaml from S3 on startup
3. Add `_sync_to_s3()` — uploads config.yaml to S3 after each save
4. Call `_sync_from_s3()` in `__init__` (before `_load()`)
5. Call `_sync_to_s3()` at the end of `_save()`

**Environment variable:** `CONFIG_S3_BUCKET` — if not set, skip S3 sync (preserves local dev behavior)

**Graceful fallback:**
- S3 download fails → use bundled default config.yaml
- S3 upload fails → log warning, don't crash

---

## Edge Cases

| Scenario | Handling |
|---|---|
| First deploy (empty S3) | Use bundled default config.yaml; first officer command uploads to S3 |
| EC2 instance terminated | Terraform recreates it; config from S3; secrets from Secrets Manager |
| Deploy during operation | SSM stops old container, starts new one. ~10-30s downtime |
| S3 upload fails | Warning logged; local config preserved; risk of losing changes on redeploy |
| Secrets rotation | Update in Secrets Manager, redeploy (entrypoint pulls fresh values) |
| Bot crash | Docker `--restart unless-stopped` auto-recovers |
| Instance reboot | Docker auto-restarts container |

---

## What This Design Does NOT Include

- Multiple environments (staging/dev) — single prod is sufficient
- RDS or DynamoDB — no database needed, config.yaml covers all state
- Load balancer or auto-scaling — single instance is sufficient
- HTTPS/domain — bot doesn't serve HTTP
- Monitoring/alerting beyond CloudWatch Logs — bot offline = Discord users notice

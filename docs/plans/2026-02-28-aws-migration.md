# AWS Migration & CI/CD Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate the WarcraftLogs Discord bot to AWS with Terraform IaC, Docker containerization, S3 config persistence, and GitHub Actions CI/CD.

**Architecture:** Docker container on EC2, secrets from AWS Secrets Manager, config.yaml synced to S3, images stored in ECR. GitHub Actions runs tests on every push and deploys to EC2 via SSM on pushes to HR/Testing.

**Tech Stack:** Python 3.11, Docker, Terraform, AWS (EC2, ECR, S3, Secrets Manager, IAM, CloudWatch), GitHub Actions, boto3.

---

## Task 1: Split requirements into production and dev

**Files:**
- Modify: `requirements.txt`
- Create: `requirements-dev.txt`

**Step 1: Update requirements.txt to production-only deps**

Replace the contents of `requirements.txt` with:

```
discord.py==2.3.2
aiohttp==3.9.1
pyyaml==6.0.1
python-dotenv==1.0.0
boto3>=1.34.0
```

Note: `boto3` is added for S3 config sync (Task 2). The `>=` pin allows minor updates.

**Step 2: Create requirements-dev.txt**

Create `requirements-dev.txt`:

```
-r requirements.txt
pytest==7.4.3
pytest-asyncio==0.23.2
```

This includes production deps plus test tools.

**Step 3: Verify tests still pass**

Run: `pip install -r requirements-dev.txt && python -m pytest -v`
Expected: All 73 tests pass.

**Step 4: Commit**

```bash
git add requirements.txt requirements-dev.txt
git commit -m "build: split requirements into production and dev"
```

---

## Task 2: Add S3 config sync to ConfigLoader

**Files:**
- Modify: `src/config/loader.py`
- Modify: `tests/test_config.py`

**Step 1: Write failing tests for S3 sync**

Add to `tests/test_config.py`:

```python
from unittest.mock import patch, MagicMock


def test_save_calls_sync_to_s3_when_bucket_set(config_file, monkeypatch):
    """_save() should call _sync_to_s3() when CONFIG_S3_BUCKET is set."""
    monkeypatch.setenv("CONFIG_S3_BUCKET", "my-bucket")
    loader = ConfigLoader(config_file)
    with patch.object(loader, "_sync_to_s3") as mock_sync:
        loader.update_target("warrior:protection", "sunder_armor_uptime", 95)
        mock_sync.assert_called_once()


def test_save_skips_s3_when_no_bucket(config_file, monkeypatch):
    """_save() should not attempt S3 when CONFIG_S3_BUCKET is not set."""
    monkeypatch.delenv("CONFIG_S3_BUCKET", raising=False)
    loader = ConfigLoader(config_file)
    with patch.object(loader, "_sync_to_s3") as mock_sync:
        loader.update_target("warrior:protection", "sunder_armor_uptime", 95)
        mock_sync.assert_not_called()


def test_init_calls_sync_from_s3_when_bucket_set(config_file, monkeypatch):
    """__init__ should attempt S3 download when CONFIG_S3_BUCKET is set."""
    monkeypatch.setenv("CONFIG_S3_BUCKET", "my-bucket")
    with patch("src.config.loader.ConfigLoader._sync_from_s3") as mock_sync:
        ConfigLoader(config_file)
        mock_sync.assert_called_once()


def test_init_skips_s3_when_no_bucket(config_file, monkeypatch):
    """__init__ should skip S3 when CONFIG_S3_BUCKET is not set."""
    monkeypatch.delenv("CONFIG_S3_BUCKET", raising=False)
    with patch("src.config.loader.ConfigLoader._sync_from_s3") as mock_sync:
        ConfigLoader(config_file)
        mock_sync.assert_not_called()


def test_sync_to_s3_uploads_file(config_file, monkeypatch):
    """_sync_to_s3() should upload config.yaml to the S3 bucket."""
    monkeypatch.setenv("CONFIG_S3_BUCKET", "my-bucket")
    mock_client = MagicMock()
    with patch("boto3.client", return_value=mock_client):
        loader = ConfigLoader(config_file)
        loader._sync_to_s3()
        mock_client.upload_file.assert_called_once_with(
            config_file, "my-bucket", "config.yaml"
        )


def test_sync_from_s3_downloads_file(config_file, monkeypatch):
    """_sync_from_s3() should download config.yaml from the S3 bucket."""
    monkeypatch.setenv("CONFIG_S3_BUCKET", "my-bucket")
    mock_client = MagicMock()
    with patch("boto3.client", return_value=mock_client):
        loader = ConfigLoader.__new__(ConfigLoader)
        loader._path = config_file
        loader._s3_bucket = "my-bucket"
        loader._sync_from_s3()
        mock_client.download_file.assert_called_once_with(
            "my-bucket", "config.yaml", config_file
        )


def test_sync_from_s3_graceful_on_missing_key(config_file, monkeypatch):
    """_sync_from_s3() should not crash if the S3 key doesn't exist (first deploy)."""
    monkeypatch.setenv("CONFIG_S3_BUCKET", "my-bucket")
    mock_client = MagicMock()
    error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
    mock_client.download_file.side_effect = mock_client.exceptions.NoSuchKey(
        error_response, "GetObject"
    ) if hasattr(mock_client.exceptions, "NoSuchKey") else Exception("NoSuchKey")
    # Use a ClientError to simulate missing key
    from botocore.exceptions import ClientError
    mock_client.download_file.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "Not Found"}}, "GetObject"
    )
    with patch("boto3.client", return_value=mock_client):
        loader = ConfigLoader.__new__(ConfigLoader)
        loader._path = config_file
        loader._s3_bucket = "my-bucket"
        # Should not raise
        loader._sync_from_s3()
```

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_config.py::test_save_calls_sync_to_s3_when_bucket_set -v`
Expected: FAIL — `_sync_to_s3` method does not exist.

**Step 3: Implement S3 sync in ConfigLoader**

Replace the full contents of `src/config/loader.py`:

```python
import logging
import os

import yaml
from typing import Optional

logger = logging.getLogger(__name__)

_GEAR_CHECK_DEFAULTS = {
    "min_avg_ilvl": 100,
    "min_quality": 3,
    "check_enchants": True,
    "check_gems": True,
    "enchant_slots": [0, 1, 2, 4, 5, 6, 7, 8, 9, 14, 15],
}


class ConfigLoader:
    def __init__(self, path: str = "config.yaml"):
        self._path = path
        self._s3_bucket = os.environ.get("CONFIG_S3_BUCKET")
        if self._s3_bucket:
            self._sync_from_s3()
        self._data = self._load()

    def _load(self) -> dict:
        with open(self._path, "r") as f:
            return yaml.safe_load(f) or {}

    def _save(self) -> None:
        with open(self._path, "w") as f:
            yaml.dump(self._data, f, default_flow_style=False, sort_keys=False)
        if self._s3_bucket:
            self._sync_to_s3()

    def _sync_to_s3(self) -> None:
        """Upload config.yaml to S3."""
        try:
            import boto3
            s3 = boto3.client("s3")
            s3.upload_file(self._path, self._s3_bucket, "config.yaml")
        except Exception as e:
            logger.warning("Failed to upload config to S3: %s", e)

    def _sync_from_s3(self) -> None:
        """Download config.yaml from S3. Gracefully handles missing key (first deploy)."""
        try:
            import boto3
            s3 = boto3.client("s3")
            s3.download_file(self._s3_bucket, "config.yaml", self._path)
        except Exception as e:
            logger.info("S3 config download skipped: %s", e)

    def get_spec(self, spec_key: str) -> Optional[dict]:
        """Return the profile for a class:spec key, or None if not configured."""
        return self._data.get(spec_key)

    def get_consumables(self) -> list:
        """Return the global consumables list, or empty list if not configured."""
        return self._data.get("consumables", [])

    def get_attendance(self) -> list:
        """Return the attendance requirements list, or empty list if not configured."""
        return self._data.get("attendance", [])

    def get_gear_check(self) -> dict:
        """Return the gear check config, or defaults if not configured."""
        config = self._data.get("gear_check")
        if config is None:
            return dict(_GEAR_CHECK_DEFAULTS)
        return {**_GEAR_CHECK_DEFAULTS, **config}

    def all_specs(self) -> list[str]:
        """Return all configured spec keys, excluding non-spec top-level keys."""
        return [k for k in self._data.keys() if k not in ("consumables", "attendance", "gear_check")]

    def update_target(self, spec_key: str, metric: str, new_target: int) -> None:
        """Update the target for a metric in a spec profile and persist to disk."""
        profile = self._data.get(spec_key)
        if profile is None:
            raise ValueError(f"Spec '{spec_key}' not found in config")

        for contrib in profile["contributions"]:
            if contrib["metric"] == metric:
                contrib["target"] = new_target
                self._save()
                return

        raise ValueError(f"metric '{metric}' not found in spec '{spec_key}'")

    def add_attendance_zone(self, zone_id: int, label: str, required_per_week: int) -> None:
        """Add a new zone to attendance requirements and persist to disk."""
        attendance = self._data.setdefault("attendance", [])
        if any(e["zone_id"] == zone_id for e in attendance):
            raise ValueError(f"Zone {zone_id} already exists in attendance config")
        attendance.append({
            "zone_id": zone_id,
            "label": label,
            "required_per_week": required_per_week,
        })
        self._save()

    def remove_attendance_zone(self, zone_id: int) -> None:
        """Remove a zone from attendance requirements and persist to disk."""
        attendance = self._data.get("attendance", [])
        original_len = len(attendance)
        self._data["attendance"] = [e for e in attendance if e["zone_id"] != zone_id]
        if len(self._data["attendance"]) == original_len:
            raise ValueError(f"Zone {zone_id} not found in attendance config")
        self._save()

    def update_attendance_zone(self, zone_id: int, required_per_week: int) -> None:
        """Update the required_per_week for a zone and persist to disk."""
        attendance = self._data.get("attendance", [])
        for entry in attendance:
            if entry["zone_id"] == zone_id:
                entry["required_per_week"] = required_per_week
                self._save()
                return
        raise ValueError(f"Zone {zone_id} not found in attendance config")
```

**Step 4: Run all tests**

Run: `python -m pytest tests/test_config.py -v`
Expected: All config tests pass (22 existing + 7 new = 29 tests).

Run: `python -m pytest -v`
Expected: All tests pass.

**Step 5: Commit**

```bash
git add src/config/loader.py tests/test_config.py
git commit -m "feat: add S3 config sync to ConfigLoader"
```

---

## Task 3: Create Dockerfile and entrypoint

**Files:**
- Create: `Dockerfile`
- Create: `entrypoint.sh`
- Create: `.dockerignore`

**Step 1: Create .dockerignore**

Create `.dockerignore`:

```
.git/
.github/
__pycache__/
*.pyc
.pytest_cache/
.env
tests/
docs/
infra/
requirements-dev.txt
*.md
```

**Step 2: Create entrypoint.sh**

Create `entrypoint.sh`:

```bash
#!/bin/bash
set -e

# --- Pull secrets from AWS Secrets Manager ---
if [ -n "$AWS_SECRET_NAME" ]; then
    echo "Fetching secrets from AWS Secrets Manager..."
    SECRET_JSON=$(aws secretsmanager get-secret-value \
        --secret-id "$AWS_SECRET_NAME" \
        --query SecretString \
        --output text)

    # Export each key-value pair as an environment variable
    for key in $(echo "$SECRET_JSON" | python3 -c "import sys,json; print(' '.join(json.load(sys.stdin).keys()))"); do
        value=$(echo "$SECRET_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['$key'])")
        export "$key"="$value"
    done
    echo "Secrets loaded."
fi

# --- Download config.yaml from S3 (if bucket is set) ---
if [ -n "$CONFIG_S3_BUCKET" ]; then
    echo "Downloading config.yaml from S3..."
    aws s3 cp "s3://${CONFIG_S3_BUCKET}/config.yaml" /app/config.yaml 2>/dev/null || echo "No config in S3, using default."
fi

# --- Start the bot ---
echo "Starting WarcraftLogs bot..."
exec python -m src.bot
```

**Step 3: Create Dockerfile**

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Install AWS CLI for entrypoint secret fetching
RUN pip install --no-cache-dir awscli

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and default config
COPY src/ src/
COPY config.yaml .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
```

**Step 4: Verify the Docker build works**

Run: `docker build -t warcraftlogs-bot .`
Expected: Image builds successfully. (Do NOT run it — no secrets available locally.)

**Step 5: Commit**

```bash
git add Dockerfile entrypoint.sh .dockerignore
git commit -m "build: add Dockerfile, entrypoint, and .dockerignore"
```

---

## Task 4: Create Terraform bootstrap

**Files:**
- Create: `infra/bootstrap/bootstrap.sh`

**Step 1: Create the bootstrap directory and script**

Create `infra/bootstrap/bootstrap.sh`:

```bash
#!/bin/bash
# One-time bootstrap: creates the S3 bucket and DynamoDB table for Terraform state.
# Run this ONCE before the first `terraform init`.
#
# Usage: ./bootstrap.sh <aws-region> <account-id>
# Example: ./bootstrap.sh us-east-1 123456789012

set -e

REGION="${1:?Usage: ./bootstrap.sh <aws-region> <account-id>}"
ACCOUNT_ID="${2:?Usage: ./bootstrap.sh <aws-region> <account-id>}"
BUCKET_NAME="warcraftlogs-terraform-state-${ACCOUNT_ID}"
TABLE_NAME="warcraftlogs-terraform-locks"

echo "Creating Terraform state bucket: ${BUCKET_NAME}"
aws s3api create-bucket \
    --bucket "$BUCKET_NAME" \
    --region "$REGION" \
    $([ "$REGION" != "us-east-1" ] && echo "--create-bucket-configuration LocationConstraint=$REGION")

aws s3api put-bucket-versioning \
    --bucket "$BUCKET_NAME" \
    --versioning-configuration Status=Enabled

aws s3api put-public-access-block \
    --bucket "$BUCKET_NAME" \
    --public-access-block-configuration \
        BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo "Creating DynamoDB lock table: ${TABLE_NAME}"
aws dynamodb create-table \
    --table-name "$TABLE_NAME" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST \
    --region "$REGION"

echo ""
echo "Bootstrap complete. Use these values in infra/main.tf:"
echo "  bucket         = \"${BUCKET_NAME}\""
echo "  dynamodb_table = \"${TABLE_NAME}\""
echo "  region         = \"${REGION}\""
```

**Step 2: Commit**

```bash
git add infra/bootstrap/bootstrap.sh
git commit -m "infra: add Terraform state bootstrap script"
```

---

## Task 5: Create Terraform infrastructure

**Files:**
- Create: `infra/main.tf`
- Create: `infra/variables.tf`
- Create: `infra/ecr.tf`
- Create: `infra/s3.tf`
- Create: `infra/secrets.tf`
- Create: `infra/iam.tf`
- Create: `infra/ec2.tf`
- Create: `infra/cloudwatch.tf`
- Create: `infra/outputs.tf`
- Create: `infra/user-data.sh`

**Step 1: Create infra/variables.tf**

```hcl
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "aws_account_id" {
  description = "AWS account ID (used for state bucket name)"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type"
  type        = string
  default     = "t3.micro"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "warcraftlogs-bot"
}
```

**Step 2: Create infra/main.tf**

```hcl
terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    # Values filled in by terraform init -backend-config or terraform.tfvars
    # bucket         = "warcraftlogs-terraform-state-<account-id>"
    # key            = "terraform.tfstate"
    # region         = "us-east-1"
    # dynamodb_table = "warcraftlogs-terraform-locks"
    # encrypt        = true
    key     = "terraform.tfstate"
    encrypt = true
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "terraform"
    }
  }
}
```

**Step 3: Create infra/ecr.tf**

```hcl
resource "aws_ecr_repository" "bot" {
  name                 = var.project_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = false
  }
}

# Keep only the last 10 images to save storage costs
resource "aws_ecr_lifecycle_policy" "bot" {
  repository = aws_ecr_repository.bot.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = {
        type = "expire"
      }
    }]
  })
}
```

**Step 4: Create infra/s3.tf**

```hcl
resource "aws_s3_bucket" "config" {
  bucket = "${var.project_name}-config-${var.aws_account_id}"
}

resource "aws_s3_bucket_versioning" "config" {
  bucket = aws_s3_bucket.config.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "config" {
  bucket = aws_s3_bucket.config.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

**Step 5: Create infra/secrets.tf**

```hcl
resource "aws_secretsmanager_secret" "bot" {
  name                    = "${var.project_name}/credentials"
  description             = "WarcraftLogs bot secrets (Discord token, WCL credentials)"
  recovery_window_in_days = 7
}

# Placeholder structure — actual values are set manually via AWS Console or CLI:
#   aws secretsmanager put-secret-value --secret-id warcraftlogs-bot/credentials \
#     --secret-string '{"DISCORD_BOT_TOKEN":"...","WARCRAFTLOGS_CLIENT_ID":"...","WARCRAFTLOGS_CLIENT_SECRET":"...","GUILD_NAME":"...","GUILD_SERVER":"...","GUILD_REGION":"US","OFFICER_ROLE_NAME":"Officer"}'
```

**Step 6: Create infra/iam.tf**

```hcl
# IAM role for the EC2 instance
resource "aws_iam_role" "bot" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_instance_profile" "bot" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.bot.name
}

# ECR pull access
resource "aws_iam_role_policy" "ecr_pull" {
  name = "ecr-pull"
  role = aws_iam_role.bot.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "ecr:GetAuthorizationToken",
        "ecr:BatchGetImage",
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchCheckLayerAvailability",
      ]
      Resource = "*"
    }]
  })
}

# S3 config bucket access
resource "aws_iam_role_policy" "s3_config" {
  name = "s3-config"
  role = aws_iam_role.bot.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket",
      ]
      Resource = [
        aws_s3_bucket.config.arn,
        "${aws_s3_bucket.config.arn}/*",
      ]
    }]
  })
}

# Secrets Manager read access
resource "aws_iam_role_policy" "secrets" {
  name = "secrets-read"
  role = aws_iam_role.bot.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "secretsmanager:GetSecretValue"
      Resource = aws_secretsmanager_secret.bot.arn
    }]
  })
}

# CloudWatch Logs
resource "aws_iam_role_policy" "cloudwatch" {
  name = "cloudwatch-logs"
  role = aws_iam_role.bot.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "logs:CreateLogStream",
        "logs:PutLogEvents",
      ]
      Resource = "${aws_cloudwatch_log_group.bot.arn}:*"
    }]
  })
}

# SSM for remote commands (deploy via GitHub Actions)
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.bot.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
```

**Step 7: Create infra/cloudwatch.tf**

```hcl
resource "aws_cloudwatch_log_group" "bot" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 30
}
```

**Step 8: Create infra/user-data.sh**

```bash
#!/bin/bash
set -e

# Install Docker
yum update -y
yum install -y docker
systemctl enable docker
systemctl start docker

# Login to ECR and pull the latest image
REGION="${region}"
ACCOUNT_ID="${account_id}"
ECR_URL="${ecr_url}"

aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URL

# Pull and run the bot container
docker pull ${ecr_url}:latest || echo "No image in ECR yet — first deploy will push one."

if docker image inspect ${ecr_url}:latest >/dev/null 2>&1; then
    docker run -d \
        --name warcraftlogs-bot \
        --restart unless-stopped \
        --log-driver=awslogs \
        --log-opt awslogs-region=$REGION \
        --log-opt awslogs-group=${log_group} \
        -e AWS_SECRET_NAME="${secret_name}" \
        -e CONFIG_S3_BUCKET="${config_bucket}" \
        -e AWS_DEFAULT_REGION=$REGION \
        ${ecr_url}:latest
fi
```

**Step 9: Create infra/ec2.tf**

```hcl
# Use the latest Amazon Linux 2023 AMI
data "aws_ami" "amazon_linux" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_security_group" "bot" {
  name        = "${var.project_name}-sg"
  description = "Security group for WarcraftLogs bot — egress only"

  # Outbound: allow all (Discord WebSocket, WCL API, ECR, S3, Secrets Manager)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-sg"
  }
}

resource "aws_instance" "bot" {
  ami                    = data.aws_ami.amazon_linux.id
  instance_type          = var.instance_type
  iam_instance_profile   = aws_iam_instance_profile.bot.name
  vpc_security_group_ids = [aws_security_group.bot.id]

  user_data = templatefile("${path.module}/user-data.sh", {
    region        = var.aws_region
    account_id    = var.aws_account_id
    ecr_url       = aws_ecr_repository.bot.repository_url
    secret_name   = aws_secretsmanager_secret.bot.name
    config_bucket = aws_s3_bucket.config.id
    log_group     = aws_cloudwatch_log_group.bot.name
  })

  tags = {
    Name = var.project_name
  }
}
```

**Step 10: Create infra/outputs.tf**

```hcl
output "ecr_repository_url" {
  description = "ECR repository URL for Docker images"
  value       = aws_ecr_repository.bot.repository_url
}

output "instance_id" {
  description = "EC2 instance ID (for SSM commands)"
  value       = aws_instance.bot.id
}

output "instance_public_ip" {
  description = "EC2 instance public IP"
  value       = aws_instance.bot.public_ip
}

output "config_bucket" {
  description = "S3 bucket name for config.yaml"
  value       = aws_s3_bucket.config.id
}

output "secret_name" {
  description = "Secrets Manager secret name"
  value       = aws_secretsmanager_secret.bot.name
}

output "log_group" {
  description = "CloudWatch Log Group name"
  value       = aws_cloudwatch_log_group.bot.name
}
```

**Step 11: Validate Terraform syntax**

Run: `cd infra && terraform init -backend=false && terraform validate`
Expected: "Success! The configuration is valid."

Note: Use `-backend=false` because the state bucket doesn't exist yet. Full `init` happens after running the bootstrap script.

**Step 12: Commit**

```bash
git add infra/
git commit -m "infra: add Terraform configuration for AWS deployment"
```

---

## Task 6: Create GitHub Actions CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

**Step 1: Create the CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
    branches: ["**"]
  pull_request:
    branches: [HR/Testing]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements-dev.txt

      - name: Run tests
        run: python -m pytest -v
```

**Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions test workflow"
```

---

## Task 7: Create GitHub Actions deploy workflow

**Files:**
- Create: `.github/workflows/deploy.yml`

**Step 1: Create the deploy workflow**

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy

on:
  push:
    branches: [HR/Testing]

jobs:
  test:
    uses: ./.github/workflows/ci.yml

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/HR/Testing'

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }}

      - name: Login to Amazon ECR
        id: ecr-login
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build and push Docker image
        env:
          ECR_REGISTRY: ${{ steps.ecr-login.outputs.registry }}
          ECR_REPOSITORY: warcraftlogs-bot
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker tag $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG $ECR_REGISTRY/$ECR_REPOSITORY:latest
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest

      - name: Deploy to EC2 via SSM
        env:
          ECR_REGISTRY: ${{ steps.ecr-login.outputs.registry }}
          ECR_REPOSITORY: warcraftlogs-bot
          INSTANCE_ID: ${{ secrets.EC2_INSTANCE_ID }}
        run: |
          aws ssm send-command \
            --instance-ids "$INSTANCE_ID" \
            --document-name "AWS-RunShellScript" \
            --parameters "commands=[
              'aws ecr get-login-password --region ${{ secrets.AWS_REGION }} | docker login --username AWS --password-stdin $ECR_REGISTRY',
              'docker pull $ECR_REGISTRY/$ECR_REPOSITORY:latest',
              'docker stop warcraftlogs-bot || true',
              'docker rm warcraftlogs-bot || true',
              'docker run -d --name warcraftlogs-bot --restart unless-stopped --log-driver=awslogs --log-opt awslogs-region=${{ secrets.AWS_REGION }} --log-opt awslogs-group=/ecs/warcraftlogs-bot -e AWS_SECRET_NAME=warcraftlogs-bot/credentials -e CONFIG_S3_BUCKET=${{ secrets.CONFIG_S3_BUCKET }} -e AWS_DEFAULT_REGION=${{ secrets.AWS_REGION }} $ECR_REGISTRY/$ECR_REPOSITORY:latest'
            ]" \
            --output text
```

**Step 2: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: add GitHub Actions deploy workflow"
```

---

## Task 8: Update .gitignore, .env.example, and documentation

**Files:**
- Modify: `.gitignore`
- Modify: `.env.example`
- Modify: `CLAUDE.md`
- Modify: `README.md`

**Step 1: Update .gitignore**

Add to `.gitignore`:

```
# Existing
.env
__pycache__/
*.pyc
.pytest_cache/

# Terraform
infra/.terraform/
infra/*.tfstate
infra/*.tfstate.backup
infra/*.tfvars
infra/.terraform.lock.hcl

# Docker
*.tar
```

**Step 2: Update .env.example**

Add to `.env.example`:

```
# --- Discord ---
DISCORD_BOT_TOKEN=your_discord_bot_token_here

# --- WarcraftLogs API ---
WARCRAFTLOGS_CLIENT_ID=your_client_id_here
WARCRAFTLOGS_CLIENT_SECRET=your_client_secret_here

# --- Guild ---
GUILD_NAME=YourGuildName
GUILD_SERVER=your-server-slug
GUILD_REGION=US
OFFICER_ROLE_NAME=Officer

# --- AWS (optional, for S3 config sync) ---
# CONFIG_S3_BUCKET=warcraftlogs-bot-config-123456789012
```

**Step 3: Update CLAUDE.md**

Add to the project structure:
- `Dockerfile` — Docker image definition
- `entrypoint.sh` — Container startup script (secrets + S3 sync)
- `.dockerignore` — Files excluded from Docker build
- `requirements-dev.txt` — Dev/test dependencies (includes production deps)
- `infra/` — Terraform IaC for AWS deployment
- `.github/workflows/ci.yml` — GitHub Actions test workflow
- `.github/workflows/deploy.yml` — GitHub Actions deploy workflow

Update test count to reflect new config tests.

Add a Known Design Decision:
- **S3 config sync** — ConfigLoader uploads config.yaml to S3 after each save and downloads from S3 on startup. Skipped when `CONFIG_S3_BUCKET` env var is not set (local dev). Failures are logged but never crash the bot.

Add an AWS Deployment section with key resource names, GitHub secrets needed, and first-deploy instructions.

**Step 4: Update README.md**

Add an "AWS Deployment" section covering:
- Prerequisites (AWS CLI, Terraform, Docker)
- Bootstrap (running the bootstrap script)
- Terraform apply
- Setting secrets in Secrets Manager
- GitHub secrets configuration
- First deploy flow

**Step 5: Run all tests**

Run: `python -m pytest -v`
Expected: All tests pass.

**Step 6: Commit**

```bash
git add .gitignore .env.example CLAUDE.md README.md
git commit -m "docs: add AWS deployment docs and update project configuration"
```

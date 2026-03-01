# crankguild.com Domain Setup — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Connect the Cloudflare-registered domain `crankguild.com` to the guild website running on EC2 via Nginx reverse proxy.

**Architecture:** Cloudflare terminates HTTPS and proxies to an Elastic IP on EC2. Nginx (in a Docker container) reverse-proxies to the FastAPI `web-api` container. The deploy pipeline is expanded from single-container bot to a full docker-compose stack.

**Tech Stack:** Terraform (AWS), Nginx, Docker Compose, GitHub Actions (SSM deploy)

---

### Task 1: Terraform — Add Elastic IP

**Files:**
- Modify: `infra/ec2.tf`
- Modify: `infra/outputs.tf`

**Step 1: Add Elastic IP resource to ec2.tf**

Append to the end of `infra/ec2.tf`:

```hcl
resource "aws_eip" "bot" {
  instance = aws_instance.bot.id

  tags = {
    Name = "${var.project_name}-eip"
  }
}
```

**Step 2: Add Elastic IP output**

Append to `infra/outputs.tf`:

```hcl
output "elastic_ip" {
  description = "Elastic IP for crankguild.com DNS"
  value       = aws_eip.bot.public_ip
}
```

**Step 3: Validate Terraform**

Run: `cd infra && terraform validate`
Expected: `Success! The configuration is valid.`

**Step 4: Commit**

```bash
git add infra/ec2.tf infra/outputs.tf
git commit -m "infra: add Elastic IP for crankguild.com"
```

---

### Task 2: Terraform — Open HTTP/HTTPS in Security Group

**Files:**
- Modify: `infra/ec2.tf`

**Step 1: Add ingress rules to the `aws_security_group.bot` resource**

In `infra/ec2.tf`, add two ingress blocks to the `aws_security_group.bot` resource (before the `egress` block). Also update the description:

```hcl
resource "aws_security_group" "bot" {
  name        = "${var.project_name}-sg"
  description = "Security group for WarcraftLogs bot and guild website"

  ingress {
    description = "HTTP from anywhere (Cloudflare proxy)"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS from anywhere (Cloudflare proxy)"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

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
```

**Step 2: Validate Terraform**

Run: `cd infra && terraform validate`
Expected: `Success! The configuration is valid.`

**Step 3: Commit**

```bash
git add infra/ec2.tf
git commit -m "infra: open ports 80/443 for web traffic"
```

---

### Task 3: Terraform — Add ECR Repository for Web Image

The bot image and web image are separate Dockerfiles. Add a second ECR repository for the web image.

**Files:**
- Modify: `infra/ecr.tf`
- Modify: `infra/outputs.tf`

**Step 1: Add web ECR repository to ecr.tf**

Append to `infra/ecr.tf`:

```hcl
resource "aws_ecr_repository" "web" {
  name                 = "${var.project_name}-web"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = false
  }
}

resource "aws_ecr_lifecycle_policy" "web" {
  repository = aws_ecr_repository.web.name

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

**Step 2: Add web ECR output**

Append to `infra/outputs.tf`:

```hcl
output "web_ecr_repository_url" {
  description = "ECR repository URL for web Docker images"
  value       = aws_ecr_repository.web.repository_url
}
```

**Step 3: Validate Terraform**

Run: `cd infra && terraform validate`
Expected: `Success! The configuration is valid.`

**Step 4: Commit**

```bash
git add infra/ecr.tf infra/outputs.tf
git commit -m "infra: add ECR repository for web image"
```

---

### Task 4: Create Nginx Configuration

**Files:**
- Create: `web/nginx.conf`

**Step 1: Create the Nginx config**

Create `web/nginx.conf`:

```nginx
server {
    listen 80;
    server_name crankguild.com www.crankguild.com;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml;
    gzip_min_length 256;

    location / {
        proxy_pass http://web-api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Step 2: Commit**

```bash
git add web/nginx.conf
git commit -m "feat: add Nginx reverse proxy config for crankguild.com"
```

---

### Task 5: Update docker-compose.yml — Add Nginx, Adjust Ports

**Files:**
- Modify: `docker-compose.yml`

**Step 1: Add nginx service and remove web-api port exposure**

Replace the full `docker-compose.yml` with:

```yaml
version: "3.8"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: crankguild
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  bot:
    build:
      context: .
      dockerfile: Dockerfile
    env_file: .env
    depends_on:
      - postgres
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./web/nginx.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - web-api
    restart: unless-stopped

  web-api:
    build:
      context: .
      dockerfile: Dockerfile.web
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/crankguild
    env_file: .env
    depends_on:
      - postgres
    restart: unless-stopped

  sync-worker:
    build:
      context: .
      dockerfile: Dockerfile.web
    command: ["python", "-m", "web.api.sync.run"]
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/crankguild
    env_file: .env
    depends_on:
      - postgres
    restart: unless-stopped

volumes:
  pgdata:
```

Key changes from the original:
- Added `nginx` service on port 80 with the config volume-mounted
- Removed `ports: ["8000:8000"]` from `web-api` (Nginx proxies to it internally)

**Step 2: Validate compose file**

Run: `docker compose config --quiet` (or `docker-compose config -q`)
Expected: No errors

**Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add Nginx service to docker-compose, remove direct web-api port"
```

---

### Task 6: Create Production Compose Override

The production docker-compose override replaces local `build:` directives with ECR image references and removes dev-only settings (postgres port exposure, .env file).

**Files:**
- Create: `docker-compose.prod.yml`

**Step 1: Create the production override**

Create `docker-compose.prod.yml`:

```yaml
version: "3.8"

services:
  postgres:
    ports: !reset []

  bot:
    image: ${ECR_REGISTRY}/${BOT_ECR_REPOSITORY}:latest
    build: !reset null
    env_file: !reset []
    environment:
      AWS_SECRET_NAME: ${AWS_SECRET_NAME}
      CONFIG_S3_BUCKET: ${CONFIG_S3_BUCKET}
      AWS_DEFAULT_REGION: ${AWS_REGION}

  nginx:
    volumes:
      - ./web/nginx.conf:/etc/nginx/conf.d/default.conf:ro

  web-api:
    image: ${ECR_REGISTRY}/${WEB_ECR_REPOSITORY}:latest
    build: !reset null
    env_file: !reset []
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/crankguild
      AWS_SECRET_NAME: ${AWS_SECRET_NAME}
      CONFIG_S3_BUCKET: ${CONFIG_S3_BUCKET}
      AWS_DEFAULT_REGION: ${AWS_REGION}

  sync-worker:
    image: ${ECR_REGISTRY}/${WEB_ECR_REPOSITORY}:latest
    build: !reset null
    env_file: !reset []
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@postgres:5432/crankguild
      AWS_SECRET_NAME: ${AWS_SECRET_NAME}
      CONFIG_S3_BUCKET: ${CONFIG_S3_BUCKET}
      AWS_DEFAULT_REGION: ${AWS_REGION}
```

**Note:** The `!reset` YAML tag is a docker-compose v2 feature that clears an inherited value from the base file. If the EC2 instance uses docker-compose v1, we'll need a standalone production compose file instead. Verify during Task 8 which version is available.

**Step 2: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "feat: add production docker-compose override with ECR images"
```

---

### Task 7: Update EC2 Bootstrap Script

The user-data script needs to install docker-compose, pull compose files from S3, and run the full stack instead of a single container.

**Files:**
- Modify: `infra/user-data.sh`

**Step 1: Rewrite user-data.sh**

Replace `infra/user-data.sh` with:

```bash
#!/bin/bash
set -e

# Install Docker
yum update -y
yum install -y docker git
systemctl enable docker
systemctl start docker

# Install Docker Compose v2 plugin
mkdir -p /usr/local/lib/docker/cli-plugins
curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-x86_64" \
  -o /usr/local/lib/docker/cli-plugins/docker-compose
chmod +x /usr/local/lib/docker/cli-plugins/docker-compose

# Set up working directory
mkdir -p /opt/crankguild
cd /opt/crankguild

# Login to ECR
REGION="${region}"
ECR_URL="${ecr_url}"
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URL

# Download compose files and nginx config from S3
aws s3 cp "s3://${config_bucket}/deploy/docker-compose.yml" docker-compose.yml 2>/dev/null || echo "No compose file in S3 yet."
aws s3 cp "s3://${config_bucket}/deploy/docker-compose.prod.yml" docker-compose.prod.yml 2>/dev/null || echo "No prod compose file in S3 yet."
mkdir -p web
aws s3 cp "s3://${config_bucket}/deploy/nginx.conf" web/nginx.conf 2>/dev/null || echo "No nginx config in S3 yet."

# Pull images and start stack (if compose files exist)
if [ -f docker-compose.yml ] && [ -f docker-compose.prod.yml ]; then
    export ECR_REGISTRY=$(echo ${ecr_url} | cut -d'/' -f1)
    export BOT_ECR_REPOSITORY=$(echo ${ecr_url} | cut -d'/' -f2)
    export WEB_ECR_REPOSITORY=$(echo ${ecr_url} | cut -d'/' -f2)-web
    export AWS_SECRET_NAME="${secret_name}"
    export CONFIG_S3_BUCKET="${config_bucket}"
    export AWS_REGION="${region}"

    docker compose -f docker-compose.yml -f docker-compose.prod.yml pull
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
fi
```

**Step 2: Validate Terraform**

Run: `cd infra && terraform validate`
Expected: `Success! The configuration is valid.`

**Step 3: Commit**

```bash
git add infra/user-data.sh
git commit -m "infra: update bootstrap for docker-compose stack deployment"
```

---

### Task 8: Update GitHub Actions Deploy Pipeline

The deploy pipeline needs to build both images, push both to ECR, upload compose files to S3, and trigger docker-compose on EC2.

**Files:**
- Modify: `.github/workflows/deploy.yml`

**Step 1: Rewrite deploy.yml**

Replace `.github/workflows/deploy.yml` with:

```yaml
name: Deploy

on:
  push:
    branches: [main]

jobs:
  test:
    uses: ./.github/workflows/ci.yml

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'

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

      - name: Build and push bot image
        env:
          ECR_REGISTRY: ${{ steps.ecr-login.outputs.registry }}
          ECR_REPOSITORY: warcraftlogs-bot
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:${{ github.sha }} -t $ECR_REGISTRY/$ECR_REPOSITORY:latest -f Dockerfile .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:${{ github.sha }}
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest

      - name: Build and push web image
        env:
          ECR_REGISTRY: ${{ steps.ecr-login.outputs.registry }}
          ECR_REPOSITORY: warcraftlogs-bot-web
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:${{ github.sha }} -t $ECR_REGISTRY/$ECR_REPOSITORY:latest -f Dockerfile.web .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:${{ github.sha }}
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:latest

      - name: Upload deploy files to S3
        run: |
          aws s3 cp docker-compose.yml s3://${{ secrets.CONFIG_S3_BUCKET }}/deploy/docker-compose.yml
          aws s3 cp docker-compose.prod.yml s3://${{ secrets.CONFIG_S3_BUCKET }}/deploy/docker-compose.prod.yml
          aws s3 cp web/nginx.conf s3://${{ secrets.CONFIG_S3_BUCKET }}/deploy/nginx.conf

      - name: Deploy to EC2 via SSM
        env:
          ECR_REGISTRY: ${{ steps.ecr-login.outputs.registry }}
          INSTANCE_ID: ${{ secrets.EC2_INSTANCE_ID }}
        run: |
          aws ssm send-command \
            --instance-ids "$INSTANCE_ID" \
            --document-name "AWS-RunShellScript" \
            --parameters "commands=[
              'cd /opt/crankguild',
              'aws ecr get-login-password --region ${{ secrets.AWS_REGION }} | docker login --username AWS --password-stdin $ECR_REGISTRY',
              'aws s3 cp s3://${{ secrets.CONFIG_S3_BUCKET }}/deploy/docker-compose.yml docker-compose.yml',
              'aws s3 cp s3://${{ secrets.CONFIG_S3_BUCKET }}/deploy/docker-compose.prod.yml docker-compose.prod.yml',
              'mkdir -p web',
              'aws s3 cp s3://${{ secrets.CONFIG_S3_BUCKET }}/deploy/nginx.conf web/nginx.conf',
              'export ECR_REGISTRY=$ECR_REGISTRY',
              'export BOT_ECR_REPOSITORY=warcraftlogs-bot',
              'export WEB_ECR_REPOSITORY=warcraftlogs-bot-web',
              'export AWS_SECRET_NAME=warcraftlogs-bot/credentials',
              'export CONFIG_S3_BUCKET=${{ secrets.CONFIG_S3_BUCKET }}',
              'export AWS_REGION=${{ secrets.AWS_REGION }}',
              'docker compose -f docker-compose.yml -f docker-compose.prod.yml pull',
              'docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --remove-orphans',
              'docker stop warcraftlogs-bot 2>/dev/null || true',
              'docker rm warcraftlogs-bot 2>/dev/null || true'
            ]" \
            --output text
```

The last two commands clean up the old standalone bot container if it exists.

**Step 2: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: expand deploy pipeline for full docker-compose stack"
```

---

### Task 9: Update Bot Entrypoint for Compose Compatibility

The bot `entrypoint.sh` currently works standalone. In docker-compose, it needs the same secrets/S3 mechanism. No changes needed — it already reads `AWS_SECRET_NAME` and `CONFIG_S3_BUCKET` from environment variables, which will be passed via the prod compose override.

However, `Dockerfile.web` doesn't have `entrypoint.sh` or `awscli` installed. The web containers need AWS CLI to fetch secrets at startup.

**Files:**
- Create: `web/entrypoint.sh`
- Modify: `Dockerfile.web`

**Step 1: Create web entrypoint script**

Create `web/entrypoint.sh`:

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

# --- Run the provided command ---
exec "$@"
```

**Step 2: Update Dockerfile.web to use entrypoint**

Modify `Dockerfile.web` — add `awscli`, copy `web/entrypoint.sh`, and use it as the entrypoint:

```dockerfile
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY web/frontend/package*.json ./
RUN npm ci
COPY web/frontend/ .
RUN npm run build

FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN pip install --no-cache-dir awscli

COPY requirements.txt .
COPY web/requirements.txt web-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r web-requirements.txt

COPY src/ src/
COPY web/ web/
COPY config.yaml .

COPY --from=frontend-build /frontend/dist web/frontend/dist

COPY web/entrypoint.sh .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "web.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

This way, `web-api` runs uvicorn (the default CMD) and `sync-worker` overrides CMD with `["python", "-m", "web.api.sync.run"]` in docker-compose. Both go through the entrypoint which loads secrets first.

**Step 3: Commit**

```bash
git add web/entrypoint.sh Dockerfile.web
git commit -m "feat: add entrypoint with secrets loading for web containers"
```

---

### Task 10: Verify Locally with docker-compose

**Step 1: Run the local stack**

Run: `docker compose up --build -d`
Expected: All 5 services start (postgres, bot may fail without .env — that's fine, focus on nginx + web-api + postgres)

**Step 2: Test Nginx proxy**

Run: `curl http://localhost/api/health`
Expected: `{"status":"ok"}`

**Step 3: Test frontend**

Open `http://localhost` in browser.
Expected: The React app loads.

**Step 4: Stop the stack**

Run: `docker compose down`

---

### Task 11: Terraform Apply and Cloudflare DNS (Manual)

This task is done manually by the user, not by an agent.

**Step 1: Run terraform apply**

```bash
cd infra
terraform plan
terraform apply
```

Note the `elastic_ip` output value.

**Step 2: Configure Cloudflare DNS**

In the Cloudflare dashboard for `crankguild.com`:

1. Add A record: `crankguild.com` → `<elastic_ip>` → Proxied (orange cloud)
2. Add CNAME record: `www` → `crankguild.com` → Proxied (orange cloud)
3. SSL/TLS → set mode to **Full**
4. Under SSL/TLS → Edge Certificates → Always Use HTTPS → **On**
5. Under SSL/TLS → Edge Certificates → HTTP Strict Transport Security (HSTS) → **Enable** (optional, recommended)

**Step 3: Verify DNS propagation**

Run: `dig crankguild.com`
Expected: Returns Cloudflare IP addresses (not your Elastic IP — Cloudflare proxies it)

**Step 4: Deploy and test**

Push to `main` to trigger the deploy pipeline, then:

Run: `curl -I https://crankguild.com`
Expected: HTTP 200 with Cloudflare headers (`cf-ray`, `server: cloudflare`)

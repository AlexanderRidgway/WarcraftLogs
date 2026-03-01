#!/bin/bash
set -e

# Install Docker
yum update -y
yum install -y docker
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
aws s3 cp "s3://${config_bucket}/deploy/docker-compose.prod.yml" docker-compose.prod.yml 2>/dev/null || echo "No compose file in S3 yet."
mkdir -p web
aws s3 cp "s3://${config_bucket}/deploy/nginx.conf" web/nginx.conf 2>/dev/null || echo "No nginx config in S3 yet."

# Pull images and start stack (if compose file exists)
if [ -f docker-compose.prod.yml ]; then
    export ECR_REGISTRY=$(echo ${ecr_url} | cut -d'/' -f1)
    export BOT_ECR_REPOSITORY=$(echo ${ecr_url} | cut -d'/' -f2)
    export WEB_ECR_REPOSITORY=$(echo ${ecr_url} | cut -d'/' -f2)-web
    export AWS_SECRET_NAME="${secret_name}"
    export CONFIG_S3_BUCKET="${config_bucket}"
    export AWS_REGION="${region}"

    docker compose -f docker-compose.prod.yml pull
    docker compose -f docker-compose.prod.yml up -d
fi

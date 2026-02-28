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

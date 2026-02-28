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
exec python -m src

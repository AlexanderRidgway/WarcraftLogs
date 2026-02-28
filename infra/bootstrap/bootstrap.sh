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

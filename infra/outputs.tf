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

output "elastic_ip" {
  description = "Elastic IP for crankguild.com DNS"
  value       = aws_eip.bot.public_ip
}

output "web_ecr_repository_url" {
  description = "ECR repository URL for web Docker images"
  value       = aws_ecr_repository.web.repository_url
}

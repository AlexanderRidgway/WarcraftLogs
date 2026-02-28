resource "aws_cloudwatch_log_group" "bot" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 30
}

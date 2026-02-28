resource "aws_secretsmanager_secret" "bot" {
  name                    = "${var.project_name}/credentials"
  description             = "WarcraftLogs bot secrets (Discord token, WCL credentials)"
  recovery_window_in_days = 7
}

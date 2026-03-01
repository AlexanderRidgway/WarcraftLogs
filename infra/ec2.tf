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

resource "aws_eip" "bot" {
  instance = aws_instance.bot.id

  tags = {
    Name = "${var.project_name}-eip"
  }
}

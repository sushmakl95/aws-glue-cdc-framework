resource "aws_db_subnet_group" "this" {
  name       = "${var.project_prefix}-pg-${var.environment}"
  subnet_ids = var.subnet_ids
}

resource "aws_security_group" "postgres" {
  name        = "${var.project_prefix}-pg-sg-${var.environment}"
  description = "Postgres operational mirror"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.glue_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

data "aws_secretsmanager_secret_version" "postgres" {
  secret_id = var.master_secret_arn
}

resource "aws_db_instance" "this" {
  identifier             = "${var.project_prefix}-pg-${var.environment}"
  engine                 = "postgres"
  engine_version         = "16.2"
  instance_class         = "db.t4g.micro"
  allocated_storage      = 20
  max_allocated_storage  = 50
  storage_encrypted      = true
  db_name                = "operational"
  username               = jsondecode(data.aws_secretsmanager_secret_version.postgres.secret_string)["username"]
  password               = jsondecode(data.aws_secretsmanager_secret_version.postgres.secret_string)["password"]
  db_subnet_group_name   = aws_db_subnet_group.this.name
  vpc_security_group_ids = [aws_security_group.postgres.id]
  publicly_accessible    = false
  skip_final_snapshot    = true

  backup_retention_period = 7
  deletion_protection     = false # set to true in prod
}

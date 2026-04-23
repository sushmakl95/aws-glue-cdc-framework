resource "aws_redshift_subnet_group" "this" {
  name       = "${var.project_prefix}-redshift-${var.environment}"
  subnet_ids = var.subnet_ids
}

resource "aws_security_group" "redshift" {
  name        = "${var.project_prefix}-redshift-sg-${var.environment}"
  description = "Redshift cluster"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5439
    to_port         = 5439
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

# Password is populated from Secrets Manager — terraform only references the secret
data "aws_secretsmanager_secret_version" "redshift" {
  secret_id = var.master_secret_arn
}

resource "aws_redshift_cluster" "this" {
  cluster_identifier = "${var.project_prefix}-redshift-${var.environment}"
  database_name      = "analytics"
  master_username    = jsondecode(data.aws_secretsmanager_secret_version.redshift.secret_string)["username"]
  master_password    = jsondecode(data.aws_secretsmanager_secret_version.redshift.secret_string)["password"]

  node_type       = "dc2.large"
  cluster_type    = "single-node"
  number_of_nodes = 1

  cluster_subnet_group_name = aws_redshift_subnet_group.this.name
  vpc_security_group_ids    = [aws_security_group.redshift.id]
  iam_roles                 = [var.iam_role_arn]
  encrypted                 = true
  publicly_accessible       = false
  skip_final_snapshot       = true

  # Cost safety: auto-pause in dev environments
  enhanced_vpc_routing = true
}

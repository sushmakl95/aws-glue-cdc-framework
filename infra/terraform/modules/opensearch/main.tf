resource "aws_security_group" "opensearch" {
  name        = "${var.project_prefix}-os-sg-${var.environment}"
  description = "OpenSearch domain"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [var.glue_security_group_id]
  }
}

data "aws_secretsmanager_secret_version" "opensearch" {
  secret_id = var.master_secret_arn
}

resource "aws_opensearch_domain" "this" {
  domain_name    = "${var.project_prefix}-os-${var.environment}"
  engine_version = "OpenSearch_2.11"

  cluster_config {
    instance_type  = "t3.small.search"
    instance_count = 1
  }

  ebs_options {
    ebs_enabled = true
    volume_size = 10
    volume_type = "gp3"
  }

  vpc_options {
    subnet_ids         = var.subnet_ids
    security_group_ids = [aws_security_group.opensearch.id]
  }

  encrypt_at_rest {
    enabled = true
  }

  node_to_node_encryption {
    enabled = true
  }

  domain_endpoint_options {
    enforce_https       = true
    tls_security_policy = "Policy-Min-TLS-1-2-2019-07"
  }

  advanced_security_options {
    enabled                        = true
    internal_user_database_enabled = true
    master_user_options {
      master_user_name     = jsondecode(data.aws_secretsmanager_secret_version.opensearch.secret_string)["username"]
      master_user_password = jsondecode(data.aws_secretsmanager_secret_version.opensearch.secret_string)["password"]
    }
  }
}

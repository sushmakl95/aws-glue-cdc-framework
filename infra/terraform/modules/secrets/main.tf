resource "aws_secretsmanager_secret" "mysql_source" {
  name                    = "${var.project_prefix}/${var.environment}/mysql-source"
  description             = "Source MySQL (Debezium CDC)"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret" "redshift" {
  name                    = "${var.project_prefix}/${var.environment}/redshift"
  description             = "Redshift analytics target"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret" "postgres" {
  name                    = "${var.project_prefix}/${var.environment}/postgres"
  description             = "Postgres operational mirror"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret" "opensearch" {
  name                    = "${var.project_prefix}/${var.environment}/opensearch"
  description             = "OpenSearch search index"
  recovery_window_in_days = 7
}

# NOTE: Secret *values* are set manually (aws secretsmanager put-secret-value).
# Committing them to terraform would leak them into state files.

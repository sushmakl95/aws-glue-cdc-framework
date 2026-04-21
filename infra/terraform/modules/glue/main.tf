resource "aws_security_group" "glue" {
  name        = "${var.project_prefix}-glue-${var.environment}"
  description = "Glue job connectivity"
  vpc_id      = var.vpc_id

  # Self-referencing rule — Glue connections require this for cross-node comms
  ingress {
    from_port = 0
    to_port   = 65535
    protocol  = "tcp"
    self      = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# Glue VPC connection — required to reach VPC-bound targets (Redshift, RDS, OpenSearch)
resource "aws_glue_connection" "vpc" {
  name            = "${var.project_prefix}-vpc-${var.environment}"
  connection_type = "NETWORK"

  physical_connection_requirements {
    subnet_id              = var.subnet_ids[0]
    security_group_id_list = [aws_security_group.glue.id]
    availability_zone      = data.aws_subnet.first.availability_zone
  }
}

data "aws_subnet" "first" {
  id = var.subnet_ids[0]
}

resource "aws_glue_job" "cdc" {
  name              = "${var.project_prefix}-cdc-${var.environment}"
  role_arn          = var.role_arn
  glue_version      = "4.0"
  worker_type       = var.worker_type
  number_of_workers = var.number_of_workers
  timeout           = 60
  max_retries       = 0  # Step Functions retries — no double-retry

  command {
    script_location = "s3://${var.scripts_bucket}/glue/cdc_to_sinks.py"
    python_version  = "3"
  }

  default_arguments = {
    "--job-language"                     = "python"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--enable-glue-datacatalog"          = "true"
    "--enable-job-insights"              = "true"
    "--enable-auto-scaling"              = "true"
    "--extra-py-files"                   = "s3://${var.scripts_bucket}/glue/src.zip"
    "--additional-python-modules" = join(",", [
      "boto3==1.34.*",
      "psycopg2-binary==2.9.*",
      "redshift-connector==2.1.*",
      "opensearch-py==2.4.*",
      "structlog==24.1.*",
      "pydantic==2.6.*",
    ])
    "--TempDir" = "s3://${var.scripts_bucket}/glue/tmp/"
  }

  connections = [aws_glue_connection.vpc.name]

  execution_property {
    max_concurrent_runs = 1
  }
}

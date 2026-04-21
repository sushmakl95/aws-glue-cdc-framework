# DynamoDB for idempotency tracking
resource "aws_dynamodb_table" "idempotency" {
  name         = "${var.project_prefix}-idempotency-${var.environment}"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"

  attribute {
    name = "pk"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }
}

# SNS topic for pipeline alerts
resource "aws_sns_topic" "alerts" {
  name              = "${var.project_prefix}-alerts-${var.environment}"
  kms_master_key_id = "alias/aws/sns"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# CloudWatch log group for all Glue jobs
resource "aws_cloudwatch_log_group" "glue" {
  name              = "/aws-glue/jobs/${var.project_prefix}-${var.environment}"
  retention_in_days = 14
}

# Dashboard
resource "aws_cloudwatch_dashboard" "pipeline" {
  dashboard_name = "${var.project_prefix}-${var.environment}"
  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          title   = "CDC Rows Processed (by Sink)"
          region  = data.aws_region.current.name
          view    = "timeSeries"
          stacked = false
          metrics = [
            ["CDC/Glue", "CdcRowsUpserted", "Sink", "redshift"],
            ["CDC/Glue", "CdcRowsUpserted", "Sink", "postgres"],
            ["CDC/Glue", "CdcRowsUpserted", "Sink", "opensearch"],
          ]
          period = 300
          stat   = "Sum"
        }
      },
      {
        type   = "metric"
        width  = 12
        height = 6
        properties = {
          title  = "CDC Deletes (by Sink)"
          region = data.aws_region.current.name
          view   = "timeSeries"
          metrics = [
            ["CDC/Glue", "CdcRowsDeleted", "Sink", "redshift"],
            ["CDC/Glue", "CdcRowsDeleted", "Sink", "postgres"],
            ["CDC/Glue", "CdcRowsDeleted", "Sink", "opensearch"],
          ]
          period = 300
          stat   = "Sum"
        }
      }
    ]
  })
}

data "aws_region" "current" {}

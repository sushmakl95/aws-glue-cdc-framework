resource "aws_sfn_state_machine" "cdc" {
  name     = "${var.project_prefix}-cdc-${var.environment}"
  role_arn = var.role_arn
  type     = "STANDARD"

  definition = jsonencode({
    Comment = "CDC pipeline: Glue job → DQ validation → multi-sink fanout → notify"
    StartAt = "RunCdcJob"
    States = {
      RunCdcJob = {
        Type     = "Task"
        Resource = "arn:aws:states:::glue:startJobRun.sync"
        Parameters = {
          JobName = var.glue_job_name
          Arguments = {
            "--batch_id.$"    = "$.batch_id"
            "--raw_s3_path.$" = "$.raw_prefix"
            "--config_path"   = var.config_s3_path
          }
        }
        Retry = [{
          ErrorEquals     = ["States.ALL"]
          IntervalSeconds = 30
          MaxAttempts     = 2
          BackoffRate     = 2.0
        }]
        Catch = [{
          ErrorEquals = ["States.ALL"]
          Next        = "NotifyFailure"
          ResultPath  = "$.error"
        }]
        Next = "NotifySuccess"
      }
      NotifySuccess = {
        Type     = "Task"
        Resource = "arn:aws:states:::sns:publish"
        Parameters = {
          TopicArn    = var.sns_topic_arn
          Subject     = "[CDC] Pipeline SUCCEEDED"
          "Message.$" = "$"
        }
        End = true
      }
      NotifyFailure = {
        Type     = "Task"
        Resource = "arn:aws:states:::sns:publish"
        Parameters = {
          TopicArn    = var.sns_topic_arn
          Subject     = "[CDC] Pipeline FAILED"
          "Message.$" = "$.error"
        }
        Next = "FailState"
      }
      FailState = {
        Type  = "Fail"
        Error = "PipelineFailed"
        Cause = "See SNS notification for details"
      }
    }
  })

  logging_configuration {
    log_destination        = "${aws_cloudwatch_log_group.sfn.arn}:*"
    include_execution_data = true
    level                  = "ALL"
  }
}

resource "aws_cloudwatch_log_group" "sfn" {
  name              = "/aws/states/${var.project_prefix}-cdc-${var.environment}"
  retention_in_days = 14
}

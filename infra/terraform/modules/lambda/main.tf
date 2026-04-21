data "archive_file" "s3_trigger" {
  type        = "zip"
  source_file = "${path.module}/../../../../src/lambdas/s3_trigger.py"
  output_path = "${path.module}/builds/s3_trigger.zip"
}

data "archive_file" "sfn_notifier" {
  type        = "zip"
  source_file = "${path.module}/../../../../src/lambdas/sfn_notifier.py"
  output_path = "${path.module}/builds/sfn_notifier.zip"
}

resource "aws_lambda_function" "s3_trigger" {
  function_name    = "${var.project_prefix}-s3-trigger-${var.environment}"
  role             = var.role_arn
  handler          = "s3_trigger.handler"
  runtime          = "python3.11"
  timeout          = 60
  filename         = data.archive_file.s3_trigger.output_path
  source_code_hash = data.archive_file.s3_trigger.output_base64sha256

  environment {
    variables = {
      STATE_MACHINE_ARN          = var.state_machine_arn
      MIN_BATCH_INTERVAL_SECONDS = "60"
    }
  }
}

resource "aws_lambda_function" "sfn_notifier" {
  function_name    = "${var.project_prefix}-sfn-notifier-${var.environment}"
  role             = var.role_arn
  handler          = "sfn_notifier.handler"
  runtime          = "python3.11"
  timeout          = 30
  filename         = data.archive_file.sfn_notifier.output_path
  source_code_hash = data.archive_file.sfn_notifier.output_base64sha256

  environment {
    variables = {
      SNS_TOPIC_ARN = var.sns_topic_arn
    }
  }
}

# S3 event notification triggering s3_trigger Lambda
resource "aws_lambda_permission" "s3_invoke" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.s3_trigger.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = var.raw_bucket_arn
}

resource "aws_s3_bucket_notification" "raw" {
  bucket = var.raw_bucket_name

  lambda_function {
    lambda_function_arn = aws_lambda_function.s3_trigger.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "cdc/raw/"
    filter_suffix       = ".gz"
  }

  depends_on = [aws_lambda_permission.s3_invoke]
}

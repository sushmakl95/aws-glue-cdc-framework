# Scheduled trigger: fire the state machine on a cron/rate schedule
resource "aws_cloudwatch_event_rule" "schedule" {
  name                = "${var.project_prefix}-schedule-${var.environment}"
  description         = "Scheduled CDC batch processing"
  schedule_expression = var.schedule_expression
}

resource "aws_cloudwatch_event_target" "schedule_sfn" {
  rule     = aws_cloudwatch_event_rule.schedule.name
  arn      = var.state_machine_arn
  role_arn = var.eventbridge_role_arn
  input = jsonencode({
    batch_id   = "$.id"
    raw_prefix = ""
    trigger    = "scheduled"
  })
}

# Reactive trigger: Step Functions state change → notifier Lambda
resource "aws_cloudwatch_event_rule" "sfn_state_change" {
  name        = "${var.project_prefix}-sfn-state-${var.environment}"
  description = "Fire notifier on SFN state change"

  event_pattern = jsonencode({
    source      = ["aws.states"]
    detail-type = ["Step Functions Execution Status Change"]
    detail = {
      stateMachineArn = [var.state_machine_arn]
      status          = ["SUCCEEDED", "FAILED", "TIMED_OUT", "ABORTED"]
    }
  })
}

resource "aws_cloudwatch_event_target" "sfn_state_change_lambda" {
  rule = aws_cloudwatch_event_rule.sfn_state_change.name
  arn  = var.sfn_notifier_function_arn
}

resource "aws_lambda_permission" "eventbridge_invoke_notifier" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.sfn_notifier_function_arn
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.sfn_state_change.arn
}

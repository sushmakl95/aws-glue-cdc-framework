output "schedule_rule_arn" { value = aws_cloudwatch_event_rule.schedule.arn }
output "state_change_rule_arn" { value = aws_cloudwatch_event_rule.sfn_state_change.arn }

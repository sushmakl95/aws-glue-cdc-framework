output "idempotency_table_name" { value = aws_dynamodb_table.idempotency.name }
output "idempotency_table_arn" { value = aws_dynamodb_table.idempotency.arn }
output "sns_topic_arn" { value = aws_sns_topic.alerts.arn }
output "log_group_name" { value = aws_cloudwatch_log_group.glue.name }

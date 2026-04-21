output "s3_trigger_function_arn" { value = aws_lambda_function.s3_trigger.arn }
output "sfn_notifier_function_arn" { value = aws_lambda_function.sfn_notifier.arn }

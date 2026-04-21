output "glue_role_arn" { value = aws_iam_role.glue.arn }
output "redshift_role_arn" { value = aws_iam_role.redshift.arn }
output "stepfunctions_role_arn" { value = aws_iam_role.stepfunctions.arn }
output "lambda_role_arn" { value = aws_iam_role.lambda.arn }
output "eventbridge_role_arn" { value = aws_iam_role.eventbridge.arn }

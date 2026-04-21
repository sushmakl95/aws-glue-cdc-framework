output "job_name" { value = aws_glue_job.cdc.name }
output "job_arn" { value = aws_glue_job.cdc.arn }
output "security_group_id" { value = aws_security_group.glue.id }
output "connection_name" { value = aws_glue_connection.vpc.name }

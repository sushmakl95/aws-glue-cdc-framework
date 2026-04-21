output "raw_bucket" {
  value = module.s3.raw_bucket_name
}

output "scripts_bucket" {
  value = module.s3.scripts_bucket
}

output "kinesis_stream_name" {
  value = module.kinesis.stream_name
}

output "glue_job_name" {
  value = module.glue.job_name
}

output "state_machine_arn" {
  value = module.stepfunctions.state_machine_arn
}

output "redshift_endpoint" {
  value     = module.redshift.endpoint
  sensitive = true
}

output "postgres_endpoint" {
  value     = module.rds.endpoint
  sensitive = true
}

output "sns_alert_topic" {
  value = module.monitoring.sns_topic_arn
}

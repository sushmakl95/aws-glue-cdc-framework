variable "project_prefix" { type = string }
variable "environment" { type = string }
variable "raw_bucket_arn" { type = string }
variable "staging_bucket_arn" { type = string }
variable "kinesis_stream_arn" { type = string }
variable "secret_arns" { type = list(string) }
variable "dynamodb_table_arn" { type = string }
variable "sns_topic_arn" { type = string }

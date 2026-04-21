variable "project_prefix" { type = string }
variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "glue_security_group_id" { type = string }
variable "iam_role_arn" { type = string }
variable "master_secret_arn" { type = string }

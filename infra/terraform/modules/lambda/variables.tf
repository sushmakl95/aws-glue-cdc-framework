variable "project_prefix" { type = string }
variable "environment" { type = string }
variable "role_arn" { type = string }
variable "state_machine_arn" { type = string }
variable "sns_topic_arn" { type = string }
variable "raw_bucket_arn" { type = string }
variable "raw_bucket_name" { type = string }

terraform {
  required_providers {
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }
}

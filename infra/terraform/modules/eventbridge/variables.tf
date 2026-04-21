variable "project_prefix" { type = string }
variable "environment" { type = string }
variable "state_machine_arn" { type = string }
variable "sfn_notifier_function_arn" { type = string }
variable "eventbridge_role_arn" { type = string }
variable "schedule_expression" {
  type    = string
  default = "rate(15 minutes)"
}

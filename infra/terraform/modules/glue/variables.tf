variable "project_prefix" { type = string }
variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "role_arn" { type = string }
variable "scripts_bucket" { type = string }
variable "worker_type" {
  type    = string
  default = "G.1X"
}
variable "number_of_workers" {
  type    = number
  default = 5
}

variable "aws_region" {
  type    = string
  default = "ap-south-1"
}

variable "environment" {
  type = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "project_prefix" {
  type    = string
  default = "cdc-glue"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "azs" {
  type    = list(string)
  default = ["ap-south-1a", "ap-south-1b"]
}

variable "glue_worker_type" {
  type    = string
  default = "G.1X"
}

variable "glue_num_workers" {
  type    = number
  default = 5
}

variable "eventbridge_schedule" {
  type    = string
  default = "rate(15 minutes)"
}

variable "alert_email" {
  type    = string
  default = ""
}

variable "enable_opensearch" {
  type    = bool
  default = false
}

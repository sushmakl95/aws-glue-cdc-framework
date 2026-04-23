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
variable "iceberg_warehouse_bucket" {
  type        = string
  description = "S3 bucket for Iceberg warehouse root. Glue 5.0 writes silver.cdc_events here."
}
variable "openlineage_url" {
  type        = string
  description = "OpenLineage receiver (Marquez / DataHub)"
  default     = "http://marquez.internal:5000/api/v1/lineage"
}

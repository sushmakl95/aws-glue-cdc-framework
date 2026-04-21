terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.30"
    }
  }

  backend "s3" {
    key = "aws-glue-cdc-framework/terraform.tfstate"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "aws-glue-cdc-framework"
      Environment = var.environment
      Owner       = "data-platform"
      ManagedBy   = "terraform"
    }
  }
}

module "vpc" {
  source         = "./modules/vpc"
  project_prefix = var.project_prefix
  environment    = var.environment
  vpc_cidr       = var.vpc_cidr
  azs            = var.azs
}

module "s3" {
  source         = "./modules/s3"
  project_prefix = var.project_prefix
  environment    = var.environment
}

module "kinesis" {
  source         = "./modules/kinesis"
  project_prefix = var.project_prefix
  environment    = var.environment
  raw_bucket_arn = module.s3.raw_bucket_arn
}

module "secrets" {
  source         = "./modules/secrets"
  project_prefix = var.project_prefix
  environment    = var.environment
}

module "monitoring" {
  source            = "./modules/monitoring"
  project_prefix    = var.project_prefix
  environment       = var.environment
  alert_email       = var.alert_email
}

module "iam" {
  source             = "./modules/iam"
  project_prefix     = var.project_prefix
  environment        = var.environment
  raw_bucket_arn     = module.s3.raw_bucket_arn
  staging_bucket_arn = module.s3.staging_bucket_arn
  kinesis_stream_arn = module.kinesis.stream_arn
  secret_arns        = module.secrets.secret_arns
  dynamodb_table_arn = module.monitoring.idempotency_table_arn
  sns_topic_arn      = module.monitoring.sns_topic_arn
}

module "glue" {
  source            = "./modules/glue"
  project_prefix    = var.project_prefix
  environment       = var.environment
  vpc_id            = module.vpc.vpc_id
  subnet_ids        = module.vpc.private_subnet_ids
  role_arn          = module.iam.glue_role_arn
  scripts_bucket    = module.s3.scripts_bucket
  worker_type       = var.glue_worker_type
  number_of_workers = var.glue_num_workers
}

module "redshift" {
  source                 = "./modules/redshift"
  project_prefix         = var.project_prefix
  environment            = var.environment
  vpc_id                 = module.vpc.vpc_id
  subnet_ids             = module.vpc.private_subnet_ids
  glue_security_group_id = module.glue.security_group_id
  iam_role_arn           = module.iam.redshift_role_arn
  master_secret_arn      = module.secrets.redshift_secret_arn
}

module "rds" {
  source                 = "./modules/rds"
  project_prefix         = var.project_prefix
  environment            = var.environment
  vpc_id                 = module.vpc.vpc_id
  subnet_ids             = module.vpc.private_subnet_ids
  glue_security_group_id = module.glue.security_group_id
  master_secret_arn      = module.secrets.postgres_secret_arn
}

module "stepfunctions" {
  source          = "./modules/stepfunctions"
  project_prefix  = var.project_prefix
  environment     = var.environment
  role_arn        = module.iam.stepfunctions_role_arn
  glue_job_name   = module.glue.job_name
  raw_bucket_name = module.s3.raw_bucket_name
  config_s3_path  = "s3://${module.s3.scripts_bucket}/config/${var.environment}.yaml"
  sns_topic_arn   = module.monitoring.sns_topic_arn
}

module "lambda" {
  source            = "./modules/lambda"
  project_prefix    = var.project_prefix
  environment       = var.environment
  role_arn          = module.iam.lambda_role_arn
  state_machine_arn = module.stepfunctions.state_machine_arn
  sns_topic_arn     = module.monitoring.sns_topic_arn
  raw_bucket_arn    = module.s3.raw_bucket_arn
  raw_bucket_name   = module.s3.raw_bucket_name
}

module "eventbridge" {
  source                    = "./modules/eventbridge"
  project_prefix            = var.project_prefix
  environment               = var.environment
  state_machine_arn         = module.stepfunctions.state_machine_arn
  sfn_notifier_function_arn = module.lambda.sfn_notifier_function_arn
  eventbridge_role_arn      = module.iam.eventbridge_role_arn
  schedule_expression       = var.eventbridge_schedule
}

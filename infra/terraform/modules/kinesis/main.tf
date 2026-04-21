resource "aws_kinesis_stream" "cdc" {
  name             = "${var.project_prefix}-cdc-${var.environment}"
  retention_period = 48
  stream_mode_details {
    stream_mode = "ON_DEMAND"
  }
  encryption_type = "KMS"
  kms_key_id      = "alias/aws/kinesis"
}

# Firehose to deliver Kinesis → S3 with buffered batching
resource "aws_kinesis_firehose_delivery_stream" "to_s3" {
  name        = "${var.project_prefix}-firehose-${var.environment}"
  destination = "extended_s3"

  kinesis_source_configuration {
    kinesis_stream_arn = aws_kinesis_stream.cdc.arn
    role_arn           = aws_iam_role.firehose.arn
  }

  extended_s3_configuration {
    role_arn            = aws_iam_role.firehose.arn
    bucket_arn          = var.raw_bucket_arn
    buffering_size      = 5
    buffering_interval  = 60
    compression_format  = "GZIP"
    prefix              = "cdc/raw/!{partitionKeyFromQuery:db}/!{partitionKeyFromQuery:table}/!{timestamp:yyyy/MM/dd/HH}/"
    error_output_prefix = "cdc/errors/!{firehose:error-output-type}/!{timestamp:yyyy/MM/dd/HH}/"

    dynamic_partitioning_configuration {
      enabled = true
    }

    processing_configuration {
      enabled = true
      processors {
        type = "MetadataExtraction"
        parameters {
          parameter_name  = "MetadataExtractionQuery"
          parameter_value = "{db: .payload.source.db, table: .payload.source.table}"
        }
        parameters {
          parameter_name  = "JsonParsingEngine"
          parameter_value = "JQ-1.6"
        }
      }
    }
  }
}

resource "aws_iam_role" "firehose" {
  name = "${var.project_prefix}-firehose-${var.environment}"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "firehose.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "firehose" {
  role = aws_iam_role.firehose.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["kinesis:DescribeStream", "kinesis:GetRecords", "kinesis:GetShardIterator", "kinesis:ListShards"]
        Resource = aws_kinesis_stream.cdc.arn
      },
      {
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetBucketLocation", "s3:ListBucket"]
        Resource = [var.raw_bucket_arn, "${var.raw_bucket_arn}/*"]
      }
    ]
  })
}

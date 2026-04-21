resource "aws_s3_bucket" "raw" {
  bucket = "${var.project_prefix}-raw-${var.environment}-${random_string.suffix.result}"
}

resource "aws_s3_bucket" "staging" {
  bucket = "${var.project_prefix}-staging-${var.environment}-${random_string.suffix.result}"
}

resource "aws_s3_bucket" "scripts" {
  bucket = "${var.project_prefix}-scripts-${var.environment}-${random_string.suffix.result}"
}

resource "random_string" "suffix" {
  length  = 6
  special = false
  upper   = false
}

# Encryption + public access block for all buckets
resource "aws_s3_bucket_server_side_encryption_configuration" "all" {
  for_each = toset([aws_s3_bucket.raw.id, aws_s3_bucket.staging.id, aws_s3_bucket.scripts.id])
  bucket   = each.key
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "all" {
  for_each                = toset([aws_s3_bucket.raw.id, aws_s3_bucket.staging.id, aws_s3_bucket.scripts.id])
  bucket                  = each.key
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Lifecycle: expire raw CDC events after 90 days, staging after 14 days
resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id
  rule {
    id     = "expire-raw-cdc"
    status = "Enabled"
    filter { prefix = "cdc/raw/" }
    expiration { days = 90 }
    noncurrent_version_expiration { noncurrent_days = 30 }
    abort_incomplete_multipart_upload { days_after_initiation = 7 }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "staging" {
  bucket = aws_s3_bucket.staging.id
  rule {
    id     = "expire-staging"
    status = "Enabled"
    filter { prefix = "" }
    expiration { days = 14 }
    abort_incomplete_multipart_upload { days_after_initiation = 3 }
  }
}

# Deny insecure transport
resource "aws_s3_bucket_policy" "deny_insecure" {
  for_each = toset([aws_s3_bucket.raw.id, aws_s3_bucket.staging.id, aws_s3_bucket.scripts.id])
  bucket   = each.key
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = "s3:*"
      Resource = [
        "arn:aws:s3:::${each.key}",
        "arn:aws:s3:::${each.key}/*"
      ]
      Condition = {
        Bool = { "aws:SecureTransport" = "false" }
      }
    }]
  })
}

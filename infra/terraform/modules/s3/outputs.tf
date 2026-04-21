output "raw_bucket_name" { value = aws_s3_bucket.raw.id }
output "raw_bucket_arn" { value = aws_s3_bucket.raw.arn }
output "staging_bucket_name" { value = aws_s3_bucket.staging.id }
output "staging_bucket_arn" { value = aws_s3_bucket.staging.arn }
output "scripts_bucket" { value = aws_s3_bucket.scripts.id }
output "scripts_bucket_arn" { value = aws_s3_bucket.scripts.arn }

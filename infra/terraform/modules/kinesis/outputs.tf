output "stream_name" { value = aws_kinesis_stream.cdc.name }
output "stream_arn" { value = aws_kinesis_stream.cdc.arn }
output "firehose_arn" { value = aws_kinesis_firehose_delivery_stream.to_s3.arn }

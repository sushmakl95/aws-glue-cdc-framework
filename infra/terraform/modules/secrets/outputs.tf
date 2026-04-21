output "mysql_source_secret_arn" { value = aws_secretsmanager_secret.mysql_source.arn }
output "redshift_secret_arn" { value = aws_secretsmanager_secret.redshift.arn }
output "postgres_secret_arn" { value = aws_secretsmanager_secret.postgres.arn }
output "opensearch_secret_arn" { value = aws_secretsmanager_secret.opensearch.arn }
output "secret_arns" {
  value = [
    aws_secretsmanager_secret.mysql_source.arn,
    aws_secretsmanager_secret.redshift.arn,
    aws_secretsmanager_secret.postgres.arn,
    aws_secretsmanager_secret.opensearch.arn,
  ]
}

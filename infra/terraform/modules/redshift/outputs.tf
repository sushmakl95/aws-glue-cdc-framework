output "endpoint" { value = aws_redshift_cluster.this.endpoint }
output "cluster_identifier" { value = aws_redshift_cluster.this.cluster_identifier }
output "security_group_id" { value = aws_security_group.redshift.id }

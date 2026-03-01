output "redis_endpoint" {
  value = aws_elasticache_cluster.redis.cache_nodes[0].address
}

output "redis_url" {
  value = "redis://${aws_elasticache_cluster.redis.cache_nodes[0].address}:6379/0"
}

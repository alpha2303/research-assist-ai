output "alb_5xx_alarm_arn" {
  description = "ARN of the ALB 5xx CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.alb_5xx.arn
}

output "ecs_cpu_alarm_arn" {
  description = "ARN of the ECS CPU CloudWatch alarm"
  value       = aws_cloudwatch_metric_alarm.ecs_cpu_high.arn
}

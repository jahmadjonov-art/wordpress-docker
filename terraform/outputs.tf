output "public_ip" {
  description = "Server public IP address"
  value       = aws_eip.app.public_ip
}

output "app_url" {
  description = "Finance dashboard URL"
  value       = "http://${aws_eip.app.public_ip}:8001"
}

output "ssh_command" {
  description = "Command to SSH into the server"
  value       = "ssh ubuntu@${aws_eip.app.public_ip}"
}

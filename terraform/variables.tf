variable "aws_region" {
  description = "AWS region to deploy into"
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type"
  default     = "t3.micro"
}

variable "ssh_public_key" {
  description = "Contents of your SSH public key (~/.ssh/id_rsa.pub)"
}

variable "repo_url" {
  description = "Git repo to clone on the server"
  default     = "https://github.com/jahmadjonov-art/wordpress-docker.git"
}

variable "finance_user" {
  description = "Dashboard login username"
  default     = "driver"
}

variable "finance_pass" {
  description = "Dashboard login password"
  sensitive   = true
}

variable "ca_operation" {
  description = "Set to true if operating in California (applies scoring penalty to pre-2010 trucks)"
  default     = "false"
}

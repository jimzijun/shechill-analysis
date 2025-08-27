terraform {
  required_version = ">= 1.0"
  required_providers {
    null = {
      source  = "hashicorp/null"
      version = "~> 3.0"
    }
  }
}

# Variables
variable "nas_host" {
  description = "Synology NAS hostname or IP"
  type        = string
}

variable "ssh_user" {
  description = "SSH user for NAS access"
  type        = string
}

variable "ssh_private_key" {
  description = "SSH private key content"
  type        = string
  sensitive   = true
}

variable "container_name" {
  description = "Docker container name"
  type        = string
  default     = "shechill-analysis"
}

variable "container_port" {
  description = "Container port to expose"
  type        = number
  default     = 8000
}

variable "image_name" {
  description = "Docker image name"
  type        = string
  default     = "shechill-analysis:latest"
}

# Docker image build
resource "null_resource" "docker_build" {
  triggers = {
    dockerfile_hash = filemd5("../Dockerfile")
    source_hash     = md5(join("", [for f in fileset("../", "**/*.py") : filemd5("../${f}")]))
  }

  provisioner "local-exec" {
    command = "cd .. && docker build -t ${var.image_name} ."
  }
}

# Docker image save and transfer
resource "null_resource" "docker_deploy" {
  depends_on = [null_resource.docker_build]

  triggers = {
    image_id = null_resource.docker_build.id
  }

  provisioner "local-exec" {
    command = <<-EOT
      cd ..
      docker save ${var.image_name} | gzip > /tmp/shechill-analysis.tar.gz
      echo '${var.ssh_private_key}' > /tmp/terraform_key
      chmod 600 /tmp/terraform_key
      scp -o StrictHostKeyChecking=no -i /tmp/terraform_key /tmp/shechill-analysis.tar.gz ${var.ssh_user}@${var.nas_host}:/tmp/
      rm -f /tmp/shechill-analysis.tar.gz /tmp/terraform_key
    EOT
  }
}

# Container deployment on NAS
resource "null_resource" "container_deploy" {
  depends_on = [null_resource.docker_deploy]

  triggers = {
    deployment_id = null_resource.docker_deploy.id
  }

  provisioner "remote-exec" {
    connection {
      type        = "ssh"
      user        = var.ssh_user
      host        = var.nas_host
      private_key = file(var.ssh_private_key_path)
    }

    inline = [
      "cd /tmp",
      "bash -l -c 'docker load < shechill-analysis.tar.gz'",
      "bash -l -c 'docker stop ${var.container_name} || true'",
      "bash -l -c 'docker rm ${var.container_name} || true'",
      "bash -l -c 'docker run -d --name ${var.container_name} --restart unless-stopped -p ${var.container_port}:${var.container_port} ${var.image_name}'",
      "rm -f shechill-analysis.tar.gz",
      "bash -l -c 'docker ps | grep ${var.container_name}'"
    ]
  }
}

# Health check
resource "null_resource" "health_check" {
  depends_on = [null_resource.container_deploy]

  triggers = {
    container_id = null_resource.container_deploy.id
  }

  provisioner "local-exec" {
    command = <<-EOT
      sleep 10
      curl -f http://${var.nas_host}:${var.container_port} || exit 1
    EOT
  }
}

# Outputs
output "deployment_endpoint" {
  description = "Application endpoint URL"
  value       = "http://${var.nas_host}:${var.container_port}"
}

output "container_status" {
  description = "Container deployment status"
  value       = "deployed"
  depends_on  = [null_resource.health_check]
}
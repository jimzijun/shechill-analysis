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

variable "nas_username" {
  description = "SSH username for NAS access"
  type        = string
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

# Docker image build and deployment via SSH
resource "null_resource" "docker_build_and_deploy" {
  triggers = {
    dockerfile_hash = filemd5("../Dockerfile")
    source_hash     = md5(join("", [for f in fileset("../", "**/*.py") : filemd5("../${f}")]))
  }

  # Build image locally
  provisioner "local-exec" {
    command = "cd .. && docker build -t ${var.image_name} ."
  }
  
  # Save and transfer image
  provisioner "local-exec" {
    command = <<-EOT
      cd ..
      docker save ${var.image_name} | gzip > /tmp/shechill-analysis.tar.gz
      scp -i ~/.ssh/synology_nas -o StrictHostKeyChecking=no /tmp/shechill-analysis.tar.gz ${var.nas_username}@${var.nas_host}:/tmp/
      rm -f /tmp/shechill-analysis.tar.gz
    EOT
  }
  
  # Deploy container on NAS
  provisioner "local-exec" {
    command = <<-EOT
      ssh -i ~/.ssh/synology_nas -o StrictHostKeyChecking=no ${var.nas_username}@${var.nas_host} << 'ENDSSH'
        cd /tmp
        /usr/local/bin/docker load < shechill-analysis.tar.gz
        /usr/local/bin/docker stop ${var.container_name} || true
        /usr/local/bin/docker rm ${var.container_name} || true
        /usr/local/bin/docker run -d --name ${var.container_name} --restart unless-stopped -p ${var.container_port}:${var.container_port} ${var.image_name}
        rm -f shechill-analysis.tar.gz
        /usr/local/bin/docker ps | grep ${var.container_name}
ENDSSH
    EOT
  }
}

# Health check
resource "null_resource" "health_check" {
  depends_on = [null_resource.docker_build_and_deploy]

  triggers = {
    deployment_id = null_resource.docker_build_and_deploy.id
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
terraform {
  required_version = ">= 1.0"
  required_providers {
    synology = {
      source  = "synology-community/synology"
      version = "~> 0.5"
    }
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
  description = "Synology NAS admin username"
  type        = string
}

variable "nas_password" {
  description = "Synology NAS admin password"
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

# Configure Synology provider
provider "synology" {
  host            = "${var.nas_host}:5001"
  user            = var.nas_username
  password        = var.nas_password
  skip_cert_check = true
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

# Deploy container using Synology Container Manager
resource "synology_container_project" "shechill_analysis" {
  depends_on = [null_resource.docker_build]
  
  name = var.container_name
  
  compose_content = yamlencode({
    version = "3.8"
    services = {
      "${var.container_name}" = {
        image         = var.image_name
        container_name = var.container_name
        restart       = "unless-stopped"
        ports = [
          "${var.container_port}:${var.container_port}"
        ]
      }
    }
  })
  
  force_recreate = true
}

# Health check
resource "null_resource" "health_check" {
  depends_on = [synology_container_project.shechill_analysis]

  triggers = {
    container_id = synology_container_project.shechill_analysis.id
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
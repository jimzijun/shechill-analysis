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
  default     = 8001
}

variable "image_name" {
  description = "Docker image name"
  type        = string
  default     = "shechill-analysis:latest"
}

variable "persistent_data_path" {
  description = "Base path on NAS for persistent data storage"
  type        = string
  default     = "/volume1/docker/shechill-analysis"
}

variable "square_access_token" {
  description = "Square API access token"
  type        = string
  sensitive   = true
}

variable "square_location_id" {
  description = "Square location ID"
  type        = string
  sensitive   = true
}

# Docker image build and deployment via SSH
resource "null_resource" "docker_build_and_deploy" {
  triggers = {
    dockerfile_hash = filemd5("../Dockerfile")
    source_hash     = md5(join("", [for f in fileset("../", "**/*.py") : filemd5("../${f}")]))
  }

  # Note: Docker image is now built by GitHub Actions workflow
  
  # Note: Docker image is now transferred by GitHub Actions workflow
  # The image archive should already be available at /volume1/docker/shechill-analysis/uploads/shechill-analysis.tar.gz on the NAS
  
  # Deploy container on NAS
  provisioner "local-exec" {
    command = <<-EOT
      ssh -i ~/.ssh/synology_nas -o StrictHostKeyChecking=no -T ${var.nas_username}@${var.nas_host} << 'ENDSSH'
        # Create persistent directories with proper permissions
        mkdir -p ${var.persistent_data_path}/config
        mkdir -p ${var.persistent_data_path}/data
        mkdir -p ${var.persistent_data_path}/logs
        mkdir -p ${var.persistent_data_path}/uploads
        chmod -R 777 ${var.persistent_data_path}
        
        # Ensure directories exist and are writable by container
        ls -la ${var.persistent_data_path}
        
        cd ${var.persistent_data_path}/uploads
        /usr/local/bin/docker load < shechill-analysis.tar.gz
        /usr/local/bin/docker stop ${var.container_name} || true
        /usr/local/bin/docker rm ${var.container_name} || true
        /usr/local/bin/docker run -d --name ${var.container_name} --restart unless-stopped \
          -p ${var.container_port}:8000 \
          -e SQUARE_ACCESS_TOKEN="${var.square_access_token}" \
          -e SQUARE_LOCATION_ID="${var.square_location_id}" \
          -v ${var.persistent_data_path}/config:/app/config \
          -v ${var.persistent_data_path}/data:/app/data \
          -v ${var.persistent_data_path}/logs:/app/logs \
          ${var.image_name}
        rm -f shechill-analysis.tar.gz
        cd ~
        /usr/local/bin/docker ps | grep ${var.container_name}
ENDSSH
    EOT
  }
}


# Outputs
output "deployment_endpoint" {
  description = "Application endpoint URL (internal)"
  value       = "http://${var.nas_host}:${var.container_port}"
  depends_on  = [null_resource.docker_build_and_deploy]
}

output "https_endpoint_info" {
  description = "HTTPS endpoint configuration info"
  value       = "Configure reverse proxy: HTTPS ${var.nas_host}:8000 → HTTP 127.0.0.1:${var.container_port}"
}

output "deployment_status" {
  description = "Deployment status"
  value = {
    status         = "deployed"
    container_name = var.container_name
    image_name     = var.image_name
    container_port = var.container_port
    endpoint_url   = "http://${var.nas_host}:${var.container_port}"
  }
  depends_on = [null_resource.docker_build_and_deploy]
}

output "management_commands" {
  description = "Useful Docker management commands for the deployed container"
  value = {
    view_logs    = "ssh ${var.nas_username}@${var.nas_host} '/usr/local/bin/docker logs ${var.container_name}'"
    restart      = "ssh ${var.nas_username}@${var.nas_host} '/usr/local/bin/docker restart ${var.container_name}'"
    stop         = "ssh ${var.nas_username}@${var.nas_host} '/usr/local/bin/docker stop ${var.container_name}'"
    shell_access = "ssh ${var.nas_username}@${var.nas_host} '/usr/local/bin/docker exec -it ${var.container_name} /bin/bash'"
    status       = "ssh ${var.nas_username}@${var.nas_host} '/usr/local/bin/docker ps --filter name=${var.container_name}'"
  }
}
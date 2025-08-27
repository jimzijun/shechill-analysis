# Terraform Infrastructure

This directory contains Terraform configuration for deploying the Shechill Analysis application to a Synology NAS.

## GitHub Actions Usage

The GitHub workflow automatically uses repository secrets to deploy. No local setup needed.

## Local Usage (Optional)

For local testing, pass variables directly:

```bash
terraform init
```

```bash
terraform plan \
  -var="nas_host=your-nas-ip" \
  -var="nas_username=your-ssh-user"
```

```bash
terraform apply \
  -var="nas_host=your-nas-ip" \
  -var="nas_username=your-ssh-user"
```

```bash
terraform destroy \
  -var="nas_host=your-nas-ip" \
  -var="nas_username=your-ssh-user"
```

## What it does

The Terraform configuration:
1. Builds the Docker image locally
2. Uses Docker provider to connect via SSH to Synology NAS
3. Deploys container using standard Docker resources
4. Performs health checks
5. Provides deployment status outputs

## Benefits over manual deployment

- **Docker provider**: Uses well-documented Docker Terraform provider
- **State management**: Terraform tracks infrastructure state
- **Idempotent**: Safe to run multiple times
- **SSH connection**: Reliable SSH-based Docker daemon access
- **Standard Docker resources**: Uses familiar docker_container resource
- **Infrastructure as code**: Version controlled infrastructure

## Required GitHub Secrets

- `NAS_HOST`: Your Synology NAS IP/hostname
- `SSH_USER`: SSH username for NAS access
- `SSH_PRIVATE_KEY`: SSH private key for authentication
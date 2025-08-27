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
  -var="nas_username=your-username" \
  -var="nas_password=your-password"
```

```bash
terraform apply \
  -var="nas_host=your-nas-ip" \
  -var="nas_username=your-username" \
  -var="nas_password=your-password"
```

```bash
terraform destroy \
  -var="nas_host=your-nas-ip" \
  -var="nas_username=your-username" \
  -var="nas_password=your-password"
```

## What it does

The Terraform configuration:
1. Builds the Docker image locally
2. Uses Synology Container Manager API to deploy containers
3. Deploys using Docker Compose format via Synology provider
4. Performs health checks
5. Provides deployment status outputs

## Benefits over SSH-based deployment

- **Native Synology integration**: Uses official Synology APIs
- **State management**: Terraform tracks infrastructure state
- **Idempotent**: Safe to run multiple times
- **No SSH required**: Uses web API instead of shell access
- **Container Manager integration**: Leverages Synology's container orchestration
- **Infrastructure as code**: Version controlled infrastructure

## Required GitHub Secrets

- `NAS_HOST`: Your Synology NAS IP/hostname
- `NAS_USERNAME`: Admin username for Synology NAS
- `NAS_PASSWORD`: Admin password for Synology NAS
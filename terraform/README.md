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
  -var="ssh_user=your-user" \
  -var="ssh_private_key_path=~/.ssh/id_rsa"
```

```bash
terraform apply \
  -var="nas_host=your-nas-ip" \
  -var="ssh_user=your-user" \
  -var="ssh_private_key_path=~/.ssh/id_rsa"
```

```bash
terraform destroy \
  -var="nas_host=your-nas-ip" \
  -var="ssh_user=your-user" \
  -var="ssh_private_key_path=~/.ssh/id_rsa"
```

## What it does

The Terraform configuration:
1. Builds the Docker image locally
2. Transfers the image to your Synology NAS
3. Deploys the container with proper restart policies
4. Performs health checks
5. Provides deployment status outputs

## Benefits over GitHub Actions alone

- **State management**: Terraform tracks infrastructure state
- **Idempotent**: Safe to run multiple times
- **Rollback capability**: Easy to revert changes
- **Local development**: Test deployments locally
- **Infrastructure as code**: Version controlled infrastructure
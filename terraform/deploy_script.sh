#!/bin/bash

# Enable error handling
set -e

echo "Starting deployment script..."

# Change to tmp directory
cd /tmp

# Load Docker image
echo "Loading Docker image..."
bash -l -c 'docker load < shechill-analysis.tar.gz'

# Stop existing container if running
echo "Stopping existing container..."
bash -l -c 'docker stop shechill-analysis || true'
bash -l -c 'docker rm shechill-analysis || true'

# Run new container
echo "Starting new container..."
bash -l -c 'docker run -d --name shechill-analysis --restart unless-stopped -p 8000:8000 shechill-analysis:latest'

# Cleanup
echo "Cleaning up..."
rm -f shechill-analysis.tar.gz

# Show running containers
echo "Checking running containers..."
bash -l -c 'docker ps | grep shechill-analysis'

echo "Deployment completed successfully!"
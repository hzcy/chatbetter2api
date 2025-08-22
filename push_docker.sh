#!/bin/bash
# Linux Bash script to build and push Docker image to DockerHub
# Repository: wxyin/cbt2api

set -e

# Set variables
REPOSITORY="wxyin/cbt2api"
TAG=$(date +"%Y%m%d-%H%M%S")
LATEST="latest"

# Build frontend
echo "Building frontend..."
cd ./admin_frontend
echo "Installing frontend dependencies..."
npm install
echo "Building frontend production assets..."
npm run build
cd ..
echo "Frontend build completed."

# Login to Docker Hub (will prompt for credentials if not already logged in)
echo "Logging into Docker Hub..."
docker login

# Build the image
echo "Building Docker image..."
docker build -t "${REPOSITORY}:${TAG}" -t "${REPOSITORY}:${LATEST}" .

# Push the images
echo "Pushing image with tag ${TAG}..."
docker push "${REPOSITORY}:${TAG}"

echo "Pushing image with tag ${LATEST}..."
docker push "${REPOSITORY}:${LATEST}"

echo "Docker image pushed successfully to ${REPOSITORY}"
echo "Tags: ${TAG} and ${LATEST}" 
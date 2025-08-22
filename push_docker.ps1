# Windows PowerShell script to build and push Docker image to DockerHub
# Repository: wxyin/cbt2api

$ErrorActionPreference = "Stop"

# Set variables
$REPOSITORY = "wxyin/cbt2api"
$TAG = Get-Date -Format "yyyyMMdd-HHmmss"
$LATEST = "latest"

# Build frontend
Write-Host "Building frontend..."
Set-Location -Path ".\admin_frontend"
Write-Host "Installing frontend dependencies..."
npm install
Write-Host "Building frontend production assets..."
npm run build
Set-Location -Path ".."
Write-Host "Frontend build completed."

# Login to Docker Hub (will prompt for credentials if not already logged in)
Write-Host "Logging into Docker Hub..."
docker login

# Build the image
Write-Host "Building Docker image..."
docker build -t "$REPOSITORY`:$TAG" -t "$REPOSITORY`:$LATEST" .

# Push the images
Write-Host "Pushing image with tag $TAG..."
docker push "$REPOSITORY`:$TAG"

Write-Host "Pushing image with tag $LATEST..."
docker push "$REPOSITORY`:$LATEST"

Write-Host "Docker image pushed successfully to $REPOSITORY"
Write-Host "Tags: $TAG and $LATEST" 
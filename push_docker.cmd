@echo off
REM Windows CMD batch script to build and push Docker image to DockerHub
REM Repository: wxyin/cbt2api

setlocal enabledelayedexpansion

REM Set variables
set REPOSITORY=wxyin/cbt2api
for /f "tokens=2 delims==" %%I in ('wmic os get localdatetime /format:list') do set datetime=%%I
set TAG=%datetime:~0,8%-%datetime:~8,6%
set LATEST=latest

REM Build frontend
echo Building frontend...
cd .\admin_frontend
echo Installing frontend dependencies...
call npm install
echo Building frontend production assets...
call npm run build
cd ..
echo Frontend build completed.

REM Login to Docker Hub (will prompt for credentials if not already logged in)
echo Logging into Docker Hub...
docker login

REM Build the image
echo Building Docker image...
docker build -t "%REPOSITORY%:%TAG%" -t "%REPOSITORY%:%LATEST%" .

REM Push the images
echo Pushing image with tag %TAG%...
docker push "%REPOSITORY%:%TAG%"

echo Pushing image with tag %LATEST%...
docker push "%REPOSITORY%:%LATEST%"

echo Docker image pushed successfully to %REPOSITORY%
echo Tags: %TAG% and %LATEST%

endlocal 
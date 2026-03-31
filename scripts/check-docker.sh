#!/bin/bash
# Docker Build Check
# Usage: ./scripts/check-docker.sh
# Verifies that the Dockerfile builds successfully without producing a tagged image.

set -e

# Build the image with a temporary tag so we can clean it up
TEMP_TAG="hospital-dwh-catalogue-check:$$"

if docker build -f docker/Dockerfile -t "$TEMP_TAG" . > /dev/null 2>&1; then
    # Remove the temporary image
    docker rmi "$TEMP_TAG" > /dev/null 2>&1 || true
    echo "PASSED: Docker image builds successfully"
else
    docker rmi "$TEMP_TAG" > /dev/null 2>&1 || true
    echo "FAILED: Docker image build failed"
    exit 1
fi

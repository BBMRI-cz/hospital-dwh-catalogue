#!/bin/bash

# Deploy script for hospital-dwh-catalogue
# Usage: ./deploy.sh
# Requires: .env file with DEPLOY_ENV variable set

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Hospital DWH Catalogue Deployment${NC}"
echo -e "${GREEN}========================================${NC}"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo -e "${YELLOW}Please create a .env file based on one of the examples:${NC}"
    echo -e "${YELLOW}  - .env.dev.example${NC}"
    echo -e "${YELLOW}  - .env.prod.example${NC}"
    echo -e "${YELLOW}  - .env.test.example${NC}"
    exit 1
fi

# Load environment variables from .env file
set -a
source .env
set +a

# Check if DEPLOY_ENV is set
if [ -z "$DEPLOY_ENV" ]; then
    echo -e "${RED}Error: DEPLOY_ENV is not set in .env file!${NC}"
    echo -e "${YELLOW}Please add DEPLOY_ENV=<dev|prod|test> to your .env file${NC}"
    exit 1
fi

# Validate DEPLOY_ENV value
if [[ ! "$DEPLOY_ENV" =~ ^(dev|prod|test)$ ]]; then
    echo -e "${RED}Error: Invalid DEPLOY_ENV value: $DEPLOY_ENV${NC}"
    echo -e "${YELLOW}DEPLOY_ENV must be one of: dev, prod, test${NC}"
    exit 1
fi

echo -e "${GREEN}Deploying to: ${YELLOW}$DEPLOY_ENV${GREEN} environment${NC}"

# Set the docker-compose file based on environment
COMPOSE_FILE="docker-compose.$DEPLOY_ENV.yml"

if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}Error: Docker compose file not found: $COMPOSE_FILE${NC}"
    exit 1
fi

echo -e "${GREEN}Using docker-compose file: ${YELLOW}$COMPOSE_FILE${NC}"

# Pull latest changes (skip for dev environment)
if [ "$DEPLOY_ENV" != "dev" ]; then
    echo -e "${GREEN}Pulling latest changes from git...${NC}"
    git pull origin $(git branch --show-current)
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to pull latest changes${NC}"
        exit 1
    fi
    echo -e "${GREEN}Successfully pulled latest changes${NC}"
else
    echo -e "${YELLOW}Skipping git pull for dev environment${NC}"
fi

# Stop existing containers
echo -e "${GREEN}Stopping existing containers...${NC}"
docker-compose -f "$COMPOSE_FILE" down

# Build and start containers
echo -e "${GREEN}Building and starting containers...${NC}"
docker-compose -f "$COMPOSE_FILE" up -d --build

if [ $? -eq 0 ]; then
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Deployment successful!${NC}"
    echo -e "${GREEN}Environment: ${YELLOW}$DEPLOY_ENV${NC}"
    echo -e "${GREEN}========================================${NC}"
    
    # Show running containers
    echo -e "${GREEN}Running containers:${NC}"
    docker-compose -f "$COMPOSE_FILE" ps
else
    echo -e "${RED}========================================${NC}"
    echo -e "${RED}Deployment failed!${NC}"
    echo -e "${RED}========================================${NC}"
    exit 1
fi

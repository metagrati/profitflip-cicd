#!/bin/bash

# Log the push event
echo "Received push event at $(date)"

# Get the repository name and branch from the webhook payload
REPO_NAME=$(echo "$WEBHOOK_PAYLOAD" | jq -r '.repository.name')
BRANCH=$(echo "$WEBHOOK_PAYLOAD" | jq -r '.ref' | sed 's/refs\/heads\///')

echo "Repository: $REPO_NAME"
echo "Branch: $BRANCH"

# Only proceed if this is the profitflip-front-visual repository
if [ "$REPO_NAME" != "profitflip-front-visual" ]; then
    echo "Ignoring push event for non-target repository: $REPO_NAME"
    exit 0
fi

# Switch to the project directory
cd ~/profitflip-front-visual || {
    echo "Failed to change directory to ~/profitflip-front-visual"
    exit 1
}

# Pull the latest changes
echo "Pulling latest changes from $BRANCH"
git pull origin "$BRANCH" || {
    echo "Failed to pull latest changes"
    exit 1
}

# Build the new Docker image
echo "Building new Docker image: profitflip-frontend"
docker build -t profitflip-frontend . || {
    echo "Failed to build Docker image"
    exit 1
}

# Stop and remove the current container
echo "Stopping and removing current profitflip-app container"
docker stop profitflip-app || true
docker rm profitflip-app || true

# Start the new container
echo "Starting new profitflip-app container"
docker run -d \
    --name profitflip-app \
    --network ssl_default \
    profitflip-frontend || {
    echo "Failed to start new container"
    exit 1
}

echo "Deployment completed successfully" 
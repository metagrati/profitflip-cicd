#!/bin/bash

# Configuration
DEPLOY_FILE="/var/lib/docker/volumes/cicd_deploy-data/_data/deploy.json"
FRONTEND_DIR="/home/1/profitflip-front-visual"

# Function to log messages
log() {
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] $1"
}

# Function to update deployment status
update_status() {
    local status=$1
    local message=$2
    jq --arg status "$status" --arg message "$message" \
        '. + {status: $status, last_message: $message}' "$DEPLOY_FILE" > "${DEPLOY_FILE}.tmp" \
        && mv "${DEPLOY_FILE}.tmp" "$DEPLOY_FILE"
}

# Main loop
while true; do
    if [ -f "$DEPLOY_FILE" ]; then
        # Read deployment data
        if DEPLOY_DATA=$(jq -r '. | @base64' "$DEPLOY_FILE" 2>/dev/null); then
            # Parse deployment data
            REPOSITORY=$(echo "$DEPLOY_DATA" | base64 -d | jq -r '.repository')
            BRANCH=$(echo "$DEPLOY_DATA" | base64 -d | jq -r '.branch')
            STATUS=$(echo "$DEPLOY_DATA" | base64 -d | jq -r '.status')
            
            # Only process pending deployments
            if [ "$STATUS" = "pending" ]; then
                log "Processing deployment for $REPOSITORY:$BRANCH"
                
                # Update status to in-progress
                update_status "in_progress" "Starting deployment"
                
                # Step 1: Pull latest changes
                log "Pulling latest changes"
                cd "$FRONTEND_DIR" && \
                git pull origin "$BRANCH"
                if [ $? -ne 0 ]; then
                    update_status "failed" "Failed to pull changes"
                    continue
                fi
                
                # Step 2: Build Docker image
                log "Building Docker image"
                docker build -t profitflip-frontend .
                if [ $? -ne 0 ]; then
                    update_status "failed" "Failed to build Docker image"
                    continue
                fi
                
                # Step 3: Stop and remove old container
                log "Stopping old container"
                docker stop profitflip-app || true
                docker rm profitflip-app || true
                
                # Step 4: Start new container
                log "Starting new container"
                docker run -d \
                    --name profitflip-app \
                    --network ssl_default \
                    profitflip-frontend
                if [ $? -ne 0 ]; then
                    update_status "failed" "Failed to start new container"
                    continue
                fi
                
                # Update status to completed
                update_status "completed" "Deployment successful"
                log "Deployment completed successfully"
            fi
        fi
    fi
    
    # Wait before checking again
    sleep 5
done 
#!/bin/bash

# Configuration
DEPLOY_FILE="/var/lib/docker/volumes/cicd_deploy-data/_data/deploy.json"
FRONTEND_DIR="/home/1/profitflip-front-visual"
LOG_FILE="$HOME/deploy.log"

# Function to log messages
log() {
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] $1" | tee -a "$LOG_FILE"
}

# Function to update deployment status
update_status() {
    local status=$1
    local message=$2
    jq --arg status "$status" --arg message "$message" \
        '. + {status: $status, last_message: $message}' "$DEPLOY_FILE" > "${DEPLOY_FILE}.tmp" \
        && mv "${DEPLOY_FILE}.tmp" "$DEPLOY_FILE"
}

# Function to check if deployment is needed
check_deployment() {
    if [ ! -f "$DEPLOY_FILE" ]; then
        return 1
    fi
    
    local status=$(jq -r '.status' "$DEPLOY_FILE" 2>/dev/null)
    if [ "$status" = "pending" ]; then
        return 0
    fi
    
    return 1
}

# Function to handle deployment
handle_deployment() {
    local repository=$(jq -r '.repository' "$DEPLOY_FILE")
    local branch=$(jq -r '.branch' "$DEPLOY_FILE")
    local commit=$(jq -r '.commit' "$DEPLOY_FILE")
    
    log "Starting deployment for $repository:$branch (commit: $commit)"
    
    # Update status to in-progress
    update_status "in_progress" "Starting deployment"
    
    # Step 1: Pull latest changes
    log "Pulling latest changes from $branch"
    cd "$FRONTEND_DIR" || {
        log "Failed to change directory to $FRONTEND_DIR"
        update_status "failed" "Failed to change directory"
        return 1
    }
    
    git pull origin "$branch" || {
        log "Failed to pull changes from $branch"
        update_status "failed" "Failed to pull changes"
        return 1
    }
    
    # Step 2: Build Docker image
    log "Building Docker image"
    docker build -t profitflip-frontend . || {
        log "Failed to build Docker image"
        update_status "failed" "Failed to build Docker image"
        return 1
    }
    
    # Step 3: Stop and remove old container
    log "Stopping old container"
    docker stop profitflip-app 2>/dev/null || true
    docker rm profitflip-app 2>/dev/null || true
    
    # Step 4: Start new container
    log "Starting new container"
    docker run -d \
        --name profitflip-app \
        --network ssl_default \
        profitflip-frontend || {
        log "Failed to start new container"
        update_status "failed" "Failed to start new container"
        return 1
    }
    
    # Update status to completed
    update_status "completed" "Deployment successful"
    log "Deployment completed successfully"
    return 0
}

# Main loop
log "Starting deployment monitor"
while true; do
    if check_deployment; then
        handle_deployment
    fi
    sleep 5
done 
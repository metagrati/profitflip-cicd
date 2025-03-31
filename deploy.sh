#!/bin/bash

# Configuration
DEPLOY_FILE="/var/lib/docker/volumes/profitflip-cicd_deploy-data/_data/deploy.json"
FRONTEND_DIR="/home/profitflip/profitflip-front-visual"
LOG_FILE="$HOME/deploy.log"

# Function to log messages with more detail
log() {
    echo "[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] $1" | tee -a "$LOG_FILE"
}

# Debug function to check file and permissions
debug_check() {
    log "DEBUG: Checking deploy file and permissions..."
    log "DEBUG: Deploy file path: $DEPLOY_FILE"
    log "DEBUG: Current user: $(whoami)"
    log "DEBUG: File exists? $(test -f "$DEPLOY_FILE" && echo "Yes" || echo "No")"
    if [ -f "$DEPLOY_FILE" ]; then
        log "DEBUG: File permissions: $(ls -l "$DEPLOY_FILE")"
        log "DEBUG: File content: $(cat "$DEPLOY_FILE")"
    fi
    log "DEBUG: Directory permissions: $(ls -l "$(dirname "$DEPLOY_FILE")")"
}

# Function to check if deployment is needed
check_deployment() {
    debug_check  # Add debug information

    if [ ! -f "$DEPLOY_FILE" ]; then
        log "DEBUG: Deploy file does not exist"
        return 1
    fi
    
    log "DEBUG: Reading status from deploy file..."
    local status=$(jq -r '.status // empty' "$DEPLOY_FILE" 2>/dev/null)
    log "DEBUG: Current status: '$status'"  # Added quotes to see if status is empty or contains whitespace
    
    if [ "$status" = "pending" ]; then
        log "DEBUG: Found pending deployment"
        return 0
    fi
    
    log "DEBUG: Status is not pending: '$status'"
    return 1
}

# Function to update deployment status
update_status() {
    local status=$1
    local message=$2
    log "DEBUG: Updating status to: $status ($message)"
    
    if ! jq --arg status "$status" --arg message "$message" \
        '. + {status: $status, last_message: $message}' "$DEPLOY_FILE" > "${DEPLOY_FILE}.tmp"; then
        log "DEBUG: Failed to update status (jq command failed)"
        return 1
    fi
    
    if ! mv "${DEPLOY_FILE}.tmp" "$DEPLOY_FILE"; then
        log "DEBUG: Failed to move temporary file"
        return 1
    fi
    
    log "DEBUG: Status updated successfully"
}

# Function to handle deployment
handle_deployment() {
    local repository=$(jq -r '.repository' "$DEPLOY_FILE")
    local branch=$(jq -r '.branch' "$DEPLOY_FILE")
    local commit=$(jq -r '.commit' "$DEPLOY_FILE")
    
    log "DEBUG: Starting deployment process"
    log "DEBUG: Repository: $repository"
    log "DEBUG: Branch: $branch"
    log "DEBUG: Commit: $commit"
    
    # Update status to in-progress
    update_status "in_progress" "Starting deployment"
    
    # Step 1: Pull latest changes
    log "DEBUG: Changing to frontend directory: $FRONTEND_DIR"
    cd "$FRONTEND_DIR" || {
        log "DEBUG: Failed to change directory. Current directory: $(pwd)"
        update_status "failed" "Failed to change directory"
        return 1
    }
    
    log "DEBUG: Current directory after cd: $(pwd)"
    log "DEBUG: Git status before pull:"
    git status
    
    log "DEBUG: Pulling latest changes from $branch"
    if ! git pull origin "$branch"; then
        log "DEBUG: Git pull failed. Git error: $?"
        update_status "failed" "Failed to pull changes"
        return 1
    fi
    
    # Step 2: Build Docker image
    log "DEBUG: Building Docker image"
    log "DEBUG: Docker version: $(docker --version)"
    if ! docker build -t profitflip-frontend .; then
        log "DEBUG: Docker build failed. Docker error: $?"
        update_status "failed" "Failed to build Docker image"
        return 1
    fi
    
    # Step 3: Stop and remove old container
    log "DEBUG: Stopping old container"
    docker ps -a | grep profitflip-app && {
        log "DEBUG: Found existing container, stopping and removing"
        docker stop profitflip-app 2>/dev/null
        docker rm profitflip-app 2>/dev/null
    }
    
    # Step 4: Start new container
    log "DEBUG: Starting new container"
    if ! docker run -d \
        --name profitflip-app \
        --network ssl_default \
        profitflip-frontend; then
        log "DEBUG: Failed to start container. Docker error: $?"
        update_status "failed" "Failed to start new container"
        return 1
    fi
    
    log "DEBUG: New container started. Container info:"
    docker ps | grep profitflip-app
    
    # Update status to completed
    update_status "completed" "Deployment successful"
    log "DEBUG: Deployment completed successfully"
    return 0
}

# Main loop
log "Starting deployment monitor with debug logging"
log "DEBUG: Initial environment check:"
debug_check

while true; do
    if check_deployment; then
        log "DEBUG: Starting deployment cycle"
        handle_deployment
        log "DEBUG: Deployment cycle completed"
    else
        log "DEBUG: No pending deployment found"
    fi
    sleep 5
done
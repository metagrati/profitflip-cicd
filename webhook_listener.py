import os
import hmac
import hashlib
import json
import traceback
from flask import Flask, request, abort
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
DEPLOY_FILE = '/deploy/deploy.json'

def verify_webhook_signature(payload_body, signature_header):
    """Verify GitHub webhook signature."""
    if not WEBHOOK_SECRET:
        app.logger.error("WEBHOOK_SECRET not configured")
        raise ValueError("WEBHOOK_SECRET not configured")
    
    if not signature_header:
        app.logger.error("No signature header received")
        return False
    
    try:
        sha_name, signature = signature_header.split('=', 1)
    except ValueError:
        app.logger.error(f"Invalid signature format: {signature_header}")
        return False
        
    if sha_name != 'sha256':
        app.logger.error(f"Invalid hash algorithm: {sha_name}")
        return False
    
    # Calculate expected signature
    mac = hmac.new(WEBHOOK_SECRET.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = mac.hexdigest()
    
    app.logger.info(f"Received signature: {signature}")
    app.logger.info(f"Expected signature: {expected_signature}")
    app.logger.info(f"Secret being used: {WEBHOOK_SECRET}")
    app.logger.info(f"Payload length: {len(payload_body)} bytes")
    
    return hmac.compare_digest(expected_signature, signature)

def write_deploy_instruction(payload):
    """Write deployment instructions to shared volume."""
    try:
        # Create deployment instruction
        deploy_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'repository': payload.get('repository', {}).get('name'),
            'branch': payload.get('ref', '').replace('refs/heads/', ''),
            'commit': payload.get('after'),
            'author': payload.get('pusher', {}).get('name'),
            'status': 'pending'
        }
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(DEPLOY_FILE), exist_ok=True)
        
        # Write deployment instruction
        with open(DEPLOY_FILE, 'w') as f:
            json.dump(deploy_data, f, indent=2)
            
        app.logger.info(f"Wrote deployment instructions to {DEPLOY_FILE}")
        app.logger.info(f"Deploy data: {json.dumps(deploy_data, indent=2)}")
        
        return True
    except Exception as e:
        app.logger.error(f"Failed to write deployment instructions: {str(e)}")
        app.logger.error(f"Traceback:\n{traceback.format_exc()}")
        return False

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        # Log headers for debugging
        app.logger.info("Received headers:")
        for header, value in request.headers.items():
            app.logger.info(f"{header}: {value}")

        # Get the raw payload body for signature verification
        payload_body = request.get_data()
        app.logger.info(f"Raw payload: {payload_body.decode('utf-8')}")
        
        # Verify webhook signature
        signature_header = request.headers.get('X-Hub-Signature-256')
        if not verify_webhook_signature(payload_body, signature_header):
            app.logger.error("Invalid webhook signature")
            abort(401)
        
        # Process the webhook
        event_type = request.headers.get('X-GitHub-Event')
        
        # Parse JSON payload
        try:
            payload = request.get_json()
        except Exception as e:
            app.logger.error(f"Failed to parse JSON payload: {e}")
            app.logger.error(f"Traceback:\n{traceback.format_exc()}")
            return 'Invalid JSON payload', 400
        
        # Only process push events
        if event_type != 'push':
            app.logger.info(f"Ignoring non-push event: {event_type}")
            return 'OK', 200
        
        # Log the event
        app.logger.info(f"Received push event for repository: {payload.get('repository', {}).get('name')}")
        app.logger.info(f"Payload: {json.dumps(payload, indent=2)}")
        
        # Write deployment instructions
        if write_deploy_instruction(payload):
            app.logger.info("Successfully wrote deployment instructions")
            return 'OK', 200
        else:
            app.logger.error("Failed to write deployment instructions")
            return 'Failed to write deployment instructions', 500
            
    except Exception as e:
        app.logger.error(f"Webhook processing error: {str(e)}")
        app.logger.error(f"Traceback:\n{traceback.format_exc()}")
        return 'Internal server error', 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000) 

import os
import hmac
import hashlib
import json
import traceback
from flask import Flask, request, abort, jsonify
from dotenv import load_dotenv
from datetime import datetime

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
DEPLOY_FILE = '/deploy/deploy.json'

# Enable debug logging
app.logger.setLevel('DEBUG')

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'webhook_secret_configured': bool(WEBHOOK_SECRET),
        'deploy_file_exists': os.path.exists(DEPLOY_FILE)
    })

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
        # Log the current state of the file
        app.logger.info("Checking current deploy file state...")
        if os.path.exists(DEPLOY_FILE):
            try:
                with open(DEPLOY_FILE, 'r') as f:
                    current_data = json.load(f)
                app.logger.info(f"Current deploy file content: {json.dumps(current_data, indent=2)}")
            except Exception as e:
                app.logger.error(f"Error reading current deploy file: {str(e)}")
        else:
            app.logger.info("Deploy file does not exist yet")

        # Create deployment instruction
        deploy_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'repository': payload.get('repository', {}).get('name'),
            'branch': payload.get('ref', '').replace('refs/heads/', ''),
            'commit': payload.get('after'),
            'author': payload.get('pusher', {}).get('name'),
            'status': 'pending'
        }
        
        app.logger.info(f"Created new deploy data: {json.dumps(deploy_data, indent=2)}")
        
        # Ensure directory exists
        deploy_dir = os.path.dirname(DEPLOY_FILE)
        app.logger.info(f"Ensuring directory exists: {deploy_dir}")
        os.makedirs(deploy_dir, exist_ok=True)
        
        # Check directory permissions
        app.logger.info(f"Directory permissions: {oct(os.stat(deploy_dir).st_mode)}")
        
        # Write deployment instruction
        app.logger.info("Writing new deploy data...")
        with open(DEPLOY_FILE, 'w') as f:
            json.dump(deploy_data, f, indent=2)
            
        # Verify the write
        app.logger.info("Verifying write operation...")
        if os.path.exists(DEPLOY_FILE):
            with open(DEPLOY_FILE, 'r') as f:
                written_data = json.load(f)
            app.logger.info(f"Written deploy file content: {json.dumps(written_data, indent=2)}")
            if written_data != deploy_data:
                app.logger.error("Written data does not match intended data!")
                return False
        else:
            app.logger.error("Deploy file does not exist after write!")
            return False
            
        app.logger.info(f"Successfully wrote deployment instructions to {DEPLOY_FILE}")
        return True
    except Exception as e:
        app.logger.error(f"Failed to write deployment instructions: {str(e)}")
        app.logger.error(f"Traceback:\n{traceback.format_exc()}")
        app.logger.error(f"Current working directory: {os.getcwd()}")
        app.logger.error(f"Deploy file path: {os.path.abspath(DEPLOY_FILE)}")
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
            return jsonify({
                'status': 'success',
                'message': 'Deployment instructions written successfully'
            }), 200
        else:
            app.logger.error("Failed to write deployment instructions")
            return jsonify({
                'status': 'error',
                'message': 'Failed to write deployment instructions'
            }), 500
            
    except Exception as e:
        app.logger.error(f"Webhook processing error: {str(e)}")
        app.logger.error(f"Traceback:\n{traceback.format_exc()}")
        return jsonify({
            'status': 'error',
            'message': 'Internal server error'
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000) 

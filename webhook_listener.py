import os
import hmac
import hashlib
import subprocess
import json
from flask import Flask, request, abort
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET')
SCRIPT_PATH = os.getenv('SCRIPT_PATH', '/home/1/profitflip-cicd/scripts/run.sh')

def verify_webhook_signature(payload_body, signature_header):
    """Verify GitHub webhook signature."""
    if not WEBHOOK_SECRET:
        raise ValueError("WEBHOOK_SECRET not configured")
    
    if not signature_header:
        return False
    
    sha_name, signature = signature_header.split('=')
    if sha_name != 'sha256':
        return False
    
    mac = hmac.new(WEBHOOK_SECRET.encode(), msg=payload_body, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), signature)

def execute_script(payload):
    """Execute the script on the host machine."""
    try:
        # Pass the payload as an environment variable
        env = os.environ.copy()
        env['WEBHOOK_PAYLOAD'] = json.dumps(payload)
        
        # Execute commands on the host machine
        commands = [
            f"cd /home/1/profitflip-front-visual",
            f"git pull origin {payload.get('ref', '').replace('refs/heads/', '')}",
            "docker build -t profitflip-frontend .",
            "docker stop profitflip-app || true",
            "docker rm profitflip-app || true",
            "docker run -d --name profitflip-app --network ssl_default profitflip-frontend"
        ]
        
        for cmd in commands:
            result = subprocess.run(
                ['docker', 'exec', 'host', 'bash', '-c', cmd],
                capture_output=True,
                text=True,
                check=True,
                env=env
            )
            app.logger.info(f"Command executed: {cmd}")
            app.logger.info(f"Output: {result.stdout}")
            if result.stderr:
                app.logger.warning(f"Stderr: {result.stderr}")
        
        return "Deployment completed successfully"
    except subprocess.CalledProcessError as e:
        app.logger.error(f"Command execution failed: {e.stderr}")
        return None

@app.route('/webhook', methods=['POST'])
def webhook():
    # Check content type
    if not request.is_json:
        app.logger.error(f"Received non-JSON payload with Content-Type: {request.headers.get('Content-Type')}")
        return 'Content-Type must be application/json', 415
    
    # Get the raw payload body for signature verification
    payload_body = request.get_data()
    
    # Verify webhook signature
    signature_header = request.headers.get('X-Hub-Signature-256')
    if not verify_webhook_signature(payload_body, signature_header):
        app.logger.error("Invalid webhook signature")
        abort(401)
    
    # Process the webhook
    event_type = request.headers.get('X-GitHub-Event')
    payload = request.get_json()
    
    # Log headers for debugging
    app.logger.info("Received headers:")
    for header, value in request.headers.items():
        app.logger.info(f"{header}: {value}")
    
    # Only process push events
    if event_type != 'push':
        app.logger.info(f"Ignoring non-push event: {event_type}")
        return 'OK', 200
    
    # Log the event
    app.logger.info(f"Received push event for repository: {payload.get('repository', {}).get('name')}")
    app.logger.info(f"Payload: {json.dumps(payload, indent=2)}")
    
    # Execute the script
    output = execute_script(payload)
    if output:
        app.logger.info(f"Script executed successfully: {output}")
        return 'OK', 200
    else:
        app.logger.error("Script execution failed")
        return 'Script execution failed', 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000) 
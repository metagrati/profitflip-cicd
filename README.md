# GitHub Webhook Listener

A secure webhook listener that executes scripts on the host machine when receiving GitHub webhooks.

## Setup

1. Create a `.env` file with the following variables:
```env
WEBHOOK_SECRET=your_github_webhook_secret
SCRIPT_PATH=/path/to/your/script.sh
```

2. Make sure your script is executable:
```bash
chmod +x /path/to/your/script.sh
```

3. Build and start the container:
```bash
docker-compose up -d
```

## GitHub Webhook Configuration

1. Go to your GitHub repository settings
2. Navigate to Webhooks
3. Add a new webhook with:
   - Payload URL: `https://your-domain/webhook`
   - Content type: `application/json`
   - Secret: Same as `WEBHOOK_SECRET` in your `.env` file
   - Select the events you want to trigger the webhook

## Security Considerations

- The webhook listener validates GitHub signatures
- Scripts are executed through Docker's exec API
- The container has minimal permissions
- All webhook events are logged

## Logs

View container logs:
```bash
docker-compose logs -f
``` 
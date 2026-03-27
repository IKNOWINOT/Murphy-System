# Murphy System Multi-Channel Delivery

> **Created:** 2026-03-27  
> **Addresses:** B-009 (Multi-channel delivery testing)

---

## Overview

Murphy System supports delivering notifications, alerts, and reports through
multiple channels. All channels use a unified delivery interface.

---

## Supported Channels

| Channel | Module | Status | Credentials Required |
|---------|--------|--------|---------------------|
| Email (SMTP) | `src/delivery/email.py` | ✅ Ready | `SMTP_*` |
| Email (SendGrid) | `src/delivery/sendgrid.py` | ✅ Ready | `SENDGRID_API_KEY` |
| SMS (Twilio) | `src/delivery/twilio_sms.py` | ✅ Ready | `TWILIO_*` |
| Slack | `src/delivery/slack.py` | ✅ Ready | `SLACK_BOT_TOKEN` |
| Discord | `src/delivery/discord.py` | ✅ Ready | `DISCORD_BOT_TOKEN` |
| Teams | `src/delivery/teams.py` | ✅ Ready | `TEAMS_WEBHOOK_URL` |
| Telegram | `src/delivery/telegram.py` | ✅ Ready | `TELEGRAM_BOT_TOKEN` |
| WhatsApp | `src/delivery/whatsapp.py` | ✅ Ready | `WHATSAPP_*` |
| Push (Web) | `src/delivery/web_push.py` | ✅ Ready | `VAPID_*` |
| Push (Mobile) | `src/delivery/firebase.py` | ✅ Ready | `FIREBASE_*` |
| Webhook | `src/delivery/webhook.py` | ✅ Ready | (custom URL) |
| In-App | `src/delivery/in_app.py` | ✅ Ready | (none) |

---

## Unified Interface

```python
from src.delivery import DeliveryService

# Initialize with configured channels
delivery = DeliveryService()

# Send to all user's preferred channels
await delivery.send(
    user_id="user123",
    message="Your task completed",
    priority="normal",
    channels=["email", "slack"],  # or None for user preferences
)

# Send to specific channel
await delivery.send_to_channel(
    channel="slack",
    recipient="#general",
    message="System alert",
)
```

---

## Configuration

### Per-User Preferences

Users configure their delivery preferences via:
- `/api/users/me/notifications` - API endpoint
- `/ui/settings` - UI settings page

### System-Wide

```bash
# Default channels for different priority levels
MURPHY_NOTIFY_LOW=in_app
MURPHY_NOTIFY_NORMAL=email,in_app
MURPHY_NOTIFY_HIGH=email,slack,in_app
MURPHY_NOTIFY_URGENT=email,sms,slack,in_app
```

---

## Testing

### Unit Tests (No Credentials)

```bash
# Runs with mocked channels
pytest tests/test_delivery.py -v
```

### Integration Tests (Requires Credentials)

```bash
# Set credentials in environment
export SENDGRID_API_KEY=...
export SLACK_BOT_TOKEN=...

# Run integration tests
pytest tests/integration/test_delivery_channels.py -v
```

### Manual Testing

```bash
# Test email delivery
curl -X POST http://localhost:8000/api/test/delivery \
  -H "Content-Type: application/json" \
  -d '{"channel": "email", "recipient": "test@example.com", "message": "Test"}'

# Test Slack delivery
curl -X POST http://localhost:8000/api/test/delivery \
  -H "Content-Type: application/json" \
  -d '{"channel": "slack", "recipient": "#test", "message": "Test"}'
```

---

## Error Handling

The delivery service handles failures gracefully:

1. **Retry Logic:** Failed deliveries are retried 3 times with exponential backoff
2. **Fallback Channels:** If primary channel fails, falls back to secondary
3. **Dead Letter Queue:** Permanently failed messages stored for manual review
4. **Alerting:** Repeated failures trigger system alerts

---

## Monitoring

Delivery metrics available at `/api/metrics`:

- `murphy_delivery_total` - Total delivery attempts
- `murphy_delivery_success` - Successful deliveries
- `murphy_delivery_failures` - Failed deliveries
- `murphy_delivery_latency` - Delivery latency histogram

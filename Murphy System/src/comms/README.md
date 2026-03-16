# Comms

The `comms` package provides the outbound communications pipeline for the
Murphy System: email, SMS, push, and webhook notifications, all subject to
compliance and governance checks.

## Key Modules

| Module | Purpose |
|--------|---------|
| `pipeline.py` | `CommsPipeline` — routes outbound messages through compliance checks |
| `connectors.py` | Provider connectors (SMTP, Twilio, SendGrid, Webhook) |
| `compliance.py` | CAN-SPAM, GDPR, and outreach-compliance enforcement |
| `governance.py` | Rate-limiting and opt-out management |
| `schemas.py` | `Message`, `Channel`, `ComplianceRecord` Pydantic schemas |

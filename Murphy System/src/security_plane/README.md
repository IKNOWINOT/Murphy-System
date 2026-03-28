# Security Plane

The `security_plane` package provides authentication, authorisation,
cryptography, anomaly detection, and compliance enforcement for every
request that passes through the Murphy System.

## Key Modules

| Module | Purpose |
|--------|---------|
| `authentication.py` | JWT / API-key validation, multi-factor hooks |
| `access_control.py` | RBAC policy evaluation, role-permission matrices |
| `cryptography.py` | Key generation, AES-GCM encryption/decryption helpers |
| `adaptive_defense.py` | Real-time threat scoring, automatic rate-limit escalation |
| `bot_anomaly_detector.py` | Detects non-human request patterns |
| `bot_identity_verifier.py` | Verifies bot JWTs and capability attestation |
| `bot_resource_quotas.py` | Per-bot CPU / memory / API-call budgets |
| `anti_surveillance.py` | Anti-tracking and data-minimisation helpers |
| `authorization_enhancer.py` | Context-aware permission expansion (ABAC layer) |

## Architecture

```
Request ──▶ authentication ──▶ access_control ──▶ adaptive_defense ──▶ Handler
                                                        │
                                               anomaly / quota guards
```

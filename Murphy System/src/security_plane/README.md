# `src/security_plane` — Security Plane Package

Zero-trust security architecture for the Murphy System. Wraps all subsystems with
authentication, authorization, post-quantum cryptography, DLP, and anti-surveillance.

## Public API

```python
from security_plane import (
    HumanAuthenticator, MachineAuthenticator,
    ZeroTrustAccessController,
    HybridCryptography, KeyManager, PacketSigner,
    SensitiveDataClassifier, ExfiltrationDetector,
    wire_security_plane_middleware,
)
```

## Architecture

See [`documentation/architecture/SECURITY_PLANE.md`](../../documentation/architecture/SECURITY_PLANE.md) for the full reference.

## Key Components

| Module | Purpose |
|--------|---------|
| `authentication.py` | FIDO2 / mTLS human + machine auth |
| `access_control.py` | Zero-trust RBAC per request |
| `cryptography.py` | Hybrid classical + post-quantum crypto |
| `middleware.py` | ASGI middleware stack (4 classes) |
| `data_leak_prevention.py` | DLP scanning for all responses |
| `adaptive_defense.py` | Anomaly detection + auto-block |
| `anti_surveillance.py` | Timing normalization + metadata scrubbing |
| `packet_protection.py` | Execution packet signing/verification |

## Tests

`tests/test_security_plane_wiring.py` — 45 tests covering all middleware classes.

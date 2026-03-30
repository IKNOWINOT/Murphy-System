# Security Plane — Architecture & Implementation Reference

**Murphy System — Zero-Trust Security Architecture**

> **Copyright © 2020–2026 Murphy Collective — Created by Corey Post  
> License: BSL 1.1**

---

## Table of Contents

1. [Overview and Principles](#overview-and-principles)
2. [Component Map](#component-map)
3. [Authentication Layer](#authentication-layer)
4. [Access Control (Zero-Trust)](#access-control-zero-trust)
5. [Cryptography (Post-Quantum)](#cryptography-post-quantum)
6. [Data Leak Prevention (DLP)](#data-leak-prevention)
7. [ASGI Middleware Stack](#asgi-middleware-stack)
8. [Adaptive Defense](#adaptive-defense)
9. [Anti-Surveillance](#anti-surveillance)
10. [Packet Protection](#packet-protection)
11. [Environment Variables](#environment-variables)
12. [Security Architecture Diagram](#security-architecture-diagram)

---

## Overview and Principles

The Murphy Security Plane wraps **all** system components with a zero-trust, defence-in-depth
model. It operates as an **orthogonal layer** — every request passes through it before reaching
business logic, and every response passes through it on exit.

**Six non-negotiable security principles:**

| # | Principle | Implementation |
|---|-----------|----------------|
| 1 | **Security is additive, orthogonal, absolute** | ASGI middleware stack applied universally |
| 2 | **Control Plane supremacy preserved** | Security checks never block health/liveness endpoints |
| 3 | **No hidden execution paths** | All routes visible in manifest; DLP scans all responses |
| 4 | **Fail closed always** | `AuthZ denied` → 403; crypto failure → 500 (never silently passes) |
| 5 | **Trust is continuously re-computed** | Per-request RBAC + risk classification, no session-level caching |
| 6 | **Authority decays automatically** | Tokens expire; roles without recent activity are downgraded |

**Source:** `src/security_plane/`

---

## Component Map

```
src/security_plane/
├── __init__.py               — Public API exports
├── schemas.py                — Core security data models (SecurityEvent, etc.)
├── authentication.py         — Human + machine authentication (FIDO2 / mTLS)
├── authorization_enhancer.py — Enhanced AuthZ with fine-grained policies
├── access_control.py         — Zero-trust RBAC enforcement
├── cryptography.py           — Hybrid post-quantum cryptographic primitives
├── hardening.py              — Entrance/exit hardening (request/response scrubbing)
├── adaptive_defense.py       — Security telemetry and anomaly detection
├── bot_anomaly_detector.py   — Bot traffic detection and rate limiting
├── bot_identity_verifier.py  — Bot identity verification
├── bot_resource_quotas.py    — Per-bot resource quota enforcement
├── data_leak_prevention.py   — DLP scanning (exfiltration detection)
├── log_sanitizer.py          — Strips secrets from log output
├── middleware.py             — ASGI middleware stack (4 classes)
├── packet_protection.py      — Execution packet signing and verification
├── security_dashboard.py     — Security event dashboard aggregator
├── swarm_communication_monitor.py — Monitors inter-bot communication
└── anti_surveillance.py      — Anti-tracking and timing normalization
```

---

## Authentication Layer

**Source:** `src/security_plane/authentication.py`

Murphy implements **passwordless authentication** as a non-negotiable UX principle:

> *If a human must copy a secret, the system failed.*

### Human Authentication

- **FIDO2 / WebAuthn passkeys** — hardware security key or platform authenticator.
- **Biometric verification** — fingerprint / FaceID (delegated to OS platform API).
- **Contextual verification** — time-of-day, geo-region, task type.
- **Intent confirmation** — semantic intent matched to the requested action before execution.

```python
from security_plane.authentication import HumanAuthenticator, ContextualVerifier, IntentConfirmer

authenticator = HumanAuthenticator()
session = authenticator.begin_challenge(user_id="user-1")
result  = authenticator.verify_response(session.challenge_id, response)
```

### Machine Authentication

- **mTLS (mutual TLS)** — both sides present certificates; no shared secrets.
- Certificates issued by Murphy's internal CA (`CertificateAuthority` in `cryptography.py`).
- Short-lived (default: 24 h); automatically rotated by `KeyManager`.

```python
from security_plane.authentication import MachineAuthenticator

authenticator = MachineAuthenticator()
identity = authenticator.authenticate(client_cert_pem, ca_cert_pem)
```

### Key Data Models

```python
class AuthenticationType(Enum):
    PASSKEY     = "passkey"
    BIOMETRIC   = "biometric"
    MTLS        = "mtls"
    HARDWARE_KEY = "hardware_key"

@dataclass
class AuthenticationSession:
    session_id: str
    user_id: str
    auth_type: AuthenticationType
    created_at: datetime
    expires_at: datetime
    verified: bool
```

---

## Access Control (Zero-Trust)

**Source:** `src/security_plane/access_control.py`

Every API request is evaluated against a **per-request access decision**:

1. Extract identity from the authenticated session.
2. Look up the role-permission matrix (in-memory, loaded from config).
3. Evaluate contextual rules (time window, risk score, MFA status).
4. Emit an `AccessDecision` (`ALLOW` / `DENY` / `REQUIRE_ESCALATION`).

```python
from security_plane.access_control import ZeroTrustAccessController

controller = ZeroTrustAccessController()
decision = controller.evaluate(
    identity=identity,
    resource="/api/mfm/promote",
    action="POST",
    context={"risk_score": 0.12, "mfa_verified": True},
)
# decision.result → "ALLOW" | "DENY" | "REQUIRE_ESCALATION"
```

---

## Cryptography (Post-Quantum)

**Source:** `src/security_plane/cryptography.py`

Murphy uses a **hybrid classical + post-quantum** cryptographic scheme to protect against harvest-now-decrypt-later attacks:

| Algorithm | Purpose |
|-----------|---------|
| X25519 | Classical ECDH key exchange |
| CRYSTALS-Kyber (PQC) | Post-quantum key encapsulation |
| AES-256-GCM | Symmetric data encryption |
| Ed25519 | Digital signatures (classical) |
| CRYSTALS-Dilithium (PQC) | Post-quantum digital signatures |
| SHA-3 | Hashing |

```python
from security_plane.cryptography import HybridCryptography, KeyManager, PacketSigner

crypto  = HybridCryptography()
manager = KeyManager(rotation_interval_hours=24)
signer  = PacketSigner(manager)

# Encrypt a payload
ciphertext = crypto.encrypt(plaintext, recipient_public_key)
# Sign an execution packet
signed = signer.sign_packet(packet_bytes)
# Verify
ok = signer.verify_packet(signed)
```

---

## Data Leak Prevention (DLP)

**Source:** `src/security_plane/data_leak_prevention.py`

DLP scans **all outbound responses** for sensitive data patterns before transmission:

| Detector | Pattern | Action |
|----------|---------|--------|
| PII Detector | SSN, email, phone, address | Redact / block |
| Key Detector | API keys, tokens, credentials | Block + alert |
| Secret Detector | Passwords, private keys | Block + alert |
| Financial Detector | Credit card numbers, IBAN | Redact |
| Medical Detector | ICD codes, medication names | Redact |

```python
from security_plane.data_leak_prevention import SensitiveDataClassifier, ExfiltrationDetector

classifier = SensitiveDataClassifier()
result = classifier.classify(response_body)

detector = ExfiltrationDetector()
exfil = detector.check(source_ip="10.0.0.1", payload=response_body, size_bytes=len(response_body))
# exfil.is_suspicious → True | False
```

---

## ASGI Middleware Stack

**Source:** `src/security_plane/middleware.py`

Four ASGI middleware classes are registered via `wire_security_plane_middleware()`, applied in order:

| Order | Class | Function |
|-------|-------|---------|
| 1 | `RBACMiddleware` | Enforce role-based access per route |
| 2 | `RiskClassificationMiddleware` | Assign risk score to request; block high-risk |
| 3 | `DLPScannerMiddleware` | Scan request and response body for sensitive data |
| 4 | `PerUserRateLimitMiddleware` | Per-user token-bucket rate limiting |

**Wiring** (called at FastAPI app startup):

```python
from security_plane.middleware import wire_security_plane_middleware

app = FastAPI()
wire_security_plane_middleware(app)
```

**Rate limit configuration:**

| Variable | Default | Description |
|----------|---------|-------------|
| `MURPHY_RATE_LIMIT_RPS` | `100` | Requests per second per authenticated user |
| `MURPHY_RATE_LIMIT_BURST` | `200` | Token bucket burst capacity |

---

## Adaptive Defense

**Source:** `src/security_plane/adaptive_defense.py`

The adaptive defense module collects security telemetry and responds to anomalies:

- **Anomaly detection** — statistical deviation from baseline request patterns.
- **Automatic IP blocking** — blocks IPs exceeding configurable thresholds.
- **Security event publication** — every event published to `EventBackbone` as `SECURITY_EVENT`.
- **Dashboard integration** — aggregated in `security_dashboard.py` → `/api/security/events`.

---

## Anti-Surveillance

**Source:** `src/security_plane/anti_surveillance.py`

Prevents operational security leakage through side-channels:

- **Timing normalization** (`ExecutionTimeNormalizer`) — adds padding to response times to prevent timing-based fingerprinting.
- **Metadata scrubbing** (`MetadataScrubber`) — strips `X-Powered-By`, `Server`, and custom headers that reveal implementation details.
- **Anti-tracking** — removes tracking pixels and third-party analytics from HTML responses.

---

## Packet Protection

**Source:** `src/security_plane/packet_protection.py`

All execution packets moving between Murphy subsystems are cryptographically signed:

1. `PacketSigner.sign_packet(bytes)` → signed packet with Ed25519 + Dilithium signatures.
2. Receiving subsystem calls `PacketSigner.verify_packet(signed_packet)`.
3. If verification fails → packet is rejected; `SECURITY_EVENT` is published.

This prevents replay attacks and ensures control plane integrity.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MURPHY_SECURITY_MODE` | `permissive` | `strict` / `permissive` / `audit-only` |
| `MURPHY_API_KEY` | — | API key for `X-API-Key` header auth |
| `MURPHY_RATE_LIMIT_RPS` | `100` | Per-user rate limit (req/sec) |
| `MURPHY_RATE_LIMIT_BURST` | `200` | Token bucket burst |
| `MURPHY_DLP_ACTION` | `redact` | `redact` / `block` / `log-only` |
| `MURPHY_TLS_CERT` | — | Path to TLS certificate |
| `MURPHY_TLS_KEY` | — | Path to TLS private key |
| `MURPHY_CA_CERT` | — | Path to CA certificate for mTLS |
| `MURPHY_KEY_ROTATION_HOURS` | `24` | Internal key rotation interval |

---

## Security Architecture Diagram

```
INBOUND REQUEST
      │
      ▼
┌───────────────────────────────────────────────────────────┐
│  ASGI Middleware Stack (src/security_plane/middleware.py)  │
│                                                           │
│  1. RBACMiddleware           ← identity → role lookup     │
│  2. RiskClassificationMiddleware ← score 0.0–1.0          │
│  3. DLPScannerMiddleware     ← scan request body          │
│  4. PerUserRateLimitMiddleware ← token bucket             │
└────────────────────┬──────────────────────────────────────┘
                     │ passes all checks
                     ▼
┌───────────────────────────────────────────────────────────┐
│               FastAPI Route Handler                        │
│     (business logic, db access, LLM calls, etc.)         │
└────────────────────┬──────────────────────────────────────┘
                     │ response body
                     ▼
┌───────────────────────────────────────────────────────────┐
│  DLPScannerMiddleware (response scan)                     │
│  + MetadataScrubber (strip fingerprinting headers)        │
│  + ExecutionTimeNormalizer (timing normalization)         │
└────────────────────┬──────────────────────────────────────┘
                     │
                     ▼
             OUTBOUND RESPONSE

─────────────────────────────────────────────────────────────

EXECUTION PACKETS (inter-subsystem)
      │
      ▼
┌──────────────────────────────────────────┐
│  PacketSigner (Ed25519 + Dilithium)      │
│  ← sign on send; verify on receive      │
│  ← reject + SECURITY_EVENT on failure   │
└──────────────────────────────────────────┘

─────────────────────────────────────────────────────────────

CRYPTO LAYER (key management)
┌──────────────────────────────────────────┐
│  HybridCryptography                      │
│  X25519 + CRYSTALS-Kyber (PQC)           │
│  AES-256-GCM (symmetric)                 │
│  Ed25519 + Dilithium (signatures)        │
│  KeyManager (24h rotation)               │
└──────────────────────────────────────────┘
```

---

*See also:*
- [`documentation/architecture/SYSTEM_COMPONENTS.md`](SYSTEM_COMPONENTS.md) — full component map
- [`tests/test_security_plane_wiring.py`](../../tests/test_security_plane_wiring.py) — 45 tests
- [`src/security_plane/__init__.py`](../../src/security_plane/__init__.py) — public exports

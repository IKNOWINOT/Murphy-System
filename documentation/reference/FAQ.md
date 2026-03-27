# Frequently Asked Questions

Common questions and answers about the Murphy System.

## Setup & Installation

### Q1: What are the minimum Python version requirements?

Murphy System requires **Python 3.10 or later**. The CI matrix tests against Python 3.10, 3.11,
and 3.12. Check your version with `python --version`.

### Q2: How do I install Murphy System and its dependencies?

```bash
cd "Murphy System"
pip install -r requirements_murphy_1.0.txt
```

Optionally review `pyproject.toml` for optional dependency groups (`dev`, `security`, `llm`).

### Q3: What environment variables must be set before running Murphy System?

Copy `.env.example` to `.env` and fill in at minimum:
- `MURPHY_MASTER_KEY` — master encryption key (auto-generated if absent, but must be persisted)
- `MURPHY_CORS_ORIGINS` — comma-separated allowed frontend origins (defaults to `http://localhost:3000`)
- `LLM_API_KEY` — API key for your chosen LLM provider (DeepInfra, OpenAI, etc.)

### Q4: How do I start the Murphy System server?

```bash
cd "Murphy System"
python -m uvicorn src.main:app --reload --port 8000
```

Or use the provided helper scripts:

```bash
./setup_and_start.sh   # Linux/macOS
setup_and_start.bat    # Windows
```

## API Keys & LLM Configuration

### Q5: Which LLM providers does Murphy System support?

Murphy System supports any OpenAI-compatible API (OpenAI, DeepInfra, Mistral, Ollama, etc.).
Set `LLM_PROVIDER` and `LLM_API_KEY` in your `.env` file. See
[API Reference](../../docs/API_REFERENCE.md) for the full list of supported providers and
their environment variable names.

### Q6: How do I rotate the master key without losing encrypted data?

Use `SecureKeyManager.rotate_key()` from `src/secure_key_manager.py`. The manager
re-encrypts all stored credentials with the new key before marking the old key inactive.
Never delete the old key until rotation is confirmed complete.

## Security

### Q7: How is authentication handled? Are passwords used anywhere?

Murphy System uses **passwordless authentication only**:
- Humans authenticate via FIDO2 passkeys or biometric hardware keys.
- Machine-to-machine communication uses mutual TLS (mTLS) with short-lived certificates.

No password fields exist in the data model. See `src/security_plane/authentication.py`.

### Q8: How does Murphy System prevent prompt injection attacks?

Inputs are sanitised through `InputSanitizer` in `src/security_plane/middleware.py` before
being passed to any LLM. DLP (Data Loss Prevention) scanning runs on all outbound LLM
responses. Enable strict mode with `MURPHY_STRICT_INPUT_VALIDATION=true`.

### Q9: What encryption is used for stored credentials?

Credentials at rest are encrypted with HMAC-SHA256 authenticated encryption via
`HybridCryptography` (`src/security_plane/cryptography.py`). Post-quantum cryptography
(liboqs) is on the roadmap (INFRA-002).

## Deployment

### Q10: What is the recommended production deployment topology?

For single-process deployments (solo operator, small team): the default in-memory stores
are sufficient. For multi-process or horizontally-scaled deployments:
- Rate limiter: upgrade to Redis-backed store (INFRA-001 — see `QA_AUDIT_REPORT.md`)
- Session store: use the `MURPHY_SESSION_BACKEND=redis` option
- See the full [Deployment Guide](../deployment/DEPLOYMENT_GUIDE.md)

### Q11: Does Murphy System support multi-tenancy?

Yes. The Confidence Engine API uses per-tenant state stores (tenant ID extracted from
the `X-Tenant-ID` header). Tenant isolation is enforced at the API layer. See
`src/confidence_engine/api_server.py` for implementation details.

## Testing & CI

### Q12: How do I run the test suite?

```bash
cd "Murphy System"
python -m pytest tests/ --timeout=60 -v --tb=short
```

Skip end-to-end and integration tests (which require live services) with:

```bash
python -m pytest tests/ --ignore=tests/e2e --ignore=tests/test_integration.py
```

### Q13: Why does the CI use `-x` (fail-fast)?

The CI is configured with `-x` so the first failure is immediately visible. When
debugging multiple failures, run locally without `-x` to see the full picture.

## Troubleshooting

### Q14: I see "No handler registered for action" warnings in the workflow engine. Is this normal?

Yes, in development. The workflow DAG engine logs a warning and executes the step in
**simulation mode** (result includes `"simulated": true`). For production, register
handlers with `engine.register_step_handler(action, fn)`. Use `strict_mode=True` to
fail instead of simulating.

### Q15: How do I report a security vulnerability?

Follow the responsible-disclosure process described in
[SECURITY.md](../../../SECURITY.md). Do **not** open a public GitHub issue for
security vulnerabilities.

## See Also

- [Installation](../getting_started/INSTALLATION.md)
- [Quick Start](../getting_started/QUICK_START.md)
- [Troubleshooting](../user_guides/TROUBLESHOOTING.md)
- [Deployment Guide](../deployment/DEPLOYMENT_GUIDE.md)

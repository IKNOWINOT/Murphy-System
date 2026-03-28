# API Authentication Guide

## Current Implementation Status

> **Security Hardening Applied (2026-02):** All Murphy System API servers now enforce
> authentication, CORS origin allowlisting, rate limiting, input sanitization, and security
> headers via `src/fastapi_security.py` and the unified `_APIKeyMiddleware` in `src/runtime/app.py`.
> See `docs/QA_AUDIT_REPORT.md` for full details.
>
> **Unified Gateway (2026-03):** All previously-standalone services (Cost Optimization Advisor,
> Compliance as Code Engine, Blockchain Audit Trail, Gate Synthesis, Module Compiler, Compute Plane)
> are now served by the single FastAPI runtime on port 8000 under their respective `/api/` prefixes.
> No separate Flask servers need to be started.
>
> **Quick Start:**
> - In **development** mode (`MURPHY_ENV=development`): Auth is optional — requests without API keys are allowed.
> - In **production** mode (`MURPHY_ENV=production`): All non-health endpoints require a valid API key via `X-API-Key` header.
> - Configure the API key via `MURPHY_API_KEY` environment variable (single key) or `MURPHY_API_KEYS` (comma-separated list).
> - Configure allowed CORS origins via `MURPHY_CORS_ORIGINS` environment variable.
> - Exempt paths (no key required): `/api/health`, `/api/info`, `/api/manifest`.

## Overview

The Murphy System Runtime provides comprehensive authentication and authorization mechanisms to secure API access. This guide covers all authentication methods, security best practices, and implementation details.

## Authentication Methods

### 1. API Key Authentication

The simplest authentication method using API keys.

#### Generating API Keys

```python
from src.system_integrator import SystemIntegrator

integrator = SystemIntegrator()

# Generate a new API key
api_key = integrator.auth.generate_api_key(
    user_id="user123",
    description="Production API key",
    scopes=["read", "write"]
)

print(f"API Key: {api_key}")
# Output: sk-murphy-abc123def456...
```

#### Using API Keys

```python
import requests

# Include API key in headers
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

response = requests.get(
    "https://api.murphy-system.com/v1/metrics",
    headers=headers
)
```

#### API Key Properties

- **Format**: `sk-murphy-{random_string}`
- **Length**: 64 characters
- **Encoding**: Base64
- **Storage**: Hashed in database
- **Revocation**: Can be revoked at any time

### 2. JWT (JSON Web Token) Authentication

Token-based authentication with expiration and refresh capabilities.

#### Generating JWT Tokens

```python
from src.system_integrator import SystemIntegrator

integrator = SystemIntegrator()

# Generate JWT token
token_data = {
    "user_id": "user123",
    "email": "user@example.com",
    "scopes": ["read", "write"],
    "exp": 3600  # 1 hour expiration
}

token = integrator.auth.generate_jwt(token_data)
print(f"JWT Token: {token}")
```

#### Using JWT Tokens

```python
import requests

headers = {
    "Authorization": f"Bearer {jwt_token}",
    "Content-Type": "application/json"
}

response = requests.get(
    "https://api.murphy-system.com/v1/metrics",
    headers=headers
)
```

#### JWT Properties

- **Algorithm**: RS256 (RSA Signature with SHA-256)
- **Expiration**: Configurable (default: 1 hour)
- **Refresh Token**: Available for token renewal
- **Claims**: Standard + custom claims
- **Revocation**: Token blacklist support

### 3. OAuth 2.0 Authentication

Standard OAuth 2.0 flow for third-party integrations.

#### Authorization Code Flow

```python
from src.system_integrator import SystemIntegrator

integrator = SystemIntegrator()

# Step 1: Get authorization URL
auth_url = integrator.auth.get_authorization_url(
    client_id="your_client_id",
    redirect_uri="https://your-app.com/callback",
    scopes=["read", "write"]
)

# Redirect user to auth_url
# After authorization, receive authorization code

# Step 2: Exchange code for tokens
tokens = integrator.auth.exchange_code_for_tokens(
    authorization_code="received_code",
    client_id="your_client_id",
    client_secret="your_client_secret"
)

access_token = tokens["access_token"]
refresh_token = tokens["refresh_token"]
```

#### Using OAuth Tokens

```python
import requests

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

response = requests.get(
    "https://api.murphy-system.com/v1/metrics",
    headers=headers
)
```

#### OAuth 2.0 Properties

- **Grant Types**: Authorization Code, Client Credentials, Refresh Token
- **Token Types**: Access Token, Refresh Token
- **Expiration**: Access token (1 hour), Refresh token (30 days)
- **Scopes**: Granular permissions
- **PKCE**: Supported for enhanced security

## Authorization & Scopes

### Available Scopes

| Scope | Description | Access Level |
|-------|-------------|--------------|
| `read` | Read-only access to resources | Basic |
| `write` | Write access to resources | Standard |
| `admin` | Administrative operations | Advanced |
| `metrics` | Access to metrics and telemetry | Basic |
| `telemetry` | Full telemetry access | Standard |
| `org` | Organization management | Advanced |
| `system` | System configuration | Advanced |

### Scope Examples

```python
# Read-only access
api_key = integrator.auth.generate_api_key(
    user_id="user123",
    scopes=["read", "metrics"]
)

# Full access
api_key = integrator.auth.generate_api_key(
    user_id="admin123",
    scopes=["read", "write", "admin", "metrics", "telemetry"]
)

# Organization management
api_key = integrator.auth.generate_api_key(
    user_id="org_admin",
    scopes=["read", "write", "org"]
)
```

## Security Best Practices

### 1. API Key Management

**DO:**
- Store API keys securely (environment variables, secret managers)
- Use different keys for different environments
- Rotate keys regularly (every 90 days)
- Revoke unused keys immediately
- Use key-specific scopes

**DON'T:**
- Commit API keys to version control
- Share keys in plain text
- Use production keys in development
- Reuse keys across applications
- Log API keys in plain text

### 2. JWT Token Management

**DO:**
- Use short expiration times (1 hour or less)
- Implement token refresh mechanism
- Validate token signature on every request
- Include user context in tokens
- Use HTTPS for token transmission

**DON'T:**
- Store tokens in localStorage
- Use long expiration times
- Skip token validation
- Include sensitive data in tokens
- Transmit tokens over HTTP

### 3. OAuth 2.0 Best Practices

**DO:**
- Use PKCE for public clients
- Implement state parameter for CSRF protection
- Validate redirect URIs strictly
- Use short-lived access tokens
- Implement token revocation

**DON'T:**
- Use implicit flow (legacy)
- Skip token validation
- Accept any redirect URI
- Use client credentials in public clients
- Share refresh tokens across sessions

### 4. General Security

**DO:**
- Use HTTPS for all API calls
- Implement rate limiting
- Monitor authentication logs
- Use strong encryption algorithms
- Implement IP whitelisting when appropriate

**DON'T:**
- Use HTTP for API calls
- Disable rate limiting
- Ignore authentication failures
- Use weak encryption
- Disable security features

## Implementation Examples

### Python Client

```python
from src.system_integrator import SystemIntegrator
import requests

class MurphyClient:
    def __init__(self, api_key, base_url="https://api.murphy-system.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })
    
    def get_metrics(self, metric_type=None):
        """Get metrics from the system"""
        params = {"metric_type": metric_type} if metric_type else {}
        response = self.session.get(
            f"{self.base_url}/v1/metrics",
            params=params
        )
        response.raise_for_status()
        return response.json()
    
    def collect_metric(self, metric_type, metric_name, value, labels=None):
        """Collect a metric"""
        data = {
            "metric_type": metric_type,
            "metric_name": metric_name,
            "value": value
        }
        if labels:
            data["labels"] = labels
        
        response = self.session.post(
            f"{self.base_url}/v1/metrics",
            json=data
        )
        response.raise_for_status()
        return response.json()

# Usage
client = MurphyClient(api_key="sk-murphy-abc123...")
metrics = client.get_metrics(metric_type="performance")
```

### JavaScript/Node.js Client

```javascript
const axios = require('axios');

class MurphyClient {
    constructor(apiKey, baseUrl = 'https://api.murphy-system.com') {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
        this.client = axios.create({
            baseURL: baseUrl,
            headers: {
                'Authorization': `Bearer ${apiKey}`,
                'Content-Type': 'application/json'
            }
        });
    }

    async getMetrics(metricType = null) {
        const params = metricType ? { metric_type: metricType } : {};
        const response = await this.client.get('/v1/metrics', { params });
        return response.data;
    }

    async collectMetric(metricType, metricName, value, labels = null) {
        const data = {
            metric_type: metricType,
            metric_name: metricName,
            value: value
        };
        if (labels) {
            data.labels = labels;
        }
        const response = await this.client.post('/v1/metrics', data);
        return response.data;
    }
}

// Usage
const client = new MurphyClient('sk-murphy-abc123...');
const metrics = await client.getMetrics('performance');
```

### curl Examples

```bash
# API Key Authentication
curl -X GET \
  https://api.murphy-system.com/v1/metrics \
  -H "Authorization: Bearer sk-murphy-abc123..." \
  -H "Content-Type: application/json"

# JWT Authentication
curl -X POST \
  https://api.murphy-system.com/v1/metrics \
  -H "Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "metric_type": "performance",
    "metric_name": "response_time",
    "value": 42.5
  }'
```

## Error Handling

### Authentication Errors

```python
try:
    response = client.get_metrics()
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 401:
        print("Authentication failed - Invalid or expired token")
    elif e.response.status_code == 403:
        print("Authorization failed - Insufficient permissions")
    else:
        print(f"HTTP Error: {e.response.status_code}")
```

### Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| 401 | Unauthorized | Check API key/token validity |
| 403 | Forbidden | Check user permissions/scopes |
| 409 | Conflict | Resource already exists |
| 429 | Too Many Requests | Only `POST /api/auth/login` counts toward brute-force lockout; wait for the lockout window to expire or contact support |
| 500 | Internal Server Error | Contact support |

## Configuration

### Environment Variables

```bash
# Authentication Settings
MURPHY_AUTH_ENABLED=true
MURPHY_AUTH_METHOD=api_key,jwt,oauth2

# API Key Settings
MURPHY_API_KEY_ENABLED=true
MURPHY_API_KEY_LENGTH=64
MURPHY_API_KEY_ROTATION_DAYS=90

# JWT Settings
MURPHY_JWT_ENABLED=true
MURPHY_JWT_SECRET=your-secret-key
MURPHY_JWT_EXPIRATION=3600
MURPHY_JWT_ALGORITHM=RS256

# OAuth 2.0 Settings
MURPHY_OAUTH_ENABLED=true
MURPHY_OAUTH_TOKEN_EXPIRATION=3600
MURPHY_OAUTH_REFRESH_EXPIRATION=2592000

# Brute-force protection (CWE-307) — applies only to POST /api/auth/login
# Other API endpoints (chat, librarian, execute, etc.) return 401 on missing
# credentials but never count toward the brute-force lockout, so normal
# multi-call interactions cannot accidentally lock a user's IP.
MURPHY_AUTH_MAX_ATTEMPTS=20          # failed login POSTs before IP lockout (default: 20)
MURPHY_AUTH_WINDOW_SECONDS=900       # sliding window for attempt counting (default: 15 min)
MURPHY_AUTH_LOCKOUT_SECONDS=900      # lockout duration after threshold reached (default: 15 min)
```

### Configuration File

```yaml
authentication:
  enabled: true
  
  api_key:
    enabled: true
    length: 64
    rotation_days: 90
    hash_algorithm: sha256
  
  jwt:
    enabled: true
    secret: ${JWT_SECRET}
    expiration: 3600
    algorithm: RS256
    refresh_token:
      enabled: true
      expiration: 2592000
  
  oauth2:
    enabled: true
    grant_types:
      - authorization_code
      - client_credentials
      - refresh_token
    pkce_enabled: true
  
  security:
    rate_limiting:
      enabled: true
      requests_per_minute: 60
    ip_whitelist:
      enabled: false
    https_required: true
```

## Monitoring & Auditing

### Authentication Logs

```python
# Enable authentication logging
integrator.auth.enable_logging(
    log_file="/var/log/murphy/auth.log",
    log_level="INFO"
)

# Monitor authentication events
events = integrator.auth.get_authentication_events(
    start_time="2024-01-01T00:00:00",
    end_time="2024-01-02T00:00:00"
)

for event in events:
    print(f"{event['timestamp']}: {event['event_type']} - {event['user_id']}")
```

### Auditing

```python
# Audit user access
audit_log = integrator.auth.audit_user_access(
    user_id="user123",
    start_time="2024-01-01T00:00:00",
    end_time="2024-01-02T00:00:00"
)

# Generate security report
report = integrator.auth.generate_security_report(
    period="daily",
    include_failed_attempts=True
)
```

## Troubleshooting

### Common Issues

**Issue**: API key not working
- Check if key is valid and not expired
- Verify key has required scopes
- Check if key is revoked
- Ensure correct Authorization header format

**Issue**: JWT token validation failing
- Verify token is not expired
- Check token signature
- Ensure issuer claim is correct
- Verify audience claim matches

**Issue**: OAuth token refresh failing
- Check refresh token is not expired
- Verify client credentials
- Ensure token endpoint is accessible
- Check token revocation status

**Issue**: Rate limiting errors
- Implement exponential backoff
- Cache responses appropriately
- Optimize API calls
- Consider upgrading plan

## License

BSL 1.1 (converts to Apache 2.0 after four years) - See LICENSE.md for details.

## Support

For authentication issues or questions:
- Contact: corey.gfc@gmail.com
- Owner: Corey Post InonI LLC
# OAuth Provider Setup Guide

Murphy System supports social login via Google, GitHub, Meta (Facebook), LinkedIn, Apple, and Microsoft. This guide walks through configuring each provider.

## Prerequisites

- Murphy System deployed and accessible at your domain (e.g., `https://murphy.systems`)
- SSH access to the production server
- Admin access to each provider's developer console

## Google OAuth Setup

### 1. Create OAuth Credentials

1. Go to [Google Cloud Console - Credentials](https://console.cloud.google.com/apis/credentials)
2. Create a new project or select existing one
3. Click **Create Credentials → OAuth client ID**
4. Application type: **Web application**
5. Name: `Murphy System`
6. Authorized JavaScript origins: `https://murphy.systems`
7. Authorized redirect URIs: `https://murphy.systems/api/auth/callback`
8. Click **Create** — copy the Client ID and Client Secret

### 2. Configure OAuth Consent Screen

1. Go to [OAuth Consent Screen](https://console.cloud.google.com/apis/credentials/consent)
2. User type: **External**
3. App name: `Murphy System`
4. User support email: your admin email
5. Authorized domains: `murphy.systems`
6. Scopes: `email`, `profile`, `openid`
7. Publishing status: **Testing** (up to 100 test users for beta)

### 3. Set Environment Variables

```bash
sudo systemctl edit murphy-production
```

Add:
```ini
[Service]
Environment="MURPHY_OAUTH_GOOGLE_CLIENT_ID=your-client-id"
Environment="MURPHY_OAUTH_GOOGLE_SECRET=your-client-secret"
Environment="MURPHY_OAUTH_REDIRECT_URI=https://murphy.systems/api/auth/callback"
```

Reload and restart:
```bash
sudo systemctl daemon-reload
sudo systemctl restart murphy-production
```

### 4. Verify

Visit `https://murphy.systems/api/auth/providers` — Google should show `true` in the providers object:

```json
{"providers": {"google": true, "github": false, ...}}
```

## GitHub OAuth Setup

### 1. Create OAuth App

1. Go to [GitHub Developer Settings](https://github.com/settings/developers)
2. Click **New OAuth App**
3. Application name: `Murphy System`
4. Homepage URL: `https://murphy.systems`
5. Authorization callback URL: `https://murphy.systems/api/auth/callback`
6. Click **Register application**
7. Copy Client ID, then generate a Client Secret

### 2. Set Environment Variables

```bash
sudo systemctl edit murphy-production
```

Add:
```ini
[Service]
Environment="MURPHY_OAUTH_GITHUB_CLIENT_ID=your-github-client-id"
Environment="MURPHY_OAUTH_GITHUB_SECRET=your-github-client-secret"
```

## Meta (Facebook) OAuth Setup

### 1. Create Facebook App

1. Go to [Meta for Developers](https://developers.facebook.com/apps/)
2. Create App → Select **Consumer** or **Business** type
3. Add **Facebook Login** product
4. Settings → Basic: copy App ID and App Secret
5. Facebook Login → Settings:
   - Valid OAuth Redirect URIs: `https://murphy.systems/api/auth/callback`
   - Enforce HTTPS: Yes

### 2. Set Environment Variables

```ini
Environment="MURPHY_OAUTH_META_CLIENT_ID=your-facebook-app-id"
Environment="MURPHY_OAUTH_META_SECRET=your-facebook-app-secret"
```

## LinkedIn OAuth Setup

### 1. Create LinkedIn App

1. Go to [LinkedIn Developers](https://www.linkedin.com/developers/apps)
2. Create app → Fill in details
3. Products tab → Request access to **Sign In with LinkedIn using OpenID Connect**
4. Auth tab: copy Client ID and Client Secret
5. Add redirect URL: `https://murphy.systems/api/auth/callback`

### 2. Set Environment Variables

```ini
Environment="MURPHY_OAUTH_LINKEDIN_CLIENT_ID=your-linkedin-client-id"
Environment="MURPHY_OAUTH_LINKEDIN_SECRET=your-linkedin-client-secret"
```

## Apple OAuth Setup

### 1. Create Apple Service ID

1. Go to [Apple Developer - Identifiers](https://developer.apple.com/account/resources/identifiers/list)
2. Register a new Services ID
3. Enable **Sign In with Apple**
4. Configure: Domains: `murphy.systems`, Return URLs: `https://murphy.systems/api/auth/callback`
5. Create a Key for Sign In with Apple and download it

### 2. Set Environment Variables

```ini
Environment="MURPHY_OAUTH_APPLE_CLIENT_ID=your-apple-services-id"
Environment="MURPHY_OAUTH_APPLE_SECRET=your-apple-key-contents"
```

## Microsoft OAuth Setup

### 1. Register Application

1. Go to [Azure Portal - App registrations](https://portal.azure.com/#blade/Microsoft_AAD_RegisteredApps/ApplicationsListBlade)
2. New registration
3. Name: `Murphy System`
4. Supported account types: **Accounts in any organizational directory and personal Microsoft accounts**
5. Redirect URI: Web → `https://murphy.systems/api/auth/callback`
6. Copy Application (client) ID
7. Certificates & secrets → New client secret → copy the value

### 2. Set Environment Variables

```ini
Environment="MURPHY_OAUTH_MICROSOFT_CLIENT_ID=your-azure-client-id"
Environment="MURPHY_OAUTH_MICROSOFT_SECRET=your-azure-client-secret"
```

## Verifying Configuration

After setting environment variables and restarting:

```bash
# Check which providers are enabled
curl -s https://murphy.systems/api/auth/providers | python3 -m json.tool

# Test a specific provider
# Open in browser:
https://murphy.systems/api/auth/oauth/google
# Should redirect to Google's consent screen
```

## Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| "Social sign-in temporarily unavailable" | Provider env vars not set | Set `MURPHY_OAUTH_<PROVIDER>_CLIENT_ID` and `_SECRET` |
| Google shows "redirect_uri_mismatch" | Callback URL mismatch | Ensure Google Console has `https://murphy.systems/api/auth/callback` exactly |
| OAuth button greyed out / "Coming soon" | Provider not configured | Follow setup steps above for that provider |
| Login redirects to `/dashboard.html` 404 | Old callback code | Ensure latest code is deployed |

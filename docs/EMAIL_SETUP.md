# Murphy System — Email Setup Guide

> Self-hosted email for `@murphy.systems` using docker-mailserver (Postfix + Dovecot + ClamAV + SpamAssassin + OpenDKIM + Fail2ban) and Roundcube webmail.

---

## Architecture

```
Internet ──► [DNS MX: mail.murphy.systems]
                     │
                     ▼
           ┌─────────────────────┐
           │  murphy-mailserver  │   Postfix (25/465/587) + Dovecot (143/993)
           │  docker-mailserver  │   ClamAV + SpamAssassin + Fail2ban + DKIM
           └─────────┬───────────┘
                     │  IMAP (143/993)
          ┌──────────┴────────────┐
          │                       │
          ▼                       ▼
  ┌───────────────┐     ┌──────────────────────────┐
  │ murphy-webmail│     │  Murphy Platform          │
  │  Roundcube    │     │  EmailService (SMTP:587)  │
  │  port 8443    │     │  EmailConnector (IMAP:993)│
  └───────────────┘     │  Matrix Email Bridge      │
                        │  Ambient Delivery         │
                        └──────────────────────────┘
```

---

## Quick Start

### 1. Start the containers

```bash
cp .env.example .env
# Edit .env — set MAIL_ADMIN_PASSWORD and ROUNDCUBE_DES_KEY
docker compose up -d murphy-mailserver murphy-webmail
```

### 2. Wait for the mail server to initialise (~60s)

```bash
docker compose logs -f murphy-mailserver
# Wait until you see "Postfix SMTP server is ready"
```

### 3. Provision mailboxes and aliases

```bash
./scripts/mail_setup.sh
```

This creates all personal mailboxes and group aliases. Initial passwords are saved to `/tmp/murphy-mail-passwords.txt`.

### 4. Add DNS records (Hetzner DNS panel)

| Type | Name | Value | Priority |
|------|------|-------|----------|
| MX | `murphy.systems` | `mail.murphy.systems` | 10 |
| A | `mail.murphy.systems` | `<your-hetzner-ip>` | — |
| TXT | `murphy.systems` | `v=spf1 a mx ip4:<your-hetzner-ip> -all` | — |
| TXT | `_dmarc.murphy.systems` | `v=DMARC1; p=quarantine; rua=mailto:postmaster@murphy.systems` | — |
| TXT | `mail._domainkey.murphy.systems` | *(see DKIM key below)* | — |

### 5. Get the DKIM DNS record

```bash
python scripts/mail_admin.py generate-dkim
```

Or view the full DNS record summary:

```bash
python scripts/mail_admin.py show-dns-records
```

### 6. Enable internal mail in Murphy Platform

Add to your `.env`:

```env
MURPHY_MAIL_INTERNAL=true
MAIL_ADMIN_EMAIL=cpost@murphy.systems
MAIL_ADMIN_PASSWORD=<your-password>
```

---

## User Accounts

### Personal Mailboxes

| Email | Name |
|-------|------|
| cpost@murphy.systems | Corey Post |
| hpost@murphy.systems | Hawthorn Post |
| abeltaine@murphy.systems | A. Beltaine |
| mpost@murphy.systems | M. Post |
| jcarney@murphy.systems | J. Carney |
| bgillespie@murphy.systems | B. Gillespie |
| lpost@murphy.systems | L. Post |
| kpost@murphy.systems | K. Post |
| d.post@murphy.systems | D. Post |
| zgillespie@murphy.systems | Z. Gillespie |

### Group Aliases

| Alias | Forwards To |
|-------|-------------|
| sales@murphy.systems | cpost, jcarney |
| marketing@murphy.systems | cpost, bgillespie |
| pr@murphy.systems | cpost, bgillespie |
| allstaff@murphy.systems | All personal mailboxes |
| operations@murphy.systems | cpost, hpost, mpost |
| support@murphy.systems | cpost, jcarney |
| billing@murphy.systems | cpost, mpost |
| legal@murphy.systems | cpost, abeltaine |
| hr@murphy.systems | cpost, hpost |
| admin@murphy.systems | cpost |
| postmaster@murphy.systems | cpost |
| abuse@murphy.systems | cpost |
| info@murphy.systems | cpost, jcarney |
| hello@murphy.systems | cpost |
| security@murphy.systems | cpost, abeltaine |
| engineering@murphy.systems | cpost, abeltaine |
| careers@murphy.systems | cpost, hpost |
| noreply@murphy.systems | *(send-only — no forward)* |

### Adding / Removing Users

```bash
# Add a new account (default quota: 5G)
python scripts/mail_admin.py add-account newuser@murphy.systems StrongPass123

# Add with custom quota
python scripts/mail_admin.py add-account newuser@murphy.systems StrongPass123 --quota 10G

# Remove an account
python scripts/mail_admin.py remove-account newuser@murphy.systems

# Change password
python scripts/mail_admin.py change-password cpost@murphy.systems NewSecurePass!

# List all accounts
python scripts/mail_admin.py list-accounts

# Manage aliases
python scripts/mail_admin.py add-alias devops@murphy.systems cpost@murphy.systems
python scripts/mail_admin.py list-aliases
```

---

## Email Client Configuration

### IMAP / SMTP Settings

| Setting | Value |
|---------|-------|
| **Incoming server (IMAP)** | `mail.murphy.systems` |
| IMAP port | `993` |
| IMAP security | SSL/TLS |
| **Outgoing server (SMTP)** | `mail.murphy.systems` |
| SMTP port | `587` |
| SMTP security | STARTTLS |
| Username | your full email address |
| Password | your account password |

### Thunderbird
1. File → New → Existing Mail Account
2. Enter name, email, password → Configure Manually
3. Use settings from the table above

### Apple Mail
1. System Preferences → Internet Accounts → Add Other Account → Mail account
2. Enter email and password
3. Apple Mail will auto-detect server settings (if MX/A records are set)
4. Confirm the settings match the table above

### Outlook
1. File → Add Account → Advanced Setup → Internet Email
2. Account type: IMAP
3. Use settings from the table above

### Mobile (iOS / Android)
- Use your email app's "Other" or "Manual" setup option
- Use the IMAP/SMTP settings from the table above

---

## Webmail

Roundcube webmail is available at:

```
http://<your-server-ip>:8443
```

Log in with your full email address and password.

**Features:**
- Read, compose, reply, forward email
- Manage folders (Inbox, Sent, Spam, Trash, Drafts)
- Vacation auto-reply (via Manage Sieve plugin)
- Server-side email filters
- PGP encryption (via Enigma plugin)

---

## Gmail-Level Features

| Feature | Status | Implementation |
|---------|--------|----------------|
| DKIM signing | ✅ | OpenDKIM (auto-keyed on first start) |
| SPF | ✅ | DNS TXT record (see DNS section) |
| DMARC | ✅ | DNS TXT record (see DNS section) |
| Spam filtering | ✅ | SpamAssassin (score 5.0, Bayesian) |
| Virus scanning | ✅ | ClamAV |
| Brute-force protection | ✅ | Fail2ban (5 retries → 1h ban) |
| Vacation responder | ✅ | Dovecot Sieve (via Roundcube plugin) |
| Server-side filtering | ✅ | Dovecot Sieve (default.sieve) |
| IMAP IDLE | ✅ | Dovecot (push notifications) |
| Quota management | ✅ | 5 GB per user (configurable) |
| TLS everywhere | ✅ | Self-signed (dev) / Let's Encrypt (prod) |
| Email forwarding | ✅ | postfix-virtual.cf aliases |
| Catch-all | ⚙️ | Add `@murphy.systems admin@murphy.systems` to postfix-virtual.cf |

---

## Matrix Integration

When `MURPHY_MAIL_INTERNAL=true`, the Matrix ↔ Email bridge automatically:

- Routes emails received on role addresses to Matrix rooms:
  - `support@` → `#murphy-support`
  - `sales@` → `#murphy-sales`
  - *(etc. — see `src/matrix_bridge/email_bridge.py`)*
- Posts delivery notifications to `#murphy-comms`
- Accepts Murphy bot commands:
  ```
  !murphy email send cpost@murphy.systems "Subject" "Body text"
  ```

---

## Troubleshooting

### Port 25 blocked (common on cloud VMs)

Many cloud providers block port 25 outbound. Contact Hetzner support to request removal of the outgoing SMTP restriction, or use a relay (e.g., SendGrid as a relay host):

```
# In config/mail/postfix-main.cf
relayhost = [smtp.sendgrid.net]:587
```

### DKIM not signing

```bash
docker exec murphy-mailserver python3 /usr/local/bin/setup config dkim
docker compose restart murphy-mailserver
```

### Emails landing in spam

Ensure all four DNS records (MX, A, SPF TXT, DKIM TXT) are set and propagated:

```bash
dig MX murphy.systems
dig TXT murphy.systems
dig TXT mail._domainkey.murphy.systems
dig TXT _dmarc.murphy.systems
```

### Check mail logs

```bash
docker logs murphy-mailserver -f
docker compose exec murphy-mailserver tail -100 /var/log/mail/mail.log
```

### ClamAV database updates

ClamAV downloads its database on first start — this can take 5–10 minutes. During this time, virus scanning is disabled but mail delivery continues.

---

## Security Hardening (Production)

1. **Replace self-signed TLS with Let's Encrypt:**
   ```yaml
   # In docker-compose.yml
   SSL_TYPE: letsencrypt
   ```
   And mount `/etc/letsencrypt` into the container.

2. **Change all initial passwords** immediately after setup.

3. **Set `ROUNDCUBE_DES_KEY`** to a random 24-character string in `.env`.

4. **Do not expose port 25 directly** — use a reverse proxy or cloud firewall rule.

5. **Enable DMARC reporting** — set `rua=` in your DMARC TXT record so you receive aggregate reports.

6. **Backup mail data** — the `mailserver-data` Docker volume contains all emails. Back it up regularly:
   ```bash
   docker run --rm -v murphy-mailserver-data:/data -v /backup:/backup alpine \
     tar czf /backup/mail-$(date +%F).tar.gz /data
   ```

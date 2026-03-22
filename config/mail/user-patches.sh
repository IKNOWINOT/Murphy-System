#!/bin/bash
# user-patches.sh — Run after docker-mailserver setup completes.
# Applies Murphy System-specific post-setup customizations.

set -e

echo "[murphy-mail] Applying user patches..."

# Ensure sieve directory exists for all users
if [ -d /var/mail/murphy.systems ]; then
    for user_dir in /var/mail/murphy.systems/*/; do
        user=$(basename "$user_dir")
        mkdir -p "$user_dir/sieve"
        # Copy default sieve script if user doesn't have one
        if [ ! -f "$user_dir/.dovecot.sieve" ] && [ -f /etc/dovecot/sieve/default.sieve ]; then
            cp /etc/dovecot/sieve/default.sieve "$user_dir/.dovecot.sieve"
            chown 5000:5000 "$user_dir/.dovecot.sieve"
        fi
    done
fi

# Generate DKIM key if it doesn't exist
if [ ! -f /etc/opendkim/keys/murphy.systems/mail.private ]; then
    echo "[murphy-mail] Generating DKIM key for murphy.systems..."
    mkdir -p /etc/opendkim/keys/murphy.systems
    opendkim-genkey -b 2048 -d murphy.systems -s mail \
        -D /etc/opendkim/keys/murphy.systems/
    echo "[murphy-mail] DKIM key generated. Add the following DNS TXT record:"
    cat /etc/opendkim/keys/murphy.systems/mail.txt
fi

echo "[murphy-mail] User patches applied."

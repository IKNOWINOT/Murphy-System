require ["fileinto", "reject", "vacation", "imap4flags"];

# ── Move spam to Junk folder ───────────────────────────────────────────────
if header :contains "X-Spam-Flag" "YES" {
    fileinto "Spam";
    stop;
}

if header :contains "Subject" "[SPAM]" {
    fileinto "Spam";
    stop;
}

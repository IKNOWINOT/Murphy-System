<?php
// Murphy System — Roundcube Webmail Configuration — PATCH-172

$config = [];

// ── URL / Proxy ────────────────────────────────────────────────────────────
$config['base_url'] = 'https://mail.murphy.systems/';

// ── Database ───────────────────────────────────────────────────────────────
$config['db_dsnw'] = 'sqlite:////var/roundcube/db/sqlite.db?mode=0646';

// ── IMAP (IMAPS / SSL on 993) ──────────────────────────────────────────────
$config['default_host'] = 'ssl://murphy-mailserver';
$config['default_port'] = 993;
$config['imap_timeout']  = 15;
$config['imap_cache']    = 'db';
$config['imap_conn_options'] = [
    'ssl' => [
        'verify_peer'       => false,
        'verify_peer_name'  => false,
    ],
];
$config['messages_cache'] = true;

// ── SMTP (STARTTLS on 587) ─────────────────────────────────────────────────
$config['smtp_server'] = 'tls://murphy-mailserver';
$config['smtp_port']   = 587;
$config['smtp_user']   = '%u';
$config['smtp_pass']   = '%p';
$config['smtp_conn_options'] = [
    'ssl' => [
        'verify_peer'       => false,
        'verify_peer_name'  => false,
    ],
];

// ── Identity ───────────────────────────────────────────────────────────────
$config['product_name']    = 'Murphy System Mail';
$config['mail_domain']     = 'murphy.systems';
$config['username_domain'] = 'murphy.systems';

// ── Performance
$config['mail_pagesize'] = 20;  // Fewer messages per page = faster mobile load

// ── UI / UX ────────────────────────────────────────────────────────────────
$config['skin']           = 'elastic';
$config['language']       = 'en_US';
$config['draft_autosave'] = 60;
$config['preview_pane']   = true;
$config['show_images']    = 0;
$config['max_message_size'] = '50M';

// ── Security ───────────────────────────────────────────────────────────────
$config['des_key']          = getenv('ROUNDCUBE_DES_KEY') ?: 'murphy-system-changeme-key';
$config['enable_installer'] = false;
$config['ip_check']         = false;
$config['referer_check']    = false;
$config['session_lifetime'] = 60;

// ── Plugins ────────────────────────────────────────────────────────────────
$config['plugins'] = [
    'archive',
    'zipdownload',
];

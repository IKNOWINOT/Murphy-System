<?php
// Murphy System — Roundcube Webmail Configuration
// See https://github.com/roundcube/roundcubemail/wiki/Configuration

$config = [];

// ── URL / Proxy ────────────────────────────────────────────────────────────
// Set base_url so Roundcube generates correct absolute URLs when served
// behind nginx at the /mail/ subpath (config/nginx/murphy-production.conf).
// Replace with your actual domain before going live.
$config['base_url'] = 'https://murphy.systems/mail/';

// ── Database ───────────────────────────────────────────────────────────────
$config['db_dsnw'] = 'sqlite:////var/roundcube/db/sqlite.db?mode=0646';

// ── IMAP ───────────────────────────────────────────────────────────────────
$config['default_host'] = 'murphy-mailserver';
$config['default_port'] = 143;
$config['imap_timeout']  = 15;
$config['imap_cache']    = 'db';
$config['messages_cache'] = true;

// ── SMTP ───────────────────────────────────────────────────────────────────
$config['smtp_server'] = 'murphy-mailserver';
$config['smtp_port']   = 587;
$config['smtp_user']   = '%u';
$config['smtp_pass']   = '%p';

// ── Identity ───────────────────────────────────────────────────────────────
$config['product_name']  = 'Murphy System Mail';
$config['mail_domain']   = 'murphy.systems';
$config['username_domain'] = 'murphy.systems';

// ── UI / UX ────────────────────────────────────────────────────────────────
$config['skin']                = 'elastic';
$config['language']            = 'en_US';
$config['draft_autosave']      = 60;
$config['preview_pane']        = true;
$config['show_images']         = 0;  // don't auto-load remote images (privacy)
$config['max_message_size']    = '50M';

// ── Plugins ────────────────────────────────────────────────────────────────
$config['plugins'] = [
    'archive',
    'zipdownload',
    'managesieve',   // vacation responder + server-side filters
    'enigma',        // PGP encryption
];

// ── Security ───────────────────────────────────────────────────────────────
$config['des_key']         = getenv('ROUNDCUBE_DES_KEY') ?: 'murphy-system-changeme-key';
$config['enable_installer'] = false;
$config['ip_check']         = false;
$config['referer_check']    = true;
$config['session_lifetime'] = 60;

// ── Managesieve (vacation / filters) ─────────────────────────────────────
$config['managesieve_host']    = 'murphy-mailserver';
$config['managesieve_port']    = 4190;
$config['managesieve_vacation_addresses'] = ['%u@murphy.systems'];

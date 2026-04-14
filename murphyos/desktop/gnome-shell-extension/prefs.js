// SPDX-License-Identifier: BSL-1.1
// © 2020 Inoni Limited Liability Company — Creator: Corey Post
//
// Murphy System GNOME Shell Extension — Preferences

import Adw from 'gi://Adw';
import Gio from 'gi://Gio';
import Gtk from 'gi://Gtk';

import {ExtensionPreferences, gettext as _} from 'resource:///org/gnome/Shell/Extensions/js/extensions/prefs.js';

export default class MurphyPreferences extends ExtensionPreferences {
    fillPreferencesWindow(window) {
        const settings = this.getSettings('org.murphy.system');

        const page = new Adw.PreferencesPage({
            title: _('Murphy System'),
            icon_name: 'preferences-system-symbolic',
        });
        window.add(page);

        // ── Connection group ──────────────────────────────────
        const connectionGroup = new Adw.PreferencesGroup({
            title: _('Connection'),
            description: _('Murphy API connection settings'),
        });
        page.add(connectionGroup);

        // API URL
        const apiRow = new Adw.EntryRow({
            title: _('API URL'),
            text: settings.get_string('api-url'),
        });
        apiRow.connect('changed', () => {
            settings.set_string('api-url', apiRow.text);
        });
        connectionGroup.add(apiRow);

        // Poll interval
        const pollRow = new Adw.SpinRow({
            title: _('Poll Interval (seconds)'),
            subtitle: _('How often to refresh the confidence score'),
            adjustment: new Gtk.Adjustment({
                lower: 1,
                upper: 300,
                step_increment: 1,
                page_increment: 10,
                value: settings.get_int('poll-interval'),
            }),
        });
        pollRow.connect('notify::value', () => {
            settings.set_int('poll-interval', pollRow.value);
        });
        connectionGroup.add(pollRow);

        // ── Display group ─────────────────────────────────────
        const displayGroup = new Adw.PreferencesGroup({
            title: _('Display'),
            description: _('Indicator appearance settings'),
        });
        page.add(displayGroup);

        // Show notifications
        const notifRow = new Adw.SwitchRow({
            title: _('Show Notifications'),
            subtitle: _('Display HITL approval requests and forge progress'),
        });
        settings.bind('show-notifications', notifRow, 'active', Gio.SettingsBindFlags.DEFAULT);
        displayGroup.add(notifRow);

        // Show PQC indicator
        const pqcRow = new Adw.SwitchRow({
            title: _('Show PQC Indicator'),
            subtitle: _('Display the post-quantum cryptography lock icon'),
        });
        settings.bind('show-pqc-indicator', pqcRow, 'active', Gio.SettingsBindFlags.DEFAULT);
        displayGroup.add(pqcRow);

        // ── Branding group ────────────────────────────────────
        const brandGroup = new Adw.PreferencesGroup({
            title: _('Branding'),
            description: _('Murphy System visual identity'),
        });
        page.add(brandGroup);

        // Brand accent colour
        const accentRow = new Adw.EntryRow({
            title: _('Accent Colour'),
            text: settings.get_string('brand-accent-color'),
        });
        accentRow.connect('changed', () => {
            settings.set_string('brand-accent-color', accentRow.text);
        });
        brandGroup.add(accentRow);
    }
}

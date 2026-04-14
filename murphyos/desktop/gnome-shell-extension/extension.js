// SPDX-License-Identifier: BSL-1.1
// © 2020 Inoni Limited Liability Company — Creator: Corey Post
//
// Murphy System GNOME Shell Extension
// MurphyOS desktop integration — confidence indicator, HITL notifications, Forge launcher

import GLib from 'gi://GLib';
import St from 'gi://St';
import Gio from 'gi://Gio';

import * as Main from 'resource:///org/gnome/shell/ui/main.js';
import * as PanelMenu from 'resource:///org/gnome/shell/ui/panelMenu.js';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import * as MessageTray from 'resource:///org/gnome/shell/ui/messageTray.js';

import {Extension, gettext as _} from 'resource:///org/gnome/shell/extensions/extension.js';

const DBUS_CONFIDENCE_NAME = 'org.murphy.Confidence';
const DBUS_CONFIDENCE_PATH = '/org/murphy/Confidence';
const DBUS_CONFIDENCE_IFACE = 'org.murphy.Confidence';

const DBUS_HITL_NAME = 'org.murphy.HITL';
const DBUS_HITL_PATH = '/org/murphy/HITL';
const DBUS_HITL_IFACE = 'org.murphy.HITL';

const DBUS_FORGE_NAME = 'org.murphy.Forge';
const DBUS_FORGE_PATH = '/org/murphy/Forge';
const DBUS_FORGE_IFACE = 'org.murphy.Forge';

const CONFIDENCE_FILE = '/murphy/live/confidence';

/**
 * Return icon name / colour band for a given confidence score.
 */
function _confidenceBand(score) {
    if (score >= 0.85) return 'green';
    if (score >= 0.50) return 'yellow';
    return 'red';
}

class MurphyIndicator extends PanelMenu.Button {
    static {
        GLib.type_ensure(St.Label.$gtype);
    }

    _init(ext) {
        super._init(0.0, _('Murphy System'));
        this._ext = ext;
        this._settings = ext.getSettings('org.murphy.system');

        this._confidence = 0.0;
        this._engineCount = 0;
        this._swarmCount = 0;
        this._pqcAlgorithm = 'ML-KEM-768';
        this._pqcEpoch = 0;
        this._pqcVerified = false;

        // ── Top-bar layout ────────────────────────────────────
        this._box = new St.BoxLayout({style_class: 'panel-status-menu-box'});

        this._icon = new St.Icon({
            icon_name: 'emblem-ok-symbolic',
            style_class: 'murphy-indicator-green system-status-icon',
        });
        this._box.add_child(this._icon);

        this._pqcLock = new St.Icon({
            icon_name: 'changes-prevent-symbolic',
            style_class: 'murphy-pqc-lock system-status-icon',
            visible: this._settings.get_boolean('show-pqc-indicator'),
        });
        this._box.add_child(this._pqcLock);

        this._label = new St.Label({
            text: '⚙ Murphy: —',
            y_align: imports.gi.Clutter?.ActorAlign?.CENTER ?? 2,
        });
        this._box.add_child(this._label);
        this.add_child(this._box);

        // ── Popup menu items ──────────────────────────────────
        this._buildMenu();

        // ── D-Bus subscriptions ───────────────────────────────
        this._dbusSubscriptions = [];
        this._subscribeDBus();

        // ── Polling timer ─────────────────────────────────────
        this._pollInterval = this._settings.get_int('poll-interval');
        this._timerId = GLib.timeout_add_seconds(
            GLib.PRIORITY_DEFAULT,
            this._pollInterval > 0 ? this._pollInterval : 5,
            () => {
                this._refresh();
                return GLib.SOURCE_CONTINUE;
            },
        );

        this._refresh();
    }

    // ── Menu construction ─────────────────────────────────────
    _buildMenu() {
        // Confidence row
        this._confidenceItem = new PopupMenu.PopupMenuItem(_('Confidence: —'));
        this.menu.addMenuItem(this._confidenceItem);

        // Engine count
        this._engineItem = new PopupMenu.PopupMenuItem(_('Engines: —'));
        this.menu.addMenuItem(this._engineItem);

        // Swarm agent count
        this._swarmItem = new PopupMenu.PopupMenuItem(_('Swarm Agents: —'));
        this.menu.addMenuItem(this._swarmItem);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // PQC status
        this._pqcItem = new PopupMenu.PopupMenuItem(_('PQC: —'));
        this.menu.addMenuItem(this._pqcItem);

        // Gate status
        this._gateItem = new PopupMenu.PopupMenuItem(_('Gates: —'));
        this.menu.addMenuItem(this._gateItem);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Forge command entry
        const forgeBox = new St.BoxLayout({style_class: 'murphy-forge-entry'});
        this._forgeEntry = new St.Entry({
            hint_text: _('Forge command…'),
            can_focus: true,
            track_hover: true,
            x_expand: true,
        });
        this._forgeEntry.clutter_text.connect('activate', () => {
            this._onForgeSubmit(this._forgeEntry.get_text());
            this._forgeEntry.set_text('');
        });
        forgeBox.add_child(this._forgeEntry);

        const forgeMenuItem = new PopupMenu.PopupBaseMenuItem({reactive: false});
        forgeMenuItem.add_child(forgeBox);
        this.menu.addMenuItem(forgeMenuItem);

        this.menu.addMenuItem(new PopupMenu.PopupSeparatorMenuItem());

        // Open Dashboard
        const dashItem = new PopupMenu.PopupMenuItem(_('Open Dashboard'));
        dashItem.connect('activate', () => {
            const apiUrl = this._settings.get_string('api-url') || 'http://localhost:8000';
            Gio.AppInfo.launch_default_for_uri(apiUrl, null);
        });
        this.menu.addMenuItem(dashItem);
    }

    // ── Data refresh ──────────────────────────────────────────
    _refresh() {
        this._readConfidenceFile();
        this._readConfidenceDBus();
    }

    _readConfidenceFile() {
        try {
            const file = Gio.File.new_for_path(CONFIDENCE_FILE);
            const [ok, contents] = file.load_contents(null);
            if (ok) {
                const text = new TextDecoder().decode(contents).trim();
                const parsed = JSON.parse(text);
                this._applyState(parsed);
            }
        } catch (_e) {
            // File may not exist — fall through to D-Bus
        }
    }

    _readConfidenceDBus() {
        try {
            const bus = Gio.DBus.system;
            bus.call(
                DBUS_CONFIDENCE_NAME,
                DBUS_CONFIDENCE_PATH,
                'org.freedesktop.DBus.Properties',
                'GetAll',
                new GLib.Variant('(s)', [DBUS_CONFIDENCE_IFACE]),
                null,
                Gio.DBusCallFlags.NONE,
                2000,
                null,
                (conn, res) => {
                    try {
                        const reply = conn.call_finish(res);
                        const props = reply.deep_unpack()[0];
                        this._applyState({
                            confidence: props.Score?.deep_unpack() ?? this._confidence,
                            engines: props.EngineCount?.deep_unpack() ?? this._engineCount,
                            swarm_agents: props.SwarmCount?.deep_unpack() ?? this._swarmCount,
                            pqc_algorithm: props.PQCAlgorithm?.deep_unpack() ?? this._pqcAlgorithm,
                            pqc_epoch: props.PQCEpoch?.deep_unpack() ?? this._pqcEpoch,
                            pqc_verified: props.PQCVerified?.deep_unpack() ?? this._pqcVerified,
                        });
                    } catch (_e) {
                        // D-Bus not available
                    }
                },
            );
        } catch (_e) {
            // D-Bus unavailable
        }
    }

    _applyState(state) {
        if (state.confidence !== undefined) {
            this._confidence = parseFloat(state.confidence);
        }
        if (state.engines !== undefined) this._engineCount = state.engines;
        if (state.swarm_agents !== undefined) this._swarmCount = state.swarm_agents;
        if (state.pqc_algorithm !== undefined) this._pqcAlgorithm = state.pqc_algorithm;
        if (state.pqc_epoch !== undefined) this._pqcEpoch = state.pqc_epoch;
        if (state.pqc_verified !== undefined) this._pqcVerified = state.pqc_verified;

        this._updateUI();
    }

    _updateUI() {
        const band = _confidenceBand(this._confidence);
        this._label.set_text(`⚙ Murphy: ${this._confidence.toFixed(2)}`);

        // Update indicator icon style
        this._icon.style_class = `murphy-indicator-${band} system-status-icon`;

        // PQC lock colour
        if (this._settings.get_boolean('show-pqc-indicator')) {
            this._pqcLock.visible = true;
            this._pqcLock.style_class = this._pqcVerified
                ? 'murphy-pqc-lock murphy-pqc-verified system-status-icon'
                : 'murphy-pqc-lock murphy-pqc-unverified system-status-icon';
        } else {
            this._pqcLock.visible = false;
        }

        // Menu items
        this._confidenceItem.label.set_text(
            _(`Confidence: ${this._confidence.toFixed(4)} [${band.toUpperCase()}]`),
        );
        this._engineItem.label.set_text(_(`Engines: ${this._engineCount}`));
        this._swarmItem.label.set_text(_(`Swarm Agents: ${this._swarmCount}`));
        this._pqcItem.label.set_text(
            _(`PQC: ${this._pqcAlgorithm}  epoch ${this._pqcEpoch}  ${this._pqcVerified ? '✓ verified' : '✗ unverified'}`),
        );
        this._gateItem.label.set_text(
            _(`Gates: ${this._confidence >= 0.50 ? 'OPEN' : 'LOCKED'}`),
        );
    }

    // ── D-Bus signal subscriptions ────────────────────────────
    _subscribeDBus() {
        try {
            const bus = Gio.DBus.system;

            // HITL approval-required signal
            const hitlSub = bus.signal_subscribe(
                DBUS_HITL_NAME,
                DBUS_HITL_IFACE,
                'ApprovalRequired',
                DBUS_HITL_PATH,
                null,
                Gio.DBusSignalFlags.NONE,
                (_conn, _sender, _path, _iface, _signal, params) => {
                    this._onHITLApprovalRequired(params);
                },
            );
            this._dbusSubscriptions.push(hitlSub);

            // Forge build progress signal
            const forgeSub = bus.signal_subscribe(
                DBUS_FORGE_NAME,
                DBUS_FORGE_IFACE,
                'BuildProgress',
                DBUS_FORGE_PATH,
                null,
                Gio.DBusSignalFlags.NONE,
                (_conn, _sender, _path, _iface, _signal, params) => {
                    this._onForgeProgress(params);
                },
            );
            this._dbusSubscriptions.push(forgeSub);
        } catch (_e) {
            // D-Bus unavailable at enable time
        }
    }

    // ── HITL notifications ────────────────────────────────────
    _onHITLApprovalRequired(params) {
        if (!this._settings.get_boolean('show-notifications')) return;

        const [requestId, description] = params.deep_unpack();
        const source = new MessageTray.Source({
            title: _('⚙ Murphy HITL'),
            iconName: 'dialog-question-symbolic',
        });
        Main.messageTray.add(source);

        const notification = new MessageTray.Notification({
            source,
            title: _('Approval Required'),
            body: description || _('A Murphy action requires human approval.'),
        });
        notification.addAction(_('Approve'), () => this._hitlRespond(requestId, true));
        notification.addAction(_('Deny'), () => this._hitlRespond(requestId, false));
        notification.setUrgency(MessageTray.Urgency.HIGH);
        source.addNotification(notification);
    }

    _hitlRespond(requestId, approved) {
        try {
            const bus = Gio.DBus.system;
            const method = approved ? 'Approve' : 'Deny';
            bus.call(
                DBUS_HITL_NAME,
                DBUS_HITL_PATH,
                DBUS_HITL_IFACE,
                method,
                new GLib.Variant('(s)', [requestId]),
                null,
                Gio.DBusCallFlags.NONE,
                5000,
                null,
                null,
            );
        } catch (_e) {
            log(`[Murphy] Failed to send HITL ${approved ? 'Approve' : 'Deny'}: ${_e}`);
        }
    }

    // ── Forge integration ─────────────────────────────────────
    _onForgeSubmit(command) {
        if (!command || command.trim() === '') return;

        try {
            const bus = Gio.DBus.system;
            bus.call(
                DBUS_FORGE_NAME,
                DBUS_FORGE_PATH,
                DBUS_FORGE_IFACE,
                'Build',
                new GLib.Variant('(s)', [command.trim()]),
                null,
                Gio.DBusCallFlags.NONE,
                30000,
                null,
                (conn, res) => {
                    try {
                        const reply = conn.call_finish(res);
                        const [buildId] = reply.deep_unpack();
                        this._showNotification(
                            _('Forge'),
                            _(`Build started: ${buildId}`),
                        );
                    } catch (e) {
                        this._showNotification(
                            _('Forge Error'),
                            _(`Failed to start build: ${e.message}`),
                        );
                    }
                },
            );
        } catch (e) {
            log(`[Murphy] Forge D-Bus call failed: ${e}`);
        }
    }

    _onForgeProgress(params) {
        const [buildId, progress, message] = params.deep_unpack();
        this._showNotification(
            _(`Forge [${buildId}]`),
            _(`${Math.round(progress * 100)}% — ${message}`),
        );
    }

    _showNotification(title, body) {
        if (!this._settings.get_boolean('show-notifications')) return;

        const source = new MessageTray.Source({
            title: _('⚙ Murphy System'),
            iconName: 'system-run-symbolic',
        });
        Main.messageTray.add(source);

        const notification = new MessageTray.Notification({source, title, body});
        source.addNotification(notification);
    }

    // ── Cleanup ───────────────────────────────────────────────
    destroy() {
        if (this._timerId) {
            GLib.source_remove(this._timerId);
            this._timerId = null;
        }

        try {
            const bus = Gio.DBus.system;
            for (const id of this._dbusSubscriptions) {
                bus.signal_unsubscribe(id);
            }
        } catch (_e) {
            // ignore
        }
        this._dbusSubscriptions = [];

        super.destroy();
    }
}

export default class MurphyExtension extends Extension {
    _indicator = null;

    enable() {
        this._indicator = new MurphyIndicator(this);
        Main.panel.addToStatusArea(this.uuid, this._indicator);
    }

    disable() {
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
    }
}

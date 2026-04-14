# murphy-dbus — Murphy System D-Bus Bridge & Polkit Policy

> © 2020 Inoni Limited Liability Company | Creator: Corey Post | License: BSL 1.1

Exposes the Murphy System REST API as native Linux D-Bus services,
enabling desktop applications, CLI tools, and other system components
to interact with Murphy through standard IPC rather than raw HTTP.

## Interfaces

| Bus Name | Interface | Purpose |
|----------|-----------|---------|
| `org.murphy.System` | `org.murphy.ControlPlane` | Engine lifecycle — start, stop, list, execute |
| | `org.murphy.Confidence` | Live confidence score, Murphy Index, gate satisfaction |
| | `org.murphy.HITL` | Human-in-the-loop approval workflow |
| | `org.murphy.Swarm` | Autonomous agent swarm management |
| | `org.murphy.Forge` | Natural-language → deliverable build pipeline |

All interfaces are served from the single object path `/org/murphy/System`.

## Files

| File | Install Path | Purpose |
|------|-------------|---------|
| `org.murphy.System.conf` | `/etc/dbus-1/system.d/` | Bus policy — ownership & method ACLs |
| `org.murphy.System.service` | `/usr/share/dbus-1/system-services/` | D-Bus service activation |
| `murphy-dbus.service` | `/usr/lib/systemd/system/` | systemd unit |
| `murphy_dbus_service.py` | `/usr/lib/murphy/murphy-dbus-service` | Python bridge daemon |
| `org.murphy.System.xml` | `/usr/share/dbus-1/interfaces/` | Introspection XML |
| `org.murphy.policy` | `/usr/share/polkit-1/actions/` | Polkit action definitions |
| `org.murphy.rules` | `/usr/share/polkit-1/rules.d/60-org.murphy.rules` | Polkit JS rules (confidence-aware) |

## Installation

```bash
# Copy files to their system locations
sudo install -Dm644 org.murphy.System.conf   /etc/dbus-1/system.d/org.murphy.System.conf
sudo install -Dm644 org.murphy.System.service /usr/share/dbus-1/system-services/org.murphy.System.service
sudo install -Dm644 murphy-dbus.service       /usr/lib/systemd/system/murphy-dbus.service
sudo install -Dm755 murphy_dbus_service.py    /usr/lib/murphy/murphy-dbus-service
sudo install -Dm644 org.murphy.System.xml     /usr/share/dbus-1/interfaces/org.murphy.System.xml
sudo install -Dm644 org.murphy.policy         /usr/share/polkit-1/actions/org.murphy.policy
sudo install -Dm644 org.murphy.rules          /usr/share/polkit-1/rules.d/60-org.murphy.rules

# Reload D-Bus and systemd
sudo systemctl daemon-reload
sudo systemctl reload dbus

# Start the bridge
sudo systemctl enable --now murphy-dbus.service
```

## Dependencies

| Package | Purpose |
|---------|---------|
| `python3-dbus-next` | Async D-Bus bindings (asyncio-native) |
| `python3-aiohttp` | Non-blocking HTTP client for REST API calls |
| `polkit` | Privilege escalation framework |

## Polkit Authorization

Murphy uses a confidence-aware Polkit policy that dynamically adjusts
required authorization levels:

| Confidence Score | Behaviour |
|-----------------|-----------|
| ≥ 0.85 | Auto-approve routine automation (engine-control, swarm-spawn) |
| 0.50 – 0.84 | Prompt for admin authentication |
| < 0.50 | Deny |

HITL approvals **always** require admin authentication regardless of
confidence.  Forge builds are allowed for any active session.

The live confidence score is read from `/murphy/live/confidence`, which
is written by the confidence polling loop in the D-Bus bridge.

## Usage Examples

### Introspect

```bash
busctl introspect org.murphy.System /org/murphy/System
```

### List engines

```bash
busctl call org.murphy.System /org/murphy/System \
    org.murphy.ControlPlane ListEngines
```

### Read confidence score

```bash
busctl get-property org.murphy.System /org/murphy/System \
    org.murphy.Confidence Score
```

### Spawn a swarm agent

```bash
busctl call org.murphy.System /org/murphy/System \
    org.murphy.Swarm SpawnAgent s "analyst"
```

### Approve a HITL request

```bash
busctl call org.murphy.System /org/murphy/System \
    org.murphy.HITL Approve s "req-abc123"
```

### Invoke Forge

```bash
busctl call org.murphy.System /org/murphy/System \
    org.murphy.Forge Build s "Build a revenue dashboard"
```

### Monitor signals

```bash
busctl monitor org.murphy.System
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MURPHY_API_URL` | `http://127.0.0.1:8000` | Base URL of the Murphy REST API |
| `MURPHY_CONFIDENCE_POLL_INTERVAL` | `5` | Seconds between confidence poll cycles |

## Architecture

```
┌─────────────────┐     D-Bus IPC      ┌────────────────────────┐
│  Desktop App /  │◄──────────────────►│  murphy-dbus-service   │
│  CLI / Script   │                    │  (murphy_dbus_service.py) │
└─────────────────┘                    └───────────┬────────────┘
                                                   │ HTTP (aiohttp)
                                                   ▼
                                       ┌────────────────────────┐
                                       │  Murphy REST API       │
                                       │  (localhost:8000)      │
                                       └────────────────────────┘
```

The bridge runs as the `murphy` system user under systemd supervision
and can be auto-activated by D-Bus on first method call.

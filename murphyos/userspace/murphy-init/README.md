# murphy-init — systemd Integration for Murphy System

> © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1

systemd unit files, generators, and support configs that integrate the
Murphy System (Universal AI Automation Runtime) as a first-class OS service
under MurphyOS.

## Contents

| File | Install path | Purpose |
|------|-------------|---------|
| `murphy-system.service` | `/usr/lib/systemd/system/` | Core Murphy runtime (FastAPI, sd_notify) |
| `murphy-bus.socket` | `/usr/lib/systemd/system/` | Unix socket for zero-latency IPC |
| `murphy-watchdog.service` | `/usr/lib/systemd/system/` | Self-Healing Coordinator watchdog |
| `murphy-session@.service` | `/usr/lib/systemd/system/` | Per-user Murphy session template |
| `murphy-system-generator` | `/usr/lib/systemd/system-generators/` | Boot-time engine service generator |
| `murphy-watchdog` | `/usr/lib/murphy/` | Health-check shell script |
| `murphy-tmpfiles.conf` | `/usr/lib/tmpfiles.d/murphy.conf` | Runtime & persistent directory creation |
| `murphy-sysusers.conf` | `/usr/lib/sysusers.d/murphy.conf` | `murphy` user/group creation |

## Quick Install

```bash
# Create the murphy system user
sudo cp murphy-sysusers.conf /usr/lib/sysusers.d/murphy.conf
sudo systemd-sysusers

# Create directory tree
sudo cp murphy-tmpfiles.conf /usr/lib/tmpfiles.d/murphy.conf
sudo systemd-tmpfiles --create murphy.conf

# Install the watchdog script
sudo install -Dm755 murphy-watchdog /usr/lib/murphy/murphy-watchdog

# Install the generator
sudo install -Dm755 murphy-system-generator \
    /usr/lib/systemd/system-generators/murphy-system-generator

# Install unit files
sudo cp murphy-system.service murphy-bus.socket \
       murphy-watchdog.service murphy-session@.service \
       /usr/lib/systemd/system/

# Reload and enable
sudo systemctl daemon-reload
sudo systemctl enable --now murphy-bus.socket murphy-system.service
```

## Architecture

```
                ┌───────────────────────────┐
                │   multi-user.target       │
                └──────────┬────────────────┘
                           │ WantedBy
              ┌────────────▼────────────┐
              │  murphy-system.service   │◄── Type=notify (sd_notify)
              │  (FastAPI runtime)       │
              └──┬──────────┬───────────┘
        Wants    │          │  BindsTo
    ┌────────────▼──┐  ┌────▼───────────────┐
    │ murphy-bus    │  │ murphy-watchdog     │
    │  .socket      │  │  .service           │
    │ (IPC socket)  │  │ (self-healing loop) │
    └───────────────┘  └────────────────────┘

    murphy-session@<user>.service   ← per-user sessions
    murphy-engine-<name>.service    ← generated at boot
```

### Socket Activation

`murphy-bus.socket` owns `/run/murphy/murphy.sock`. When a client connects
before the runtime is fully up, systemd buffers the connection and hands
the file descriptor to `murphy-system.service` via socket activation.

### Self-Healing Watchdog

`murphy-watchdog.service` polls `http://localhost:8000/api/health` every
10 seconds. After 3 consecutive failures it restarts the runtime and
writes a self-healing event to `/dev/murphy-event` (if the Murphy event
character device is loaded).

### Engine Generator

At boot, `murphy-system-generator` reads `/murphy/engines/*.conf` and
synthesises a `murphy-engine-<name>.service` for each enabled engine.

Engine config format (`/murphy/engines/sensor.conf`):

```ini
name=sensor
enabled=true
args=--interval 5
```

### Per-User Sessions

```bash
sudo systemctl start murphy-session@alice.service
```

Each instantiated session runs as the target user inside its own
`user-<name>.slice` with isolated state under `/murphy/sessions/<user>/`.

## Uninstall

```bash
sudo systemctl disable --now murphy-system.service murphy-bus.socket
sudo rm /usr/lib/systemd/system/murphy-system.service \
        /usr/lib/systemd/system/murphy-bus.socket \
        /usr/lib/systemd/system/murphy-watchdog.service \
        /usr/lib/systemd/system/murphy-session@.service \
        /usr/lib/systemd/system-generators/murphy-system-generator \
        /usr/lib/murphy/murphy-watchdog \
        /usr/lib/tmpfiles.d/murphy.conf \
        /usr/lib/sysusers.d/murphy.conf
sudo systemctl daemon-reload
sudo userdel murphy
```

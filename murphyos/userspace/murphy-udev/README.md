# MurphyOS udev Rules

© 2020 Inoni Limited Liability Company, Creator: Corey Post
License: BSL 1.1

Automatic hardware discovery and registration for MurphyOS. When devices
are plugged in or detected by the kernel, these udev rules notify the
Murphy runtime so engines can immediately use the new hardware.

## Files

| File | Purpose |
|------|---------|
| `90-murphy.rules` | udev rules for USB serial, IoT, GPU, network, block devices, and Murphy char devices |
| `murphy-device-register` | Helper script — registers IoT/USB devices with Murphy |
| `murphy-gpu-register` | Helper script — registers GPUs with the Compute Plane |
| `murphy-net-register` | Helper script — registers network interfaces with the Event Backbone |

## Installation

```bash
# Install udev rules
sudo install -m 0644 90-murphy.rules /etc/udev/rules.d/

# Install helper scripts
sudo install -m 0755 murphy-device-register /usr/lib/murphy/
sudo install -m 0755 murphy-gpu-register    /usr/lib/murphy/
sudo install -m 0755 murphy-net-register    /usr/lib/murphy/

# Create the murphy group (if it doesn't exist)
sudo groupadd -f murphy

# Reload udev rules
sudo udevadm control --reload-rules
sudo udevadm trigger
```

## How It Works

1. **USB serial** (`ttyUSB*`, `ttyACM*`) — Registered as potential
   Modbus/sensor devices. Permissions set to `murphy:0660`.

2. **IoT vendor devices** (FTDI, Silicon Labs, Arduino, Espressif) —
   Tagged `murphy-iot` and registered via `murphy-device-register`.

3. **GPU devices** (`card*` under `drm`) — `murphy-gpu-register` detects
   the GPU vendor (NVIDIA, AMD, Intel) and notifies the Compute Plane.

4. **Network interfaces** — New interfaces trigger `murphy-net-register`
   to inform the Event Backbone.

5. **Block devices** — Tagged `murphy-storage` for optional use by
   storage-aware engines.

6. **Murphy char devices** (`/dev/murphy-event`, `/dev/murphy-confidence`)
   — Secured with `murphy:0660` permissions.

## Communication Path

Each helper script tries, in order:

1. Write JSON to `/dev/murphy-event` (kernel char device, lowest latency)
2. `curl` HTTP POST to `localhost:8000/api/system/…` (fallback)
3. Log a warning via `logger` if neither path is available

## Dependencies

- `udev` (systemd-udevd or eudevd)
- `curl` (for HTTP fallback)
- `logger` (util-linux)
- Murphy runtime listening on port 8000 (for HTTP path)

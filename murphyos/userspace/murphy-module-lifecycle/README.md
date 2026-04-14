# murphy-module-lifecycle

> MurphyOS module lifecycle manager — systemd-based module instance management

## Overview

`murphy-module-lifecycle` is the OS-level counterpart to Murphy System's
higher-level Python module management layer (`module_instance_manager.py`,
`module_loader.py`, `module_manager.py`, `module_registry.py`).  It runs
each Murphy module as a **systemd transient scope** under a dedicated cgroup
slice, providing:

* Persistent module registry (`/var/lib/murphy/modules/registry.json`)
* Start / stop / restart via `systemd-run` and `systemctl`
* Health monitoring (HTTP probes and process liveness)
* Automatic crash recovery with exponential backoff
* Per-module resource governance (memory, CPU) via cgroup integration

## Architecture

```
┌───────────────────────────────────────────────────────────────────┐
│  Murphy System  (Python)                                          │
│  module_instance_manager / module_manager / module_loader          │
└────────────────────┬──────────────────────────────────────────────┘
                     │  spawns / manages via CLI or direct import
                     ▼
┌───────────────────────────────────────────────────────────────────┐
│  murphy-module-lifecycle  (this module)                            │
│  ModuleLifecycleManager                                           │
│    ├── Registry  ─ JSON persistence                               │
│    ├── Lifecycle ─ systemd-run / systemctl                        │
│    ├── Health    ─ HTTP probe / process liveness                  │
│    └── Restart   ─ exponential backoff (1s, 2s, 4s… max 60s)     │
└────────────────────┬──────────────────────────────────────────────┘
                     │
                     ▼
┌───────────────────────────────────────────────────────────────────┐
│  systemd (cgroup v2)                                              │
│  murphy-modules.slice/                                            │
│    ├── murphy-module-foo-<id>.scope   (MemoryMax=256M, CPUw=100)  │
│    ├── murphy-module-bar-<id>.scope                               │
│    └── …                                                          │
└───────────────────────────────────────────────────────────────────┘
```

## Installation

```bash
# Copy files
sudo cp murphy_module_lifecycle.py /opt/murphy/murphyos/userspace/murphy-module-lifecycle/
sudo cp module-lifecycle.yaml      /etc/murphy/module-lifecycle.yaml
sudo cp murphy-module-lifecycle.service /etc/systemd/system/

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable --now murphy-module-lifecycle
```

## CLI Usage

All commands accept `--config <path>` to override the default config file.

### Daemon mode

```bash
murphy-module-lifecycle daemon
```

Runs the health-monitor loop and handles signals (SIGTERM / SIGINT).

### Register a module

```bash
murphy-module-lifecycle register my-module \
    --version 1.0.0 \
    --entry-point /opt/murphy/modules/my-module/run.py \
    --health-url http://localhost:8080/healthz
```

### Unregister a module

```bash
murphy-module-lifecycle unregister my-module
```

### Start / stop / restart

```bash
murphy-module-lifecycle start   my-module [--instance-id abc123]
murphy-module-lifecycle stop    my-module [--instance-id abc123]
murphy-module-lifecycle restart my-module [--instance-id abc123]
```

### Status and health

```bash
murphy-module-lifecycle status my-module   # JSON output
murphy-module-lifecycle health my-module   # exit 0 = healthy, 1 = unhealthy
murphy-module-lifecycle list               # All modules with status
```

### Logs

```bash
murphy-module-lifecycle logs my-module --lines 100
```

## Module Registration

Modules are tracked in a JSON registry at the configured `registry_path`
(default: `/var/lib/murphy/modules/registry.json`).  Each entry stores:

| Field           | Type   | Description                          |
|-----------------|--------|--------------------------------------|
| `name`          | str    | Unique module identifier             |
| `version`       | str    | Semantic version                     |
| `entry_point`   | str    | Executable or script path            |
| `config`        | dict   | Module-specific configuration        |
| `memory_max`    | str    | cgroup memory limit (e.g. `256M`)    |
| `cpu_weight`    | int    | cgroup CPU weight (1-10000)          |
| `registered_at` | str    | ISO 8601 registration timestamp      |
| `crash_count`   | int    | Consecutive crash counter            |
| `last_crash_ts` | float  | Epoch time of last crash             |

## Resource Governance

Each module scope is created under `murphy-modules.slice` with configurable
limits:

```
murphy-modules.slice/
  └── murphy-module-{name}-{instance_id}.scope
        MemoryMax  = 256M   (default)
        CPUWeight  = 100    (default)
```

These integrate with `murphy-cgroup` for cgroup v2 enforcement.

## Auto-Restart

When the health monitor detects a module is unhealthy for
`unhealthy_threshold` consecutive checks (default: 3), it triggers an
auto-restart with exponential backoff:

| Crash # | Delay  |
|---------|--------|
| 1       | 1 s    |
| 2       | 2 s    |
| 3       | 4 s    |
| 4       | 8 s    |
| 5       | 16 s   |
| > max   | capped at `restart_backoff_max` (60 s) |

After `restart_max` (default: 5) consecutive crashes, auto-restart is
disabled and the module is left stopped.

## Error Codes

| Code                    | Description                        |
|-------------------------|------------------------------------|
| MURPHY-MODULE-ERR-001   | Registry load failure              |
| MURPHY-MODULE-ERR-002   | Registry save failure              |
| MURPHY-MODULE-ERR-003   | Module not found                   |
| MURPHY-MODULE-ERR-004   | Module already registered          |
| MURPHY-MODULE-ERR-005   | systemd-run start failed           |
| MURPHY-MODULE-ERR-006   | systemctl stop failed              |
| MURPHY-MODULE-ERR-007   | Status query failed                |
| MURPHY-MODULE-ERR-008   | Health check failed                |
| MURPHY-MODULE-ERR-009   | Log retrieval failed               |
| MURPHY-MODULE-ERR-010   | Configuration load error           |
| MURPHY-MODULE-ERR-011   | Restart limit exceeded             |
| MURPHY-MODULE-ERR-012   | Invalid module specification       |

## Configuration Reference

See `module-lifecycle.yaml` for the full default configuration:

```yaml
murphy_module_lifecycle:
  enabled: true
  registry_path: /var/lib/murphy/modules/registry.json
  module_slice: murphy-modules.slice
  defaults:
    memory_max: 256M
    cpu_weight: 100
    restart_max: 5
    restart_backoff_max: 60
  health_check:
    interval_seconds: 30
    timeout_seconds: 5
    unhealthy_threshold: 3
```

## License

BSL 1.1 — See repository root `LICENSE` for full terms.

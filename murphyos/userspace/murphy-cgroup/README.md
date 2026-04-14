# MurphyOS cgroup v2 Resource Isolation Manager

> SPDX-License-Identifier: LicenseRef-BSL-1.1
> © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1

OS-level resource isolation for Murphy System workloads using Linux cgroups v2.

## Hierarchy

```
/sys/fs/cgroup/
└── murphy.slice/                         ← base slice (managed)
    ├── murphy-swarm-<uuid>.scope         ← per-agent scope
    ├── murphy-swarm-<uuid>.scope
    ├── murphy-llm.slice/                 ← LLM inference workloads
    └── murphy-automation.slice/          ← automation tasks
```

Each scope/slice has its own `memory.max`, `cpu.weight`, `io.weight`, and
`pids.max` limits written to the corresponding cgroup v2 controller files.

## Quick Start

```bash
# Install the systemd unit
sudo cp murphy-cgroup.service /etc/systemd/system/
sudo cp cgroup.yaml /etc/murphy/cgroup.yaml
sudo systemctl daemon-reload
sudo systemctl enable --now murphy-cgroup
```

## CLI Usage

```bash
# Create a scope with explicit limits
python3 murphy_cgroup_manager.py create murphy-swarm-abc123.scope \
    --memory-max 512M --cpu-weight 100 --pids-max 64

# List all managed scopes
python3 murphy_cgroup_manager.py list

# Show resource usage
python3 murphy_cgroup_manager.py usage murphy-swarm-abc123.scope

# Update limits on a running scope
python3 murphy_cgroup_manager.py set-limits murphy-swarm-abc123.scope \
    --memory-max 1G --cpu-weight 200

# Destroy a scope
python3 murphy_cgroup_manager.py destroy murphy-swarm-abc123.scope

# Clean up scopes with no running processes
python3 murphy_cgroup_manager.py cleanup

# Run as daemon (used by systemd unit)
python3 murphy_cgroup_manager.py --config /etc/murphy/cgroup.yaml daemon
```

## Python API

```python
from murphy_cgroup_manager import CGroupManager

mgr = CGroupManager(config_path="cgroup.yaml")

# Create a per-agent scope
mgr.create_scope(
    "murphy-swarm-abc123.scope",
    memory_max="512M",
    cpu_weight=100,
    pids_max=64,
)

# Read usage
usage = mgr.get_usage("murphy-swarm-abc123.scope")
print(usage.memory_current_bytes, usage.cpu_usage_usec)

# Update limits at runtime
mgr.set_limits("murphy-swarm-abc123.scope", memory_max="1G")

# Destroy
mgr.destroy_scope("murphy-swarm-abc123.scope")
```

### Graceful Degradation

When cgroup v2 is not available (e.g. inside a container or on cgroup v1
hosts), the manager enters **no-op mode**. All methods return successfully
but perform no filesystem operations. Check `manager.is_noop` to detect
this state.

## Configuration

Edit `cgroup.yaml` (default location `/etc/murphy/cgroup.yaml`):

| Key | Description | Default |
|-----|-------------|---------|
| `enabled` | Master switch | `true` |
| `base_slice` | Slice name under `/sys/fs/cgroup/` | `murphy.slice` |
| `swarm_defaults.memory_max` | Per-agent memory ceiling | `512M` |
| `swarm_defaults.cpu_weight` | Per-agent CPU weight | `100` |
| `swarm_defaults.pids_max` | Per-agent process limit | `64` |
| `llm_defaults.memory_max` | LLM memory ceiling | `4G` |
| `llm_defaults.cpu_weight` | LLM CPU weight | `500` |
| `llm_defaults.io_weight` | LLM I/O weight | `200` |
| `automation_defaults.memory_max` | Automation memory ceiling | `1G` |
| `automation_defaults.cpu_weight` | Automation CPU weight | `200` |
| `automation_defaults.io_weight` | Automation I/O weight | `100` |

## Error Codes

| Code | Description |
|------|-------------|
| `MURPHY-CGROUP-ERR-001` | cgroup v2 filesystem not mounted / not available |
| `MURPHY-CGROUP-ERR-002` | Base slice directory creation failed |
| `MURPHY-CGROUP-ERR-003` | Scope creation failed (mkdir) |
| `MURPHY-CGROUP-ERR-004` | Scope destruction failed (rmdir / process drain) |
| `MURPHY-CGROUP-ERR-005` | Failed to write a cgroup controller file |
| `MURPHY-CGROUP-ERR-006` | Failed to read a cgroup controller file |
| `MURPHY-CGROUP-ERR-007` | Scope not found at expected path |
| `MURPHY-CGROUP-ERR-008` | Invalid scope name (disallowed characters) |
| `MURPHY-CGROUP-ERR-009` | Permission denied (likely missing `CAP_SYS_ADMIN`) |
| `MURPHY-CGROUP-ERR-010` | Orphan scope cleanup failed |
| `MURPHY-CGROUP-ERR-011` | Configuration file load / parse error |
| `MURPHY-CGROUP-ERR-012` | Invalid human-readable memory specification |
| `MURPHY-CGROUP-ERR-013` | Subtree controller delegation failed |
| `MURPHY-CGROUP-ERR-014` | Signal handler registration failed |
| `MURPHY-CGROUP-ERR-015` | Daemon lifecycle error (init / sd_notify) |

## systemd Unit

The included `murphy-cgroup.service` runs the manager as a `Type=notify`
daemon under root with the following hardening:

- `ProtectHome=yes` — no access to `/home`
- `ProtectSystem=strict` — read-only `/usr`, `/boot`, `/etc`
- `ReadWritePaths=/sys/fs/cgroup/murphy.slice` — only the managed slice
- `NoNewPrivileges=yes` — no privilege escalation
- `MemoryDenyWriteExecute=yes` — W^X enforcement

## Requirements

- Linux kernel ≥ 5.2 with unified cgroup v2 hierarchy
- Python ≥ 3.10
- PyYAML (included in Murphy runtime)
- `CAP_SYS_ADMIN` (or run as root) for cgroup writes

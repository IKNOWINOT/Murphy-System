# murphy-telemetry-export

OS-level Prometheus textfile collector for the Murphy System.

Reads Murphy runtime metrics via a four-source fallback chain (D-Bus →
REST API → MurphyFS → cgroup) and writes them in Prometheus exposition
format so that `node_exporter --collector.textfile` can scrape them.

## Quick start

```bash
# One-shot collection
python3 murphy_telemetry_export.py --once

# Continuous loop (default 15 s)
python3 murphy_telemetry_export.py -c /etc/murphy/telemetry.yaml

# systemd timer (recommended)
sudo systemctl enable --now murphy-telemetry-export.timer
```

## Installation

```bash
# Copy files
sudo install -m 0755 murphy_telemetry_export.py /opt/Murphy-System/murphyos/userspace/murphy-telemetry-export/
sudo install -m 0644 telemetry.yaml             /etc/murphy/telemetry.yaml
sudo install -m 0644 murphy-telemetry-export.service /etc/systemd/system/
sudo install -m 0644 murphy-telemetry-export.timer   /etc/systemd/system/

# Ensure output directory exists
sudo mkdir -p /var/lib/prometheus/node-exporter
sudo chown murphy:murphy /var/lib/prometheus/node-exporter

# Enable
sudo systemctl daemon-reload
sudo systemctl enable --now murphy-telemetry-export.timer
```

## Data-source fallback chain

| Priority | Source | Description |
|----------|--------|-------------|
| 1 | D-Bus `org.murphy.System` | Fastest, zero-copy IPC |
| 2 | REST API `http://127.0.0.1:8000/api/` | Reliable JSON over HTTP |
| 3 | MurphyFS `/murphy/live/` | Always-available virtual FS |
| 4 | cgroup `/sys/fs/cgroup/murphy.slice/` | Direct kernel counters |

Each metric collector tries source 1 first; on failure it falls through
to source 2, then 3, then 4.  If all sources fail the metric is omitted
(no stale data).

## Metric reference

All metrics use the `murphy_` prefix and follow Prometheus naming
conventions (`_total` for counters, `_seconds` for durations,
`_bytes` for sizes).

### Confidence

| Metric | Type | Description |
|--------|------|-------------|
| `murphy_confidence_score` | gauge | Current confidence score (0-1) |
| `murphy_confidence_changes_total` | counter | Cumulative confidence changes |

### Gates

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `murphy_gate_status` | gauge | `gate` | 1 = active, 0 = inactive |
| `murphy_gate_decisions_total` | counter | `gate`, `action` | Decisions per gate |

### Swarm

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `murphy_swarm_agents_active` | gauge | — | Currently active agents |
| `murphy_swarm_tasks_total` | counter | `status` | Task count by status |
| `murphy_swarm_agent_memory_bytes` | gauge | `agent_id` | Memory per agent |

### Forge

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `murphy_forge_builds_total` | counter | `status` | Builds by outcome |
| `murphy_forge_duration_seconds` | histogram | `le` | Build duration buckets |

### LLM

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `murphy_llm_requests_total` | counter | `provider`, `model` | API requests |
| `murphy_llm_tokens_total` | counter | `provider`, `direction` | Token usage |
| `murphy_llm_latency_seconds` | summary | `provider` | Request latency |
| `murphy_llm_cost_usd_total` | counter | `provider` | Cumulative cost |
| `murphy_llm_errors_total` | counter | `provider` | Error count |

### Security

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `murphy_security_posture_score` | gauge | — | Posture score (0-100) |
| `murphy_security_threats_total` | counter | `engine` | Threats by engine |
| `murphy_security_encryptions_total` | counter | — | Encryption ops |

### System

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `murphy_uptime_seconds` | gauge | — | System uptime |
| `murphy_health_status` | gauge | — | 1 = healthy |
| `murphy_event_backbone_events_total` | counter | `type` | Events by type |

### Backup

| Metric | Type | Description |
|--------|------|-------------|
| `murphy_backup_last_success_timestamp` | gauge | Unix epoch of last backup |
| `murphy_backup_size_bytes` | gauge | Backup size |

### CGroup

| Metric | Type | Labels | Description |
|--------|------|--------|-------------|
| `murphy_cgroup_memory_usage_bytes` | gauge | `slice` | Memory per cgroup slice |
| `murphy_cgroup_cpu_usage_seconds` | counter | `slice` | CPU time per slice |

## Prometheus configuration

Add the node\_exporter textfile directory to your `prometheus.yml`:

```yaml
scrape_configs:
  - job_name: "node"
    static_configs:
      - targets: ["localhost:9100"]
    # node_exporter must be started with:
    #   --collector.textfile.directory=/var/lib/prometheus/node-exporter
```

## Grafana dashboard hints

Import the metrics above into a Grafana dashboard.  Useful panels:

| Panel | Query |
|-------|-------|
| Confidence trend | `murphy_confidence_score` |
| LLM spend (24 h) | `increase(murphy_llm_cost_usd_total[24h])` |
| Gate overview | `murphy_gate_status` with variable `$gate` |
| Swarm fleet size | `murphy_swarm_agents_active` |
| Build success rate | `rate(murphy_forge_builds_total{status="success"}[5m]) / rate(murphy_forge_builds_total[5m])` |
| Backup freshness | `time() - murphy_backup_last_success_timestamp` |
| Memory by slice | `murphy_cgroup_memory_usage_bytes` grouped by `slice` |
| LLM p95 latency | `murphy_llm_latency_seconds_sum / murphy_llm_latency_seconds_count` |
| Security posture | `murphy_security_posture_score` with thresholds |

## Error codes

| Code | Meaning |
|------|---------|
| MURPHY-TELEMETRY-ERR-001 | Config file not found / unreadable |
| MURPHY-TELEMETRY-ERR-002 | Config file YAML parse error |
| MURPHY-TELEMETRY-ERR-003 | Output path not writable |
| MURPHY-TELEMETRY-ERR-004 | D-Bus query failed |
| MURPHY-TELEMETRY-ERR-005 | REST API query failed |
| MURPHY-TELEMETRY-ERR-006 | MurphyFS read failed |
| MURPHY-TELEMETRY-ERR-007 | cgroup read failed |
| MURPHY-TELEMETRY-ERR-008 | Metric collection error |
| MURPHY-TELEMETRY-ERR-009 | Atomic rename failed |
| MURPHY-TELEMETRY-ERR-010 | Unexpected fatal error |

## License

BSL 1.1 — see repository root `LICENSE` for full terms.

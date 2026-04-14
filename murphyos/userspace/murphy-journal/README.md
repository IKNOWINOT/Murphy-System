# MurphyOS Journald Structured Logging Integration

> SPDX-License-Identifier: LicenseRef-BSL-1.1
> © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1

OS-level bridge between Murphy Event Backbone events and **systemd-journald**
structured fields.  Every confidence change, gate decision, swarm lifecycle
event, security alert, and LLM request becomes a first-class journal entry
queryable with `journalctl`.

## Quick Start

```bash
# Install the systemd unit and namespace config
sudo cp murphy-journal.service /etc/systemd/system/
sudo mkdir -p /etc/systemd/journald@murphy.conf.d
sudo cp murphy-journal.conf /etc/systemd/journald@murphy.conf.d/murphy.conf
sudo systemctl daemon-reload
sudo systemctl enable --now murphy-journal

# Install the catalog (enables journalctl --catalog help text)
sudo journalctl --update-catalog < murphy.catalog
```

## Python API

```python
from murphy_journal import MurphyJournal

journal = MurphyJournal()

# Confidence change
journal.log_confidence_change(old_score=0.72, new_score=0.85)

# Gate decision
journal.log_gate_decision("deploy", "allow", confidence=0.85)

# Swarm agent lifecycle
journal.log_swarm_lifecycle(
    agent_id="a1b2c3d4-...", action="spawn", role="researcher",
)

# Security engine event
journal.log_security_event(
    engine="network-sentinel", event="port-scan detected", severity="warning",
)

# LLM request tracking
journal.log_llm_request(
    provider="openai", model="gpt-4o", tokens=1523, latency_ms=820.5,
)

# Generic structured event
journal.log_event(
    event_type="automation",
    message="Workflow step completed",
    severity="info",
    MURPHY_WORKFLOW_ID="wf-42",
)

# Query events
entries = journal.query_events(event_type="confidence", limit=20)
```

## Structured Journal Fields

| Field | Description | Example |
|-------|-------------|---------|
| `MURPHY_EVENT_TYPE` | Event category | `confidence`, `gate`, `swarm`, `forge`, `security`, `llm`, `automation` |
| `MURPHY_CONFIDENCE` | MFGC score at event time | `0.8500` |
| `MURPHY_CONFIDENCE_OLD` | Previous MFGC score (confidence change events) | `0.7200` |
| `MURPHY_AGENT_ID` | Swarm agent UUID | `a1b2c3d4-e5f6-...` |
| `MURPHY_SWARM_ACTION` | Agent lifecycle action | `spawn`, `kill`, `error` |
| `MURPHY_SWARM_ROLE` | Agent role | `researcher`, `coder`, `reviewer` |
| `MURPHY_GATE_NAME` | Governance gate name | `deploy`, `spend`, `delete` |
| `MURPHY_GATE_ACTION` | Gate verdict | `allow`, `deny`, `escalate` |
| `MURPHY_SECURITY_ENGINE` | Security engine name | `network-sentinel`, `auto-encrypt` |
| `MURPHY_SEVERITY` | Murphy severity level | `emergency` through `debug` |
| `MURPHY_ERROR_CODE` | Error code | `MURPHY-JOURNAL-ERR-003` |
| `MURPHY_LLM_PROVIDER` | LLM provider | `openai`, `anthropic` |
| `MURPHY_LLM_MODEL` | LLM model name | `gpt-4o`, `claude-3.5-sonnet` |
| `MURPHY_LLM_TOKENS` | Total tokens consumed | `1523` |
| `MURPHY_LLM_LATENCY_MS` | Request latency in milliseconds | `820.5` |
| `SYSLOG_IDENTIFIER` | Fixed identifier | `murphy-system` |

## Query Examples

```bash
# All Murphy events since boot
journalctl -b SYSLOG_IDENTIFIER=murphy-system

# Confidence changes only
journalctl SYSLOG_IDENTIFIER=murphy-system MURPHY_EVENT_TYPE=confidence

# Gate denials in the last hour
journalctl --since "-1h" SYSLOG_IDENTIFIER=murphy-system \
    MURPHY_EVENT_TYPE=gate MURPHY_GATE_ACTION=deny

# Security events at warning or above
journalctl -p warning SYSLOG_IDENTIFIER=murphy-system \
    MURPHY_EVENT_TYPE=security

# LLM requests for a specific provider
journalctl SYSLOG_IDENTIFIER=murphy-system MURPHY_EVENT_TYPE=llm \
    MURPHY_LLM_PROVIDER=openai

# Swarm agent lifecycle for a specific agent
journalctl SYSLOG_IDENTIFIER=murphy-system MURPHY_EVENT_TYPE=swarm \
    MURPHY_AGENT_ID=a1b2c3d4-e5f6-7890-abcd-ef1234567890

# JSON output for programmatic consumption
journalctl -o json SYSLOG_IDENTIFIER=murphy-system --since "-24h"

# Follow live events
journalctl -f SYSLOG_IDENTIFIER=murphy-system

# Show catalog help for a message
journalctl --catalog SYSLOG_IDENTIFIER=murphy-system
```

## Graceful Degradation

| Backend | Condition | Behaviour |
|---------|-----------|-----------|
| `systemd` (native) | `python-systemd` installed | Direct C API writes; full structured fields |
| `logger` (fallback) | `logger(1)` on PATH | Subprocess invocation; structured data in SD-ELEMENT |
| `none` | Neither available | Writes silently skipped; Python `logging` still active |

Check the active backend at runtime:

```python
journal = MurphyJournal()
print(journal.backend)  # "systemd", "logger", or "none"
```

## Error Codes

| Code | Description |
|------|-------------|
| `MURPHY-JOURNAL-ERR-001` | `python-systemd` not installed; using logger fallback |
| `MURPHY-JOURNAL-ERR-002` | `logger` binary not found on PATH |
| `MURPHY-JOURNAL-ERR-003` | Journal send failed |
| `MURPHY-JOURNAL-ERR-004` | Invalid event type |
| `MURPHY-JOURNAL-ERR-005` | Invalid severity level |
| `MURPHY-JOURNAL-ERR-006` | Journal query failed |
| `MURPHY-JOURNAL-ERR-007` | Subprocess logger invocation failed |
| `MURPHY-JOURNAL-ERR-008` | Timestamp parse error |

## Namespace Configuration

The included `murphy-journal.conf` configures a dedicated journald namespace:

| Setting | Value | Purpose |
|---------|-------|---------|
| `Storage` | `persistent` | Survive reboots |
| `Compress` | `yes` | Save disk space |
| `MaxRetentionSec` | `90day` | 90-day audit window |
| `MaxFileSec` | `1day` | Daily log rotation |
| `RateLimitIntervalSec` | `5s` | Rate-limit window |
| `RateLimitBurst` | `1000` | Max entries per window |

## systemd Unit

The `murphy-journal.service` unit runs the bridge as a `Type=notify` daemon
with the following hardening:

- `User=murphy` — runs as unprivileged murphy user
- `SupplementaryGroups=systemd-journal` — journal read access
- `ProtectHome=yes` / `ProtectSystem=strict` — filesystem isolation
- `NoNewPrivileges=yes` / `MemoryDenyWriteExecute=yes` — W^X enforcement
- `MemoryMax=64M` / `CPUQuota=5%` — resource caps

## Requirements

- Linux with systemd (systemd ≥ 245 recommended)
- Python ≥ 3.10
- `python-systemd` (recommended; falls back to `logger(1)` if absent)

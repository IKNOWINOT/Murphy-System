# MurphyOS LLM Resource Governor

> SPDX-License-Identifier: LicenseRef-BSL-1.1
> © 2020 Inoni Limited Liability Company — Creator: Corey Post — BSL 1.1

OS-level governance for LLM workloads in the Murphy System. Sits between the
userspace LLM subsystem (`llm_provider.py`, `llm_controller.py`,
`safe_llm_wrapper.py`, `groq_key_rotator.py`) and the underlying hardware /
cloud APIs to enforce budgets, rate limits, and health constraints.

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                 Murphy LLM Subsystem                 │
│  llm_provider · llm_controller · safe_llm_wrapper    │
└────────────────────┬─────────────────────────────────┘
                     │  record_usage / acquire / check_*
                     ▼
┌──────────────────────────────────────────────────────┐
│              murphy_llm_governor.py                   │
│  ┌────────────┐ ┌──────────┐ ┌───────────────────┐  │
│  │Token Budget│ │Rate Limit│ │ Provider Health    │  │
│  │  Tracker   │ │(tok-buck)│ │ p50/p95/p99 + err  │  │
│  └────────────┘ └──────────┘ └───────────────────┘  │
│  ┌────────────┐ ┌──────────────────────────────────┐ │
│  │GPU Governor│ │   Cost Circuit Breaker           │ │
│  │OOM + temp  │ │   daily / hourly / per-provider  │ │
│  └────────────┘ └──────────────────────────────────┘ │
│  State → /var/lib/murphy/llm-governor.json           │
└──────────────────────────────────────────────────────┘
                     │
                     ▼
          nvidia-smi / sysfs · LLM cloud APIs
```

### Key Components

| Component | Purpose |
|-----------|---------|
| **Token Budget Tracker** | Per-provider daily/hourly token and cost accounting |
| **Rate Limiter** | Token-bucket RPM/TPM enforcement per provider |
| **GPU Memory Governor** | OOM prevention via `nvidia-smi` or sysfs fallback |
| **Provider Health** | Sliding-window latency percentiles and error rates |
| **Cost Circuit Breaker** | Trips when daily/hourly caps are exceeded; auto-resets at midnight UTC |

---

## Budget Enforcement

The governor tracks every API call via `record_usage()` and enforces three
layers of cost protection:

1. **Per-provider daily cap** — e.g. DeepInfra $20/day, OpenAI $30/day.
2. **Global daily cap** — $50/day across all providers.
3. **Global hourly cap** — $10/hour burst protection.

When any cap is exceeded the **cost circuit breaker** trips, blocking further
requests via `is_circuit_open()`. Breakers auto-reset at midnight UTC.

---

## Rate Limiting

Each provider gets independent RPM (requests per minute) and TPM (tokens per
minute) token-bucket rate limiters. Call `acquire(provider, estimated_tokens)`
before dispatching an API call:

```python
from murphy_llm_governor import get_governor

gov = get_governor(config)
if gov.acquire("deepinfra", estimated_tokens=500):
    # proceed with API call
    ...
```

---

## GPU Monitoring

For local-model inference the governor monitors GPU resources:

- **OOM prevention**: blocks new inference when VRAM usage ≥ 90%.
- **Temperature guard**: blocks inference when GPU temp ≥ 85 °C.
- **Memory check**: `check_gpu_available(memory_required_mb)` verifies
  sufficient free VRAM.

Uses `nvidia-smi` for NVIDIA GPUs with a sysfs fallback for AMD GPUs that
expose `mem_info_vram_used` / `mem_info_vram_total`.

---

## Provider Health

`record_latency(provider, latency_ms, success)` feeds a sliding window
(default 300 s). The governor computes:

- **p50 / p95 / p99** latency
- **Error rate** — fraction of failed requests
- A provider is marked **unhealthy** when error rate ≥ 5 % or p99 ≥ 30 000 ms.

---

## Quick Start

```bash
# Install config
sudo mkdir -p /etc/murphy /var/lib/murphy
sudo cp llm-governor.yaml /etc/murphy/llm-governor.yaml

# Install systemd service
sudo cp murphy-llm-governor.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now murphy-llm-governor
```

---

## Error Codes

| Code | Description |
|------|-------------|
| `MURPHY-LLM-GOV-ERR-001` | Configuration file load failure |
| `MURPHY-LLM-GOV-ERR-002` | State persistence write failed |
| `MURPHY-LLM-GOV-ERR-003` | State persistence read failed |
| `MURPHY-LLM-GOV-ERR-004` | Daily budget exceeded |
| `MURPHY-LLM-GOV-ERR-005` | Hourly budget exceeded |
| `MURPHY-LLM-GOV-ERR-006` | Rate limit exceeded — requests per minute |
| `MURPHY-LLM-GOV-ERR-007` | Rate limit exceeded — tokens per minute |
| `MURPHY-LLM-GOV-ERR-008` | GPU OOM prevention triggered |
| `MURPHY-LLM-GOV-ERR-009` | GPU temperature limit exceeded |
| `MURPHY-LLM-GOV-ERR-010` | nvidia-smi execution failed |
| `MURPHY-LLM-GOV-ERR-011` | Provider health degraded |
| `MURPHY-LLM-GOV-ERR-012` | Cost circuit breaker open |

---

## Configuration Reference

See [`llm-governor.yaml`](llm-governor.yaml) for the full configuration
schema. The top-level key is `murphy_llm_governor`.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | bool | `true` | Master enable/disable |
| `state_file` | path | `/var/lib/murphy/llm-governor.json` | Persistent state location |
| `budgets.daily_total_usd` | float | `50.0` | Global daily cost cap |
| `budgets.hourly_total_usd` | float | `10.0` | Global hourly cost cap |
| `budgets.per_provider.<name>.daily_usd` | float | — | Per-provider daily cost cap |
| `budgets.per_provider.<name>.rpm` | int | — | Requests per minute limit |
| `budgets.per_provider.<name>.tpm` | int | — | Tokens per minute limit |
| `gpu.oom_threshold_percent` | float | `90` | VRAM % above which inference is blocked |
| `gpu.temperature_limit_celsius` | float | `85` | GPU °C above which inference is blocked |
| `health.error_rate_threshold` | float | `0.05` | Error rate (0–1) marking provider unhealthy |
| `health.latency_p99_threshold_ms` | float | `30000` | p99 latency above which provider is unhealthy |
| `health.window_seconds` | float | `300` | Sliding window for health metrics |

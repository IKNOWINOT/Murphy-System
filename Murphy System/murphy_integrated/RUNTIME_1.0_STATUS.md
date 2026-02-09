# Runtime 1.0 Status (Current Runnable System)

**Date:** 2026-02-09

Runtime 1.0 (`murphy_system_1.0_runtime.py`) is the only prepared runtime in this repository. Any references to v2/v3 are planning documents and are **not** runnable releases.

## Can I run it right now?

Yes. Use the provided startup script from the `murphy_integrated` directory:

```bash
./start_murphy_1.0.sh
```

This installs `requirements_murphy_1.0.txt`, sets up a virtual environment, and starts the API server on port **6666**.

### Smoke checks

```bash
curl http://localhost:6666/api/health
curl http://localhost:6666/api/status
curl http://localhost:6666/api/info
```

## What does runtime 1.0 actually do?

Runtime 1.0 provides a working orchestration and automation framework with these core capabilities:

- **Task execution** via `/api/execute` (uses the control plane + orchestrator).
- **System visibility** via `/api/status`, `/api/info`, and `/api/health`.
- **Business automation endpoints** under `/api/automation/{engine}/{action}` (sales, marketing, R&D, business, production). These require configuration of connectors/credentials to act on real systems.
- **Integration requests** via `/api/integrations/...` when integration dependencies are installed and the integration engine is available.

## Can it truly automate as the claims state?

It can **automate workflows once integrations and credentials are configured**, but it is **not fully autonomous out-of-the-box**. The runtime ships with automation engines and templates; real-world automation depends on connecting external APIs, data sources, and infrastructure.

In short:
- ✅ **Yes** — it can automate tasks when configured.
- ⚠️ **No** — it will not execute end-to-end business automation without setup, credentials, and safety approvals.

## Optional UI

Runtime 1.0 does not serve a web UI by default. A static UI (`murphy_ui_integrated.html`) can be served separately if desired:

```bash
python -m http.server 8090
# open http://localhost:8090/murphy_ui_integrated.html
```

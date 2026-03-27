# Murphy System — Troubleshooting Guide

## LLM / Ollama Issues

### phi3 never responds — chat returns template text

**Symptom:** Chat always returns text like `"DeepInfra generative response for..."` instead of a real reply.

**Cause:** Ollama is not running or phi3 is not pulled.

**Fix:**
```bash
# Check if Ollama is running
systemctl is-active ollama

# Start if not running
sudo systemctl start ollama

# Pull phi3 if not present
ollama pull phi3

# Verify phi3 is available
ollama list | grep phi3

# Check Murphy health
curl -s 'http://localhost:8000/api/health?deep=true' | python3 -c "
import sys, json
d = json.load(sys.stdin).get('checks', {})
print('Ollama running:', d.get('ollama_running'))
print('Ollama models: ', d.get('ollama_models'))
"
```

---

### Ollama starts after Murphy — phi3 unreachable on boot

**Symptom:** Murphy starts but Ollama isn't up yet; phi3 never used even after Ollama starts.

**Fix:** Add a systemd override so Murphy waits for Ollama:

```bash
sudo mkdir -p /etc/systemd/system/murphy-production.service.d
sudo tee /etc/systemd/system/murphy-production.service.d/override.conf > /dev/null << 'EOF'
[Unit]
After=network.target ollama.service
Requires=ollama.service
EOF
sudo systemctl daemon-reload
sudo systemctl restart murphy-production
```

---

### DEEPINFRA_API_KEY missing — want to use DeepInfra cloud

```bash
# Store key (persists across restarts)
curl -s -X POST http://localhost:8000/api/credentials/store \
  -H "Content-Type: application/json" \
  -d '{"integration":"deepinfra","credential":"gsk_YOUR_KEY_HERE"}'

# OR via terminal command inside Murphy
set key deepinfra gsk_YOUR_KEY_HERE
```

---

## Commissioning / Self-Assembly Issues

### Workflow health score below 0.75

**Symptom:** `POST /api/automations/commission` returns `ready_for_deploy: false`, health_score < 0.75.

**Cause:** Steps have insufficient context — generic descriptions, no domain keywords.

**Fix:** Provide richer descriptions:
```json
{
  "description": "Invoice processing: read PDF from email inbox, extract line items and amounts, create accounting entry in QuickBooks via API, send confirmation email",
  "context": {
    "integration": "quickbooks",
    "source": "gmail",
    "target": "quickbooks-api"
  }
}
```

**Understanding scores:**
- `keyword_overlap` (40%) — desc words that appear in step output
- `success_patterns` (30%) — words like "completed", "success", "validated"
- `output_length` (15%) — longer outputs score higher
- `structured_bonus` (15%) — explicit `status`, `passed`, `sent` fields

A score of 0.69 means all steps passed but descriptions are too generic. Add connector names, data schemas, or sample values.

---

### `generate_workflow` returns only 3 generic steps

**Symptom:** Workflow has `input_processing → execution → output` instead of domain-specific steps.

**Cause:** Description has no recognisable domain keywords.

**Fix:** Use explicit verbs from the `STEP_KEYWORDS` list:
- `read`, `extract`, `validate`, `approve`, `send`, `deploy`, `schedule`, `transform`, `filter`
- `invoice`, `email`, `report`, `alert`, `review`, `process`, `analyze`

**Example:**
```
✗ "Handle the thing with QuickBooks"
✓ "Read invoice email, extract PDF data, validate amounts, post to QuickBooks, send confirmation"
```

---

## Production Wizard Issues

### Production Wizard shows "Connecting..." and crashes back to landing page

**Status:** Fixed in this release. `apiFetch()` now catches 401/403 and shows an inline login banner instead of propagating the error.

**If still occurring:**
1. Clear browser cookies and log in again
2. Check `/api/health` returns `{"status":"healthy"}`
3. Open browser DevTools → Network → look for failed requests

---

### `/api/heatmap/coverage` returns 404

**Status:** Fixed in this release — endpoint now exists at `GET /api/heatmap/coverage`.

---

## System Map Issues

### Live Automations panel shows "No active automations"

**Cause:** No workflows have been commissioned yet, or the server was just restarted (in-memory store cleared).

**Fix:**
1. Commission a workflow via `POST /api/automations/commission`
2. The panel polls every 5 seconds — wait up to 5s after commissioning
3. Executions are in-memory — they clear on server restart (DB persistence is a future enhancement)

---

## Authentication Issues

### Session expires / returns to login page unexpectedly

**Symptom:** Pages redirect to `/ui/login` after working fine.

**Cause:** Session token expired (default: 24h).

**Fix:** Log in again. For production, set a longer session duration:
```bash
# In /etc/murphy-production/environment
MURPHY_SESSION_TTL_HOURS=168   # 7 days
```

---

## API Key Harvester Issues

### `/api/key-harvester/start` returns error about `murphy_native_automation`

**Cause:** The harvester requires the `murphy_native_automation` native module which needs OS-level browser automation support.

**Status:** The REST endpoints are fully wired. The native runner is a platform-specific component. On Ubuntu 22.04:
```bash
# Ensure X11/Xvfb is available for headless browser automation
sudo apt-get install -y xvfb chromium-browser
export DISPLAY=:99
Xvfb :99 -screen 0 1280x720x24 &
```

---

## Health Check

```bash
# Quick health check
curl -s http://localhost:8000/api/health | python3 -m json.tool

# Deep health check (includes Ollama, LLM, integrations)
curl -s 'http://localhost:8000/api/health?deep=true' | python3 -m json.tool

# LLM providers status
curl -s http://localhost:8000/api/llm/providers | python3 -m json.tool

# Module coverage
curl -s http://localhost:8000/api/heatmap/coverage | python3 -m json.tool
```

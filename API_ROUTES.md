# Murphy System API Routes

**Canonical reference for all API endpoints.**  
All routes follow the pattern: `/api/<domain>/<resource>[/<id>][/<action>]`  
All responses use the standard envelope: `{"success": bool, "data": ..., "error": {"code": "...", "message": "..."}}`

Auth: Include `X-API-Key: <key>` header when `MURPHY_API_KEY` env var is set.  
Dev mode: Auth is disabled when `MURPHY_API_KEY` is unset.

---

## Core & System (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/health | No | System health check |
| GET | /api/manifest | No | Machine-readable list of all registered API endpoints |
| GET | /api/info | No | System info |
| GET | /api/status | Yes | Full system status |
| GET | /api/readiness | Yes | Readiness probe |
| GET | /api/config | Yes | Get system configuration |
| POST | /api/config | Yes | Update system configuration |
| GET | /api/bootstrap | Yes | Bootstrap status |
| GET | /api/ui/links | No | UI navigation links |
| GET | /api/system/info | Yes | Detailed system information |
| GET | /api/telemetry | Yes | Telemetry data |
| GET | /api/test-mode/status | Yes | Test mode status |
| POST | /api/test-mode/toggle | Yes | Toggle test mode |
| GET | /api/safety/status | Yes | Safety system status |

---

## Auth (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/auth/signup | No | Create new account |
| GET | /api/auth/oauth/{provider} | No | Initiate OAuth flow |
| GET | /api/auth/callback | No | OAuth callback — sets `murphy_session` cookie and redirects to `/ui/terminal-unified?oauth_success=1&provider=<name>` |
| GET | /api/auth/role | Yes | Get current user role |
| GET | /api/auth/permissions | Yes | Get current user permissions |

---

## Profiles (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/profiles | Yes | List profiles |
| POST | /api/profiles | Yes | Create profile |
| GET | /api/profiles/{profile_id} | Yes | Get profile |
| PUT | /api/profiles/{profile_id} | Yes | Update profile |
| POST | /api/profiles/{profile_id}/activate | Yes | Activate profile |
| GET | /api/profiles/me | Yes | Get current user profile |
| GET | /api/profiles/me/terminal-config | Yes | Get terminal feature config |

---

## Orchestrator (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/orchestrator/overview | Yes | Orchestrator system overview |
| GET | /api/orchestrator/flows | Yes | List active flows |

---

## Workflows (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/workflows | Yes | List workflows |
| POST | /api/workflows | Yes | Create workflow |
| GET | /api/workflows/{workflow_id} | Yes | Get workflow |
| POST | /api/execute | Yes | Execute a state graph / flow |

---

## Workflow Terminal (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/workflow-terminal/list | Yes | List workflow programs |
| GET | /api/workflow-terminal/load | Yes | Load a workflow program |
| POST | /api/workflow-terminal/save | Yes | Save a workflow program |
| GET | /api/workflow-terminal/sessions | Yes | List active sessions |
| POST | /api/workflow-terminal/sessions | Yes | Create session |
| GET | /api/workflow-terminal/sessions/{session_id} | Yes | Get session |
| POST | /api/workflow-terminal/sessions/{session_id}/message | Yes | Send message to session |
| GET | /api/workflow-terminal/sessions/{session_id}/agents/{agent_id} | Yes | Get agent state |
| GET | /api/workflow-terminal/sessions/{session_id}/compile | Yes | Compile session state graph |

---

## Agents (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/agents | Yes | List agents |
| GET | /api/agents/{agent_id} | Yes | Get agent |
| GET | /api/agent-dashboard/snapshot | Yes | Dashboard snapshot |
| GET | /api/agent-dashboard/agents | Yes | List dashboard agents |
| POST | /api/agent-dashboard/agents | Yes | Register agent |
| GET | /api/agent-dashboard/agents/{agent_id} | Yes | Get agent detail |
| GET | /api/agent-dashboard/agents/{agent_id}/activity | Yes | Get agent activity |

---

## Tasks (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/tasks | Yes | List tasks |
| GET | /api/corrections/list | Yes | List corrections |
| GET | /api/corrections/patterns | Yes | Get correction patterns |
| GET | /api/corrections/statistics | Yes | Correction statistics |

---

## LLM / AI (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/llm/status | Yes | LLM provider status |
| GET | /api/llm/providers | Yes | Available providers |
| POST | /api/llm/configure | Yes | Configure LLM |
| POST | /api/llm/reload | Yes | Reload LLM |
| POST | /api/llm/test | Yes | Test LLM inference |
| POST | /api/chat | Yes | Chat completion |
| GET | /api/learning/status | Yes | Learning system status |
| POST | /api/learning/toggle | Yes | Toggle learning |

---

## Modules (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/modules | Yes | List loaded modules |
| GET | /api/modules/{name}/status | Yes | Get module status |

---

## Module Compiler (FastAPI — unified gateway from src/module_compiler/api/endpoints.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/module-compiler/compile | Yes | Compile a module from source path |
| POST | /api/module-compiler/compile-directory | Yes | Compile all modules in a directory |
| GET | /api/module-compiler/modules | Yes | List registered modules |
| GET | /api/module-compiler/modules/{module_id} | Yes | Get module specification |
| DELETE | /api/module-compiler/modules/{module_id} | Yes | Remove module from registry |
| GET | /api/module-compiler/capabilities | Yes | Search capabilities |
| GET | /api/module-compiler/capabilities/{capability_name} | Yes | Get capability detail |
| GET | /api/module-compiler/stats | Yes | Registry statistics |
| GET | /api/module-compiler/health | Yes | Module compiler health |

---

## Compute Plane (FastAPI — unified gateway from src/compute_plane/api/endpoints.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/compute-plane/health | Yes | Compute plane health |
| POST | /api/compute-plane/compute | Yes | Submit computation request |
| GET | /api/compute-plane/compute/{request_id} | Yes | Get computation result |
| GET | /api/compute-plane/compute/{request_id}/steps | Yes | Get derivation steps |
| POST | /api/compute-plane/compute/validate | Yes | Validate expression syntax |
| GET | /api/compute-plane/statistics | Yes | Compute service statistics |

---

## Gate Synthesis (FastAPI — unified gateway from src/gate_synthesis/api_server.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/gate-synthesis/health | Yes | Gate synthesis health |
| POST | /api/gate-synthesis/failure-modes/enumerate | Yes | Enumerate failure modes |
| POST | /api/gate-synthesis/murphy/estimate | Yes | Estimate Murphy probability |
| POST | /api/gate-synthesis/murphy/analyze-exposure | Yes | Analyze exposure signal |
| POST | /api/gate-synthesis/gates/generate | Yes | Generate gates for failure modes |
| POST | /api/gate-synthesis/gates/activate/{gate_id} | Yes | Activate a gate |
| POST | /api/gate-synthesis/gates/activate-all | Yes | Activate all proposed gates |
| POST | /api/gate-synthesis/gates/retire/{gate_id} | Yes | Retire a gate |
| POST | /api/gate-synthesis/gates/check-expiry | Yes | Check and retire expired gates |
| POST | /api/gate-synthesis/gates/update-retirement-conditions | Yes | Update retirement conditions |
| GET | /api/gate-synthesis/gates/list | Yes | List all gates |
| GET | /api/gate-synthesis/gates/active | Yes | Get active gates |
| GET | /api/gate-synthesis/gates/by-target/{target} | Yes | Get gates by target |
| GET | /api/gate-synthesis/gates/{gate_id} | Yes | Get specific gate |
| GET | /api/gate-synthesis/statistics | Yes | Gate statistics |
| GET | /api/gate-synthesis/logs/activation | Yes | Activation log |
| GET | /api/gate-synthesis/logs/retirement | Yes | Retirement log |
| POST | /api/gate-synthesis/artifacts/add | Yes | Add artifact to graph |
| POST | /api/gate-synthesis/reset | Yes | Reset state (for testing) |

---

## Cost Optimization Advisor — COA-001 (FastAPI — unified gateway from src/cost_optimization_advisor.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/coa/health | Yes | COA health check |
| POST | /api/coa/resources | Yes | Register a cloud resource |
| GET | /api/coa/resources | Yes | List cloud resources |
| GET | /api/coa/resources/{resource_id} | Yes | Get resource |
| PUT | /api/coa/resources/{resource_id} | Yes | Update resource |
| DELETE | /api/coa/resources/{resource_id} | Yes | Delete resource |
| POST | /api/coa/spend | Yes | Record spend |
| GET | /api/coa/spend | Yes | Get spend records |
| POST | /api/coa/analyze/{resource_id} | Yes | Analyze rightsizing |
| POST | /api/coa/spot/scan | Yes | Scan spot opportunities |
| GET | /api/coa/recommendations | Yes | Get recommendations |
| PUT | /api/coa/recommendations/{rec_id}/status | Yes | Update recommendation status |
| POST | /api/coa/budgets | Yes | Set budget |
| GET | /api/coa/budgets/check | Yes | Check budget alerts |
| GET | /api/coa/summary | Yes | Cost summary |
| POST | /api/coa/export | Yes | Export COA state |

---

## Compliance as Code Engine — CCE-001 (FastAPI — unified gateway from src/compliance_as_code_engine.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/cce/health | Yes | CCE health check |
| POST | /api/cce/rules | Yes | Create compliance rule |
| GET | /api/cce/rules | Yes | List rules |
| GET | /api/cce/rules/{rule_id} | Yes | Get rule |
| PUT | /api/cce/rules/{rule_id} | Yes | Update rule |
| DELETE | /api/cce/rules/{rule_id} | Yes | Delete rule |
| POST | /api/cce/check/{rule_id} | Yes | Check a rule |
| POST | /api/cce/scan | Yes | Run compliance scan |
| GET | /api/cce/scans | Yes | List scans |
| GET | /api/cce/scans/{scan_id} | Yes | Get scan |
| GET | /api/cce/scans/{scan_id}/report | Yes | Generate scan report |
| POST | /api/cce/remediations | Yes | Create remediation |
| GET | /api/cce/remediations | Yes | List remediations |
| POST | /api/cce/remediations/{remediation_id}/complete | Yes | Complete remediation |
| GET | /api/cce/summary | Yes | Compliance summary |
| POST | /api/cce/export | Yes | Export CCE state |

---

## Blockchain Audit Trail — BAT-001 (FastAPI — unified gateway from src/blockchain_audit_trail.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/bat/health | Yes | BAT health check |
| POST | /api/bat/entries | Yes | Record audit entry |
| GET | /api/bat/entries/search | Yes | Search entries |
| GET | /api/bat/blocks | Yes | List blocks |
| GET | /api/bat/blocks/{block_id} | Yes | Get block by ID |
| GET | /api/bat/blocks/index/{idx} | Yes | Get block by index |
| POST | /api/bat/blocks/seal | Yes | Seal current block |
| GET | /api/bat/verify | Yes | Verify chain integrity |
| GET | /api/bat/export | Yes | Export full chain |
| GET | /api/bat/stats | Yes | Blockchain statistics |

---

## Matrix Bridge (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/matrix/status | Yes | Matrix bridge connection status |
| GET | /api/matrix/rooms | Yes | List joined rooms |
| POST | /api/matrix/send | Yes | Send Matrix message |
| GET | /api/matrix/stats | Yes | Bridge statistics |

---

## Production (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/production/queue | Yes | Production queue |
| POST | /api/production/proposals | Yes | Submit proposal |
| GET | /api/production/proposals | Yes | List proposals |
| GET | /api/production/proposals/{proposal_id} | Yes | Get proposal |
| POST | /api/production/work-orders | Yes | Create work order |
| POST | /api/production/route | Yes | Route production task |
| GET | /api/production/schedule | Yes | Production schedule |
| GET | /api/production/hitl/pending | Yes | Pending HITL reviews |
| POST | /api/production/hitl/submit | Yes | Submit HITL decision |
| GET | /api/production/hitl/learned | Yes | HITL learned patterns |
| POST | /api/production/hitl/{review_id}/respond | Yes | Respond to HITL review |

---

## Deliverables (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/deliverables | Yes | List deliverables |

---

## HITL (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/hitl/interventions/pending | Yes | Pending HITL interventions |
| POST | /api/hitl/interventions/{id}/respond | Yes | Respond to intervention |
| POST | /api/hitl/qc/submit | Yes | Submit QC review |
| POST | /api/hitl/acceptance/submit | Yes | Submit acceptance |
| POST | /api/hitl/{id}/decide | Yes | Decide on HITL item |

---

## Compliance Dashboard (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/compliance/toggles | Yes | Get compliance toggles |
| POST | /api/compliance/toggles | Yes | Update compliance toggle |
| GET | /api/compliance/recommended | Yes | Recommended compliance controls |
| GET | /api/compliance/report | Yes | Compliance report |
| POST | /api/compliance/scan | Yes | Run compliance scan |

---

## Documents (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/documents/list | Yes | List documents |
| GET | /api/documents/{doc_id} | Yes | Get document |

---

## Credentials (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/credentials/list | Yes | List credentials |

---

## Onboarding (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/onboarding/wizard/questions | Yes | Get onboarding questions |
| POST | /api/onboarding/wizard/answer | Yes | Submit answer |
| GET | /api/onboarding/wizard/summary | Yes | Onboarding summary |
| GET | /api/onboarding/wizard/profile | Yes | Generated profile |
| GET | /api/onboarding/wizard/config | Yes | Wizard config |
| POST | /api/onboarding/wizard/validate | Yes | Validate answers |
| POST | /api/onboarding/wizard/generate-config | Yes | Generate configuration |
| POST | /api/onboarding/wizard/reset | Yes | Reset onboarding |
| GET | /api/onboarding/status | Yes | Onboarding status |
| GET | /api/onboarding/employees | Yes | List employees |
| POST | /api/onboarding/employees | Yes | Add employee |
| GET | /api/onboarding/employees/{profile_id} | Yes | Get employee |
| POST | /api/onboarding/employees/{profile_id}/tasks/{task_id}/complete | Yes | Complete task |
| POST | /api/onboarding/employees/{profile_id}/tasks/{task_id}/skip | Yes | Skip task |
| POST | /api/onboarding-flow/start | Yes | Start onboarding flow |
| GET | /api/onboarding-flow/status | Yes | Flow status |
| GET | /api/onboarding-flow/sessions/{session_id}/questions | Yes | Flow questions |
| POST | /api/onboarding-flow/sessions/{session_id}/answer | Yes | Submit flow answer |
| POST | /api/onboarding-flow/sessions/{session_id}/transition | Yes | Transition flow |
| POST | /api/onboarding-flow/sessions/{session_id}/shadow-agent | Yes | Activate shadow agent |
| GET | /api/onboarding-flow/org/chart | Yes | Org chart |
| GET | /api/onboarding-flow/org/positions | Yes | Org positions |
| POST | /api/onboarding-flow/org/initialize | Yes | Initialize org |

---

## Org Chart (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/orgchart/live | Yes | Live org chart |
| POST | /api/orgchart/save | Yes | Save org chart |
| GET | /api/orgchart/{task_id} | Yes | Get org chart by task |
| GET | /api/org/info | Yes | Organisation info |
| POST | /api/org/join | Yes | Join organisation |
| POST | /api/org/invite | Yes | Invite to organisation |

---

## Integrations (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/integrations | Yes | List integrations |
| GET | /api/integrations/{status} | Yes | List integrations by status |
| GET | /api/universal-integrations/categories | Yes | Integration categories |
| GET | /api/universal-integrations/services | Yes | Available services |
| POST | /api/universal-integrations/register | Yes | Register integration |
| GET | /api/universal-integrations/services/{service_id} | Yes | Get service |
| POST | /api/universal-integrations/services/{service_id}/configure | Yes | Configure service |
| POST | /api/universal-integrations/services/{service_id}/execute/{action_name} | Yes | Execute integration action |
| GET | /api/universal-integrations/stats | Yes | Integration statistics |

---

## Librarian (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/librarian/commands | Yes | Get command catalog (160+ commands) |
| POST | /api/librarian/ask | Yes | Ask the librarian |
| GET | /api/librarian/status | Yes | Librarian status |
| GET | /api/librarian/api-links | Yes | API link map |
| POST | /api/librarian/integrations | Yes | Integration help |

---

## Billing / Account (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/billing/tiers | Yes | Billing tiers |
| POST | /api/billing/check-feature | Yes | Check feature access |
| POST | /api/billing/check-limit | Yes | Check usage limit |
| GET | /api/billing/account/{account_id} | Yes | Get account billing |
| GET | /api/account/profile | Yes | Account profile |
| PUT | /api/account/profile | Yes | Update account profile |
| GET | /api/account/subscription | Yes | Subscription details |
| POST | /api/account/subscription/cancel | Yes | Cancel subscription |
| GET | /api/account/statements | Yes | Billing statements |
| GET | /api/account/flow | Yes | Account flow state |

---

## Wallet (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/wallet/balances | Yes | Wallet balances |
| GET | /api/wallet/transactions | Yes | Transaction history |
| GET | /api/wallet/addresses | Yes | Wallet addresses |
| POST | /api/wallet/send | Yes | Send transaction |
| POST | /api/wallet/receive | Yes | Generate receive address |

---

## Analytics (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/heatmap/data | Yes | Activity heatmap data |
| GET | /api/causality/graph | Yes | Causality dependency graph |
| GET | /api/causality/analysis | Yes | Causality analysis |
| GET | /api/wingman/status | Yes | Wingman co-pilot status |
| GET | /api/wingman/suggestions | Yes | Wingman suggestions |

---

## Ambient Intelligence (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/ambient/context | Yes | Submit context |
| POST | /api/ambient/insights | Yes | Generate insights |
| POST | /api/ambient/deliver | Yes | Deliver ambient output |
| POST | /api/ambient/royalty | Yes | Royalty action |
| GET | /api/ambient/settings | Yes | Ambient settings |
| POST | /api/ambient/settings | Yes | Update ambient settings |

---

## Meeting Intelligence (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/meeting-intelligence/drafts | Yes | Create meeting draft |
| POST | /api/meeting-intelligence/vote | Yes | Vote on draft |
| POST | /api/meeting-intelligence/email-report | Yes | Email meeting report |
| GET | /api/meeting-intelligence/sessions | Yes | List sessions |

---

## Community (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/community/channels | Yes | List channels |
| POST | /api/community/channels | Yes | Create channel |
| GET | /api/community/channels/{cid}/messages | Yes | Get messages |
| POST | /api/community/channels/{cid}/messages | Yes | Post message |
| GET | /api/community/channels/{cid}/members | Yes | List members |
| POST | /api/community/channels/{cid}/messages/{mid}/reactions | Yes | Add reaction |

---

## Reviews (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/reviews/submit | Yes | Submit review |
| GET | /api/reviews | Yes | List reviews |
| POST | /api/reviews/{rid}/moderate | Yes | Moderate review |

---

## Partner (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/partner/request | Yes | Submit partner request |
| GET | /api/partner/status/{pid} | Yes | Get partner request status |
| POST | /api/partner/review/{pid} | Yes | Review partner request |

---

## Referrals (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/referrals/create | Yes | Create referral |
| POST | /api/referrals/redeem | Yes | Redeem referral |

---

## Domains & Email (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/domains | Yes | List domains |
| POST | /api/domains/register | Yes | Register domain |
| POST | /api/domains/{id}/verify | Yes | Verify domain |
| GET | /api/email/accounts | Yes | List email accounts |
| POST | /api/email/accounts | Yes | Add email account |
| POST | /api/email/send | Yes | Send email |
| GET | /api/email/config | Yes | Email configuration |

---

## IP / Supply / Events (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/ip/assets | Yes | IP assets |
| POST | /api/ip/assets | Yes | Create IP asset |
| POST | /api/ip/assets/{asset_id}/access-check | Yes | Check access |
| GET | /api/ip/summary | Yes | IP summary |
| GET | /api/ip/trade-secrets | Yes | Trade secrets |
| GET | /api/supply/status | Yes | Supply chain status |
| POST | /api/events/subscribe | Yes | Subscribe to events |
| GET | /api/events/stream/{id} | Yes | SSE event stream |
| GET | /api/events/history/{id} | Yes | Event history |
| GET | /api/security/events | Yes | Security events |

---

## MFGC — Murphy Flow Gate Controller (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/mfgc/state | Yes | MFGC state |
| GET | /api/mfgc/gates | Yes | Active gates |
| GET | /api/mfgc/config | Yes | MFGC configuration |
| POST | /api/mfgc/config | Yes | Update MFGC config |
| POST | /api/mfgc/setup/{profile} | Yes | Setup MFGC profile |

---

## MFM — Murphy Flow Monitor (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/mfm/status | Yes | MFM status |
| GET | /api/mfm/metrics | Yes | MFM metrics |
| GET | /api/mfm/versions | Yes | Model versions |
| GET | /api/mfm/traces/stats | Yes | Trace statistics |
| POST | /api/mfm/promote | Yes | Promote model version |
| POST | /api/mfm/retrain | Yes | Trigger retraining |
| POST | /api/mfm/rollback | Yes | Rollback model version |

---

## MSS — Murphy Scoring System (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/mss/score | Yes | Score content |
| POST | /api/mss/simplify | Yes | Simplify content |
| POST | /api/mss/solidify | Yes | Solidify content |
| POST | /api/mss/magnify | Yes | Magnify content |

---

## UCP — Universal Control Plane (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/ucp/health | Yes | UCP health |
| POST | /api/ucp/execute | Yes | Execute UCP command |

---

## Automation (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/automation/review-response | Yes | Automate review response |
| POST | /api/automation/{engine_name}/{action} | Yes | Run automation action |

---

## Stub Endpoints (FastAPI — src/runtime/app.py, 501 Not Implemented)

These endpoints return `501 Not Implemented` and will be fully implemented in future iterations.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/analyze-domain | Yes | Domain analysis (stub) |

---

## Frontend Architecture

### API Clients
- **Vanilla JS (HTML pages):** Use `MurphyAPI` class from `static/murphy-components.js`
- **TypeScript (React/Vite):** Use `get/post/put/del` from `web/src/api/murphyClient.ts`
- **Both include:** retry logic, circuit breaker, X-API-Key auth, standard envelope parsing

### Auth Script
- All HTML pages include `<script src="murphy_auth.js"></script>` after `murphy-components.js`
- Auth checks `/api/profiles/me` on load; redirects to `/ui/landing` if not authenticated

### WebSocket
- Use `MurphyWebSocket` from `static/murphy-components.js` for real-time connections
- Auto-reconnects with exponential backoff (3s → 30s)

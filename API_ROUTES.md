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
| POST | /api/auth/signup | No | Create new account — returns `{ session_token, account_id, … }` + sets `murphy_session` cookie |
| POST | ~~/api/auth/register~~ *(removed)* | No | Create new account (alias for signup) |
| POST | /api/auth/login | No | Validate credentials — returns `{ session_token, account_id, … }` + sets `murphy_session` cookie |
| POST | /api/auth/logout | No | Invalidate session and clear `murphy_session` cookie |
| POST | /api/auth/forgot-password | No | Initiate password-reset flow — always returns success to prevent user enumeration |
| GET | /api/auth/session-token | Yes | Return active session token for the current user (used by `murphy_auth.js` after OAuth redirect to mirror HttpOnly cookie to localStorage) |
| GET | /api/auth/oauth/{provider} | No | Initiate OAuth flow |
| GET | /api/auth/callback | No | OAuth callback — sets `murphy_session` cookie and redirects to `/ui/terminal-unified?oauth_success=1&provider=<name>` |
| GET | ~~/api/auth/callback/{provider}~~ *(removed)* | No | Provider-specific OAuth callback |
| GET | /api/auth/login | No | Login page / initiate session |
| GET | /api/auth/providers | No | List configured OAuth providers and their enabled status |
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
| GET | ~~/api/profiles/me~~ *(removed)* | Yes | Get current user profile |
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
| GET | /api/llm/models/local | Yes | List downloaded Ollama models |
| POST | /api/llm/models/pull | Yes | Download a model via Ollama |
| POST | /api/llm/models/delete | Yes | Delete a downloaded Ollama model |
| POST | /api/llm/models/load | Yes | Set active Ollama model |
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
| POST | ~~/api/hitl/interventions/{id}/respond~~ *(removed)* | Yes | Respond to intervention |
| POST | /api/hitl/qc/submit | Yes | Submit QC review |
| POST | /api/hitl/acceptance/submit | Yes | Submit acceptance |
| POST | ~~/api/hitl/{id}/decide~~ *(removed)* | Yes | Decide on HITL item |

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
| POST | /api/librarian/query | Yes | Alias for /api/librarian/ask |
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

## Coinbase Advanced Trade (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/coinbase/status | Yes | Connection status, sandbox mode indicator |
| GET | /api/coinbase/accounts | Yes | List Coinbase brokerage accounts |
| GET | /api/coinbase/balances | Yes | Account balances per asset |
| GET | /api/coinbase/products | Yes | List available trading pairs |
| GET | /api/coinbase/ticker/{product_id} | Yes | Current best bid/ask for trading pair |

---

## Live Market Data Feed (FastAPI — src/runtime/app.py)

Providers: **Crypto** — Coinbase → Binance → CCXT | **Equity** — Yahoo Finance → Alpaca → Alpha Vantage → Polygon → IEX Cloud → IBKR

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/market/quote/{symbol} | Yes | Live quote for any symbol (crypto or equity) |
| GET | /api/market/candles/{symbol} | Yes | OHLCV candles — `?granularity=ONE_HOUR&limit=100` |
| GET | /api/market/movers | Yes | Top market movers — `?asset_class=all&limit=10` |
| GET | /api/market/search | Yes | Search instruments — `?q=bitcoin` |
| GET | /api/market/status | Yes | Live feed service status (shows all provider WS state) |
| GET | /api/market/instruments | Yes | List all known tradeable instruments |
| WebSocket | /ws/market/{symbol} | No | Live price stream — sends `{symbol, price, bid, ask, change_pct_24h, timestamp}` every 2 s |

---

## Trading Compliance (FastAPI — src/runtime/app.py)

Mandatory gate before live trading is permitted. All checks must pass.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/trading/compliance/status | Yes | Latest compliance evaluation result |
| POST | /api/trading/compliance/evaluate | Yes | Run full compliance check — body: `{jurisdiction, kyc_acknowledged, regulations_acknowledged, paper_trading_days, …}` |
| GET | /api/trading/compliance/graduation | Yes | Paper-trading graduation tracker summary + daily history |
| POST | /api/trading/compliance/graduation/record | Yes | Record a completed paper-trading day — body: `{date, start_equity, end_equity, trades}` |
## Paper Trading Engine (FastAPI — src/paper_trading_routes.py)

All trading is **PAPER/SIMULATED only** — no real money is moved.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | ~~/api/trading/paper/start~~ *(removed)* | Yes | Start paper trading session with selected strategies |
| POST | ~~/api/trading/paper/stop~~ *(removed)* | Yes | Stop paper trading session (optionally liquidate all positions) |
| GET | /api/trading/paper/status | Yes | Current session state: active flag, portfolio snapshot, available strategies |
| GET | ~~/api/trading/paper/positions~~ *(removed)* | Yes | All currently open paper positions with unrealized P&L |
| GET | ~~/api/trading/paper/trades~~ *(removed)* | Yes | Trade journal — paginated by `limit` and optional `strategy` filter |
| GET | ~~/api/trading/paper/performance~~ *(removed)* | Yes | Full performance metrics: Sharpe, Sortino, drawdown, win rate, profit factor, fees |
| GET | ~~/api/trading/paper/strategies~~ *(removed)* | Yes | List all 9 strategy templates with params and description |
| POST | ~~/api/trading/paper/trade~~ *(removed)* | Yes | Execute a manual paper buy or sell |
| POST | ~~/api/trading/backtest~~ *(removed)* | Yes | Run a historical backtest via yfinance or supplied OHLCV JSON |
| GET | ~~/api/trading/calibration/costs~~ *(removed)* | Yes | Hidden cost calibrator summary: observed slippage, fee, spread discrepancies |
| GET | ~~/api/trading/calibration/errors~~ *(removed)* | Yes | Error calibrator: per-strategy bias, MAE, RMSE, recalibration history |

### Strategy Templates (9 available)

| Name | Class | Algorithm |
|------|-------|-----------|
| `momentum` | `MomentumStrategy` | RSI + MACD crossover + volume confirmation |
| `mean_reversion` | `MeanReversionStrategy` | Bollinger Bands + Z-score mean reversion |
| `breakout` | `BreakoutStrategy` | Support/resistance levels + volume breakout confirmation |
| `scalping` | `ScalpingStrategy` | Short timeframe, tight stops, high-frequency entries |
| `dca` | `DCAStrategy` | Dollar Cost Average — time-based or price-dip accumulation |
| `grid` | `GridStrategy` | Grid levels: buy at lower levels, sell at upper levels |
| `trajectory` | `TrajectoryStrategy` | Parabolic move detection, projected peak exit, trailing stop |
| `sentiment` | `SentimentStrategy` | Fear/greed index + social signals — contrarian entries |
| `arbitrage` | `ArbitrageStrategy` | Cross-pair Z-score spread detection and mean reversion |

### Dashboard UI
- **Route:** `/ui/paper-trading` — `templates/paper_trading_dashboard.html`
- **Wallet widget:** `/ui/wallet` shows live engine status panel linking to the full dashboard

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

## Meetings (FastAPI — src/runtime/app.py)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/meetings/ | Yes | List all meeting sessions |
| POST | /api/meetings/start | Yes | Start a new meeting session — returns `{ session_id }` |
| POST | /api/meetings/{session_id}/end | Yes | End a meeting session |
| GET | /api/meetings/{session_id}/transcript | Yes | Get meeting transcript |
| GET | /api/meetings/{session_id}/suggestions | Yes | Get AI-powered suggestions for the meeting |

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
| GET | /api/reviews | No | List public reviews (displayed on landing/pricing pages without login) |
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
| POST | ~~/api/domains/{id}/verify~~ *(removed)* | Yes | Verify domain |
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
| GET | ~~/api/events/stream/{id}~~ *(removed)* | Yes | SSE event stream |
| GET | ~~/api/events/history/{id}~~ *(removed)* | Yes | Event history |
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

## Voice Command Interface — VCI (FastAPI — src/runtime/app.py)

Natural language voice/typed command processing for generative automation.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | ~~/api/vci/recognise~~ *(removed)* | Yes | Speech-to-text recognition |
| POST | ~~/api/vci/parse~~ *(removed)* | Yes | Parse command from transcript |
| POST | ~~/api/vci/process~~ *(removed)* | Yes | End-to-end voice processing (recognise → parse → result) |

**Process Endpoint Request:**
```json
{
  "text_input": "Monitor sales data and send weekly summary to Slack",
  "session_id": "optional-session-id"
}
```

**Response:**
```json
{
  "stt": { "transcript": "...", "confidence": 0.95 },
  "command": { "action": "create_automation", "category": "workflow", "params": {...} },
  "session_id": "vci-abc123"
}
```

### Related Documentation
- **[Generative Automation Presets](documentation/features/GENERATIVE_AUTOMATION_PRESETS.md)** — Complete guide to voice/typed command automation

---

## Generative Automation Presets (FastAPI — src/runtime/app.py)

Pre-configured automation patterns that wire together subsystems via natural language.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | ~~/api/presets~~ *(removed)* | Yes | List available automation presets |
| GET | ~~/api/presets/{preset_id}~~ *(removed)* | Yes | Get preset details |
| POST | ~~/api/presets/activate~~ *(removed)* | Yes | Activate preset via trigger phrase |
| POST | /api/workflows | Yes | Create workflow from natural language description |
| POST | /api/execute | Yes | Execute a generated workflow DAG |

**Activate Preset Request:**
```json
{
  "trigger_phrase": "run weekly sales report",
  "tenant_id": "tenant-123",
  "context": { "week_start": "2026-03-16" }
}
```

### Template-Based Workflow Generation

The system includes 12+ built-in templates:

| Template ID | Pattern | Description |
|-------------|---------|-------------|
| `etl_pipeline` | Extract-Transform-Load | Data pipeline automation |
| `ci_cd` | CI/CD Pipeline | Build, test, deploy automation |
| `incident_response` | Incident Handling | Alert triage and escalation |
| `monitoring_alert` | Metric Monitoring | Threshold-based alerting |
| `report_generation` | Report & Distribute | Scheduled report generation |
| `order_fulfillment` | E-commerce | Order processing and shipping |
| `invoice_processing` | AP Automation | Invoice approval and payment |

---

## Stub Endpoints (FastAPI — src/runtime/app.py, 501 Not Implemented)

These endpoints return `501 Not Implemented` and will be fully implemented in future iterations.

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/analyze-domain | Yes | Domain analysis (stub) |

---

## Communication Hub (FastAPI — src/comms_hub_routes.py)

> ⚠️ **Status: Planned — Not Yet Implemented.** The routes in this section are documented as part of the Communication Hub roadmap but are not currently present in `src/runtime/app.py`. They will be implemented in a future release.

Unified onboard communication system: IM, voice, video, email, automation rules, and a Discord-style moderator console.  All data is persisted to SQLite via the ORM models in `src/db.py`.

### Instant Messaging (IM)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | ~~/api/comms/im/threads~~ *(removed)* | Yes | Create a new IM thread (direct or group) |
| GET | ~~/api/comms/im/threads~~ *(removed)* | Yes | List all threads; filter by `?user=` |
| GET | ~~/api/comms/im/threads/{tid}~~ *(removed)* | Yes | Get a specific thread |
| POST | ~~/api/comms/im/threads/{tid}/messages~~ *(removed)* | Yes | Post a message to a thread — runs automod + automation rules |
| GET | ~~/api/comms/im/threads/{tid}/messages~~ *(removed)* | Yes | Get messages; filter with `?limit=` |
| POST | ~~/api/comms/im/threads/{tid}/messages/{mid}/reactions~~ *(removed)* | Yes | Add emoji reaction |

### Voice Calls

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | ~~/api/comms/voice/sessions~~ *(removed)* | Yes | Initiate a voice call (SDP offer optional) |
| GET | ~~/api/comms/voice/sessions~~ *(removed)* | Yes | List voice sessions; filter by `?user=` `?state=` |
| GET | ~~/api/comms/voice/sessions/{sid}~~ *(removed)* | Yes | Get voice session |
| POST | ~~/api/comms/voice/sessions/{sid}/answer~~ *(removed)* | Yes | Answer a call (SDP answer optional) |
| POST | ~~/api/comms/voice/sessions/{sid}/hold~~ *(removed)* | Yes | Put call on hold |
| POST | ~~/api/comms/voice/sessions/{sid}/end~~ *(removed)* | Yes | End call (optional `voicemail_url`) |
| POST | ~~/api/comms/voice/sessions/{sid}/reject~~ *(removed)* | Yes | Reject an incoming call |
| POST | ~~/api/comms/voice/sessions/{sid}/ice~~ *(removed)* | Yes | Submit an ICE candidate |

### Video Calls

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | ~~/api/comms/video/sessions~~ *(removed)* | Yes | Initiate a video call |
| GET | ~~/api/comms/video/sessions~~ *(removed)* | Yes | List video sessions |
| GET | ~~/api/comms/video/sessions/{sid}~~ *(removed)* | Yes | Get video session |
| POST | ~~/api/comms/video/sessions/{sid}/answer~~ *(removed)* | Yes | Answer a video call |
| POST | ~~/api/comms/video/sessions/{sid}/end~~ *(removed)* | Yes | End a video call |
| POST | ~~/api/comms/video/sessions/{sid}/ice~~ *(removed)* | Yes | Submit an ICE candidate |

### Email

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | ~~/api/comms/email/send~~ *(removed)* | Yes | Compose and send an email |
| GET | ~~/api/comms/email/inbox~~ *(removed)* | Yes | Get user's inbox — `?user=` |
| GET | ~~/api/comms/email/outbox~~ *(removed)* | Yes | Get user's outbox — `?user=` |
| GET | ~~/api/comms/email/{eid}~~ *(removed)* | Yes | Get a specific email |
| POST | ~~/api/comms/email/{eid}/read~~ *(removed)* | Yes | Mark email as read — body `{user}` |

### Automation Rules

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/comms/automate/rules | Yes | Create an automation rule |
| GET | /api/comms/automate/rules | Yes | List rules; filter by `?channel=` |
| GET | ~~/api/comms/automate/rules/{rid}~~ *(removed)* | Yes | Get a specific rule |
| PATCH | ~~/api/comms/automate/rules/{rid}/toggle~~ *(removed)* | Yes | Enable / disable a rule |
| DELETE | ~~/api/comms/automate/rules/{rid}~~ *(removed)* | Yes | Delete a rule |
| POST | ~~/api/comms/automate/evaluate~~ *(removed)* | Yes | Evaluate rules against a payload — returns matched rules |

### Moderator Console

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | ~~/api/moderator/users~~ *(removed)* | Yes | List all moderated users |
| POST | ~~/api/moderator/users/{user}/role~~ *(removed)* | Yes | Set user role (admin / moderator / member) |
| POST | ~~/api/moderator/users/{user}/warn~~ *(removed)* | Yes | Issue a warning |
| POST | ~~/api/moderator/users/{user}/mute~~ *(removed)* | Yes | Mute a user |
| POST | ~~/api/moderator/users/{user}/unmute~~ *(removed)* | Yes | Unmute a user |
| POST | ~~/api/moderator/users/{user}/kick~~ *(removed)* | Yes | Kick a user |
| POST | ~~/api/moderator/users/{user}/ban~~ *(removed)* | Yes | Ban a user |
| POST | ~~/api/moderator/users/{user}/unban~~ *(removed)* | Yes | Unban a user |
| DELETE | ~~/api/moderator/messages/{channel}/{mid}~~ *(removed)* | Yes | Delete a message |
| GET | ~~/api/moderator/automod/words~~ *(removed)* | Yes | List default and custom blocked words |
| POST | ~~/api/moderator/automod/words~~ *(removed)* | Yes | Add custom blocked words |
| DELETE | ~~/api/moderator/automod/words/{word}~~ *(removed)* | Yes | Remove a blocked word |
| POST | ~~/api/moderator/automod/check~~ *(removed)* | Yes | Check content against automod rules |
| GET | ~~/api/moderator/broadcast/targets~~ *(removed)* | Yes | List registered broadcast targets |
| POST | ~~/api/moderator/broadcast/targets~~ *(removed)* | Yes | Register a broadcast target |
| DELETE | ~~/api/moderator/broadcast/targets/{platform}/{channel_id}~~ *(removed)* | Yes | Unregister a target |
| POST | ~~/api/moderator/broadcast~~ *(removed)* | Yes | Broadcast to multiple platforms simultaneously |
| GET | ~~/api/moderator/broadcast/history~~ *(removed)* | Yes | Broadcast history |
| GET | ~~/api/moderator/audit~~ *(removed)* | Yes | Moderator audit log |

**UI Route:** `/ui/comms-hub` → `communication_hub.html`

---

## System Update Recommendation Engine (FastAPI — src/system_update_api.py)

Founder-level orchestrator (ARCH-020) exposing the `SystemUpdateRecommendationEngine` with five recommendation domains: maintenance, SDK updates, auto-updates, bug report auto-responses, and system operations analysis.

### Status & Recommendations

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | ~~/api/system-updates/status~~ *(removed)* | Yes | Current engine status and summary |
| GET | ~~/api/system-updates/recommendations~~ *(removed)* | Yes | List all recommendations; filter with `?category=` `?priority=` `?status=` |
| GET | ~~/api/system-updates/recommendations/{rec_id}~~ *(removed)* | Yes | Get a specific recommendation by ID |
| PUT | ~~/api/system-updates/recommendations/{rec_id}/status~~ *(removed)* | Yes | Approve or dismiss a recommendation — body: `{"action": "approve"|"dismiss", "reason": "…", "approved_by": "…"}` |

### Maintenance Domain

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | ~~/api/system-updates/maintenance/scan~~ *(removed)* | Yes | Trigger a maintenance integration scan |
| GET | ~~/api/system-updates/maintenance/recommendations~~ *(removed)* | Yes | Get maintenance-specific recommendations; filter with `?priority=` `?status=` |

### SDK Update Domain

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | ~~/api/system-updates/sdk/scan~~ *(removed)* | Yes | Trigger an SDK/dependency update scan |
| GET | ~~/api/system-updates/sdk/recommendations~~ *(removed)* | Yes | Get SDK update recommendations; filter with `?priority=` `?status=` |

### Auto-Update Domain

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | ~~/api/system-updates/auto-update/scan~~ *(removed)* | Yes | Trigger an auto-update assessment |
| GET | ~~/api/system-updates/auto-update/recommendations~~ *(removed)* | Yes | Get auto-update recommendations; filter with `?priority=` `?status=` |

### Bug Report Auto-Response Domain

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | ~~/api/system-updates/bug-responses/ingest~~ *(removed)* | Yes | Ingest a bug report for automated triage — body: `{title, description, component, severity, stack_trace, reporter}` |
| GET | ~~/api/system-updates/bug-responses/recommendations~~ *(removed)* | Yes | Get bug response recommendations; filter with `?priority=` `?status=` |

### System Operations Domain

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | ~~/api/system-updates/operations/analyze~~ *(removed)* | Yes | Trigger a system operations analysis |
| GET | ~~/api/system-updates/operations/recommendations~~ *(removed)* | Yes | Get operations recommendations; filter with `?priority=` `?status=` |

### Full Scan

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | ~~/api/system-updates/full-scan~~ *(removed)* | Yes | Trigger a full scan across all 5 domains simultaneously |

**Valid filter values:**
- `category`: `maintenance`, `sdk_update`, `auto_update`, `bug_response`, `operations`
- `priority`: `critical`, `high`, `medium`, `low`, `informational`
- `status`: `pending`, `approved`, `dismissed`, `executed`

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

### UI Navigation (MurphySidebar + Command Palette)

The sidebar and Ctrl+K command palette are defined in `static/murphy-components.js`.
All links below are accessible after login. Section dividers group related pages.

| Section | Label | Path | Notes |
|---------|-------|------|-------|
| SETUP | 🚀 ONBOARDING | `/ui/onboarding` | **First-run setup wizard — start here after login** |
| SETUP | 🔍 VISUALIZER | `/ui/system-visualizer` | System topology visualizer |
| TERMINAL | ⬡ ORCHESTRATOR | `/ui/terminal-orchestrator` | Task orchestration dashboard |
| TERMINAL | ✦ ORG CHART | `/ui/terminal-orgchart` | Organisation structure |
| TERMINAL | ⬢ INTEGRATIONS | `/ui/terminal-integrations` | LLM & service integrations setup |
| TERMINAL | ◈ ARCHITECT | `/ui/terminal-architect` | Build / MSS / gates terminal |
| TERMINAL | ◎ WORKER | `/ui/terminal-worker` | Worker execution terminal |
| TERMINAL | ⊞ COSTS | `/ui/terminal-costs` | Cost tracking terminal |
| BUILD | ⋮ WORKFLOWS | `/ui/workflow-canvas` | Visual workflow builder |
| BUILD | 🏭 PRODUCTION | `/ui/production-wizard` | Proposals, work orders, deliverables |
| FINANCE | 📈 TRADING | `/ui/trading` | Live trading dashboard |
| FINANCE | 🛡 RISK | `/ui/risk-dashboard` | Risk management |
| FINANCE | 📝 PAPER TRADE | `/ui/paper-trading` | Paper trading engine |
| FINANCE | 🎯 GRANTS | `/ui/grant-wizard` | Grant discovery wizard |
| FINANCE | 📊 GRANT DASH | `/ui/grant-dashboard` | Grant portfolio dashboard |
| FINANCE | 💼 FINANCING | `/ui/financing` | Financing options explorer |
| FINANCE | 💰 WALLET | `/ui/wallet` | Wallet & assets |
| OPS | ☑ COMPLIANCE | `/ui/compliance` | Compliance dashboard |
| OPS | 📅 CALENDAR | `/ui/calendar` | Calendar |
| OPS | 🧠 MEETINGS | `/ui/meeting-intelligence` | Meeting intelligence |
| OPS | ⚡ AMBIENT | `/ui/ambient` | Ambient intelligence |
| OPS | 📋 MANAGEMENT | `/ui/management` | Management dashboard |
| COMMUNITY | 💬 WORKSPACE | `/ui/workspace` | Workspace |
| COMMUNITY | 🏘 COMMUNITY | `/ui/community` | Community forum |
| COMMUNITY | ✉ COMMS HUB | `/ui/comms-hub` | Communications hub |
| ACCOUNT | 🏢 ORG PORTAL | `/ui/org-portal` | Organisation self-service portal |
| ACCOUNT | 📚 DOCS | `/ui/docs` | Documentation |
| ACCOUNT | ⚙ ADMIN | `/ui/admin` | Admin panel (admin/owner only) |

---

## Auto-Generated Route Index (Phase 4)

The following routes exist in `src/runtime/app.py` and were cataloged as missing from API_ROUTES.md in gap analysis items API-001 through API-043. They are documented here for completeness.

### Admin Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/admin/users | Yes | List all users |
| POST | /api/admin/users | Yes | Create a user |
| GET | /api/admin/users/{user_id} | Yes | Get user details |
| PATCH | /api/admin/users/{user_id} | Yes | Update user |
| DELETE | /api/admin/users/{user_id} | Yes | Delete user |
| POST | /api/admin/users/{user_id}/reset-password | Yes | Reset user password |
| POST | /api/admin/users/{user_id}/suspend | Yes | Suspend user |
| POST | /api/admin/users/{user_id}/unsuspend | Yes | Unsuspend user |
| GET | /api/admin/organizations | Yes | List organizations |
| POST | /api/admin/organizations | Yes | Create organization |
| GET | /api/admin/organizations/{org_id} | Yes | Get organization |
| PATCH | /api/admin/organizations/{org_id} | Yes | Update organization |
| DELETE | /api/admin/organizations/{org_id} | Yes | Delete organization |
| GET | /api/admin/organizations/{org_id}/members | Yes | List org members |
| POST | /api/admin/organizations/{org_id}/members | Yes | Add org member |
| DELETE | /api/admin/organizations/{org_id}/members/{user_id} | Yes | Remove org member |
| GET | /api/admin/stats | Yes | System statistics |
| GET | /api/admin/sessions | Yes | List active sessions |
| DELETE | /api/admin/sessions/{account_id} | Yes | Revoke session |
| GET | /api/admin/audit-log | Yes | Admin audit log |

### Auth Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/auth/role | No | Get current user role |
| GET | /api/auth/permissions | No | Get current user permissions |

### Onboarding Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/onboarding/wizard/questions | No | Get onboarding questions |
| POST | /api/onboarding/wizard/answer | No | Submit onboarding answer |
| GET | /api/onboarding/wizard/profile | No | Get generated profile |
| POST | /api/onboarding/wizard/validate | No | Validate onboarding data |
| POST | /api/onboarding/wizard/generate-config | No | Generate system config |
| GET | /api/onboarding/wizard/config | No | Get wizard config |
| GET | /api/onboarding/wizard/summary | No | Get wizard summary |
| POST | /api/onboarding/wizard/reset | No | Reset wizard state |
| POST | /api/onboarding/mfgc-chat | No | MFGC chat endpoint |
| POST | /api/onboarding/finalize | No | Finalize onboarding |
| POST | /api/onboarding/employees | Yes | Create employee profile |
| GET | /api/onboarding/employees | Yes | List employee profiles |
| GET | /api/onboarding/employees/{profile_id} | Yes | Get employee profile |
| POST | /api/onboarding/employees/{profile_id}/tasks/{task_id}/complete | Yes | Complete onboarding task |
| POST | /api/onboarding/employees/{profile_id}/tasks/{task_id}/skip | Yes | Skip onboarding task |
| GET | /api/onboarding/status | Yes | Get onboarding status |

### Workflow Terminal Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/workflow-terminal/sessions | Yes | Create terminal session |
| POST | /api/workflow-terminal/sessions/{session_id}/message | Yes | Send message to session |
| GET | /api/workflow-terminal/sessions/{session_id} | Yes | Get session state |
| GET | /api/workflow-terminal/sessions/{session_id}/compile | Yes | Compile session workflow |
| GET | /api/workflow-terminal/sessions/{session_id}/agents/{agent_id} | Yes | Get agent in session |
| GET | /api/workflow-terminal/sessions | Yes | List sessions |
| GET | /api/workflow-terminal/list | Yes | List saved workflows |
| POST | /api/workflow-terminal/save | Yes | Save workflow |
| GET | /api/workflow-terminal/load | Yes | Load workflow |
| POST | /api/workflow-terminal/execute | Yes | Execute workflow |

### Swarm Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/swarm/status | Yes | Swarm status |
| POST | /api/swarm/propose | Yes | Propose swarm task |
| POST | /api/swarm/execute | Yes | Execute swarm task |
| POST | /api/swarm/phase | Yes | Execute swarm phase |
| GET | /api/swarm/rosetta | Yes | Rosetta translation map |

### HITL & Corrections Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/hitl/interventions/pending | Yes | List pending interventions |
| POST | /api/hitl/interventions/{intervention_id}/respond | Yes | Respond to intervention |
| GET | /api/hitl/statistics | Yes | HITL statistics |
| GET | /api/corrections/patterns | Yes | Correction patterns |
| GET | /api/corrections/statistics | Yes | Correction statistics |
| GET | /api/corrections/training-data | Yes | Training data export |

### Cost & Efficiency Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/costs/summary | Yes | Cost summary |
| GET | /api/costs/by-department | Yes | Costs by department |
| GET | /api/costs/by-project | Yes | Costs by project |
| GET | /api/costs/by-bot | Yes | Costs by bot |
| POST | /api/costs/assign | Yes | Assign cost |
| PATCH | /api/costs/budget | Yes | Update budget |
| GET | /api/efficiency/costs | Yes | Efficiency cost analysis |
| GET | /api/usage/daily | Yes | Daily usage metrics |

### Self-Fix & Repair Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/self-fix/status | Yes | Self-fix status |
| POST | /api/self-fix/run | Yes | Trigger self-fix |
| GET | /api/self-fix/history | Yes | Self-fix history |
| GET | /api/self-fix/plans | Yes | Self-fix plans |
| GET | /api/repair/status | Yes | Repair status |
| POST | /api/repair/run | Yes | Trigger repair |
| GET | /api/repair/history | Yes | Repair history |
| GET | /api/repair/wiring | Yes | Repair wiring map |
| GET | /api/repair/proposals | Yes | Repair proposals |

### Scheduler & Automation Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/scheduler/status | Yes | Scheduler status |
| POST | /api/scheduler/start | Yes | Start scheduler |
| POST | /api/scheduler/stop | Yes | Stop scheduler |
| POST | /api/scheduler/trigger | Yes | Trigger scheduled job |
| GET | /api/self-automation/status | Yes | Self-automation status |
| POST | /api/self-automation/task | Yes | Submit automation task |
| GET | /api/self-automation/tasks | Yes | List automation tasks |
| GET | /api/self-improvement/status | Yes | Self-improvement status |
| GET | /api/self-improvement/proposals | Yes | Self-improvement proposals |
| GET | /api/self-improvement/corrections | Yes | Self-improvement corrections |

### Wingman & Heatmap Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/wingman/status | Yes | Wingman status |
| GET | /api/wingman/suggestions | Yes | Wingman suggestions |
| POST | /api/wingman/validate | Yes | Validate with wingman |
| GET | /api/wingman/api-gaps | Yes | API gap list |
| POST | /api/wingman/api-gaps/scan | Yes | Scan for API gaps |
| POST | /api/wingman/api-gaps/build | Yes | Build missing APIs |
| GET | /api/heatmap/data | Yes | Heatmap data |
| GET | /api/heatmap/coverage | Yes | Coverage heatmap |

### Org, Events & Other Routes

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/org/info | Yes | Organization info |
| POST | /api/org/join | Yes | Join organization |
| POST | /api/org/invite | Yes | Invite to organization |
| POST | /api/org/create | Yes | Create organization |
| GET | /api/org/portal/{org_id} | Yes | Org portal |
| GET | /api/org/portal/{org_id}/members | Yes | Org portal members |
| POST | /api/org/portal/{org_id}/members/invite | Yes | Invite org portal member |
| DELETE | /api/org/portal/{org_id}/members/{user_id} | Yes | Remove org portal member |
| PATCH | /api/org/portal/{org_id}/members/{user_id}/role | Yes | Update member role |
| GET | /api/org/portal/{org_id}/channels | Yes | Org channels |
| POST | /api/events/subscribe | Yes | Subscribe to events |
| GET | /api/events/history/{subscriber_id} | Yes | Event history |
| GET | /api/events/stream/{subscriber_id} | Yes | SSE event stream |
| GET | /api/golden-path | Yes | Golden path workflows |
| GET | /api/golden-path/{workflow_id} | Yes | Specific golden path |
| POST | /api/feedback | Yes | Submit feedback |
| POST | /api/images/generate | Yes | Generate image |
| GET | /api/images/styles | Yes | Available image styles |
| GET | /api/images/stats | Yes | Image generation stats |
| GET | /api/platform/automation-status | Yes | Platform automation status |
| GET | /api/platform/capabilities | Yes | Platform capabilities |
| GET | /api/sdk/status | Yes | SDK status |
| GET | /api/creator/moderation/status | Yes | Moderation status |
| POST | /api/creator/moderation/check | Yes | Run content moderation check |
| POST | /api/client-portfolio/save | Yes | Save client portfolio |
| GET | /api/client-portfolio/{client_id} | Yes | Get client portfolio |
| PUT | /api/client-portfolio/{client_id}/selections | Yes | Update portfolio selections |
| GET | /api/legal/terms | No | Terms of service |
| GET | /api/legal/privacy | No | Privacy policy |
| POST | /api/auar/provision | Yes | Provision AUAR resource |
| GET | /api/manifest | No | System manifest |


---

## Recently Added Routes (not in previous table)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/ambient/stats | Yes | |
| GET | /api/artifacts | Yes | |
| POST | /api/artifacts/create | Yes | |
| GET | /api/artifacts/{artifact_id} | Yes | |
| POST | /api/auth/change-password | Yes | |
| POST | /api/auth/request-password-reset | Yes | |
| POST | /api/auth/reset-password | Yes | |
| GET | /api/auth/reset-password/validate | Yes | |
| POST | /api/automations/commission | Yes | |
| GET | /api/automations/executions | Yes | |
| GET | /api/automations/executions/{execution_id} | Yes | |
| POST | /api/automations/fire-trigger | Yes | |
| GET | /api/automations/workflows/{workflow_id} | Yes | |
| POST | /api/automations/workflows/{workflow_id}/execute | Yes | |
| POST | /api/billing/checkout | Yes | |
| POST | /api/billing/start-trial | Yes | |
| GET | /api/credentials/metrics | Yes | |
| GET | /api/credentials/profiles | Yes | |
| POST | /api/credentials/profiles/{profile_id}/interactions | Yes | |
| POST | /api/credentials/store | Yes | |
| GET | /api/demo/export | Yes | |
| POST | /api/demo/generate-deliverable | Yes | |
| POST | /api/demo/run | Yes | |
| GET | /api/demo/spec/{spec_id} | Yes | |
| GET | /api/diagnostics/activation | Yes | |
| GET | /api/diagnostics/activation/last | Yes | |
| POST | /api/documents | Yes | |
| GET | /api/documents/{doc_id}/blocks | Yes | |
| POST | /api/documents/{doc_id}/gates | Yes | |
| POST | /api/documents/{doc_id}/magnify | Yes | |
| POST | /api/documents/{doc_id}/simplify | Yes | |
| POST | /api/documents/{doc_id}/solidify | Yes | |
| GET | /api/domains/{did} | Yes | |
| POST | /api/domains/{did}/verify | Yes | |
| GET | /api/flows/inbound | Yes | |
| GET | /api/flows/outbound | Yes | |
| GET | /api/flows/processing | Yes | |
| GET | /api/flows/state | Yes | |
| POST | /api/forms/correction | Yes | |
| GET | /api/forms/list | Yes | |
| POST | /api/forms/plan-generation | Yes | |
| POST | /api/forms/plan-upload | Yes | |
| GET | /api/forms/submission/{submission_id} | Yes | |
| POST | /api/forms/task-execution | Yes | |
| POST | /api/forms/validation | Yes | |
| POST | /api/forms/{form_type} | Yes | |
| POST | /api/game/balance/check | Yes | |
| GET | /api/game/balance/report | Yes | |
| GET | /api/game/eq/status | Yes | |
| POST | /api/game/monetization/validate | Yes | |
| GET | /api/game/pipeline/runs | Yes | |
| POST | /api/game/pipeline/start | Yes | |
| POST | /api/game/worlds | Yes | |
| GET | /api/graph/health | Yes | |
| POST | /api/graph/query | Yes | |
| GET | /api/hitl/pending | Yes | |
| GET | /api/hitl/queue | Yes | |
| POST | /api/hitl/{tid}/decide | Yes | |
| GET | /api/hitl-graduation/candidates | Yes | |
| GET | /api/integrations/active | Yes | |
| POST | /api/integrations/add | Yes | |
| POST | /api/integrations/wire | Yes | |
| POST | /api/integrations/{request_id}/approve | Yes | |
| POST | /api/integrations/{request_id}/reject | Yes | |
| GET | /api/org/portal/{org_id}/activity | Yes | |
| PATCH | /api/org/portal/{org_id}/settings | Yes | |
| GET | /api/orgchart/inoni-agents | Yes | |
| POST | /api/sessions/create | Yes | |
| POST | /api/setup/api-collection/enqueue | Yes | |
| GET | /api/setup/api-collection/guide/{integration_id} | Yes | |
| GET | /api/setup/api-collection/status | Yes | |
| POST | /api/setup/api-collection/{request_id}/approve | Yes | |
| POST | /api/setup/api-collection/{request_id}/fill | Yes | |
| GET | /api/setup/checklist | Yes | |
| POST | /api/workflows/generate | Yes | |
| POST | /api/workflows/{workflow_id}/execute | Yes | |

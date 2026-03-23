# Murphy System CLI Reference

**Complete reference for all command-line tools and scripts**

---

## Table of Contents

1. [Main Entry Points](#main-entry-points)
2. [Shell Scripts](#shell-scripts)
3. [Python Scripts](#python-scripts)
4. [Quick Start Commands](#quick-start-commands)

---

## Main Entry Points

### murphy_system_1.0_runtime.py

The main Murphy System API server.

```bash
# Start the server (default: localhost:8000)
python murphy_system_1.0_runtime.py

# Environment variables
MURPHY_ENV=development|staging|production
MURPHY_PORT=8000
MURPHY_API_KEYS=key1,key2
```

### murphy_terminal.py

Interactive TUI terminal for Murphy System.

```bash
# Start the terminal
python murphy_terminal.py

# Requires: textual (pip install textual)
```

### universal_control_plane.py

Universal automation engine with two-phase execution.

```bash
# Runs a demo automation
python universal_control_plane.py

# Requires: pydantic (pip install pydantic)
```

### inoni_business_automation.py

Business automation workflows.

```bash
# Run business automation demo
python inoni_business_automation.py

# Requires: pydantic, universal_control_plane
```

### two_phase_orchestrator.py

Generative + production two-phase orchestrator.

```bash
# Run orchestration demo
python two_phase_orchestrator.py
```

---

## Shell Scripts

All scripts support `--help` and `--version` flags.

### Deployment & Infrastructure

#### preflight_check.sh

Validates environment readiness for Hetzner/K8s deployment.

```bash
./scripts/preflight_check.sh [OPTIONS]

Options:
  -h, --help     Show help
  --version      Show version
  -v, --verbose  Detailed output

# Example
./scripts/preflight_check.sh
```

#### production_readiness_check.sh

Checks all K8s resources are deployed and healthy.

```bash
./scripts/production_readiness_check.sh [OPTIONS] [namespace]

Options:
  -h, --help   Show help
  --version    Show version

# Examples
./scripts/production_readiness_check.sh                # Default namespace
./scripts/production_readiness_check.sh my-namespace   # Custom namespace
```

#### verify_monitoring.sh

Verifies Prometheus, Grafana, and metrics stack.

```bash
./scripts/verify_monitoring.sh [OPTIONS]

Options:
  -h, --help           Show help
  --version            Show version
  --namespace NAME     K8s namespace (default: murphy-system)
  --port-forward       Enable port forwarding
  --prom-port PORT     Prometheus port (default: 9090)
  --grafana-port PORT  Grafana port (default: 3000)
  --murphy-port PORT   Murphy API port (default: 8000)

# Example
./scripts/verify_monitoring.sh --port-forward
```

### Runtime & Configuration

#### switch_runtime.sh

Switches between monolith and tiered runtime modes.

```bash
./scripts/switch_runtime.sh [OPTIONS] <mode>

Modes:
  monolith   All modules loaded at startup (default)
  tiered     On-demand module loading

Options:
  -h, --help   Show help
  --version    Show version
  --dry-run    Preview changes

# Examples
./scripts/switch_runtime.sh monolith
./scripts/switch_runtime.sh tiered
```

#### runtime_status.sh

Shows current runtime status.

```bash
./scripts/runtime_status.sh [--port PORT]

# Example
./scripts/runtime_status.sh --port 8000
```

### Security & Secrets

#### generate_secrets.sh

Generates production secrets for .env file.

```bash
./scripts/generate_secrets.sh [OPTIONS]

Options:
  -h, --help     Show help
  --version      Show version
  -o, --output   Write directly to .env
  --json         Output as JSON

# Examples
./scripts/generate_secrets.sh                 # Print to stdout
./scripts/generate_secrets.sh >> .env         # Append to .env
./scripts/generate_secrets.sh -o              # Write to .env
```

Generated secrets:
- `MURPHY_API_KEYS` - API keys (founder + test)
- `MURPHY_CREDENTIAL_MASTER_KEY` - Fernet encryption key
- `MURPHY_JWT_SECRET` - JWT signing secret
- `ENCRYPTION_KEY` - General encryption key
- `POSTGRES_PASSWORD` - PostgreSQL password
- `REDIS_PASSWORD` - Redis password
- `GRAFANA_ADMIN_PASSWORD` - Grafana admin password

#### test_production_auth.sh

Smoke tests for API authentication.

```bash
./scripts/test_production_auth.sh [OPTIONS] [URL] [FOUNDER_KEY] [TEST_KEY]

Options:
  -h, --help    Show help
  --version     Show version
  -v, --verbose Detailed output

Environment variables:
  MURPHY_URL    API base URL
  FOUNDER_KEY   Founder API key
  TEST_KEY      Test API key

# Examples
./scripts/test_production_auth.sh http://localhost:5000 founder_abc test_xyz
FOUNDER_KEY=founder_abc TEST_KEY=test_xyz ./scripts/test_production_auth.sh
```

### Mail Server

#### mail_setup.sh

Provisions mailboxes in docker-mailserver.

```bash
./scripts/mail_setup.sh [OPTIONS] [CONTAINER]

Options:
  -h, --help         Show help
  --version          Show version
  --container NAME   Docker container name
  --domain DOMAIN    Mail domain (default: murphy.systems)
  --dry-run          Preview changes
  --list             List existing accounts

# Examples
./scripts/mail_setup.sh                        # Default container
./scripts/mail_setup.sh --list                 # List accounts
./scripts/mail_setup.sh my-mail-container      # Custom container
```

#### mail_admin.py

Administrative CLI for mail server management.

```bash
python scripts/mail_admin.py <command> [args]

Commands:
  add-account      Add a new mailbox
  remove-account   Remove a mailbox
  list-accounts    List all mailboxes
  add-alias        Add a virtual alias
  remove-alias     Remove a virtual alias
  list-aliases     List all aliases
  change-password  Change account password
  set-quota        Set mailbox quota
  generate-dkim    Generate DKIM signing keys
  show-dns-records Print required DNS records

# Examples
python scripts/mail_admin.py add-account user@murphy.systems SecretPass123
python scripts/mail_admin.py list-accounts
python scripts/mail_admin.py show-dns-records
```

### Benchmarks & Testing

#### run_benchmarks.sh

Runs external AI agent benchmarks.

```bash
./scripts/run_benchmarks.sh [OPTIONS] [BENCHMARK...]

Benchmarks:
  all            All benchmarks
  swe-bench      Software engineering
  gaia           Multi-step tool-use
  agent-bench    8-environment agent tasks
  web-arena      Web automation
  tool-bench     Tool/API selection
  tau-bench      Multi-turn HITL workflows
  terminal-bench CLI/system automation

Options:
  -h, --help   Show help
  --version    Show version

# Examples
./scripts/run_benchmarks.sh all
./scripts/run_benchmarks.sh swe-bench gaia
```

### Maintenance

#### transfer_archive.sh

Transfers archive to dedicated repository.

```bash
./scripts/transfer_archive.sh [OPTIONS]

Options:
  -h, --help   Show help
  --version    Show version
  --dry-run    Preview transfer

# Example
./scripts/transfer_archive.sh --dry-run
```

#### fetch_eqemu_assets.sh

Downloads EQEmu server assets.

```bash
./scripts/fetch_eqemu_assets.sh [OPTIONS]

Options:
  --help              Show help
  --install-dir DIR   Installation directory
  --components LIST   Components: server,database,quests,maps,all
  --method METHOD     Download method: source, release, docker

# Example
./scripts/fetch_eqemu_assets.sh --components all
```

---

## Python Scripts

### Audit & Optimization

#### error_handling_audit.py

Audits error handling patterns in Python codebase.

```bash
python scripts/error_handling_audit.py [OPTIONS]

Options:
  --src-dir DIR   Source directory to audit (default: ./src)
  --output FILE   Output JSON report file

# Example
python scripts/error_handling_audit.py --src-dir ./src
```

#### memory_optimizer.py

Analyzes memory optimization opportunities.

```bash
python scripts/memory_optimizer.py [OPTIONS]

Options:
  --src-dir DIR   Source directory (default: ./src)
  --output FILE   Output JSON report file

# Example
python scripts/memory_optimizer.py
```

#### performance_optimizer.py

Analyzes performance optimization opportunities.

```bash
python scripts/performance_optimizer.py [OPTIONS]

Options:
  --src-dir DIR   Source directory (default: ./src)
  --output FILE   Output JSON report file

# Example
python scripts/performance_optimizer.py
```

#### security_audit.py

Performs security audit on Python codebase.

```bash
python scripts/security_audit.py [OPTIONS]

Options:
  --src-dir DIR   Source directory (default: ./src)
  --output FILE   Output JSON report file

# Example
python scripts/security_audit.py
```

### Setup & Configuration

#### bootstrap_founder.py

Bootstraps the founder account.

```bash
python scripts/bootstrap_founder.py [OPTIONS]

Options:
  --email EMAIL      Founder email (default: founder@murphy.local)
  --name NAME        Founder display name
  --org-name NAME    Organisation name
  --test-email EMAIL Optional test worker email

# Example
python scripts/bootstrap_founder.py --email admin@example.com --org-name "My Org"
```

#### compile_shims.py

Compiles bot shim files from manifests.

```bash
python scripts/compile_shims.py [OPTIONS]

Options:
  --config FILE   Path to bot_manifests.yaml
  --dry-run       Report drift without writing
  --bot NAME      Only process named bot

# Example
python scripts/compile_shims.py --dry-run
```

### Demo & Testing

#### quick_demo.py

Quick demo of Murphy System API.

```bash
python scripts/quick_demo.py

# Requires Murphy API server running at localhost:8000
```

---

## Quick Start Commands

### Development Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Generate secrets
./scripts/generate_secrets.sh > .env

# 3. Start the server
python murphy_system_1.0_runtime.py

# 4. Run tests
pytest tests/ -v
```

### Production Deployment (Hetzner)

```bash
# 1. Run preflight checks
./scripts/preflight_check.sh

# 2. Generate production secrets
./scripts/generate_secrets.sh -o

# 3. Deploy to Kubernetes
kubectl apply -f k8s/

# 4. Verify deployment
./scripts/production_readiness_check.sh

# 5. Verify monitoring
./scripts/verify_monitoring.sh --port-forward

# 6. Test authentication
./scripts/test_production_auth.sh https://murphy.systems "$FOUNDER_KEY" "$TEST_KEY"
```

### Mail Server Setup

```bash
# 1. Start docker-mailserver
docker compose up -d murphy-mailserver

# 2. Provision accounts
./scripts/mail_setup.sh

# 3. List accounts
./scripts/mail_setup.sh --list

# 4. Show DNS records
python scripts/mail_admin.py show-dns-records
```

---

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post — BSL 1.1*

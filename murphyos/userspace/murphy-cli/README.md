# Murphy CLI

© 2020 Inoni Limited Liability Company | Creator: Corey Post | License: BSL 1.1

The `murphy` command wraps the Murphy D-Bus API, REST API, and MurphyFS
filesystem into a single, ergonomic CLI tool.

## Install

```bash
cd murphyos/userspace/murphy-cli
pip install .            # installs the "murphy" command
# or, for development:
pip install -e .[dbus]   # includes optional dbus-next
```

## Commands

| Command                          | Description                          |
|----------------------------------|--------------------------------------|
| `murphy status`                  | Runtime health, confidence, engines  |
| `murphy forge "build a game"`    | Invoke the forge pipeline            |
| `murphy swarm list`              | List active swarm agents             |
| `murphy swarm spawn <role>`      | Spawn a new agent                    |
| `murphy swarm kill <id>`         | Terminate an agent                   |
| `murphy gate list`               | Show governance gate statuses        |
| `murphy gate approve <req-id>`   | Approve a pending HITL request       |
| `murphy gate deny <req-id>`      | Deny a pending HITL request          |
| `murphy engine list`             | List all engines and status          |
| `murphy engine start <name>`     | Start an engine                      |
| `murphy engine stop <name>`      | Stop an engine                       |
| `murphy log tail`                | Stream Event Backbone events         |
| `murphy log search <query>`      | Search logs                          |
| `murphy confidence`              | Print current MFGC score             |
| `murphy config get <key>`        | Get a config value                   |
| `murphy config set <key> <val>`  | Set a config value                   |
| `murphy pqc status`              | PQC key status, algorithm, epoch     |
| `murphy pqc rotate`              | Force PQC key rotation               |
| `murphy pqc verify`              | Verify runtime integrity             |
| `murphy version`                 | Print version info                   |

## Global flags

| Flag         | Description                                |
|--------------|--------------------------------------------|
| `--json`     | Output all results as JSON                 |
| `-q`         | Quiet mode — suppress non-essential output |
| `--api-url`  | Override Murphy REST API URL               |

## Data sources

The CLI tries three data sources in order:

1. **D-Bus** — `org.murphy.System` (requires `dbus-next`)
2. **REST API** — `http://127.0.0.1:8000` (override with `MURPHY_API_URL`)
3. **MurphyFS** — `/murphy/live/` (override with `MURPHY_LIVE_PATH`)

## Bash completion

```bash
# Temporary:
source murphy-completion.bash

# Permanent:
sudo cp murphy-completion.bash /etc/bash_completion.d/murphy
```

## Exit codes

| Code | Meaning   |
|------|-----------|
| `0`  | Success   |
| `1`  | Error     |
| `2`  | Degraded  |

## Colour output

Output is coloured when writing to a terminal:
- **Green** — healthy / running / open
- **Yellow** — degraded / pending
- **Red** — critical / stopped / blocked

Colour is disabled automatically when piping or when `NO_COLOR` is set.

## Environment variables

| Variable            | Default                  | Description            |
|---------------------|--------------------------|------------------------|
| `MURPHY_API_URL`    | `http://127.0.0.1:8000`  | REST API base URL      |
| `MURPHY_LIVE_PATH`  | `/murphy/live`            | MurphyFS mount point   |
| `NO_COLOR`          | —                         | Disable colour output  |

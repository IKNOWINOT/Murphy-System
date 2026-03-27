# Agent Module Loader

**MCP-Style Agent System for Murphy**

The Agent Module Loader provides a modular, interchangeable agent system inspired by MCP (Model Context Protocol) server architecture. Agents are loaded as module presets with trade-specific terminology, Rosetta history translation, and standardized compliance logging.

## Quick Start

```python
from src.agent_module_loader import AgentModuleLoader, get_mss_controller

# Load and start an agent
loader = AgentModuleLoader()
agent = loader.start("security-agent")

print(f"Started: {agent['name']} with {agent['tool_count']} tools")
```

## Built-in Agent Modules

| Module ID | Name | Specialty | Tools |
|-----------|------|-----------|-------|
| `security-agent` | SecurityBot | Vulnerability scanning, compliance, threat analysis | 10+ |
| `devops-agent` | DevOpsBot | CI/CD, Kubernetes, deployments | 10+ |
| `data-agent` | DataBot | ETL, analytics, data quality | 10+ |
| `finance-agent` | FinanceBot | Trading, risk management, accounting | 10+ |
| `comms-agent` | CommsBot | Email, Slack, notifications | 10+ |
| `general-agent` | GeneralBot | All capabilities inherited | 50+ |

## MSS System (Magnify/Simplify/Solidify)

Every request goes through MSS transformation phases to ensure clarity and actionability:

### Resolution Levels (RM0-RM5)
- **RM0**: Vague, ambiguous
- **RM1-RM2**: Partially specified
- **RM3-RM4**: Mostly specified
- **RM5**: Fully specified, executable

### Transformation Phases

1. **Magnify** (+2 RM levels): Expand into concrete components, requirements, and architecture
2. **Simplify** (-2 RM levels): Distill to core objective and key components (max 5)
3. **Solidify**: Lock as executable plan (requires 85% MFGC confidence)

### Standard Sequences

| Sequence | Phases | Use Case |
|----------|--------|----------|
| `MS` | M → S | Quick clarification |
| `MMS` | M → M → S | Standard expansion |
| `MMMS` | M → M → M → S | Prompt clarification |
| `MSS` | M → S → Solidify | Quick to execution |
| `MMSMMS` | M → M → S → M → M → S | Full pipeline |
| `MMSMM_SOLIDIFY` | M → M → S → M → M → Solidify | Error recovery |

### Usage

```python
from src.agent_module_loader import get_mss_controller, MSSSequence

mss = get_mss_controller()

# Single transformation
result = mss.magnify("deploy to kubernetes")
print(f"Resolution: {result.resolution_level}")  # e.g., "RM4"

# Full pipeline
pipeline = mss.execute_pipeline(
    "deploy application to production",
    sequence=MSSSequence.MMSMMS,
    require_mfgc=True,  # Require 85% confidence
)

if pipeline.execution_allowed:
    print("Ready to execute!")
```

## MFGC Confidence Gate

The Multi-Factor Generative-Deterministic Confidence (MFGC) system ensures only high-confidence operations proceed to execution:

| Phase | Threshold | Description |
|-------|-----------|-------------|
| Expand | 50% | Exploration, gathering information |
| Refine | 65% | Refinement, clarification |
| Execute | 85% | Final execution (solidify) |

```python
mss = MSSController(mfgc_threshold=0.85)
result = mss.solidify("deploy critical system", require_mfgc=True)

if result.governance_status == "blocked_low_confidence":
    print(f"Blocked: confidence {result.confidence:.0%} < 85%")
```

## MultiCursor Browser System

Murphy's version of Playwright with 70 action types plus Murphy extensions:

### Features
- **Split-screen zones**: single, dual_h, dual_v, triple_h, quad, hexa
- **Independent cursors**: Each zone has its own cursor
- **Parallel execution**: Actions in different zones run simultaneously
- **Recording/playback**: Record actions and replay them
- **Checkpoints**: Save and restore browser state
- **Desktop automation**: OCR, native clicks, keyboard input

### Usage

```python
from src.agent_module_loader import MultiCursorBrowser
import asyncio

async def demo():
    browser = MultiCursorBrowser()
    await browser.launch()
    
    # Create split-screen layout
    zones = browser.apply_layout("dual_h")
    
    # Navigate different pages in parallel
    await browser.navigate(zones[0]["zone_id"], "https://app1.example.com")
    await browser.navigate(zones[1]["zone_id"], "https://app2.example.com")
    
    # Independent actions
    await browser.click(zones[0]["zone_id"], "#submit")
    await browser.fill(zones[1]["zone_id"], "#search", "query")
    
    # Parallel screenshots
    results = await browser.parallel([
        browser.screenshot(zones[0]["zone_id"]),
        browser.screenshot(zones[1]["zone_id"]),
    ])
    
    await browser.close()

asyncio.run(demo())
```

## Unified Tool Registry

Discovers and categorizes 194 tools from 100 bots and 443 src modules:

```python
from src.agent_module_loader import get_tool_registry, ToolCategory

registry = get_tool_registry()

# Get tools by category
security_tools = registry.get_tools_by_category(ToolCategory.SECURITY)

# Get tools for an agent type
devops_tools = registry.get_tools_for_agent("devops-agent")

# Recommend tools for a task
tools = registry.recommend_tools(
    "scan code for vulnerabilities",
    agent_type="security-agent",
    max_tools=5,
)
```

### Tool Categories

- Security, DevOps, Data, Finance, Communications
- AI Inference, NLP, Vision
- Workflow, Scheduling, Orchestration
- API, Database, Messaging
- Analytics, Monitoring, Reporting
- Engineering, Manufacturing, Energy
- Browser, Desktop, UI Testing
- Memory, Cache, Config, Logging

## Clarification System

Agents can request clarifications with timeout handling:

```python
from src.agent_module_loader import ClarificationSystem

system = ClarificationSystem()

# Request clarification
request = system.request_clarification(
    agent_id="security-agent",
    question="What format should the report be?",
    options=["JSON", "PDF", "HTML"],
    default_option="JSON",
    timeout_seconds=300,
)

# Answer the request
system.provide_answer(request.request_id, "PDF")
```

## Checklist System

Built-in templates for tracking progress:

```python
from src.agent_module_loader import ChecklistSystem

system = ChecklistSystem()

# Create from template
checklist = system.create_checklist(
    name="Deployment",
    template="deployment_checklist",  # 8 steps
)

# Update progress
system.update_item_status(
    checklist.checklist_id,
    checklist.items[0].item_id,
    ChecklistItemStatus.COMPLETED,
)

print(f"Progress: {checklist.progress}%")
```

### Available Templates
- `agent_onboarding` (5 steps)
- `security_review` (5 steps)
- `deployment_checklist` (8 steps)
- `proposal_completion` (10 steps)
- `organization_setup` (7 steps)

## Persistent Organizations

Create persistent agent characters that maintain context across sessions:

```python
from src.agent_module_loader import PersistentOrganization, AgentModuleLoader

loader = AgentModuleLoader()
org = PersistentOrganization("acme", "Acme Corp")

# Define roles
org.define_role(
    role_id="sec-lead",
    title="Security Lead",
    department="Security",
    responsibilities=["Auditing", "Compliance"],
    required_tools=["scan_vulnerabilities"],
)

# Create character
alice = org.create_character(
    name="Alice",
    role_id="sec-lead",
    agent_module="security-agent",
)

# Start session (character context preserved)
session = org.start_session(alice.character_id, loader)
```

## Compliance Logging

8 interchangeable log formats for compliance standards:

```python
from src.agent_module_loader import ComplianceLogger, LogFormat, LogLevel

logger = ComplianceLogger(
    agent_id="security-agent",
    log_format=LogFormat.ECS,  # Elastic Common Schema
    compliance_standards=["SOC2", "GDPR"],
)

logger.log(LogLevel.INFO, "Starting scan")
logger.audit("User action", {"user_id": "123"})
logger.security("Access attempt", {"ip": "1.2.3.4"})
logger.compliance("SOC2-CC1.1", "PASS")
```

### Supported Formats
- JSON, PLAIN
- SYSLOG, CEF (ArcSight)
- LEEF (QRadar), GELF (Graylog)
- ECS (Elastic), OTEL (OpenTelemetry)

## CLI Usage

```bash
# List available modules
python src/agent_module_loader.py --list

# Start an agent
python src/agent_module_loader.py --start security-agent

# List tools for a module
python src/agent_module_loader.py --tools devops-agent

# Demo organization setup
python src/agent_module_loader.py --demo-org
```

## Testing

```bash
# Run all tests (82 tests)
pytest tests/test_agent_module_loader.py -v --override-ini="addopts="
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    AgentModuleLoader                         │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ SecurityBot  │  │  DevOpsBot   │  │   DataBot    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ FinanceBot   │  │  CommsBot    │  │ GeneralBot   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
├─────────────────────────────────────────────────────────────┤
│                    Unified Tool Registry                     │
│                    (194 tools across 22 categories)          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐   │
│  │              MSS Controller                          │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐             │   │
│  │  │ Magnify │→ │ Simplify│→ │ Solidify│ (85% MFGC) │   │
│  │  └─────────┘  └─────────┘  └─────────┘             │   │
│  └─────────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────────┐  ┌────────────────┐  ┌─────────────┐  │
│  │ MultiCursor    │  │ Clarification  │  │  Checklist  │  │
│  │ Browser (70)   │  │ System         │  │  System (5) │  │
│  └────────────────┘  └────────────────┘  └─────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────────┐  ┌────────────────┐                    │
│  │ Persistent     │  │ Compliance     │                    │
│  │ Organizations  │  │ Logger (8 fmt) │                    │
│  └────────────────┘  └────────────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

---

Copyright © 2020 Inoni Limited Liability Company  
Creator: Corey Post  
License: BSL 1.1

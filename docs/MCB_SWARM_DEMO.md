# MultiCursor Browser + Swarm System Demonstration

> **Created:** 2026-03-27  
> **Purpose:** Demonstrate integrated MCB + TrueSwarmSystem automation across any domain

---

## Overview

This document demonstrates how Murphy System uses **MultiCursor Browser (MCB)** and **TrueSwarmSystem** together to automate complex workflows. The system can:

1. **Analyze** any domain workflow using the 7-phase MFGC cycle
2. **Execute** automation scripts using 149 MCB action types
3. **Generate** itemized proposals with 100% cost transparency

---

## Demonstration: E2E Workflow Automation

### Phase 1: Swarm Analysis (EXPAND → CONSTRAIN)

```python
from src.true_swarm_system import TrueSwarmSystem, Phase, ProfessionAtom

# Initialize swarm for domain analysis
swarm = TrueSwarmSystem()

# Execute analysis phases
swarm.execute_phase(Phase.EXPAND)    # Generate solution space
swarm.execute_phase(Phase.TYPE)      # Classify artifacts
swarm.execute_phase(Phase.ENUMERATE) # List all possibilities
swarm.execute_phase(Phase.CONSTRAIN) # Apply business rules
```

### Phase 2: MCB Execution (BIND → EXECUTE)

```python
from src.agent_module_loader import MultiCursorBrowser, MultiCursorActionType

# Get controller for automation agent
mcb = MultiCursorBrowser.get_controller('automation_agent')

# Configure multi-zone layout for parallel execution
mcb.configure_layout('quad')  # 4 zones for parallel work

# Execute workflow in zone 0
zone_0_actions = [
    (MultiCursorActionType.NAVIGATE, {'url': 'https://app.target.com/login'}),
    (MultiCursorActionType.FILL, {'selector': '#email', 'value': 'user@example.com'}),
    (MultiCursorActionType.FILL, {'selector': '#password', 'value': '***'}),
    (MultiCursorActionType.CLICK, {'selector': '#login-btn'}),
    (MultiCursorActionType.WAIT_FOR_NAVIGATION, {}),
]

for action_type, params in zone_0_actions:
    mcb.execute_action(zone_id=0, action_type=action_type, **params)
```

### Phase 3: Generate Automation Proposal

```python
from src.automation_proposal_generator import generate_proposal

proposal = generate_proposal(
    client_name="ACME Corp",
    workflows=[
        {"name": "Login Flow", "actions": 5, "complexity": "simple"},
        {"name": "Dashboard Navigation", "actions": 25, "complexity": "standard"},
        {"name": "Report Generation", "actions": 75, "complexity": "complex"},
    ],
    include_maintenance=True
)

print(proposal.to_markdown())
```

---

## Guiding Principles Validation

### For Each Module/Workflow:

| Question | Process |
|----------|---------|
| **Does the module do what it was designed to do?** | Run unit tests, verify action execution |
| **What exactly is the module supposed to do?** | Document in AUTOMATION_PROPOSAL_TEMPLATE.md |
| **What conditions are possible?** | Enumerate edge cases in test profile |
| **Does test profile reflect full capabilities?** | Coverage > 85% target |
| **Expected vs actual result?** | Assertion-based validation |
| **Documentation updated?** | As-built docs in docs/ |
| **Hardening applied?** | Security review, input validation |
| **Module recommissioned?** | Production readiness sign-off |

---

## MCB Action Categories (149 Total)

| Category | Actions | Examples |
|----------|---------|----------|
| **Navigation** | 8 | NAVIGATE, GO_BACK, GO_FORWARD, RELOAD |
| **Input** | 12 | CLICK, FILL, TYPE, PRESS, SELECT_OPTION |
| **Query** | 18 | GET_TEXT, GET_ATTRIBUTE, IS_VISIBLE |
| **Wait** | 12 | WAIT_FOR_SELECTOR, WAIT_FOR_NAVIGATION |
| **Semantic** | 7 | GET_BY_ROLE, GET_BY_TEXT, GET_BY_LABEL |
| **Network** | 15 | FILE_UPLOAD, REQUEST_INTERCEPT |
| **Assertions** | 13 | ASSERT_TEXT, ASSERT_VISIBLE |
| **Multi-Cursor** | 5 | CURSOR_CREATE, CURSOR_WARP, CURSOR_SYNC |
| **Zone** | 4 | ZONE_CREATE, ZONE_RESIZE, ZONE_SPLIT |
| **Parallel** | 3 | PARALLEL_START, PARALLEL_JOIN |
| **Desktop** | 6 | DESKTOP_CLICK, DESKTOP_TYPE, DESKTOP_OCR |
| **Agent** | 4 | AGENT_HANDOFF, AGENT_CHECKPOINT |
| **Recording** | 3 | RECORD_START, RECORD_STOP, PLAYBACK |

---

## Swarm Profession Atoms (15 Total)

| Category | Professions |
|----------|-------------|
| **Engineering** | Electrical, Software, Mechanical, Systems |
| **Compliance** | Officer, Safety Engineer, Security Analyst, Risk Manager |
| **Domain** | Data Scientist, Expert, Architect |
| **Adversarial** | Red Team, Penetration Tester |
| **Synthesis** | Integrator, Optimizer |

---

## Sample Quote (100% Cost Transparency)

```
═══════════════════════════════════════════════════════════════
          MURPHY SYSTEM AUTOMATION PROPOSAL
═══════════════════════════════════════════════════════════════

Client: ACME Corp
Date: 2026-03-27
Quote Valid: 30 days

PROJECT SCOPE
─────────────────────────────────────────────────────────────
Automate 3 workflows:
1. Login Flow (5 actions) - Simple
2. Dashboard Navigation (25 actions) - Standard  
3. Report Generation (75 actions) - Complex

ITEMIZED COSTS
─────────────────────────────────────────────────────────────
1. Workflow Analysis (x3 workflows)          $ 1,500
2. Test Profile Creation                     $ 2,250
3. MCB Script Development (105 actions)      $ 2,000
4. Swarm Configuration                       $ 2,000
5. Integration Testing                       $ 1,500
6. Documentation                             $   750
─────────────────────────────────────────────────────────────
   Subtotal                                  $10,000
   Complexity Multiplier (avg 1.83x)         x  1.83
─────────────────────────────────────────────────────────────
   TOTAL                                     $18,300

OPTIONAL: Monthly Maintenance                $   800

DELIVERY TIMELINE
─────────────────────────────────────────────────────────────
Phase 1: Analysis & Design          5 days
Phase 2: Development                10 days
Phase 3: Testing & Validation       5 days
Phase 4: Deployment & Training      3 days
─────────────────────────────────────────────────────────────
Total Duration:                     23 days

ACCEPTANCE CRITERIA
─────────────────────────────────────────────────────────────
- All workflows automated per specification
- Test coverage > 85%
- Documentation complete
- Training delivered

═══════════════════════════════════════════════════════════════
```

---

## Video Recording Capability

MCB includes built-in recording for demonstration videos:

```python
# Start recording
mcb.execute_action(zone_id=0, action_type=MultiCursorActionType.RECORD_START)

# Execute automation workflow
# ... actions ...

# Stop recording
mcb.execute_action(zone_id=0, action_type=MultiCursorActionType.RECORD_STOP)

# Playback for demonstration
mcb.execute_action(zone_id=0, action_type=MultiCursorActionType.PLAYBACK_START, 
                   params={'recording_id': 'latest'})
```

---

## Deficiency List (Post-Demo)

### API/SDK Requirements

| Service | Purpose | Status |
|---------|---------|--------|
| DeepInfra | Primary LLM provider | ⬜ Key needed |
| Together AI | Overflow LLM capacity | ⬜ Key needed |
| SendGrid | Email notifications | ⬜ Key needed |
| Stripe | Payment processing | ⬜ Key needed |

### Platform-Side Requirements

| Item | Description | Priority |
|------|-------------|----------|
| DEEPINFRA_API_KEY | Configure in GitHub Secrets | 🔴 HIGH |
| TOGETHER_API_KEY | Configure in GitHub Secrets | 🔴 HIGH |
| PostgreSQL | Production database | 🔴 HIGH |
| Redis | Session/cache store | 🟡 MED |

---

*This demonstration is part of Murphy System v3.0 production documentation.*

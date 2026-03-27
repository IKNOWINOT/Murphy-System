# Murphy System — Automation Proposal Template

> **Version:** 1.0  
> **Created:** 2026-03-27  
> **Purpose:** Template for generating itemized automation proposals and quotes

---

## Executive Summary

Murphy System automates business workflows across any domain using:

1. **MultiCursor Browser (MCB)** — 149 action types covering all Playwright functionality plus Murphy extensions
2. **True Swarm System** — Parallel inference operators with 7-phase MFGC cycle
3. **Native Automation Stack** — API-first design with fallback to UI automation

---

## Automation Assessment Checklist

For each module/workflow to be automated, answer these questions:

### 1. Module Validation
- [ ] **Does the module do what it was designed to do?**
  - Document current functionality
  - Identify gaps between design and implementation

- [ ] **What exactly is the module supposed to do?**
  - Capture requirements (may evolve during design)
  - Define success criteria

- [ ] **What conditions are possible based on the module?**
  - List all input variations
  - Document edge cases

### 2. Test Profile Assessment
- [ ] **Does the test profile reflect full capabilities?**
  - Coverage percentage: ____%
  - Untested paths identified
  - Dynamic chain coverage

- [ ] **What is the expected result at all points?**
  - Define assertions per step
  - Document acceptance criteria

- [ ] **What is the actual result?**
  - Capture current behavior
  - Document deviations

### 3. Remediation Path
- [ ] **If problems exist, how do we restart validation?**
  - Symptom documentation
  - Root cause analysis process
  - Re-validation checklist

### 4. Documentation & Hardening
- [ ] **Has ancillary code/documentation been updated?**
  - API docs current
  - User manual reflects changes
  - As-built documentation complete

- [ ] **Has hardening been applied?**
  - Security review complete
  - Input validation implemented
  - Error handling robust

- [ ] **Has the module been recommissioned?**
  - Final validation pass
  - Production readiness sign-off

---

## MultiCursor Browser Capabilities

### Core Actions (Playwright Superset)
| Category | Action Count | Examples |
|----------|-------------|----------|
| Navigation | 8 | NAVIGATE, GO_BACK, GO_FORWARD, RELOAD |
| Input | 12 | CLICK, FILL, TYPE, PRESS, SELECT_OPTION |
| Query | 18 | GET_TEXT, GET_ATTRIBUTE, IS_VISIBLE, QUERY_SELECTOR |
| Wait | 12 | WAIT_FOR_SELECTOR, WAIT_FOR_NAVIGATION, WAIT_FOR_LOAD_STATE |
| Semantic Locators | 7 | GET_BY_ROLE, GET_BY_TEXT, GET_BY_LABEL, GET_BY_TEST_ID |
| Network/File | 15 | FILE_UPLOAD, REQUEST_INTERCEPT, SET_COOKIES |
| Assertions | 13 | ASSERT_TEXT, ASSERT_VISIBLE, ASSERT_VALUE, ASSERT_CLASS |

### Murphy Extensions
| Category | Action Count | Examples |
|----------|-------------|----------|
| Multi-Cursor | 5 | CURSOR_CREATE, CURSOR_WARP, CURSOR_SYNC |
| Zone Management | 4 | ZONE_CREATE, ZONE_RESIZE, ZONE_SPLIT, ZONE_CAPTURE |
| Parallel Execution | 3 | PARALLEL_START, PARALLEL_JOIN, PARALLEL_ALL |
| Desktop Automation | 6 | DESKTOP_CLICK, DESKTOP_TYPE, DESKTOP_OCR |
| Agent Integration | 4 | AGENT_HANDOFF, AGENT_CHECKPOINT, AGENT_ROLLBACK |
| Recording | 3 | RECORD_START, RECORD_STOP, PLAYBACK_START |

### Split-Screen Layouts
| Layout | Zones | Use Case |
|--------|-------|----------|
| single | 1 | Single-task focus |
| dual_h | 2 | Side-by-side comparison |
| dual_v | 2 | Sequential workflow |
| quad | 4 | Multi-panel dashboard |
| hexa | 6 | Complex workflow orchestration |
| nona | 9 | High-density monitoring |
| hex4 | 16 | Maximum parallel execution |

---

## True Swarm System

### 7-Phase MFGC Cycle
1. **EXPAND** — Generate solution space
2. **TYPE** — Classify and categorize artifacts
3. **ENUMERATE** — List all possibilities
4. **CONSTRAIN** — Apply business rules
5. **COLLAPSE** — Select optimal solutions
6. **BIND** — Commit to execution plan
7. **EXECUTE** — Perform actions with gates

### Agent Professions
| Category | Professions |
|----------|-------------|
| Engineering | Electrical, Software, Mechanical, Systems |
| Compliance | Officer, Safety Engineer, Security Analyst, Risk Manager |
| Domain | Data Scientist, Expert, Architect |
| Adversarial | Red Team, Penetration Tester |
| Synthesis | Integrator, Optimizer |

---

## Pricing Model

### Base Automation Costs
| Component | Unit | Cost |
|-----------|------|------|
| Workflow Analysis | per workflow | $500 |
| Test Profile Creation | per workflow | $750 |
| MCB Script Development | per 100 actions | $1,000 |
| Swarm Configuration | per domain | $2,000 |
| Integration Testing | per workflow | $500 |
| Documentation | per workflow | $250 |

### Complexity Multipliers
| Complexity Level | Multiplier | Criteria |
|------------------|------------|----------|
| Simple | 1.0x | < 10 actions, single zone |
| Standard | 1.5x | 10-50 actions, multi-zone |
| Complex | 2.0x | 50-200 actions, parallel execution |
| Enterprise | 3.0x | > 200 actions, swarm integration |

### Ongoing Maintenance
| Service | Monthly Cost |
|---------|-------------|
| Monitoring | $100/workflow |
| Updates | $200/workflow |
| Support | $500/month (unlimited) |

---

## Sample Quote Template

```
═══════════════════════════════════════════════════════════════
          MURPHY SYSTEM AUTOMATION PROPOSAL
═══════════════════════════════════════════════════════════════

Client: [CLIENT NAME]
Date: [DATE]
Quote Valid: 30 days

PROJECT SCOPE
─────────────────────────────────────────────────────────────
[Describe workflows to be automated]

ITEMIZED COSTS
─────────────────────────────────────────────────────────────
1. Workflow Analysis (x[N] workflows)     $ [AMOUNT]
2. Test Profile Creation                  $ [AMOUNT]
3. MCB Script Development ([N] actions)   $ [AMOUNT]
4. Swarm Configuration                    $ [AMOUNT]
5. Integration Testing                    $ [AMOUNT]
6. Documentation                          $ [AMOUNT]
─────────────────────────────────────────────────────────────
   Subtotal                               $ [SUBTOTAL]
   Complexity Multiplier ([LEVEL])        x [MULTIPLIER]
─────────────────────────────────────────────────────────────
   TOTAL                                  $ [TOTAL]

OPTIONAL: Monthly Maintenance             $ [MONTHLY]

DELIVERY TIMELINE
─────────────────────────────────────────────────────────────
Phase 1: Analysis & Design          [N] days
Phase 2: Development                [N] days
Phase 3: Testing & Validation       [N] days
Phase 4: Deployment & Training      [N] days
─────────────────────────────────────────────────────────────
Total Duration:                     [N] days

ACCEPTANCE CRITERIA
─────────────────────────────────────────────────────────────
- All workflows automated per specification
- Test coverage > 85%
- Documentation complete
- Training delivered

═══════════════════════════════════════════════════════════════
```

---

## Deficiency Report Template

After automation implementation, document any remaining gaps:

### Required APIs/SDKs
| Service | Purpose | Status |
|---------|---------|--------|
| [SERVICE] | [PURPOSE] | ⬜ Key needed |

### Platform-Side Requirements
| Item | Description | Priority |
|------|-------------|----------|
| [ITEM] | [DESCRIPTION] | [HIGH/MED/LOW] |

### Known Limitations
| Limitation | Workaround | Impact |
|------------|------------|--------|
| [LIMITATION] | [WORKAROUND] | [IMPACT] |

---

## Next Steps

1. Complete assessment checklist for target workflows
2. Generate itemized quote using pricing model
3. Review deficiency report for API/SDK requirements
4. Schedule implementation timeline
5. Execute with MultiCursor + Swarm system

---

*This template is part of Murphy System v3.0 production documentation.*
*Contact: murphy.systems for custom automation engagements.*

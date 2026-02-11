# Murphy System Flow Analysis (Runtime 1.0)

This document answers:
- Why the current attempt fails to reflect full capability
- What needs to be specified during onboarding
- What existing subsystems must be wired
- What questions are not being answered
- The current flow behavior and UI attempt script

## 1) Why the attempt fails right now

**Observed behavior:** Runtime 1.0 responds in *simulation mode* and reports planned subsystems/gates/swarm tasks, but the capability alignment reports `not_wired` for those subsystems.

**Primary causes:**
- **Orchestrator unavailable** → runtime falls back to simulation (`Two-Phase Orchestrator unavailable; using simulation mode`).
- **Planned subsystems are not wired into execution** → gate synthesis, swarm orchestration, and domain swarms exist but are not invoked in `execute_task` or form processing.
- **Subsystem services are not initialized** → compute plane and stability controllers exist as modules but do not run in the runtime 1.0 process.

**Result:** The activation preview accurately *plans* what should be used, but the capability alignment shows that the system does not yet **execute** those subsystems. That is the gap.

## 2) What needs to be specified in onboarding

To generate gates and a full business structure, the runtime requires explicit onboarding inputs:

1. **Business structure**
   - Business model (SaaS, services, hybrid)
   - Primary revenue streams
   - Org chart / executive branch authority
2. **Operational scope**
   - Target industries, geographies, compliance regimes
   - Products/services and their lifecycle stages
3. **Automation architecture**
   - Key workflows (onboarding, fulfillment, support, billing)
   - Trigger conditions and success criteria
4. **Governance + gates**
   - Risk tolerance
   - Approval levels and sign-off thresholds
   - Compliance checkpoints (legal, security, finance)
5. **Data sources + integrations**
   - CRM, billing, analytics, support tools
   - APIs, data access rules, audit requirements

Without these, the system can only **simulate** a gate tree and swarm tasks.

## 3) What existing modules must be wired

These subsystems already exist but are *not wired into runtime 1.0*:

- **Gate synthesis** (`src/gate_synthesis/`) → must be called during request processing to generate real gates.
- **TrueSwarmSystem** (`src/true_swarm_system.py`) → must expand tasks into agent swarms for execution.
- **Domain swarms** (`src/domain_swarms.py`) → required for domain-specific execution plans.
- **Compute plane** (`src/compute_plane/`) → required for deterministic calculations.
- **Recursive stability controller** (`src/recursive_stability_controller/`) → for stability/feedback gating.
- **Infinity expansion system** (`src/infinity_expansion_system.py`) → for expanding requirements beyond initial prompts.

The activation preview flags these gaps with:
```
capability_alignment[].gap_reason = not_wired
capability_alignment[].gap_action = "Wire this subsystem into execute_task or form processing."
```

## 4) Questions not being answered

These are the minimum unanswered questions preventing full capability:

1. **Executive branch governance**
   - Who approves gates at each phase?
   - What policies override automation?
2. **Business structure + compliance**
   - What compliance gates exist (SOC2, PCI, HIPAA, etc.)?
   - What is the legal risk tolerance?
3. **Automation definition**
   - What is the exact automation objective?
   - What is considered “done” and what triggers escalation?
4. **Data access**
   - Which systems are authoritative?
   - What data is allowed to drive gates?

## 5) Flow analysis (what is happening now)

1. **User submits request**
2. **Runtime creates a LivingDocument**
3. **Activation preview generates**
   - Planned subsystems
   - Planned gates
   - Planned swarm tasks
4. **Capability alignment checks**
   - Subsystems are present but not wired
5. **Simulation mode output**
   - Tasks are not executed against real systems

## 6) UI attempt script (as a user)

Use this to reproduce the exact flow:

### Integrated UI (Form Submission)
1. Open: `murphy_ui_integrated.html?apiPort=8000`
2. Task description:
   ```
   Assess onboarding automation and highlight which gates and swarms should activate.
   ```
3. Click **Execute Task**
4. Verify:
   - **Activation Preview** shows planned subsystems
   - **Capability Alignment** shows `not_wired` gaps
   - **Planned Gates** show Magnify/Simplify/Solidify gates

### Architect Terminal (block command tree)
1. Open: `terminal_architect.html?apiPort=8000`
2. Command:
   ```
   Design executive-branch automation gates for onboarding, billing, and compliance.
   ```
3. Click **BLOCKS** tab
4. Click **Solidify**
5. Verify:
   - Block tree expands to swarm tasks (signup → billing)

## 7) How to close the gaps (summary)

To move from preview to actual capability:
1. **Wire gate synthesis** into request processing to generate real gates.
2. **Wire TrueSwarmSystem + DomainSwarms** into execution to activate agent swarms.
3. **Initialize compute plane** for deterministic calculations.
4. **Add executive authority gates** to enforce governance decisions.

These steps align system behavior with your requirement to automate business, agents, and executive-level gating.

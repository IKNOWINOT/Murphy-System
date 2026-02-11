# Murphy System Runtime Activation Audit

This audit lists implemented subsystems that are not wired into the runtime 1.0 execution path and suggests verification steps for commissioned capabilities.

## Inactive / Unwired Subsystems

| Subsystem | Status | Activation Notes |
| --- | --- | --- |
| Recursive Stability Controller | Implemented, inactive | `src/recursive_stability_controller/` provides telemetry and gate damping but no runtime entrypoint. |
| Gate Synthesis Engine | Implemented, inactive | `src/gate_synthesis/` builds gates and enumerates failure modes; not invoked from execute flow. |
| Compute Plane | Implemented, inactive | `src/compute_plane/` supports symbolic/numeric solving; runtime does not expose it. |
| Infinity Expansion System | Implemented, inactive | `src/infinity_expansion_system.py` expands problem space but is not called. |
| Advanced Swarm System | Implemented, inactive | `src/advanced_swarm_system.py` defines swarm synthesis but is not used in runtime. |
| Domain Swarms | Implemented, inactive | `src/domain_swarms.py` domain generators are not wired to task intake. |
| True Swarm System | Implemented, inactive | `src/true_swarm_system.py` is instantiated but not called in `execute_task`. |
| Knowledge Gap System | Implemented, inactive | `src/knowledge_gap_system.py` exists without runtime integration. |
| Neuro-Symbolic Models | Implemented, inactive | `src/neuro_symbolic_models/` not referenced in runtime. |

## Runtime Audit Endpoint

Query the activation audit directly:

```
GET /api/diagnostics/activation
```

This returns availability and wiring status for each subsystem.

To fetch the last activation preview captured during request processing:

```
GET /api/diagnostics/activation/last
```

## Verification Checklist (Commissioned Behaviors)

1. **Block command expansion (magnify/simplify/solidify)**
   - Run a task, then expand the block tree in the architect UI.
2. **Swarm task generation**
   - Solidify a document to generate swarm tasks for signup to billing flow.
3. **Automation execution**
   - Submit a task via `/api/forms/task-execution` and validate the execution packet.
4. **Integration workflow**
   - Add a repository via `/api/integrations/add` and verify pending approvals.
5. **Governance / HITL**
   - Trigger a validation failure and review HITL intervention queue.
6. **Business automation**
   - Call `/api/automation/{engine}/{action}` with sample parameters.

## Suggested Next Tests

- Wire compute plane into execution for symbolic reasoning tasks.
- Connect gate synthesis engine to document solidification for automatic gate creation.
- Integrate TrueSwarmSystem into execution to expand tasks into domain-specific swarms.

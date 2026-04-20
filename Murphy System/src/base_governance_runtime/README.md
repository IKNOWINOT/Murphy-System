# `src/base_governance_runtime` — Base Governance & Compliance Runtime

Preset-driven governance configuration, requirement validation, and continuous compliance monitoring for the Murphy System.

![License: BSL 1.1](https://img.shields.io/badge/License-BSL%201.1-blue.svg)

## Overview

The base governance runtime provides the foundational compliance framework that all Murphy subsystems inherit. Governance presets encode domain-specific rule sets (GDPR, SOC 2, HIPAA, etc.) and are applied to the runtime configuration via the `PresetManager`. The `ValidationEngine` performs gap analysis against active presets and surfaces `ValidationResult` objects for each requirement. The `ComplianceMonitor` continuously re-evaluates the system state and publishes `ComplianceReport` snapshots, while the `GovernanceAPI` exposes all operations over a FastAPI REST interface.

## Key Components

| Module | Purpose |
|--------|---------|
| `governance_runtime.py` | `GovernanceRuntime` — wires preset, validation, and monitor together |
| `governance_runtime_complete.py` | Extended runtime with full enforcement hooks |
| `preset_manager.py` | `PresetManager`, `GovernancePreset`, `EnforcementMode` |
| `validation_engine.py` | `ValidationEngine` — requirement gap analysis and `ValidationResult` emission |
| `compliance_monitor.py` | `ComplianceMonitor` — continuous monitoring and `ComplianceReport` publishing |
| `api_server.py` | `GovernanceAPI` — REST endpoints for governance operations |

## Usage

```python
from base_governance_runtime import GovernanceRuntime, PresetManager, EnforcementMode

presets = PresetManager()
presets.load_preset("soc2", enforcement=EnforcementMode.ENFORCE)

runtime = GovernanceRuntime(preset_manager=presets)
runtime.start()

report = runtime.compliance_monitor.latest_report()
print(report.summary)
```

---
*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

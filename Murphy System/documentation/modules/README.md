# Specialized Module Documentation

This directory contains detailed documentation for standalone Murphy System
modules (i.e., single-file modules under `src/` that are not part of a package).

## Index

| Module | Source File | Design Label | Description |
|--------|-------------|--------------|-------------|
| [Adaptive Campaign Engine](ADAPTIVE_CAMPAIGN_ENGINE.md) | `src/adaptive_campaign_engine.py` | MKT-004 | Self-adjusting tier-filling marketing campaigns with HITL paid-ad approval |
| [Financial Reporting Engine](FINANCIAL_REPORTING_ENGINE.md) | `src/financial_reporting_engine.py` | BIZ-001 | Automated financial data collection, trend analysis, and periodic reporting |
| [Predictive Maintenance Engine](PREDICTIVE_MAINTENANCE_ENGINE.md) | `src/predictive_maintenance_engine.py` | PME-001 | Hardware telemetry anomaly detection and failure prediction |

## Documentation Format

Each module document follows the standard template:
- **Overview** — purpose, design label, owner
- **Architecture** — ASCII flow diagram
- **Key Classes** — method tables and dataclass definitions
- **Events** — events published to the EventBackbone
- **Safety Invariants** — thread safety, bounds, audit trail
- **Configuration** — configurable parameters with defaults
- **Dependencies** — other Murphy modules required
- **Usage** — minimal working code example

*Copyright © 2020 Inoni Limited Liability Company · Creator: Corey Post · License: BSL 1.1*

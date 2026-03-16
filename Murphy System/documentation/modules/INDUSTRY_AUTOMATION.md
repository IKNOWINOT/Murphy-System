# Industry Automation System

## Overview

The Murphy System Industry Automation framework provides a complete, conversational
wizard-driven pipeline for configuring, ingesting, simulating, and as-building any
industrial automation system. It covers 10 industries with 66+ automation types,
integrates ASHRAE/Grainger best-practices, climate-resilience design, CEM-level
energy management, 21-question knowledge elicitation, and pro/con decision logic.

---

## Architecture

```
User/Onboarding Context
         |
         v
IndustryAutomationWizard  (10 industries, 66+ types)
         |
         v
SyntheticInterviewEngine  (21-question elicitation, LLM inference)
         |
         v
UniversalIngestionFramework  (BACnet EDE / Modbus / OPC-UA / CSV / JSON / MQTT / Grainger)
         |
         +----------> BASEquipmentIngestion  (CSV/JSON/EDE -> EquipmentSpec)
         |                      |
         |                      v
         |             VirtualController  (populate_from_spec, verify_wiring)
         |                      |
         |                      v
         +----------> AsBuiltGenerator  (ControlDiagram, PointSchedule, DrawingDatabase)
         |
         v
SystemConfigurationEngine  (detect type, select strategy, MSS modes)
         |
         v
ClimateResilienceEngine  (ASHRAE 169-2021 zones, resilience factors, energy targets)
         |
         v
EnergyEfficiencyFramework  (CEM ECM catalog, ASHRAE audit levels, MSS rubric)
         |
         v
ProConDecisionEngine  (safety constraints first, then pros-beat-cons)
```

---

## Modules

### `src/industry_automation_wizard.py`
- `IndustryAutomationWizard` — session-based conversational wizard
- 10 industries: BAS/Energy, Manufacturing, Healthcare, Retail, Logistics,
  Agriculture, Water/Utilities, Oil & Gas, Data Center, Transportation
- 66+ automation types with inline recommendations
- `IndustryAutomationSpec` — structured output ready for execution engine
- Uses `onboarding_context` from `NoCodeWorkflowTerminal` sessions

### `src/universal_ingestion_framework.py`
- `AdapterRegistry.auto_detect_and_ingest()` — protocol-agnostic ingestion
- Concrete adapters: BACnet EDE, Modbus Register Map, OPC-UA Node List,
  Generic CSV, Generic JSON, MQTT Topic Map, Grainger Product CSV
- `GRAINGER_BEST_SELLERS` — 11 equipment categories × 3-5 components each,
  every item citing the ASHRAE standard that mandates it
- `ComponentRecommendation` with manufacturer, part number, and ASHRAE reference

### `src/bas_equipment_ingestion.py`
- `EquipmentDataIngestion.ingest_csv/json/ede()` — parse equipment point lists
- Auto-classifies AI/AO/DI/DO, detects protocol (BACnet/Modbus/OPC-UA)
- `populate_virtual_controller()` — auto-wires ingested points to `VirtualController`
- ASHRAE 62.1/90.1/Guideline 36 and Grainger component recommendations per type

### `src/virtual_controller.py`
- `VirtualController` — manages control points, IO map, wiring state
- `WiringVerificationEngine.verify(spec)` — validates minimum required points,
  unit validity, range logic, duplicate instances, commandable outputs
- `VerificationReport` with pass/fail/warning per rule

### `src/system_configuration_engine.py`
- `SystemConfigurationEngine.detect_system_type(description)` — keyword detection
- `STRATEGY_TEMPLATES` — 16 system types (AHU, RTU, FCU, VAV, chiller, boiler,
  cooling tower, heat pump, VRF, radiant, DOAS, HX, electrical, PLC, SCADA, generic)
- `recommend_strategy(system_type, context)` — pro/con weighted selection
- MSS modes: `magnify()` full detail, `simplify()` critical only, `solidify()` locked config

### `src/climate_resilience_engine.py`
- `CLIMATE_ZONE_DATABASE` — 15 ASHRAE 169-2021 zones with HDD/CDD, dominant load
- `ClimateResilienceEngine.get_design_recommendations(location, equipment_type)`
- `ResilienceFactors` — seismic, hurricane, flood, extreme heat, wildfire, permafrost
- `get_energy_targets(location, building_type)` — ASHRAE 90.1 EUI baselines
- `get_equipment_sizing_factors(location)` — oversizing multipliers for climate

### `src/energy_efficiency_framework.py`
- `ECM_CATALOG` — 25 ECMs across HVAC, Lighting, Envelope, Controls, Renewable,
  Compressed Air, Steam, Process, Water, Behavioral
- Every ECM cites CEM module, ASHRAE standard, IPMVP option, and KPI metrics
- `EnergyEfficiencyFramework.analyze_utility_data()` — EUI, cost breakdown, carbon
- `ASHRAE_AUDIT_LEVELS` — Level I / II / III deliverables, data required, typical findings
- `MSSEnergyRubric` — Magnify (Level III detail), Simplify (quick wins), Solidify (M&V plan)
- `calculate_roi(ecm, analysis)` — simple payback, 10-year NPV, IRR

### `src/synthetic_interview_engine.py`
- `QUESTION_BANK` — 21 questions × 6 reading levels (Elementary → Expert)
- `INFERENCE_RULES` — 43 keyword → question-answer inference rules (LLM-style implicit derivation)
- `SyntheticInterviewEngine.answer()` — records answer, infers implicit answers, detects reading level
- `detect_reading_level(text)` — expert/professional/technical/HS detection from vocabulary
- `adapt_to_reading_level(text, level)` — substitutes technical terms for accessible equivalents
- All 21 questions can be "covered" through 5-7 keyword-rich answers

### `src/as_built_generator.py`
- `AsBuiltGenerator.from_equipment_spec()` / `from_virtual_controller()` — build diagrams
- `DrawingDatabase` — ingests thousands of drawings, deduplicates by quality score
- `merge_with_database(diagram, db)` — enriches new diagrams from reference library
- `generate_point_schedule()` — CSV-ready control point table
- `generate_schematic_description()` — text schematic with equipment, instruments, notes
- `check_proposal_completeness(diagram, requirements)` — ensures as-built ≥ proposal

### `src/pro_con_decision_engine.py`
- `STANDARD_CRITERIA` — 4 sets: energy_system_selection, automation_strategy_selection,
  equipment_selection, ecm_prioritization
- Hard constraints (safety, codes) are checked FIRST — failed options are eliminated
  regardless of pro scores
- `ProConDecisionEngine.evaluate()` — net_score = Σ(pro×weight) − Σ(con×weight)
- `evaluate_ecms()`, `evaluate_equipment()`, `evaluate_strategies()` — domain shortcuts
- `explain_decision()` — human-readable reasoning including eliminated options

---

## Example Scripts

| Script | Industry | Demonstrates |
|--------|----------|-------------|
| `bas_energy_management_simulation.py` | BAS / Energy | Ingestion → virtual controller → energy audit → as-built |
| `manufacturing_automation_simulation.py` | Manufacturing | Industry wizard → universal ingestion → PLC config → interview |
| `healthcare_automation_simulation.py` | Healthcare | HIPAA/ASHRAE 170 compliance → climate → equipment decision |
| `energy_audit_simulation.py` | Energy Management | CEM Level II audit → ECM ROI → MSS rubric |
| `org_chart_simulation.py` | Org Chart | Virtual employees → shadow agents → hire_employee() tailoring |
| `system_configuration_simulation.py` | Controls | System type detection → strategy selection → as-built DB |
| `retail_automation_simulation.py` | Retail | Retail wizard → EUI → ECM prioritization |
| `climate_resilience_simulation.py` | All | Climate zones → resilience → energy targets for 5 US cities |
| `decision_engine_simulation.py` | All | Pro/con with safety elimination → ECM prioritization |
| `synthetic_interview_simulation.py` | All | 21-question elicitation → implicit inference → reading levels |

Run any script:
```bash
cd "Murphy System"
python3 examples/scripts/bas_energy_management_simulation.py
```

---

## Command Registry Entries

All 12 new commands are registered in `src/murphy_terminal/command_registry.py`:

| Command | Slash | Category | Description |
|---------|-------|----------|-------------|
| `bas_equipment_ingestion` | `/bas ingest` | IOT | Ingest BAS equipment data |
| `virtual_controller` | `/bas controller` | IOT | Virtual controller wiring |
| `industry_automation_wizard` | `/wizard industry` | AUTOMATION | 10-industry wizard |
| `org_chart_generator` | `/org virtual` | ORG | Virtual org + shadow agents |
| `production_deliverable_wizard` | `/wizard deliverable` | AUTOMATION | Deliverable wizard |
| `universal_ingestion_framework` | `/ingest auto` | DATA | Auto-detect protocol ingestion |
| `climate_resilience_engine` | `/climate zone` | INTEGRATIONS | Climate zone lookup |
| `energy_efficiency_framework` | `/energy audit` | INTEGRATIONS | CEM energy audit |
| `synthetic_interview_engine` | `/interview start` | INTELLIGENCE | 21-question interview |
| `system_configuration_engine` | `/configure system` | AUTOMATION | System config + MSS |
| `as_built_generator` | `/asbuilt generate` | IOT | As-built diagram generation |
| `pro_con_decision_engine` | `/decide` | INTELLIGENCE | Pro/con decision |

---

## Regulatory and Standards References

| Standard | Module | Application |
|----------|--------|-------------|
| ASHRAE 90.1 | EEF, Climate, VirtualController | Energy code compliance |
| ASHRAE 62.1 | EEF, BAS Ingestion | Ventilation requirements |
| ASHRAE Guideline 36 | SystemConfig, BAS | High-performance sequences |
| ASHRAE Guideline 22 | SystemConfig | Chiller plant commissioning |
| ASHRAE 169-2021 | ClimateResilienceEngine | Climate zone classification |
| ASHRAE 170 | Industry Wizard (Healthcare) | Healthcare ventilation |
| IPMVP Option A/B/C/D | EEF | M&V methodology |
| CEM Modules 1-14 | EEF ECM Catalog | Certified Energy Manager |
| ISA-88 | SystemConfig (PLC) | Batch control |
| ISA-18.2 | SystemConfig (SCADA) | Alarm management |
| IEC 61131-3 | SystemConfig | PLC programming |
| IEC 62541 OPC-UA | UniversalIngestion | OPC-UA protocol |
| NFPA 70E | SystemConfig | Electrical safety |
| OSHA CFR | SyntheticInterview, ProCon | Worker safety |
| NEC | SyntheticInterview, ProCon | Electrical code |

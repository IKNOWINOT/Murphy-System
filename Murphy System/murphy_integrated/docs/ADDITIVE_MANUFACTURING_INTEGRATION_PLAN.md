# Additive Manufacturing / 3D Printing Integration Plan

**Murphy System — Automation Integration Plan**
**Version:** 1.0.0
**Date:** 2026-02-25
**Status:** Active

---

## 1. Executive Summary

This document defines the integration plan for connecting Murphy System to **all major 3D printing and additive manufacturing (AM) automation platforms**. The plan covers every ISO/ASTM 52900 process category — FDM/FFF, SLA/DLP, SLS, SLM/DMLS, EBM, PolyJet/MJF, binder jetting, DED/WAAM, and continuous-fiber reinforcement — and maps each to the Murphy System's ISA-95 layer model, governance framework, and connector architecture.

---

## 2. Scope

### 2.1 AM Process Categories (ISO/ASTM 52900)

| Process | Technology Examples | Material Classes |
|---|---|---|
| **FDM / FFF** | Stratasys F-Series, Ultimaker S-Line, Prusa MK4/XL, Bambu Lab, Creality | Thermoplastics (PLA, ABS, PETG, Nylon, PC, PEEK), composites |
| **SLA / DLP** | Formlabs Form 4, 3D Systems ProJet, Anycubic Photon, Elegoo | Photopolymers, castable wax |
| **SLS** | EOS P 396, 3D Systems sPro, Farsoon, Sintratec | Nylon (PA11/PA12), TPU, PP |
| **SLM / DMLS** | SLM Solutions, EOS M-Series, Trumpf TruPrint, Renishaw | Ti-6Al-4V, Inconel, stainless steel, aluminium alloys |
| **EBM** | GE Additive Arcam, Freemelt ONE | Ti-6Al-4V, CoCr, copper alloys |
| **PolyJet / MJF** | HP Jet Fusion 5200, Stratasys J-Series | Thermoplastics (PA12, PA11), elastomers |
| **Binder Jetting** | ExOne / Desktop Metal, HP Metal Jet, voxeljet | Metal powders, sand, ceramics, full-colour gypsum |
| **DED / WAAM** | Lincoln Electric, Gefertec, WAAM3D, Sciaky EBAM | Steel, Ti, Ni, Cu wire / powder |
| **Continuous Fiber** | Markforged, Anisoprint, 9T Labs | Carbon fiber, fiberglass, Kevlar + thermoplastic matrix |

### 2.2 Integration Protocols

| Protocol / Standard | Version | Usage |
|---|---|---|
| **OPC UA AM Companion Spec (OPC 40564)** | 1.01 | Standardised machine-to-MES data model |
| **MTConnect** | 2.2 | CNC/additive device streaming telemetry |
| **MQTT / Sparkplug B** | 3.0 | Real-time sensor telemetry |
| **Vendor REST APIs** | Various | GrabCAD Print, Digital Factory, PreForm, Eiger, EOSTATE, 3D Command Center |
| **gRPC** | — | High-throughput streaming (in-situ monitoring, camera feeds) |
| **3MF / AMF** | 1.2 / 1.2 | Build-file interchange |
| **G-code / CLI serial** | — | Direct motion-controller interface (Marlin, Klipper, RepRapFirmware) |

---

## 3. ISA-95 Layer Mapping

```
┌──────────────────────────────────────────────────────────────────┐
│ L4 — ENTERPRISE                                                  │
│   ERP / PLM / MES order management                               │
│   Murphy System ↔ SAP / Siemens Teamcenter / Autodesk Fusion    │
├──────────────────────────────────────────────────────────────────┤
│ L3 — SITE OPERATIONS                                             │
│   Build preparation, nesting / scheduling, fleet management      │
│   Stratasys GrabCAD · Ultimaker Digital Factory · HP 3D Center  │
│   Formlabs Dashboard · Markforged Eiger · Desktop Metal Live     │
├──────────────────────────────────────────────────────────────────┤
│ L2 — SUPERVISORY                                                 │
│   Printer dashboard, job monitoring, OPC UA AM gateway           │
│   OctoPrint · Prusa Connect · EOS EOSTATE · SLM Build Processor │
│   OPC 40564 AM Gateway · MTConnect Additive Agent               │
├──────────────────────────────────────────────────────────────────┤
│ L1 — DIRECT CONTROL                                              │
│   Motion controller, laser/heater PID, G-code interpreter       │
│   Klipper/Moonraker · Marlin · RepRapFirmware · WAAM Controller │
├──────────────────────────────────────────────────────────────────┤
│ L0 — FIELD DEVICE                                                │
│   Sensors (thermocouples, load cells, cameras, IMU), actuators  │
│   MQTT/Sparkplug B telemetry · MTConnect sensor streams         │
└──────────────────────────────────────────────────────────────────┘
```

---

## 4. Connector Architecture

### 4.1 Module: `additive_manufacturing_connectors.py`

The module follows the same pattern as `building_automation_connectors.py`, `energy_management_connectors.py`, and `manufacturing_automation_standards.py`:

```
AMConnector            — adapter for one vendor/system
AdditiveManufacturingRegistry — thread-safe registry with discover/execute/health
AMWorkflowBinder       — multi-step, dependency-aware ISA-95 workflow engine
```

### 4.2 Default Connector Catalogue (18 connectors)

| # | Connector | Vendor | Process | Protocol | Layer |
|---|---|---|---|---|---|
| 1 | Stratasys F-Series (GrabCAD) | Stratasys | FDM/FFF | REST | L3 |
| 2 | Ultimaker Digital Factory | Ultimaker | FDM/FFF | REST | L3 |
| 3 | Prusa Connect | Prusa | FDM/FFF | REST | L2 |
| 4 | Klipper / Moonraker | Community | FDM/FFF | REST | L1 |
| 5 | OctoPrint API | Community | FDM/FFF | REST | L2 |
| 6 | Formlabs Dashboard | Formlabs | SLA/DLP | REST | L3 |
| 7 | HP 3D Command Center | HP | PolyJet/MJF | REST | L3 |
| 8 | EOS EOSTATE | EOS | SLS | OPC UA AM | L2 |
| 9 | SLM Solutions Build Processor | SLM Solutions | SLM/DMLS | OPC UA AM | L2 |
| 10 | GE Additive Arcam EBM | GE Additive | EBM | OPC UA AM | L2 |
| 11 | Markforged Eiger | Markforged | Continuous Fiber | REST | L3 |
| 12 | ExOne / Desktop Metal | Desktop Metal | Binder Jetting | REST | L3 |
| 13 | Lincoln Electric WAAM | Lincoln Electric | DED/WAAM | OPC UA AM | L1 |
| 14 | OPC UA AM Gateway (40564) | OPC Foundation | Generic | OPC UA AM | L2 |
| 15 | MTConnect Additive Agent | MTConnect Inst. | Generic | MTConnect | L1 |
| 16 | AM Sparkplug B Telemetry | Eclipse Sparkplug | Generic | MQTT | L0 |

---

## 5. Integration Phases

### Phase 1 — Foundation (Weeks 1-4)

| Task | Details | Owner |
|---|---|---|
| 1.1 | Implement `additive_manufacturing_connectors.py` with all 18 default connectors | Platform Team |
| 1.2 | Wire module into Murphy System `MODULE_CATALOG` and `_initialize()` | Platform Team |
| 1.3 | Unit + integration tests (registry, health, execute, workflow) | QA Team |
| 1.4 | OPC UA AM companion-spec node mapping (OPC 40564 information model) | Integration Team |
| 1.5 | MTConnect additive device model mapping (laser state, powder state, build layer) | Integration Team |

### Phase 2 — Vendor REST API Connectors (Weeks 5-10)

| Task | Details | Owner |
|---|---|---|
| 2.1 | Stratasys GrabCAD Print REST API — OAuth2, job CRUD, fleet discovery | Integration Team |
| 2.2 | Ultimaker Digital Factory API — API-key auth, printer groups, print profiles | Integration Team |
| 2.3 | Formlabs Dashboard API — resin tracking, wash/cure scheduling | Integration Team |
| 2.4 | HP 3D Command Center API — MJF build-unit lifecycle, thermal imaging | Integration Team |
| 2.5 | Markforged Eiger API — fiber routing, sintering schedule | Integration Team |
| 2.6 | Desktop Metal / ExOne API — binder jetting batch traceability | Integration Team |
| 2.7 | Prusa Connect + OctoPrint + Klipper/Moonraker REST wrappers | Integration Team |

### Phase 3 — Real-Time Telemetry & In-Situ Monitoring (Weeks 11-14)

| Task | Details | Owner |
|---|---|---|
| 3.1 | MQTT/Sparkplug B telemetry bridge — birth/death/data metrics | Telemetry Team |
| 3.2 | Melt-pool monitoring data ingestion (EOS, SLM Solutions, GE Arcam) | Data Team |
| 3.3 | Thermal camera stream integration (HP MJF, EOS) | Data Team |
| 3.4 | Layer-by-layer image analytics pipeline (defect detection) | ML Team |
| 3.5 | Wire arc AM interpass-temperature closed-loop integration | Controls Team |

### Phase 4 — MES / PLM / ERP Bridging (Weeks 15-18)

| Task | Details | Owner |
|---|---|---|
| 4.1 | SAP PP-PI / S/4HANA Manufacturing integration | Enterprise Team |
| 4.2 | Siemens Teamcenter / Xcelerator PLM connector | Enterprise Team |
| 4.3 | Autodesk Fusion / Netfabb build-preparation bridge | Enterprise Team |
| 4.4 | 3MF / AMF file format import/export pipeline | Platform Team |
| 4.5 | Part genealogy & serial-number traceability across build jobs | QA Team |

### Phase 5 — Governance, Safety & Quality (Weeks 19-22)

| Task | Details | Owner |
|---|---|---|
| 5.1 | Murphy governance gates for AM — confidence thresholds per material class | Governance Team |
| 5.2 | Build-failure risk scoring (Murphy Index for AM) | Risk Team |
| 5.3 | Powder/resin lot traceability & shelf-life enforcement | Quality Team |
| 5.4 | Post-processing workflow gates (heat treat, HIP, machining, inspection) | Quality Team |
| 5.5 | Regulatory compliance mapping (AS9100, NADCAP AM, FDA 21 CFR 820) | Compliance Team |

### Phase 6 — Advanced Capabilities (Weeks 23-26)

| Task | Details | Owner |
|---|---|---|
| 6.1 | Multi-machine nesting & scheduling optimisation | Scheduling Team |
| 6.2 | Predictive maintenance models per printer fleet | ML Team |
| 6.3 | Digital-twin synchronisation (build chamber, powder bed, wire feed) | DT Team |
| 6.4 | Closed-loop adaptive process control (laser power, speed, layer time) | Controls Team |
| 6.5 | Cost-per-part analytics dashboard | Analytics Team |

---

## 6. Data Model

### 6.1 AM Build Job

```json
{
  "job_id": "BJ-2026-0042",
  "status": "building",
  "machine_id": "ULT-S5-007",
  "vendor": "ultimaker",
  "process": "fdm_fff",
  "material": {
    "class": "thermoplastic",
    "grade": "Ultimaker Tough PLA",
    "lot_number": "LOT-2026-1234",
    "spool_remaining_g": 612
  },
  "build_file": {
    "format": "3mf",
    "name": "bracket_v3.3mf",
    "hash_sha256": "a1b2c3…"
  },
  "progress_pct": 47.3,
  "estimated_completion_utc": "2026-02-26T04:15:00Z",
  "layer_current": 142,
  "layer_total": 302,
  "temperatures": {
    "nozzle_c": 215,
    "bed_c": 60,
    "chamber_c": null
  },
  "quality_metrics": {
    "layer_adhesion_score": 0.94,
    "dimensional_accuracy_mm": 0.12,
    "surface_roughness_ra_um": 8.2
  },
  "governance": {
    "murphy_index": 0.15,
    "confidence": 0.92,
    "authority_band": "supervised_autonomy",
    "gates_passed": ["material_verification", "build_plate_level", "first_layer_inspection"]
  }
}
```

### 6.2 AM Machine Telemetry (MQTT/Sparkplug B)

```
Topic: spBv1.0/MurphyAM/DDATA/prusa_mk4_001/telemetry
Payload Metrics:
  - nozzle_temp_c       = 215.3
  - bed_temp_c          = 60.1
  - flow_rate_mm3s      = 4.82
  - fan_speed_pct       = 100
  - layer_number        = 142
  - z_height_mm         = 28.4
  - filament_used_mm    = 4312.7
  - vibration_rms_g     = 0.023
  - power_draw_w        = 187.4
```

---

## 7. Governance Integration

Murphy System governance controls are applied at every AM workflow stage:

| Gate | Trigger | Murphy Index Threshold |
|---|---|---|
| **Material Verification** | Before build start | < 0.30 |
| **Build Plate Calibration** | Before build start | < 0.20 |
| **First Layer Inspection** | After layer 1 | < 0.25 |
| **In-Process Quality** | Every N layers | < 0.40 |
| **Build Completion** | At 100% | < 0.20 |
| **Post-Processing** | Before shipping | < 0.15 |
| **Certification** | Final sign-off | < 0.10 |

Authority bands:
- **Full Auto** (Murphy Index < 0.15): routine builds with validated materials
- **Supervised Autonomy** (0.15 – 0.40): new materials, complex geometries
- **Human-in-the-Loop** (0.40 – 0.70): safety-critical parts, first-article
- **Manual Override** (> 0.70): novel process, unvalidated parameters

---

## 8. Safety & Compliance

### 8.1 Material Safety

- **Metal powder handling**: inert-gas monitoring, explosion-proof enclosures
- **Resin handling**: VOC monitoring, UV exposure limits
- **Laser safety**: Class 4 laser interlocks, beam-path enclosure verification
- **Electron beam**: vacuum integrity, X-ray shielding verification

### 8.2 Regulatory Frameworks

| Standard | Scope |
|---|---|
| **ISO/ASTM 52900-52950** | AM terminology, design, materials, post-processing |
| **AS9100 Rev D + NADCAP AM** | Aerospace AM qualification |
| **FDA 21 CFR 820** | Medical-device AM (surgical guides, implants) |
| **IATF 16949** | Automotive AM components |
| **AWS D20.1** | WAAM structural welding qualification |
| **NIST MSAM** | Measurement science for AM |

### 8.3 Data Security

- All connector credentials stored in Murphy Secure Key Manager
- OPC UA certificate-based authentication
- MQTT TLS 1.3 + Sparkplug B payload encryption
- REST API OAuth 2.0 / API-key rotation
- Build-file integrity via SHA-256 hash verification

---

## 9. Testing Strategy

| Level | Scope | Tool |
|---|---|---|
| **Unit** | Connector init, health, execute, rate-limit | pytest |
| **Integration** | Registry CRUD, workflow binder, cross-connector | pytest |
| **E2E** | Full build-job lifecycle (submit → monitor → complete) | pytest + mock API |
| **Performance** | 1 000 concurrent connector health checks < 5 s | pytest-benchmark |
| **Security** | Credential handling, TLS config, input validation | bandit + custom |

---

## 10. Success Metrics

| KPI | Target |
|---|---|
| Connector coverage (vendors) | ≥ 15 vendors |
| Process coverage (ISO 52900) | All 7 + DED + continuous fiber |
| OPC UA AM node mapping completeness | ≥ 90 % of OPC 40564 nodes |
| Mean time to integrate new printer | < 2 hours |
| Build-job telemetry latency | < 500 ms (MQTT) |
| Governance gate pass rate (routine builds) | > 95 % |
| Zero undetected build failures | 100 % detection within 5 layers |

---

## 11. Dependencies

- `manufacturing_automation_standards.py` — base ISA-95 / OPC UA / MTConnect connectors
- `building_automation_connectors.py` — shared connector pattern
- `energy_management_connectors.py` — shared connector pattern
- Murphy governance framework (confidence engine, gate synthesis, authority mapper)
- Murphy telemetry system (MQTT/Sparkplug B bridge)
- Murphy secure key manager (credential storage)

---

## 12. Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Vendor API breaking changes | Medium | Version-pinned adapters, contract tests |
| OPC UA AM spec immaturity | Medium | Fall back to vendor REST API |
| Metal AM safety interlock bypass | Critical | Hardware-level safety independent of software |
| Powder/resin lot contamination | High | RFID/barcode material verification gate |
| Network latency to cloud APIs | Medium | Local cache + store-and-forward |
| Build-file IP leakage | High | Encryption at rest + in transit, DLP integration |

---

*This integration plan is maintained by the Murphy System Platform Team and reviewed quarterly.*

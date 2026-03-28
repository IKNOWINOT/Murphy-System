# Active System Map

**Document ID:** MURPHY-ASM-2026-001  
**Version:** 1.0.0  
**Date:** February 27, 2026  
**Owner:** @arch-lead  
**Phase:** 1 — Environment Cleanup & Assessment  
**Completion:** 100%

---

## Overview

This document maps all active components in the Murphy System 1.0 codebase, their roles, dependencies, and integration points. Components are categorized by architectural layer.

---

## Layer 1: Runtime Entry Points

| Component | File | Role | Status |
|-----------|------|------|--------|
| Murphy 1.0 Runtime | `murphy_system_1.0_runtime.py` → `src/runtime/` | Thin entry-point; implementation in `src/runtime/app.py`, `murphy_system_core.py`, `living_document.py` | ✅ Active |
| Universal Control Plane | `universal_control_plane.py` | 7 modular engines for session-based automation | ✅ Active |
| Inoni Business Automation | `inoni_business_automation.py` | 5 business engines (Sales, Marketing, R&D, Biz Mgmt, Production) | ✅ Active |
| Two-Phase Orchestrator | `two_phase_orchestrator.py` | Generative setup → Production execution | ✅ Active |

---

## Layer 2: Core Subsystems (`src/`)

### Control Plane
| Component | File | Classes | Integration Points |
|-----------|------|---------|--------------------|
| Control Plane Separation | `control_plane_separation.py` | ControlPlane, ExecutionPlane | Message Bus, Packet Builder |
| Control Plane (dir) | `control_plane/` | Phase Controller, Gate Compiler | Confidence Engine, Swarms |
| Execution Engine | `execution_engine/` | ExecutionEngine | Packet Verifier, FSM |
| Execution Orchestrator | `execution_orchestrator/` | Orchestrator | Phase Controller |

### Confidence & Validation
| Component | File | Classes | Integration Points |
|-----------|------|---------|--------------------|
| Confidence Engine | `confidence_engine/` | ConfidenceEngine (G/D/H) | All subsystems |
| Verification Layer | `verification_layer.py` | VerificationLayer | Execution Plane |
| Safety Validation Pipeline | `safety_validation_pipeline.py` | SafetyValidator | Gate System |
| Input Validation | `input_validation.py` | InputValidator | API Gateway |

### Governance & Security
| Component | File | Classes | Integration Points |
|-----------|------|---------|--------------------|
| Governance Framework | `governance_framework/` | GovernanceFramework | Authority Gate |
| Governance Kernel | `governance_kernel.py` | GovernanceKernel | RBAC |
| Authority Gate | `authority_gate.py` | AuthorityGate | Governance |
| RBAC Governance | `rbac_governance.py` | RBACController | FastAPI Security |
| Security Plane | `security_plane/` | SecurityMonitor | All endpoints |
| Emergency Stop Controller | `emergency_stop_controller.py` | EmergencyStop | Watchdog |

### Learning & Self-Improvement
| Component | File | Classes | Integration Points |
|-----------|------|---------|--------------------|
| Self Improvement Engine | `self_improvement_engine.py` | SelfImprovementEngine | Telemetry, Outcomes |
| Self Automation Orchestrator | `self_automation_orchestrator.py` | SelfAutomationOrchestrator | Task Queue |
| Self Optimisation Engine | `self_optimisation_engine.py` | SelfOptimisationEngine | Metrics |
| Self Healing Coordinator | `self_healing_coordinator.py` | SelfHealingCoordinator | Health Monitor |
| Learning Engine | `learning_engine/` | LearningEngine | Telemetry |
| Telemetry Learning | `telemetry_learning/` | 4 learning engines | Event Backbone |
| Shadow Agent Integration | `shadow_agent_integration.py` | ShadowAgent | Training Data |

### Business Automation
| Component | File | Classes | Integration Points |
|-----------|------|---------|--------------------|
| Sales Automation | `sales_automation.py` | SalesEngine | CRM, Lead Scoring |
| Campaign Orchestrator | `campaign_orchestrator.py` | CampaignOrchestrator | Marketing |
| SEO Optimisation Engine | `seo_optimisation_engine.py` | SEOEngine | Content Pipeline |
| Content Pipeline Engine | `content_pipeline_engine.py` | ContentPipeline | Publishing |
| Financial Reporting Engine | `financial_reporting_engine.py` | FinancialReporter | Business Mgmt |
| Invoice Processing Pipeline | `invoice_processing_pipeline.py` | InvoicePipeline | Finance |
| KPI Tracker | `kpi_tracker.py` | KPITracker | Dashboard |

### Organization & Workflow
| Component | File | Classes | Integration Points |
|-----------|------|---------|--------------------|
| Organization Chart System | `organization_chart_system.py` | OrgChart, OrgNode | Governance |
| Org Chart Enforcement | `org_chart_enforcement.py` | OrgEnforcer | RBAC |
| Org Compiler | `org_compiler/` | OrgCompiler | Execution Packet |
| Workflow DAG Engine | `workflow_dag_engine.py` | WorkflowDAG | Execution |
| Automation Scheduler | `automation_scheduler.py` | AutomationScheduler | Task Queue |

### Integration & Communication
| Component | File | Classes | Integration Points |
|-----------|------|---------|--------------------|
| Integration Engine | `integration_engine/` | IntegrationEngine | GitHub, APIs |
| Event Backbone | `event_backbone.py` | EventBackbone | All subsystems |
| API Gateway Adapter | `api_gateway_adapter.py` | APIGateway | Endpoints |
| Webhook Event Processor | `webhook_event_processor.py` | WebhookProcessor | External |
| RAG Vector Integration | `rag_vector_integration.py` | RAGVector | Librarian |

### Persistence & Monitoring
| Component | File | Classes | Integration Points |
|-----------|------|---------|--------------------|
| Persistence Manager | `persistence_manager.py` | PersistenceManager | State, Audit |
| Health Monitor | `health_monitor.py` | HealthMonitor | All components |
| Observability Counters | `observability_counters.py` | ObservabilityCounters | Metrics |
| Metrics | `metrics.py` | MetricsCollector | Prometheus |
| Statistics Collector | `statistics_collector.py` | StatsCollector | Dashboard |

---

## Layer 3: Test Infrastructure (`tests/`)

| Category | Count | Location | Coverage |
|----------|-------|----------|----------|
| Unit Tests | ~277 | `tests/test_*.py` | Component-level |
| E2E Tests | 5 | `tests/e2e/` | Full workflow |
| Integration Tests | 7 | `tests/integration/` | Cross-component |
| System Tests | 1 | `tests/system/` | System-level |
| **Commissioning Tests** | **15** | **`tests/commissioning/`** | **Self-automation validation** |

---

## Layer 4: Infrastructure

| Component | File(s) | Role |
|-----------|---------|------|
| Docker | `Dockerfile`, `docker-compose.yml` | Container deployment |
| Kubernetes | `k8s/*.yaml` (8 files) | Orchestration |
| Monitoring | `monitoring/prometheus.yml` | Metrics collection |
| Scripts | `scripts/*.py` (4 files) | Audit, optimization |

---

## Layer 5: UI & Documentation

| Component | File | Type |
|-----------|------|------|
| Landing Page | `murphy_landing_page.html` | Marketing |
| Integrated UI | `murphy_ui_integrated.html` | Main interface |
| Terminal UI | `murphy_ui_integrated_terminal.html` | Terminal mode |
| Architect Terminal | `terminal_architect.html` | Design mode |
| Enhanced Terminal | `terminal_enhanced.html` | Advanced mode |
| Worker Terminal | `terminal_worker.html` | Worker mode |

---

## Component Interaction Summary

```
User Request → API Gateway → Control Plane
                                ↓
                        Confidence Engine (G/D/H scoring)
                                ↓
                        Gate Compiler (safety gates)
                                ↓
                        Packet Builder (HMAC-SHA256 sign)
                                ↓
                        Message Bus (one-way)
                                ↓
                        Execution Plane (FSM only)
                                ↓
                        Result → Telemetry → Learning Engine
                                              ↓
                                    Self-Improvement Engine
```

---

**Total Active Python Source Modules:** 150+  
**Total Active Test Files:** 297+  
**Total Active Documentation Files:** 60+  
**Total HTML Interfaces:** 6

---

**© 2026 Inoni Limited Liability Company. All rights reserved.**

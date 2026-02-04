# Murphy v3.0 - Code Consolidation Roadmap

**Purpose:** Map every feature to its best implementation across all versions

**Extraction Strategy:** For each feature, identify the source version with the best implementation

---

## Version Overview

| Version | Total Files | Strengths | Use For |
|---------|-------------|-----------|---------|
| murphy_integrated | 538 files | Best architecture, security plane, two-phase | Core orchestration, security |
| murphy_complete_final | 31 modules | Most AI/ML features, swarm intelligence | AI/ML systems, advanced features |
| murphy_system_fixed | 39+ modules | Most tested, production-ready, scheduler | Production features, testing |
| murphy_system_working | Clean code | Best web UI, WebSocket, clean API | Web layer, API patterns |
| murphy_implementation | Structured | Phase-based architecture | Workflow patterns |

---

## Extraction Map

### Phase 1: Core Foundation

#### Configuration System
**Extract From:** murphy_integrated  
**Source File:** `murphy_integrated/src/config.py`  
**Destination:** `murphy_v3/core/config.py`  
**Reason:** Most comprehensive, Pydantic-based, well-documented  
**Status:** ✅ Extracted (enhanced for v3)

#### Exception Hierarchy
**Extract From:** NEW (none exist complete)  
**Destination:** `murphy_v3/core/exceptions.py`  
**Reason:** Need structured hierarchy across all exception types  
**Status:** 🔄 Creating from scratch

#### Structured Logging
**Extract From:** murphy_system_fixed  
**Source File:** To be identified  
**Destination:** `murphy_v3/core/logging.py`  
**Reason:** Best production logging practices  
**Status:** ⏳ Pending

#### Event Bus
**Extract From:** murphy_complete_final  
**Source File:** Event handling patterns  
**Destination:** `murphy_v3/core/events.py`  
**Reason:** Good pub/sub patterns for decoupling  
**Status:** ⏳ Pending

#### Database Pooling
**Extract From:** NEW (based on GAP analysis)  
**Destination:** `murphy_v3/infrastructure/database.py`  
**Reason:** Need async pooling with retry logic  
**Status:** ⏳ Pending

---

### Phase 2: Security Plane (11 Modules)

**Extract From:** murphy_integrated  
**Source Directory:** `murphy_integrated/src/security_plane/`  
**Destination:** `murphy_v3/security/`

| Module | Source File | Status |
|--------|-------------|--------|
| Authentication | `security_plane/authentication.py` | ⏳ |
| Authorization | `security_plane/access_control.py` | ⏳ |
| Cryptography | `security_plane/cryptography.py` | ⏳ |
| DLP | `security_plane/data_leak_prevention.py` | ⏳ |
| Middleware | `security_plane/middleware.py` | ⏳ |
| Hardening | `security_plane/hardening.py` | ⏳ |
| Adaptive Defense | `security_plane/adaptive_defense.py` | ⏳ |
| Anti-Surveillance | `security_plane/anti_surveillance.py` | ⏳ |
| Packet Protection | `security_plane/packet_protection.py` | ⏳ |
| Schemas | `security_plane/schemas.py` | ⏳ |
| Rate Limiting | NEW | ⏳ |

**Integration Task:** Wire security middleware to FastAPI app

---

### Phase 3: Orchestration Core

#### Two-Phase Orchestrator
**Extract From:** murphy_integrated  
**Source File:** `murphy_integrated/two_phase_orchestrator.py`  
**Destination:** `murphy_v3/orchestration/two_phase.py`  
**Reason:** Core innovation, well-implemented  
**Modifications:** Enhance with better error handling  
**Status:** ⏳ Pending

#### Universal Control Plane
**Extract From:** murphy_integrated  
**Source File:** `murphy_integrated/universal_control_plane.py`  
**Destination:** `murphy_v3/orchestration/control_plane.py`  
**Reason:** Best modular engine architecture  
**Status:** ⏳ Pending

#### 7 Engines

| Engine | Source File | Destination | Status |
|--------|-------------|-------------|--------|
| Sensor | `murphy_integrated/src/engines/sensor_engine.py` | `orchestration/engines/sensor.py` | ⏳ |
| Actuator | `murphy_integrated/src/engines/actuator_engine.py` | `orchestration/engines/actuator.py` | ⏳ |
| Database | `murphy_integrated/src/engines/database_engine.py` | `orchestration/engines/database.py` | ⏳ |
| API | `murphy_integrated/src/engines/api_engine.py` | `orchestration/engines/api.py` | ⏳ |
| Content | `murphy_integrated/src/engines/content_engine.py` | `orchestration/engines/content.py` | ⏳ |
| Command | `murphy_integrated/src/engines/command_engine.py` | `orchestration/engines/command.py` | ⏳ |
| Agent | `murphy_integrated/src/engines/agent_engine.py` | `orchestration/engines/agent.py` | ⏳ |

#### ExecutionPacket System
**Extract From:** murphy_integrated  
**Source File:** `murphy_integrated/src/execution_packet.py`  
**Destination:** `murphy_v3/orchestration/execution_packet.py`  
**Reason:** Cryptographically sealed packets are core innovation  
**Status:** ⏳ Pending

#### Session Manager
**Extract From:** murphy_integrated  
**Source File:** `murphy_integrated/src/session_manager.py`  
**Destination:** `murphy_v3/orchestration/session_manager.py`  
**Reason:** Session isolation is critical  
**Status:** ⏳ Pending

---

### Phase 4: AI/ML Systems

#### Murphy Validation
**Extract From:** murphy_integrated  
**Source File:** `murphy_integrated/src/confidence_engine/murphy_validation.py`  
**Destination:** `murphy_v3/ai/murphy_validation.py`  
**Reason:** Core safety innovation (G-D)/H formula  
**Status:** ⏳ Pending

Components:
- Murphy formula calculator
- 5D uncertainty assessment (UD, UA, UI, UR, UG)
- Gate system (static, dynamic, adaptive)
- HITL integration

#### Shadow Agent System
**Extract From:** murphy_integrated + murphy_complete_final (11 patterns)  
**Source Files:**
- `murphy_integrated/src/learning_engine/shadow_agent.py`
- `murphy_complete_final/learning_engine.py` (11 patterns)

**Destination:** `murphy_v3/ai/shadow_agent.py`  
**Reason:** Merge best correction capture with 11 pattern types  
**Status:** ⏳ Pending

Components:
- 4 correction methods (Interactive, Batch, API, Inline)
- 11 pattern detection types (from murphy_complete_final)
- Training pipeline (PyTorch)
- A/B testing framework
- Gradual rollout system

#### Swarm Knowledge Pipeline
**Extract From:** murphy_complete_final  
**Source File:** `murphy_complete_final/swarm_knowledge_pipeline.py`  
**Destination:** `murphy_v3/ai/swarm_knowledge.py`  
**Reason:** Unique confidence-based knowledge buckets  
**Status:** ⏳ Pending

Components:
- Green bucket (>90% confidence)
- Yellow bucket (60-90% confidence)
- Red bucket (<60% confidence)
- Knowledge propagation
- Agent coordination

#### Dynamic Projection Gates
**Extract From:** murphy_complete_final  
**Source File:** `murphy_complete_final/dynamic_projection_gates.py`  
**Destination:** `murphy_v3/ai/dynamic_gates.py`  
**Reason:** CEO-generated business constraints  
**Status:** ⏳ Pending

#### Learning Engine (11 Patterns)
**Extract From:** murphy_complete_final  
**Source File:** `murphy_complete_final/learning_engine.py`  
**Destination:** `murphy_v3/ai/learning_engine.py`  
**Reason:** Most comprehensive pattern detection  
**Status:** ⏳ Pending

11 Pattern Types:
1. Frequency patterns
2. Sequence patterns
3. Temporal patterns
4. Context patterns
5. Correlation patterns
6. Anomaly patterns
7. Drift patterns
8. Dependency patterns
9. User patterns
10. Resource patterns
11. Success patterns

---

### Phase 5: Business Systems

#### Inoni Business Automation
**Extract From:** murphy_integrated  
**Source File:** `murphy_integrated/inoni_business_automation.py`  
**Destination:** `murphy_v3/business/`

5 Engines:

| Engine | Source | Destination | Status |
|--------|--------|-------------|--------|
| Sales | `inoni_business_automation.py` (SalesEngine) | `business/sales_engine.py` | ⏳ |
| Marketing | `inoni_business_automation.py` (MarketingEngine) | `business/marketing_engine.py` | ⏳ |
| R&D | `inoni_business_automation.py` (RDEngine) | `business/rd_engine.py` | ⏳ |
| Business Mgmt | `inoni_business_automation.py` (BusinessMgmt) | `business/business_mgmt_engine.py` | ⏳ |
| Production | `inoni_business_automation.py` (ProductionMgmt) | `business/production_mgmt_engine.py` | ⏳ |

#### B2B Negotiation Agents (NEW)
**Extract From:** NEW (no existing implementation)  
**Destination:** `murphy_v3/business/b2b_negotiation.py`  
**Design:** Based on B2B_NEGOTIATION_AGENTS.md  
**Status:** ⏳ To be created

Components:
- Negotiation protocol
- Multi-party coordination
- Fair pricing algorithms
- Legal compliance checking
- Contract generation
- Adaptive learning

#### SwissKiss Integration Engine
**Extract From:** murphy_integrated  
**Source Directory:** `murphy_integrated/src/integration_engine/`  
**Destination:** `murphy_v3/integration/`

| Component | Source | Destination | Status |
|-----------|--------|-------------|--------|
| Main Engine | `integration_engine/unified_engine.py` | `integration/swisskiss.py` | ⏳ |
| Capability Extractor | `integration_engine/capability_extractor.py` | `integration/capability_extractor.py` | ⏳ |
| Module Generator | `integration_engine/module_generator.py` | `integration/module_generator.py` | ⏳ |
| Safety Tester | `integration_engine/safety_tester.py` | `integration/safety_tester.py` | ⏳ |
| HITL Approval | `integration_engine/hitl_approval.py` | `integration/hitl_approval.py` | ⏳ |

#### Calendar Scheduler
**Extract From:** murphy_system_fixed  
**Source File:** `murphy_system_fixed/system_calendar_scheduler.py`  
**Destination:** `murphy_v3/business/scheduler.py`  
**Reason:** Time quotas, zombie prevention, restart logic  
**Status:** ⏳ Pending

#### Librarian System
**Extract From:** murphy_system_fixed  
**Source File:** `murphy_system_fixed/librarian_system_commands.py`  
**Destination:** `murphy_v3/business/librarian.py`  
**Reason:** 61+ command knowledge base  
**Status:** ⏳ Pending

#### Authority Envelope System
**Extract From:** murphy_integrated  
**Source File:** `murphy_integrated/src/authority_envelope.py`  
**Destination:** `murphy_v3/orchestration/authority_envelope.py`  
**Reason:** Formal control theory  
**Status:** ⏳ Pending

---

### Phase 6: Advanced Features

#### Multi-Agent Book Generator
**Extract From:** murphy_complete_final  
**Source File:** `murphy_complete_final/multi_agent_book_generator.py`  
**Destination:** `murphy_v3/ai/book_generator.py`  
**Reason:** Collaborative 50,000+ word generation  
**Status:** ⏳ Pending

#### Intelligent System Generator
**Extract From:** murphy_complete_final  
**Source File:** `murphy_complete_final/intelligent_system_generator.py`  
**Destination:** `murphy_v3/ai/system_generator.py`  
**Reason:** NL specification → Working system  
**Status:** ⏳ Pending

#### Payment Verification System
**Extract From:** murphy_complete_final  
**Source File:** `murphy_complete_final/payment_verification.py`  
**Destination:** `murphy_v3/business/payment_verification.py`  
**Reason:** Payment + artifact access control  
**Status:** ⏳ Pending

#### Artifact Generation Pipeline
**Extract From:** murphy_complete_final  
**Source Files:**
- `murphy_complete_final/artifact_generation.py`
- `murphy_complete_final/artifact_download.py`

**Destination:** `murphy_v3/infrastructure/artifact_system.py`  
**Reason:** Document creation & secure delivery  
**Status:** ⏳ Pending

---

### Phase 7: Competitive Features (NEW)

#### Pre-built Integrations (20+)
**Extract From:** Various + NEW  
**Destination:** `murphy_v3/integrations/prebuilt/`  
**Strategy:** Use SwissKiss to auto-generate, then curate

Integrations to create:
1. Stripe (payments)
2. Twilio (communications)
3. SendGrid (email)
4. GitHub (version control)
5. Slack (notifications)
6. Google Workspace
7. Microsoft 365
8. Salesforce (CRM)
9. HubSpot (CRM)
10. Mailchimp (email marketing)
11. Shopify (ecommerce)
12. WooCommerce (ecommerce)
13. AWS S3 (storage)
14. GCP Cloud Storage
15. Azure Blob Storage
16. Dropbox (storage)
17. Zoom (video)
18. Calendly (scheduling)
19. Asana (project management)
20. Jira (issue tracking)

**Status:** ⏳ Pending

#### Visual Workflow Builder
**Extract From:** NEW (doesn't exist)  
**Destination:** `murphy_v3/ui/workflow_builder/`  
**Technology:** React + React Flow  
**Components:**
- Drag-and-drop canvas
- Node library
- Connection logic
- Live preview
- Template library
- Version control

**Status:** ⏳ Pending

#### Marketplace Platform
**Extract From:** NEW  
**Destination:** `murphy_v3/marketplace/`  
**Components:**
- User-submitted workflows
- Pre-built templates
- Custom integrations
- Reviews & ratings
- Revenue sharing
- Search & discovery

**Status:** ⏳ Pending

#### Mobile Apps
**Extract From:** NEW  
**Destinations:**
- `murphy_v3/mobile/ios/` (Swift/SwiftUI)
- `murphy_v3/mobile/android/` (Kotlin/Jetpack Compose)

**Features:**
- Task monitoring
- HITL approvals
- Notifications
- Dashboard view
- Basic workflow editing

**Status:** ⏳ Pending

#### AI Copilot Assistant
**Extract From:** NEW  
**Destination:** `murphy_v3/ai/copilot.py`  
**Features:**
- Natural language workflow creation
- "Schedule a daily report" → generates workflow
- Suggests optimizations
- Explains errors
- Recommends integrations

**Status:** ⏳ Pending

---

### Phase 8: Infrastructure & Production

#### Database Layer
**Extract From:** NEW (enhanced patterns)  
**Source:** Best practices from murphy_integrated  
**Destination:** `murphy_v3/infrastructure/database.py`  
**Features:**
- Async PostgreSQL (asyncpg)
- Connection pooling (10 + 20 overflow)
- Retry logic
- Migration support (Alembic)

**Status:** ⏳ Pending

#### Cache Layer
**Extract From:** murphy_integrated patterns  
**Destination:** `murphy_v3/infrastructure/cache.py`  
**Technology:** Redis  
**Features:**
- Distributed caching
- Rate limit storage
- Session storage
- Token blacklist

**Status:** ⏳ Pending

#### Queue System
**Extract From:** NEW  
**Destination:** `murphy_v3/infrastructure/queue.py`  
**Technology:** Celery + Redis  
**Features:**
- Async task processing
- Task prioritization
- Retry logic
- Scheduled tasks

**Status:** ⏳ Pending

#### Storage System
**Extract From:** murphy_complete_final patterns  
**Destination:** `murphy_v3/infrastructure/storage.py`  
**Technology:** S3-compatible (MinIO/AWS S3)  
**Features:**
- Object storage
- Artifact storage
- Secure downloads
- Backup support

**Status:** ⏳ Pending

#### Monitoring System
**Extract From:** NEW (based on requirements)  
**Destination:** `murphy_v3/infrastructure/monitoring.py`  
**Technology:** Prometheus + Grafana  
**Features:**
- Metrics collection
- Health checks (liveness, readiness)
- Request tracing
- Alerting

**Status:** ⏳ Pending

---

### Phase 9: API & Frontend

#### REST API
**Extract From:** murphy_system_working (clean patterns)  
**Source File:** `murphy_system_working/murphy_complete_backend.py`  
**Destination:** `murphy_v3/api/`  
**Reason:** Cleanest API structure, good patterns  
**Technology:** FastAPI

Endpoints structure:
- `api/routes/auth.py` - Authentication
- `api/routes/forms.py` - Form submissions
- `api/routes/tasks.py` - Task management
- `api/routes/corrections.py` - Correction submissions
- `api/routes/hitl.py` - HITL approvals
- `api/routes/system.py` - System info, health

**Status:** ⏳ Pending

#### WebSocket Support
**Extract From:** murphy_system_working  
**Source:** WebSocket implementation  
**Destination:** `murphy_v3/api/websocket.py`  
**Reason:** Real-time updates for frontend  
**Status:** ⏳ Pending

#### React Frontend
**Extract From:** murphy_system_working  
**Source File:** `murphy_system_working/murphy_complete_ui.html`  
**Destination:** `murphy_v3/ui/frontend/`  
**Reason:** Modern, responsive UI  
**Technology:** React 18 + TypeScript

**Status:** ⏳ Pending

---

## Extraction Priority Order

### Week 1: Foundation
1. Configuration (✅ Done)
2. Exceptions (🔄 In Progress)
3. Logging
4. Database pooling
5. Event bus
6. Security plane (11 modules)

### Week 2: Core Systems
1. Two-Phase Orchestrator
2. Universal Control Plane
3. 7 Engines
4. ExecutionPacket system
5. Session manager
6. API gateway

### Week 3: AI/ML
1. Murphy Validation
2. Shadow Agent (+ 11 patterns from murphy_complete_final)
3. Swarm Knowledge Pipeline
4. Dynamic Gates
5. Learning Engine

### Week 4: Business
1. Inoni Business Automation (5 engines)
2. B2B Negotiation Agents (NEW)
3. SwissKiss Integration
4. Calendar Scheduler
5. Librarian System

### Week 5: Advanced
1. Multi-Agent Book Generator
2. Intelligent System Generator
3. Payment Verification
4. Artifact Generation

### Week 6-8: Competitive
1. Pre-built Integrations (20+)
2. Visual Workflow Builder
3. Marketplace Platform
4. Mobile Apps
5. AI Copilot

---

## Quality Checklist (Per Module)

Before marking any extraction as "✅ Complete":

- [ ] Code extracted and adapted for v3 architecture
- [ ] Tests created (90%+ coverage)
- [ ] Documentation written
- [ ] Type hints added (95%+ coverage)
- [ ] Docstrings complete
- [ ] Security review passed
- [ ] Performance benchmarks met
- [ ] Integration tests passing
- [ ] Code review approved

---

## Next Actions

1. Begin Week 1 extractions (foundation)
2. Create specialized agents for each stream
3. Start parallel construction
4. Quality gate after each module
5. Human approval at phase boundaries

---

**Status:** Roadmap complete, ready for systematic extraction and consolidation. 🚀

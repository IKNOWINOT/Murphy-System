## Integration Points

### External APIs

| Service | Integration Method | Purpose |
|---------|-------------------|---------|
| **Groq** | REST API + Key Rotation | Primary LLM provider |
| **Aristotle** | REST API | Alternative LLM |
| **Stripe** | Python SDK | Payment processing |
| **Twilio** | REST API | SMS/Voice |
| **SendGrid** | REST API | Email |
| **GitHub** | REST API + GitPython | Code integration |
| **AWS** | boto3 SDK | Cloud storage |
| **GCP** | google-cloud SDK | Cloud storage |
| **Azure** | azure SDK | Cloud storage |
| **Fiverr** | REST API (Business) | Freelancer HITL validation |
| **Upwork** | REST API | Freelancer HITL validation |

### Internal Integrations

| Component A | Component B | Integration Type |
|-------------|-------------|------------------|
| REST API | All Systems | Function calls |
| Form Intake | Confidence Engine | Validation pipeline |
| Confidence Engine | HITL System | Approval workflow |
| Freelancer Validator | HITL System | External human validation → InterventionResponse |
| Freelancer Validator | Budget Manager | Org-level spend authorization |
| Freelancer Validator | Credential Verifier | Public-record verification (BBB, license boards) |
| Execution Engine | Universal Control Plane | Engine execution |
| Execution Engine | Inoni Business | Business execution |
| Learning Engine | Execution Engine | Telemetry collection |
| Integration Engine | HITL System | Safety approval |
| Security Plane | REST API | Middleware |

### Database Schema

**Primary Tables:**
- `submissions` - Form submissions
- `execution_packets` - Encrypted execution plans
- `corrections` - User corrections
- `hitl_interventions` - HITL approval requests
- `sessions` - Execution sessions
- `integrations` - Registered integrations
- `shadow_agent_training` - Training data
- `telemetry` - Execution metrics

**Relationships:**
- `submissions` → `execution_packets` (1:1)
- `submissions` → `corrections` (1:many)
- `execution_packets` → `hitl_interventions` (1:many)
- `sessions` → `telemetry` (1:many)

---

## System Boundaries

### Input Boundaries

**Accepted Inputs:**
- JSON requests (validated with Pydantic)
- YAML plans
- Natural language descriptions
- File uploads (plans, configurations)
- WebSocket messages
- CLI commands

**Input Validation:**
- Schema validation (Pydantic)
- Size limits (configurable)
- Type checking
- Sanitization (basic)

⚠️ **Security Gap:** No advanced input sanitization beyond Pydantic

### Output Boundaries

**Generated Outputs:**
- JSON responses
- Generated plans
- Execution results
- Correction patterns
- System metrics
- Logs and telemetry

**Output Formats:**
- REST API responses (JSON)
- WebSocket events
- Log files
- Database records
- File artifacts

### Resource Boundaries

**Compute:**
- LLM API rate limits (Groq key rotation)
- CPU/Memory limits (no explicit limits)
- Concurrent execution (asyncio-based)

**Storage:**
- Database (PostgreSQL)
- File system (logs, workspaces)
- Redis (caching - optional)

**Network:**
- Inbound: REST API (port 8000)
- Outbound: External APIs, LLMs

⚠️ **Security Gap:** No rate limiting on API endpoints

---

## Component Interactions

### Critical Dependencies

```
murphy_system_1.0_runtime.py
    ├─ Requires: universal_control_plane.py
    ├─ Requires: inoni_business_automation.py
    ├─ Requires: two_phase_orchestrator.py
    ├─ Requires: src/runtime/app.py
    └─ Requires: All src/ modules

universal_control_plane.py
    ├─ Requires: 7 engines (sensor, actuator, database, api, content, command, agent)
    └─ Requires: Module manager

src/runtime/app.py
    ├─ Requires: Execution engine
    ├─ Requires: Learning engine
    └─ Requires: HITL system

two_phase_orchestrator.py
    ├─ Requires: Universal Control Plane
    ├─ Requires: Inoni Business Automation
    └─ Requires: Session manager

src/execution_engine/
    ├─ Requires: Confidence engine
    ├─ Requires: Workflow orchestrator
    └─ Requires: State machine

src/learning_engine/
    ├─ Requires: Correction storage
    ├─ Requires: Pattern extractor
    └─ Requires: Shadow agent trainer
```

### Circular Dependencies

⚠️ **Potential Issues:**
- Some modules may have circular imports
- Needs investigation in Phase 2

### Tight Coupling

⚠️ **Areas of Concern:**
- REST API tightly coupled to all form handlers
- Execution engine tightly coupled to control plane
- Some bots have direct database access

---


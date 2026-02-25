# Module Mapping: murphy_implementation → murphy_integrated

## Overview
This document maps each file from murphy_implementation to its target location in murphy_integrated (murphy_runtime_analysis).

## Phase 1: Form Intake System

### Source: murphy_implementation/forms/
| Source File | Target Location | Action | Notes |
|------------|----------------|--------|-------|
| `forms/__init__.py` | `src/form_intake/__init__.py` | COPY | New module |
| `forms/schemas.py` | `src/form_intake/schemas.py` | COPY | Pydantic models |
| `forms/handlers.py` | `src/form_intake/handlers.py` | COPY | Form processing |
| `forms/api.py` | `src/form_intake/api.py` | MERGE | Integrate with murphy_complete_backend.py |

### Source: murphy_implementation/plan/
| Source File | Target Location | Action | Notes |
|------------|----------------|--------|-------|
| `plan/__init__.py` | `src/form_intake/__init__.py` | MERGE | Add to existing |
| `plan/models.py` | `src/form_intake/plan_models.py` | COPY | Plan data structures |
| `plan/decomposer.py` | `src/form_intake/plan_decomposer.py` | COPY | Task decomposition |

## Phase 2: Murphy Validation Enhancement

### Source: murphy_implementation/validation/
| Source File | Target Location | Action | Notes |
|------------|----------------|--------|-------|
| `validation/__init__.py` | `src/confidence_engine/__init__.py` | MERGE | Add to existing |
| `validation/models.py` | `src/confidence_engine/murphy_models.py` | COPY | New data models |
| `validation/uncertainty_calculator.py` | `src/confidence_engine/uncertainty_calculator.py` | COPY | UD/UA/UI/UR/UG |
| `validation/murphy_gate.py` | `src/confidence_engine/murphy_gate.py` | COPY | Gate logic |
| `validation/murphy_validator.py` | `src/confidence_engine/murphy_validator.py` | INTEGRATE | Combine with existing confidence_calculator.py |
| `validation/external_validator.py` | `src/confidence_engine/external_validator.py` | COPY | External validation |
| `validation/credential_interface.py` | `src/confidence_engine/credential_interface.py` | COPY | Credential checking |
| `validation/credential_verifier.py` | `src/confidence_engine/credential_verifier.py` | COPY | Credential verification |

### Source: murphy_implementation/risk/
| Source File | Target Location | Action | Notes |
|------------|----------------|--------|-------|
| `risk/__init__.py` | `src/confidence_engine/risk/__init__.py` | COPY | New submodule |
| `risk/risk_database.py` | `src/confidence_engine/risk/risk_database.py` | COPY | Risk patterns |
| `risk/risk_lookup.py` | `src/confidence_engine/risk/risk_lookup.py` | COPY | Risk matching |
| `risk/risk_scoring.py` | `src/confidence_engine/risk/risk_scoring.py` | COPY | Risk scoring |
| `risk/risk_mitigation.py` | `src/confidence_engine/risk/risk_mitigation.py` | COPY | Mitigation strategies |
| `risk/risk_storage.py` | `src/confidence_engine/risk/risk_storage.py` | COPY | Risk persistence |

### Source: murphy_implementation/performance/
| Source File | Target Location | Action | Notes |
|------------|----------------|--------|-------|
| `performance/optimization.py` | `src/confidence_engine/performance_optimization.py` | COPY | Caching & optimization |

## Phase 3: Execution Orchestrator

### Source: murphy_implementation/execution/
| Source File | Target Location | Action | Notes |
|------------|----------------|--------|-------|
| `execution/__init__.py` | `src/execution_engine/__init__.py` | MERGE | Add to existing |
| `execution/models.py` | `src/execution_engine/form_execution_models.py` | COPY | Form execution models |
| `execution/context.py` | `src/execution_engine/execution_context.py` | COPY | Execution state |
| `execution/executor.py` | `src/execution_engine/form_executor.py` | INTEGRATE | Connect to existing execution_orchestrator |

## Phase 4: HITL Monitor

### Source: murphy_implementation/hitl/
| Source File | Target Location | Action | Notes |
|------------|----------------|--------|-------|
| `hitl/__init__.py` | `src/supervisor_system/__init__.py` | MERGE | Add to existing |
| `hitl/models.py` | `src/supervisor_system/hitl_models.py` | COPY | HITL data models |
| `hitl/monitor.py` | `src/supervisor_system/hitl_monitor.py` | INTEGRATE | Connect to existing supervisor |

## Phase 5: Correction Capture

### Source: murphy_implementation/correction/
| Source File | Target Location | Action | Notes |
|------------|----------------|--------|-------|
| `correction/__init__.py` | `src/learning_engine/__init__.py` | MERGE | Add to existing |
| `correction/correction_model.py` | `src/learning_engine/correction_models.py` | COPY | Correction data models |
| `correction/correction_capture.py` | `src/learning_engine/correction_capture.py` | INTEGRATE | Connect to existing learning_system |
| `correction/correction_metadata.py` | `src/learning_engine/correction_metadata.py` | COPY | Metadata enrichment |
| `correction/correction_storage.py` | `src/learning_engine/correction_storage.py` | COPY | Correction persistence |
| `correction/feedback_system.py` | `src/learning_engine/feedback_system.py` | COPY | Human feedback |
| `correction/validation_and_patterns.py` | `src/learning_engine/pattern_extraction.py` | COPY | Pattern mining |

## Phase 6: Shadow Agent Training

### Source: murphy_implementation/training/
| Source File | Target Location | Action | Notes |
|------------|----------------|--------|-------|
| `training/__init__.py` | `src/learning_engine/__init__.py` | MERGE | Add to existing |
| `training/data_preparation.py` | `src/learning_engine/training_data_prep.py` | COPY | Training data pipeline |
| `training/training_pipeline.py` | `src/learning_engine/training_pipeline.py` | COPY | Model training |
| `training/shadow_agent.py` | `src/learning_engine/shadow_agent.py` | INTEGRATE | Connect to existing LLM integration |

## Backend Integration

### Source: murphy_implementation/main.py
| Component | Target Location | Action | Notes |
|-----------|----------------|--------|-------|
| FastAPI app setup | `murphy_complete_backend.py` | MERGE | Add FastAPI routes to existing backend |
| Form endpoints | `murphy_complete_backend.py` | MERGE | Add /api/forms/* routes |
| Health checks | `murphy_complete_backend.py` | MERGE | Add health endpoints |
| CORS middleware | `murphy_complete_backend.py` | MERGE | Add CORS config |

## Import Path Changes

### Before (murphy_implementation):
```python
from murphy_implementation.forms.schemas import PlanUploadForm
from murphy_implementation.validation.murphy_validator import MurphyValidator
from murphy_implementation.execution.executor import FormDrivenExecutor
```

### After (murphy_integrated):
```python
from src.form_intake.schemas import PlanUploadForm
from src.confidence_engine.murphy_validator import MurphyValidator
from src.execution_engine.form_executor import FormDrivenExecutor
```

## Integration Points

### 1. Confidence Engine Integration
**File:** `src/confidence_engine/murphy_validator.py`

**Integrates:**
- Existing: `confidence_calculator.py` (G/D/H formula)
- New: `uncertainty_calculator.py` (UD/UA/UI/UR/UG)
- New: `murphy_gate.py` (threshold decisions)

**Strategy:**
```python
class UnifiedConfidenceEngine:
    def __init__(self):
        # Existing
        self.confidence_calculator = ConfidenceCalculator()  # G/D/H
        
        # New
        self.uncertainty_calculator = UncertaintyCalculator()  # UD/UA/UI/UR/UG
        self.murphy_gate = MurphyGate()
    
    def calculate_confidence(self, task):
        # Get both scores
        gdh_score = self.confidence_calculator.calculate(task)
        uncertainty_scores = self.uncertainty_calculator.calculate(task)
        
        # Merge and decide
        final_score = self._merge_scores(gdh_score, uncertainty_scores)
        gate_result = self.murphy_gate.evaluate(final_score, uncertainty_scores)
        
        return gate_result
```

### 2. Execution Engine Integration
**File:** `src/execution_engine/form_executor.py`

**Integrates:**
- Existing: `execution_orchestrator.py`
- Existing: `phase_controller.py` (from confidence_engine)
- New: Form-driven execution

**Strategy:**
```python
class FormDrivenExecutor:
    def __init__(self):
        # Use existing orchestrator
        from .execution_orchestrator import ExecutionOrchestrator
        self.orchestrator = ExecutionOrchestrator()
        
        # Use existing phase controller
        from ..confidence_engine.phase_controller import PhaseController
        self.phase_controller = PhaseController()
        
        # Add Murphy validation
        from ..confidence_engine.murphy_validator import UnifiedConfidenceEngine
        self.confidence_engine = UnifiedConfidenceEngine()
    
    async def execute_form_task(self, form_data):
        # Convert form to task
        task = self._form_to_task(form_data)
        
        # Validate with Murphy
        validation = self.confidence_engine.calculate_confidence(task)
        
        if not validation.approved:
            return {"status": "rejected"}
        
        # Execute with existing orchestrator
        result = await self.orchestrator.execute(task)
        
        return result
```

### 3. Learning Engine Integration
**File:** `src/learning_engine/correction_capture.py`

**Integrates:**
- Existing: `learning_system.py`
- New: Correction capture and pattern extraction

**Strategy:**
```python
class IntegratedCorrectionSystem:
    def __init__(self):
        # Use existing learning system
        from .learning_system import LearningSystem
        self.learning_system = LearningSystem()
        
        # Add new correction capture
        self.correction_recorder = CorrectionRecorder()
        self.pattern_extractor = PatternExtractor()
    
    def capture_correction(self, task_id, correction_data):
        # Record correction
        correction = self.correction_recorder.record(task_id, correction_data)
        
        # Extract patterns
        patterns = self.pattern_extractor.extract(correction)
        
        # Feed to existing learning engine
        self.learning_system.learn_from_correction(patterns)
        
        return correction
```

### 4. Supervisor Integration
**File:** `src/supervisor_system/hitl_monitor.py`

**Integrates:**
- Existing: `supervisor_system/` modules
- New: HITL checkpoints and interventions

**Strategy:**
```python
class IntegratedHITLMonitor:
    def __init__(self):
        # Use existing supervisor
        from .supervisor import Supervisor
        self.supervisor = Supervisor()
        
        # Add HITL monitoring
        self.hitl_monitor = HumanInTheLoopMonitor()
    
    def check_intervention_needed(self, task, phase):
        # Check with existing supervisor
        supervisor_decision = self.supervisor.should_intervene(task)
        
        # Check with HITL monitor
        hitl_decision = self.hitl_monitor.check_checkpoint(task, phase)
        
        # Combine decisions
        return supervisor_decision or hitl_decision
```

## File Count Summary

### murphy_implementation (Source)
- Total files: 54 Python files
- Forms: 4 files
- Plan: 3 files
- Validation: 8 files
- Risk: 6 files
- Performance: 1 file
- Execution: 4 files
- HITL: 3 files
- Correction: 7 files
- Training: 3 files
- Deployment: 15 files (not integrating - separate concern)

### murphy_integrated (Target)
- Existing: 272 Python files
- Adding: ~39 Python files (excluding deployment)
- Total after integration: ~311 Python files

## Next Steps

1. ✅ Create murphy_integrated/ workspace
2. ✅ Copy murphy_backup_extracted to murphy_integrated
3. Create target directories in murphy_integrated/src/
4. Copy files according to mapping
5. Update imports in copied files
6. Create integration classes
7. Test each module
8. Integrate with murphy_complete_backend.py
9. Update murphy_ui_final.html
10. Final testing

---

**Ready to proceed with file copying and integration.**
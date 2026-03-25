"""
Procedural Distiller for Murphy System

Turns learned sequence families into procedural templates that can be
executed in Mode B. This module bridges the gap between exploratory
learning (Mode A) and governed procedural execution (Mode B).

The distiller creates executable procedures from:
- Permutation policy registry (learned sequence families)
- Golden path bridge (successful execution paths)
- ML strategy engine (scoring and ranking)

Output procedures follow the pattern from spec Section 5.1:
    "first check source A, then compare with source C,
     then request HITL only if mismatch persists,
     then run route B, otherwise fallback to baseline policy"

Reference: Permutation Calibration Application Spec Section 7
Owner: INONI LLC / Corey Post
"""

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)


class StepType(str, Enum):
    """Types of procedural steps."""
    CHECK = "check"               # Check/query a source
    COMPARE = "compare"           # Compare results
    VALIDATE = "validate"         # Validate conditions
    ROUTE = "route"               # Route to a handler
    ESCALATE = "escalate"         # Escalate to HITL/higher authority
    TRANSFORM = "transform"       # Transform/process data
    FALLBACK = "fallback"         # Fallback action
    CONDITIONAL = "conditional"   # Conditional branch


class ConditionType(str, Enum):
    """Types of conditions for conditional steps."""
    CONFIDENCE_ABOVE = "confidence_above"
    CONFIDENCE_BELOW = "confidence_below"
    MISMATCH_DETECTED = "mismatch_detected"
    THRESHOLD_EXCEEDED = "threshold_exceeded"
    TIMEOUT_OCCURRED = "timeout_occurred"
    ERROR_OCCURRED = "error_occurred"
    CUSTOM = "custom"


class ProcedureStatus(str, Enum):
    """Status of a procedural template."""
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEPRECATED = "deprecated"


@dataclass
class ProceduralStep:
    """A single step in a procedural template."""
    step_id: str
    step_type: StepType
    name: str
    description: str
    
    # Step configuration
    source: Optional[str] = None        # Source to check/query
    target: Optional[str] = None        # Target for routing/comparison
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Conditions (for conditional steps)
    condition_type: Optional[ConditionType] = None
    condition_value: Any = None
    on_true_step: Optional[str] = None  # step_id to jump to if true
    on_false_step: Optional[str] = None # step_id to jump to if false
    
    # Timing
    timeout_ms: int = 30000
    retry_count: int = 3
    retry_delay_ms: int = 1000
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProceduralTemplate:
    """A complete procedural template distilled from learned patterns.
    
    This represents an executable procedure that Murphy can use in
    Mode B for governed, repeatable execution.
    """
    template_id: str
    name: str
    description: str
    domain: str
    
    # The ordered steps
    steps: List[ProceduralStep]
    entry_step_id: str
    
    # Source tracking
    source_sequence_id: Optional[str] = None  # From permutation registry
    source_path_id: Optional[str] = None       # From golden path bridge
    
    # Status and versioning
    status: ProcedureStatus = ProcedureStatus.DRAFT
    version: int = 1
    
    # Metrics from source
    confidence_score: float = 0.5
    success_rate: float = 0.0
    avg_execution_time_ms: float = 0.0
    
    # Gate requirements
    requires_gate_approval: bool = True
    gate_approved: bool = False
    gate_approver: Optional[str] = None
    
    # HITL requirements
    max_autonomous_executions: int = 10
    hitl_review_frequency: int = 5  # Review after every N executions
    
    # Fallback
    fallback_template_id: Optional[str] = None
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    activated_at: Optional[str] = None
    last_used_at: Optional[str] = None
    
    # Execution tracking
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DistillationResult:
    """Result of distilling a sequence into a procedure."""
    result_id: str
    template_id: str
    source_type: str  # "sequence" or "path"
    source_id: str
    success: bool
    steps_created: int
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ProceduralDistiller:
    """Converts learned sequence families into executable procedural templates.
    
    This bridges Mode A (exploratory) to Mode B (procedural) by:
    1. Taking learned sequences from the permutation policy registry
    2. Optionally incorporating golden path execution specs
    3. Generating step-by-step procedural templates
    4. Managing template lifecycle and versioning
    """
    
    _MAX_TEMPLATES = 5_000
    _MAX_HISTORY = 10_000
    
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._templates: Dict[str, ProceduralTemplate] = {}
        self._domain_index: Dict[str, List[str]] = {}
        self._status_index: Dict[ProcedureStatus, List[str]] = {}
        self._distillation_history: List[DistillationResult] = []
        self._step_generators: Dict[str, Callable] = {}
        
        # Register default step generators
        self._register_default_generators()
        
        logger.info("ProceduralDistiller initialized")
    
    # ------------------------------------------------------------------
    # Step Generator Registration
    # ------------------------------------------------------------------
    
    def register_step_generator(
        self,
        item_type: str,
        generator: Callable[[str, Dict[str, Any]], ProceduralStep],
    ) -> None:
        """Register a step generator for an item type.
        
        Args:
            item_type: Type of intake item (connector, api, etc.)
            generator: Function (item_id, context) -> ProceduralStep
        """
        self._step_generators[item_type] = generator
        logger.info("Registered step generator for item type '%s'", item_type)
    
    def _register_default_generators(self) -> None:
        """Register default step generators for common item types."""
        
        def connector_generator(item_id: str, ctx: Dict[str, Any]) -> ProceduralStep:
            return ProceduralStep(
                step_id=f"step-{uuid.uuid4().hex[:8]}",
                step_type=StepType.CHECK,
                name=f"Query {item_id}",
                description=f"Query connector {item_id} for data",
                source=item_id,
                parameters=ctx.get("parameters", {}),
                timeout_ms=ctx.get("timeout_ms", 30000),
            )
        
        def api_generator(item_id: str, ctx: Dict[str, Any]) -> ProceduralStep:
            return ProceduralStep(
                step_id=f"step-{uuid.uuid4().hex[:8]}",
                step_type=StepType.CHECK,
                name=f"Call API {item_id}",
                description=f"Call API endpoint {item_id}",
                source=item_id,
                parameters=ctx.get("parameters", {}),
                timeout_ms=ctx.get("timeout_ms", 10000),
            )
        
        def evidence_generator(item_id: str, ctx: Dict[str, Any]) -> ProceduralStep:
            return ProceduralStep(
                step_id=f"step-{uuid.uuid4().hex[:8]}",
                step_type=StepType.VALIDATE,
                name=f"Collect evidence {item_id}",
                description=f"Collect and validate evidence from {item_id}",
                source=item_id,
                parameters=ctx.get("parameters", {}),
            )
        
        def feedback_generator(item_id: str, ctx: Dict[str, Any]) -> ProceduralStep:
            return ProceduralStep(
                step_id=f"step-{uuid.uuid4().hex[:8]}",
                step_type=StepType.ESCALATE,
                name=f"Request feedback {item_id}",
                description=f"Request human feedback for {item_id}",
                source=item_id,
                parameters=ctx.get("parameters", {}),
            )
        
        def telemetry_generator(item_id: str, ctx: Dict[str, Any]) -> ProceduralStep:
            return ProceduralStep(
                step_id=f"step-{uuid.uuid4().hex[:8]}",
                step_type=StepType.CHECK,
                name=f"Read telemetry {item_id}",
                description=f"Read telemetry data from {item_id}",
                source=item_id,
                parameters=ctx.get("parameters", {}),
            )
        
        def routing_generator(item_id: str, ctx: Dict[str, Any]) -> ProceduralStep:
            return ProceduralStep(
                step_id=f"step-{uuid.uuid4().hex[:8]}",
                step_type=StepType.ROUTE,
                name=f"Route to {item_id}",
                description=f"Route execution to {item_id}",
                target=item_id,
                parameters=ctx.get("parameters", {}),
            )
        
        self._step_generators = {
            "connector": connector_generator,
            "api": api_generator,
            "evidence": evidence_generator,
            "feedback": feedback_generator,
            "telemetry": telemetry_generator,
            "routing": routing_generator,
            # Fallback for unknown types
            "default": connector_generator,
        }
    
    # ------------------------------------------------------------------
    # Distillation from Sequences
    # ------------------------------------------------------------------
    
    def distill_from_sequence(
        self,
        sequence_data: Dict[str, Any],
        item_types: Optional[Dict[str, str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Distill a procedural template from a sequence family.
        
        Args:
            sequence_data: Sequence family data from PermutationPolicyRegistry
            item_types: Optional mapping of item_id -> item_type
            context: Optional context for step generation
            
        Returns:
            Result dict with template_id and status
        """
        context = context or {}
        item_types = item_types or {}
        
        sequence_id = sequence_data.get("sequence_id", "unknown")
        ordering = sequence_data.get("ordering", [])
        domain = sequence_data.get("domain", "general")
        name = sequence_data.get("name", f"Procedure from {sequence_id}")
        
        if not ordering:
            return {
                "status": "error",
                "reason": "empty_ordering",
                "sequence_id": sequence_id,
            }
        
        # Generate steps from ordering
        steps: List[ProceduralStep] = []
        for i, item_id in enumerate(ordering):
            item_type = item_types.get(item_id, "default")
            generator = self._step_generators.get(item_type, self._step_generators["default"])
            
            step_ctx = dict(context)
            step_ctx["position"] = i
            step_ctx["total_steps"] = len(ordering)
            
            step = generator(item_id, step_ctx)
            steps.append(step)
        
        # Add fallback step
        fallback_step = ProceduralStep(
            step_id=f"step-fallback-{uuid.uuid4().hex[:8]}",
            step_type=StepType.FALLBACK,
            name="Fallback to baseline",
            description="Fall back to baseline policy if procedure fails",
            parameters={"fallback_to": "baseline"},
        )
        steps.append(fallback_step)
        
        # Create template
        template_id = f"proc-{uuid.uuid4().hex[:12]}"
        template = ProceduralTemplate(
            template_id=template_id,
            name=name,
            description=f"Procedural template distilled from sequence {sequence_id}",
            domain=domain,
            steps=steps,
            entry_step_id=steps[0].step_id,
            source_sequence_id=sequence_id,
            confidence_score=sequence_data.get("confidence_score", 0.5),
            success_rate=sequence_data.get("success_rate", 0.0),
        )
        
        # Store template
        with self._lock:
            self._store_template_locked(template)
            
            result = DistillationResult(
                result_id=f"dist-{uuid.uuid4().hex[:12]}",
                template_id=template_id,
                source_type="sequence",
                source_id=sequence_id,
                success=True,
                steps_created=len(steps),
            )
            capped_append(self._distillation_history, result, self._MAX_HISTORY)
        
        logger.info(
            "Distilled template %s from sequence %s with %d steps",
            template_id, sequence_id, len(steps)
        )
        
        return {
            "status": "ok",
            "template_id": template_id,
            "sequence_id": sequence_id,
            "steps_created": len(steps),
            "domain": domain,
        }
    
    def distill_from_golden_path(
        self,
        path_data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Distill a procedural template from a golden path.
        
        Args:
            path_data: Golden path data from GoldenPathBridge
            context: Optional context for step generation
            
        Returns:
            Result dict with template_id and status
        """
        context = context or {}
        
        path_id = path_data.get("path_id", "unknown")
        execution_spec = path_data.get("execution_spec", {})
        domain = path_data.get("domain", "general")
        task_pattern = path_data.get("task_pattern", "unknown")
        
        spec_steps = execution_spec.get("steps", [])
        if not spec_steps:
            return {
                "status": "error",
                "reason": "no_steps_in_spec",
                "path_id": path_id,
            }
        
        # Convert spec steps to procedural steps
        steps: List[ProceduralStep] = []
        for i, spec_step in enumerate(spec_steps):
            step = ProceduralStep(
                step_id=f"step-{uuid.uuid4().hex[:8]}",
                step_type=StepType(spec_step.get("type", "check")),
                name=spec_step.get("name", f"Step {i+1}"),
                description=spec_step.get("description", ""),
                source=spec_step.get("source"),
                target=spec_step.get("target"),
                parameters=spec_step.get("parameters", {}),
            )
            steps.append(step)
        
        # Add fallback
        fallback_step = ProceduralStep(
            step_id=f"step-fallback-{uuid.uuid4().hex[:8]}",
            step_type=StepType.FALLBACK,
            name="Fallback to baseline",
            description="Fall back to baseline policy if procedure fails",
        )
        steps.append(fallback_step)
        
        # Create template
        template_id = f"proc-{uuid.uuid4().hex[:12]}"
        template = ProceduralTemplate(
            template_id=template_id,
            name=f"Procedure from golden path: {task_pattern}",
            description=f"Procedural template from golden path {path_id}",
            domain=domain,
            steps=steps,
            entry_step_id=steps[0].step_id,
            source_path_id=path_id,
            confidence_score=path_data.get("confidence_score", 0.7),
        )
        
        # Store template
        with self._lock:
            self._store_template_locked(template)
            
            result = DistillationResult(
                result_id=f"dist-{uuid.uuid4().hex[:12]}",
                template_id=template_id,
                source_type="path",
                source_id=path_id,
                success=True,
                steps_created=len(steps),
            )
            capped_append(self._distillation_history, result, self._MAX_HISTORY)
        
        logger.info(
            "Distilled template %s from golden path %s with %d steps",
            template_id, path_id, len(steps)
        )
        
        return {
            "status": "ok",
            "template_id": template_id,
            "path_id": path_id,
            "steps_created": len(steps),
            "domain": domain,
        }
    
    def _store_template_locked(self, template: ProceduralTemplate) -> None:
        """Store a template and update indices (must hold lock)."""
        if len(self._templates) >= self._MAX_TEMPLATES:
            # Evict oldest deprecated templates
            deprecated = [t for t in self._templates.values() 
                         if t.status == ProcedureStatus.DEPRECATED]
            if deprecated:
                deprecated.sort(key=lambda t: t.created_at)
                for t in deprecated[:len(deprecated)//2]:
                    self._remove_template_locked(t.template_id)
        
        self._templates[template.template_id] = template
        
        if template.domain not in self._domain_index:
            self._domain_index[template.domain] = []
        self._domain_index[template.domain].append(template.template_id)
        
        if template.status not in self._status_index:
            self._status_index[template.status] = []
        self._status_index[template.status].append(template.template_id)
    
    def _remove_template_locked(self, template_id: str) -> None:
        """Remove a template from storage and indices (must hold lock)."""
        template = self._templates.pop(template_id, None)
        if template:
            if template_id in self._domain_index.get(template.domain, []):
                self._domain_index[template.domain].remove(template_id)
            if template_id in self._status_index.get(template.status, []):
                self._status_index[template.status].remove(template_id)
    
    # ------------------------------------------------------------------
    # Template Lifecycle
    # ------------------------------------------------------------------
    
    def activate_template(
        self,
        template_id: str,
        approver: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Activate a template for Mode B execution.
        
        Args:
            template_id: ID of template to activate
            approver: Optional approver identity
            
        Returns:
            Status dict
        """
        with self._lock:
            template = self._templates.get(template_id)
            if template is None:
                return {"status": "error", "reason": "template_not_found"}
            
            if template.requires_gate_approval and not template.gate_approved:
                if approver:
                    template.gate_approved = True
                    template.gate_approver = approver
                else:
                    return {"status": "error", "reason": "gate_approval_required"}
            
            old_status = template.status
            template.status = ProcedureStatus.ACTIVE
            template.activated_at = datetime.now(timezone.utc).isoformat()
            
            # Update status index
            if template_id in self._status_index.get(old_status, []):
                self._status_index[old_status].remove(template_id)
            if ProcedureStatus.ACTIVE not in self._status_index:
                self._status_index[ProcedureStatus.ACTIVE] = []
            self._status_index[ProcedureStatus.ACTIVE].append(template_id)
        
        logger.info("Activated template %s", template_id)
        return {"status": "ok", "template_id": template_id, "activated_at": template.activated_at}
    
    def suspend_template(
        self,
        template_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Suspend a template from Mode B execution.
        
        Args:
            template_id: ID of template to suspend
            reason: Optional reason for suspension
            
        Returns:
            Status dict
        """
        with self._lock:
            template = self._templates.get(template_id)
            if template is None:
                return {"status": "error", "reason": "template_not_found"}
            
            old_status = template.status
            template.status = ProcedureStatus.SUSPENDED
            template.metadata["suspension_reason"] = reason
            
            # Update status index
            if template_id in self._status_index.get(old_status, []):
                self._status_index[old_status].remove(template_id)
            if ProcedureStatus.SUSPENDED not in self._status_index:
                self._status_index[ProcedureStatus.SUSPENDED] = []
            self._status_index[ProcedureStatus.SUSPENDED].append(template_id)
        
        logger.info("Suspended template %s: %s", template_id, reason)
        return {"status": "ok", "template_id": template_id, "suspended": True, "reason": reason}
    
    def deprecate_template(
        self,
        template_id: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Deprecate a template.
        
        Args:
            template_id: ID of template to deprecate
            reason: Optional reason for deprecation
            
        Returns:
            Status dict
        """
        with self._lock:
            template = self._templates.get(template_id)
            if template is None:
                return {"status": "error", "reason": "template_not_found"}
            
            old_status = template.status
            template.status = ProcedureStatus.DEPRECATED
            template.metadata["deprecation_reason"] = reason
            
            # Update status index
            if template_id in self._status_index.get(old_status, []):
                self._status_index[old_status].remove(template_id)
            if ProcedureStatus.DEPRECATED not in self._status_index:
                self._status_index[ProcedureStatus.DEPRECATED] = []
            self._status_index[ProcedureStatus.DEPRECATED].append(template_id)
        
        logger.info("Deprecated template %s: %s", template_id, reason)
        return {"status": "ok", "template_id": template_id, "deprecated": True, "reason": reason}
    
    # ------------------------------------------------------------------
    # Execution Recording
    # ------------------------------------------------------------------
    
    def record_execution(
        self,
        template_id: str,
        success: bool,
        execution_time_ms: float = 0.0,
    ) -> Dict[str, Any]:
        """Record a template execution result.
        
        Args:
            template_id: ID of executed template
            success: Whether execution succeeded
            execution_time_ms: Execution time
            
        Returns:
            Status dict with updated metrics
        """
        with self._lock:
            template = self._templates.get(template_id)
            if template is None:
                return {"status": "error", "reason": "template_not_found"}
            
            template.execution_count += 1
            if success:
                template.success_count += 1
            else:
                template.failure_count += 1
            
            # Update running average execution time
            n = template.execution_count
            template.avg_execution_time_ms = (
                (template.avg_execution_time_ms * (n - 1) + execution_time_ms) / n
            )
            
            template.last_used_at = datetime.now(timezone.utc).isoformat()
            
            # Calculate success rate
            success_rate = template.success_count / max(1, template.execution_count)
            template.success_rate = success_rate
            
            return {
                "status": "ok",
                "template_id": template_id,
                "execution_count": template.execution_count,
                "success_rate": round(success_rate, 4),
                "avg_execution_time_ms": round(template.avg_execution_time_ms, 2),
            }
    
    # ------------------------------------------------------------------
    # Query Methods
    # ------------------------------------------------------------------
    
    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Get a template by ID."""
        with self._lock:
            template = self._templates.get(template_id)
            if template is None:
                return None
            return self._template_to_dict(template)
    
    def _template_to_dict(self, template: ProceduralTemplate) -> Dict[str, Any]:
        """Convert template to dict representation."""
        return {
            "template_id": template.template_id,
            "name": template.name,
            "description": template.description,
            "domain": template.domain,
            "steps": [self._step_to_dict(s) for s in template.steps],
            "entry_step_id": template.entry_step_id,
            "source_sequence_id": template.source_sequence_id,
            "source_path_id": template.source_path_id,
            "status": template.status.value,
            "version": template.version,
            "confidence_score": round(template.confidence_score, 4),
            "success_rate": round(template.success_rate, 4),
            "avg_execution_time_ms": round(template.avg_execution_time_ms, 2),
            "requires_gate_approval": template.requires_gate_approval,
            "gate_approved": template.gate_approved,
            "gate_approver": template.gate_approver,
            "execution_count": template.execution_count,
            "success_count": template.success_count,
            "failure_count": template.failure_count,
            "created_at": template.created_at,
            "activated_at": template.activated_at,
            "last_used_at": template.last_used_at,
            "metadata": template.metadata,
        }
    
    def _step_to_dict(self, step: ProceduralStep) -> Dict[str, Any]:
        """Convert step to dict representation."""
        return {
            "step_id": step.step_id,
            "step_type": step.step_type.value,
            "name": step.name,
            "description": step.description,
            "source": step.source,
            "target": step.target,
            "parameters": step.parameters,
            "condition_type": step.condition_type.value if step.condition_type else None,
            "condition_value": step.condition_value,
            "on_true_step": step.on_true_step,
            "on_false_step": step.on_false_step,
            "timeout_ms": step.timeout_ms,
            "retry_count": step.retry_count,
            "metadata": step.metadata,
        }
    
    def find_templates(
        self,
        domain: Optional[str] = None,
        status: Optional[ProcedureStatus] = None,
        min_confidence: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Find templates matching criteria."""
        with self._lock:
            candidates = list(self._templates.values())
            
            if domain is not None:
                candidates = [t for t in candidates if t.domain == domain]
            if status is not None:
                candidates = [t for t in candidates if t.status == status]
            if min_confidence > 0.0:
                candidates = [t for t in candidates if t.confidence_score >= min_confidence]
            
            candidates.sort(key=lambda t: t.confidence_score, reverse=True)
            return [self._template_to_dict(t) for t in candidates]
    
    def get_active_templates(self, domain: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all active templates for Mode B execution."""
        return self.find_templates(domain=domain, status=ProcedureStatus.ACTIVE)
    
    def get_best_template_for_domain(
        self,
        domain: str,
        require_active: bool = True,
    ) -> Optional[Dict[str, Any]]:
        """Get the best template for a domain."""
        status = ProcedureStatus.ACTIVE if require_active else None
        templates = self.find_templates(domain=domain, status=status)
        return templates[0] if templates else None
    
    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get distiller statistics."""
        with self._lock:
            total = len(self._templates)
            by_status = {s.value: len(self._status_index.get(s, [])) for s in ProcedureStatus}
            
            active = [t for t in self._templates.values() if t.status == ProcedureStatus.ACTIVE]
            avg_active_success = (
                sum(t.success_rate for t in active) / len(active)
                if active else 0.0
            )
            
            return {
                "status": "ok",
                "total_templates": total,
                "by_status": by_status,
                "domains": list(self._domain_index.keys()),
                "distillation_count": len(self._distillation_history),
                "active_count": by_status.get("active", 0),
                "avg_active_success_rate": round(avg_active_success, 4),
            }
    
    def get_status(self) -> Dict[str, Any]:
        """Get distiller operational status."""
        stats = self.get_statistics()
        return {
            "engine": "ProceduralDistiller",
            "operational": True,
            **stats,
        }
    
    # ------------------------------------------------------------------
    # Reset
    # ------------------------------------------------------------------
    
    def clear(self) -> None:
        """Clear all distiller state."""
        with self._lock:
            self._templates.clear()
            self._domain_index.clear()
            self._status_index.clear()
            self._distillation_history.clear()
        logger.info("ProceduralDistiller cleared")

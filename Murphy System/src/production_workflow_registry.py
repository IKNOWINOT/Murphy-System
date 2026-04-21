# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post | License: BSL-1.1
"""Production Workflow Registry  (label: FORGE-WORKFLOW-002).

Instead of generating a deliverable directly, the Forge now follows a
three-stage process:

    1. **Resolve** — search existing production workflows for one that
       matches the user's intent.  Decide: reuse, modify, or create new.
    2. **Execute** — run the selected/created workflow to produce the
       deliverable.
    3. **Persist + HITL** — save the workflow (growing system capability)
       and route the output through platform-side HITL review.

The registry uses Murphy System itself as the reference implementation.
Workflow steps reference real Murphy modules (MSS, MFGC, librarian, LLM
controller, etc.) so the system never reinvents the wheel.

Example workflow steps (derived from Murphy's own architecture)::

    [
        {"step_id": "scope",    "agent_role": "ScopeAnalyzer",
         "name": "Scope Analysis",
         "description": "Run MFGC gate on user request",
         "module_ref": "mfgc_adapter.MFGCSystemFactory"},
        {"step_id": "magnify",  "agent_role": "RequirementsWriter",
         "name": "Requirements Expansion",
         "description": "MSS Magnify — expand to RM+2 requirements",
         "module_ref": "mss_controls.MSSController.magnify"},
        {"step_id": "solidify", "agent_role": "ArchitectBot",
         "name": "Implementation Plan",
         "description": "MSS Solidify — RM5 implementation plan",
         "module_ref": "mss_controls.MSSController.solidify"},
        {"step_id": "generate", "agent_role": "ContentWriter",
         "name": "Content Generation",
         "description": "LLM + context → final deliverable prose",
         "module_ref": "llm_provider.MurphyLLMProvider"},
    ]
"""
from __future__ import annotations

import hashlib
import logging
import re
import threading
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reference modules — Murphy System's own architecture.
# These are the *real* module paths inside Murphy System that the Forge uses
# as building blocks.  A workflow step's ``module_ref`` points to one of
# these so the system never reinvents existing capability.
#
# WIRE-WF-001: module_ref values are intentional descriptive metadata.
# They document *which* Murphy module each workflow step corresponds to
# and populate the agent task grid in the Forge UI.  Actual execution is
# handled by the MFGC → MSS → LLM pipeline in demo_deliverable_generator.py,
# not by dynamic dispatch from these refs.  Full workflow-driven dispatch
# is tracked as a future enhancement.
# ---------------------------------------------------------------------------

MURPHY_REFERENCE_MODULES: Dict[str, str] = {
    "mfgc_gate": "mfgc_adapter.MFGCSystemFactory",
    "mss_magnify": "mss_controls.MSSController.magnify",
    "mss_solidify": "mss_controls.MSSController.solidify",
    "mss_simplify": "mss_controls.MSSController.simplify",
    "llm_generate": "llm_provider.MurphyLLMProvider.complete_messages",
    "librarian_lookup": "runtime.murphy_system_core.MurphySystem.librarian_ask",
    "confidence_score": "confidence_engine.phase_controller.PhaseController",
    "gate_synthesis": "gate_synthesis.gate_generator.GateGenerator",
    "workflow_template": "org_build_plan.workflow_templates.WorkflowTemplateLibrary",
    "hitl_review": "supervisor_system.hitl_monitor.HumanInTheLoopMonitor",
    "eu_compliance": "eu_ai_act_compliance.EUAIActComplianceEngine",
    "backup_storage": "backup_disaster_recovery.S3StorageBackend",
    "event_backbone": "event_backbone_client.get_backbone",
    "living_document": "runtime.living_document.LivingDocument",
}

# ---------------------------------------------------------------------------
# Built-in workflow templates — based on Murphy System's own patterns
# ---------------------------------------------------------------------------

_BUILTIN_WORKFLOWS: List[Dict[str, Any]] = [
    {
        "name": "General Deliverable",
        "description": "Standard MFGC → MSS → LLM pipeline for any business deliverable.",
        "category": "general",
        "query_pattern": "generate|create|build|write|make|produce|deliverable",
        "steps": [
            {
                "step_id": "scope",
                "name": "Scope Analysis",
                "description": "MFGC gate — confidence-score the request through 7-phase model",
                "agent_role": "ScopeAnalyzer",
                "module_ref": "mfgc_gate",
                "inputs": ["user_query"],
                "outputs": ["mfgc_result"],
            },
            {
                "step_id": "magnify",
                "name": "Requirements Expansion",
                "description": "MSS Magnify — expand to functional requirements + components (RM+2)",
                "agent_role": "RequirementsWriter",
                "module_ref": "mss_magnify",
                "inputs": ["user_query", "mfgc_result"],
                "outputs": ["magnify_result"],
            },
            {
                "step_id": "solidify",
                "name": "Implementation Plan",
                "description": "MSS Solidify — convert to RM5 implementation plan with module spec",
                "agent_role": "ArchitectBot",
                "module_ref": "mss_solidify",
                "inputs": ["user_query", "mfgc_result"],
                "outputs": ["solidify_result"],
            },
            {
                "step_id": "librarian",
                "name": "Context Enrichment",
                "description": "Librarian lookup — gather domain context from knowledge base",
                "agent_role": "ResearchBot",
                "module_ref": "librarian_lookup",
                "inputs": ["user_query"],
                "outputs": ["librarian_context"],
            },
            {
                "step_id": "generate",
                "name": "Content Generation",
                "description": "LLM + all enriched context → final deliverable prose",
                "agent_role": "ContentWriter",
                "module_ref": "llm_generate",
                "inputs": ["user_query", "mfgc_result", "magnify_result", "solidify_result", "librarian_context"],
                "outputs": ["deliverable_content"],
            },
            {
                "step_id": "hitl_review",
                "name": "Platform HITL Review",
                "description": "Route deliverable through platform-side HITL for quality review",
                "agent_role": "ReviewAgent",
                "module_ref": "hitl_review",
                "inputs": ["deliverable_content"],
                "outputs": ["reviewed_deliverable"],
            },
        ],
        "reference_modules": [
            "mfgc_adapter.MFGCSystemFactory",
            "mss_controls.MSSController",
            "llm_provider.MurphyLLMProvider",
            "supervisor_system.hitl_monitor.HumanInTheLoopMonitor",
        ],
    },
    {
        "name": "Automation Blueprint",
        "description": "End-to-end automation workflow: intake → connectors → compliance → deploy.",
        "category": "devops",
        "query_pattern": "automat|workflow|pipeline|ci.?cd|deploy|integration|connector",
        "steps": [
            {
                "step_id": "scope",
                "name": "Scope Analysis",
                "description": "MFGC gate — confidence-score automation request",
                "agent_role": "ScopeAnalyzer",
                "module_ref": "mfgc_gate",
                "inputs": ["user_query"],
                "outputs": ["mfgc_result"],
            },
            {
                "step_id": "magnify",
                "name": "Requirements Expansion",
                "description": "MSS Magnify — expand to automation requirements",
                "agent_role": "RequirementsWriter",
                "module_ref": "mss_magnify",
                "inputs": ["user_query", "mfgc_result"],
                "outputs": ["magnify_result"],
            },
            {
                "step_id": "solidify",
                "name": "Implementation Plan",
                "description": "MSS Solidify — full automation architecture",
                "agent_role": "ArchitectBot",
                "module_ref": "mss_solidify",
                "inputs": ["user_query", "mfgc_result"],
                "outputs": ["solidify_result"],
            },
            {
                "step_id": "org_intake",
                "name": "Organization Intake",
                "description": "Profile the target organization for connector/compliance selection",
                "agent_role": "IntakeAnalyst",
                "module_ref": "workflow_template",
                "inputs": ["user_query", "magnify_result"],
                "outputs": ["org_profile"],
            },
            {
                "step_id": "compliance",
                "name": "Compliance Check",
                "description": "EU AI Act + domain compliance assessment",
                "agent_role": "ComplianceChecker",
                "module_ref": "eu_compliance",
                "inputs": ["solidify_result", "org_profile"],
                "outputs": ["compliance_result"],
            },
            {
                "step_id": "generate",
                "name": "Blueprint Generation",
                "description": "Generate full automation blueprint with cost/time estimates",
                "agent_role": "ContentWriter",
                "module_ref": "llm_generate",
                "inputs": ["user_query", "magnify_result", "solidify_result", "compliance_result"],
                "outputs": ["deliverable_content"],
            },
            {
                "step_id": "hitl_review",
                "name": "Platform HITL Review",
                "description": "Route blueprint through HITL for bug fixing",
                "agent_role": "ReviewAgent",
                "module_ref": "hitl_review",
                "inputs": ["deliverable_content"],
                "outputs": ["reviewed_deliverable"],
            },
        ],
        "reference_modules": [
            "mfgc_adapter.MFGCSystemFactory",
            "mss_controls.MSSController",
            "org_build_plan.build_orchestrator.OrganizationBuildOrchestrator",
            "eu_ai_act_compliance.EUAIActComplianceEngine",
            "supervisor_system.hitl_monitor.HumanInTheLoopMonitor",
        ],
    },
    {
        "name": "Content & Course Builder",
        "description": "Structured content creation: outline → chapters → exercises → review.",
        "category": "content_management",
        "query_pattern": "course|curriculum|training|content|book|chapter|lesson|tutorial",
        "steps": [
            {
                "step_id": "scope",
                "name": "Scope Analysis",
                "description": "MFGC gate — confidence-score content request",
                "agent_role": "ScopeAnalyzer",
                "module_ref": "mfgc_gate",
                "inputs": ["user_query"],
                "outputs": ["mfgc_result"],
            },
            {
                "step_id": "magnify",
                "name": "Topic Expansion",
                "description": "MSS Magnify — expand to content modules + learning objectives",
                "agent_role": "CurriculumDesigner",
                "module_ref": "mss_magnify",
                "inputs": ["user_query", "mfgc_result"],
                "outputs": ["magnify_result"],
            },
            {
                "step_id": "solidify",
                "name": "Content Architecture",
                "description": "MSS Solidify — full content structure with chapter/section plan",
                "agent_role": "ArchitectBot",
                "module_ref": "mss_solidify",
                "inputs": ["user_query", "mfgc_result"],
                "outputs": ["solidify_result"],
            },
            {
                "step_id": "librarian",
                "name": "Domain Research",
                "description": "Librarian lookup — gather subject-matter context",
                "agent_role": "ResearchBot",
                "module_ref": "librarian_lookup",
                "inputs": ["user_query"],
                "outputs": ["librarian_context"],
            },
            {
                "step_id": "generate",
                "name": "Content Writing",
                "description": "LLM → generate full structured content",
                "agent_role": "ContentWriter",
                "module_ref": "llm_generate",
                "inputs": ["user_query", "magnify_result", "solidify_result", "librarian_context"],
                "outputs": ["deliverable_content"],
            },
            {
                "step_id": "hitl_review",
                "name": "Platform HITL Review",
                "description": "Route content through HITL for accuracy review",
                "agent_role": "ReviewAgent",
                "module_ref": "hitl_review",
                "inputs": ["deliverable_content"],
                "outputs": ["reviewed_deliverable"],
            },
        ],
        "reference_modules": [
            "mss_controls.MSSController",
            "llm_provider.MurphyLLMProvider",
            "supervisor_system.hitl_monitor.HumanInTheLoopMonitor",
        ],
    },
]


# ═══════════════════════════════════════════════════════════════════════════
# Registry  (label: FORGE-WORKFLOW-003)
# ═══════════════════════════════════════════════════════════════════════════

class ProductionWorkflowRegistry:
    """In-memory + DB-backed registry of production workflows.

    The Forge calls ``resolve_workflow(query)`` which:
    1. Normalises the query into an intent pattern.
    2. Searches persisted workflows (DB) and builtins for a match.
    3. Returns ``(workflow_dict, decision)`` where *decision* is one of
       ``"reuse"``, ``"modify"``, ``"create"``.

    After the forge executes the workflow, it calls ``persist_workflow()``
    to save the workflow (and any modifications) back to the registry.
    """

    # Similarity threshold: ≥ 0.55 → reuse; ≥ 0.35 → modify; < 0.35 → create
    REUSE_THRESHOLD: float = 0.55
    MODIFY_THRESHOLD: float = 0.35

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._builtins_loaded = False
        # In-memory cache: workflow_id → workflow dict
        self._cache: Dict[str, Dict[str, Any]] = {}

    # ---- Public API -------------------------------------------------------

    def resolve_workflow(
        self,
        query: str,
    ) -> Tuple[Dict[str, Any], str]:
        """Search for an existing workflow or decide to create a new one.

        Returns
        -------
        (workflow, decision)
            *workflow*: the best-matching workflow dict (or a newly created
            skeleton).  *decision*: ``"reuse"`` | ``"modify"`` | ``"create"``.
        """
        self._ensure_builtins()
        intent = self._normalise_intent(query)
        logger.info("Forge workflow resolution — intent: %s", intent[:80])

        # 1. Search persisted workflows from DB
        best_db = self._search_db(intent)

        # 2. Search builtins
        best_builtin = self._search_builtins(intent)

        # 3. Pick the best match across both pools
        best, score = self._pick_best(best_db, best_builtin)

        if score >= self.REUSE_THRESHOLD and best is not None:
            decision = "reuse"
            logger.info(
                "Workflow resolved → REUSE '%s' (score=%.2f)",
                best.get("name", "?"),
                score,
            )
        elif score >= self.MODIFY_THRESHOLD and best is not None:
            decision = "modify"
            logger.info(
                "Workflow resolved → MODIFY '%s' (score=%.2f)",
                best.get("name", "?"),
                score,
            )
        else:
            decision = "create"
            best = self._create_workflow_from_query(query, intent)
            logger.info("Workflow resolved → CREATE new workflow")

        return best, decision

    def persist_workflow(
        self,
        workflow: Dict[str, Any],
        *,
        source: str = "auto",
        parent_id: Optional[str] = None,
    ) -> str:
        """Save a workflow to the DB and in-memory cache.

        Returns the ``workflow_id``.
        """
        wf_id = workflow.get("workflow_id") or self._make_id(workflow.get("name", ""))
        workflow["workflow_id"] = wf_id
        workflow.setdefault("source", source)
        workflow.setdefault("hitl_status", "pending_review")
        workflow.setdefault("version", 1)
        workflow.setdefault("parent_workflow_id", parent_id)
        workflow.setdefault("metrics", {
            "times_used": 0,
            "avg_quality_score": 0.0,
            "last_used_at": None,
            "hitl_rejections": 0,
        })
        workflow.setdefault("created_at", datetime.now(timezone.utc).isoformat())
        workflow["updated_at"] = datetime.now(timezone.utc).isoformat()

        with self._lock:
            self._cache[wf_id] = workflow

        # Persist to DB (best-effort — works without DB in test/dev)
        self._persist_to_db(workflow)

        logger.info(
            "Persisted workflow '%s' (id=%s, source=%s, hitl=%s)",
            workflow.get("name"),
            wf_id,
            source,
            workflow.get("hitl_status"),
        )
        return wf_id

    def record_usage(self, workflow_id: str, quality_score: float = 0.0) -> None:
        """Increment usage counter and update quality metrics."""
        with self._lock:
            wf = self._cache.get(workflow_id)
            if wf:
                metrics = wf.setdefault("metrics", {})
                metrics["times_used"] = metrics.get("times_used", 0) + 1
                metrics["last_used_at"] = datetime.now(timezone.utc).isoformat()
                if quality_score > 0:
                    prev_avg = metrics.get("avg_quality_score", 0.0)
                    count = metrics["times_used"]
                    metrics["avg_quality_score"] = round(
                        ((prev_avg * (count - 1)) + quality_score) / count, 2,
                    )

    def get_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Return a workflow by ID from cache or DB."""
        with self._lock:
            cached = self._cache.get(workflow_id)
        if cached:
            return cached
        return self._load_from_db(workflow_id)

    def list_workflows(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return summary list of all workflows, optionally filtered by category."""
        self._ensure_builtins()
        with self._lock:
            workflows = list(self._cache.values())
        if category:
            workflows = [w for w in workflows if w.get("category") == category]
        return [
            {
                "workflow_id": w.get("workflow_id"),
                "name": w.get("name"),
                "category": w.get("category"),
                "source": w.get("source"),
                "hitl_status": w.get("hitl_status"),
                "version": w.get("version"),
                "times_used": w.get("metrics", {}).get("times_used", 0),
            }
            for w in workflows
        ]

    # ---- Internal ---------------------------------------------------------

    def _ensure_builtins(self) -> None:
        """Load built-in workflows into cache on first access."""
        if self._builtins_loaded:
            return
        with self._lock:
            if self._builtins_loaded:
                return
            for builtin in _BUILTIN_WORKFLOWS:
                wf = dict(builtin)
                wf["workflow_id"] = self._make_id(wf["name"])
                wf["source"] = "system"
                wf["hitl_status"] = "released"
                wf["version"] = 1
                wf["metrics"] = {
                    "times_used": 0,
                    "avg_quality_score": 0.0,
                    "last_used_at": None,
                    "hitl_rejections": 0,
                }
                self._cache[wf["workflow_id"]] = wf
            self._builtins_loaded = True
            # Also load any DB-persisted workflows
            self._load_all_from_db()

    @staticmethod
    def _normalise_intent(query: str) -> str:
        """Normalise a user query into an intent string for matching.

        Strips noise words, lowercases, and extracts the semantic core.
        """
        q = query.lower().strip()
        # Remove common noise phrases
        for noise in ("i want to", "i need to", "please", "can you", "help me",
                       "i'd like to", "could you", "would you", "i want", "i need"):
            q = q.replace(noise, "")
        # Collapse whitespace
        q = re.sub(r"\s+", " ", q).strip()
        return q

    def _search_builtins(self, intent: str) -> Tuple[Optional[Dict[str, Any]], float]:
        """Search built-in workflows by pattern + similarity."""
        best_wf: Optional[Dict[str, Any]] = None
        best_score = 0.0
        with self._lock:
            for wf in self._cache.values():
                score = self._score_match(intent, wf)
                if score > best_score:
                    best_score = score
                    best_wf = wf
        return best_wf, best_score

    def _search_db(self, intent: str) -> Tuple[Optional[Dict[str, Any]], float]:
        """Search DB-persisted workflows.

        Falls back gracefully if DB is unavailable.
        """
        try:
            from src.db import _get_session_factory, ProductionWorkflow as PWModel
            factory = _get_session_factory()
            session = factory()
            try:
                rows = session.query(PWModel).all()
                best_wf: Optional[Dict[str, Any]] = None
                best_score = 0.0
                for row in rows:
                    wf = {
                        "workflow_id": row.workflow_id,
                        "name": row.name,
                        "description": row.description,
                        "query_pattern": row.query_pattern,
                        "category": row.category,
                        "steps": row.steps or [],
                        "reference_modules": row.reference_modules or [],
                        "source": row.source,
                        "hitl_status": row.hitl_status,
                        "version": row.version,
                        "parent_workflow_id": row.parent_workflow_id,
                        "metrics": row.metrics or {},
                    }
                    score = self._score_match(intent, wf)
                    if score > best_score:
                        best_score = score
                        best_wf = wf
                        # Cache it
                        with self._lock:
                            self._cache[wf["workflow_id"]] = wf
                return best_wf, best_score
            finally:
                session.close()
        except Exception as exc:
            logger.debug("DB workflow search unavailable: %s", exc)
            return None, 0.0

    def _load_all_from_db(self) -> None:
        """Load all persisted workflows into cache.  Best-effort."""
        try:
            from src.db import _get_session_factory, ProductionWorkflow as PWModel
            factory = _get_session_factory()
            session = factory()
            try:
                for row in session.query(PWModel).all():
                    wf = {
                        "workflow_id": row.workflow_id,
                        "name": row.name,
                        "description": row.description,
                        "query_pattern": row.query_pattern,
                        "category": row.category,
                        "steps": row.steps or [],
                        "reference_modules": row.reference_modules or [],
                        "source": row.source,
                        "hitl_status": row.hitl_status,
                        "version": row.version,
                        "parent_workflow_id": row.parent_workflow_id,
                        "metrics": row.metrics or {},
                    }
                    self._cache[wf["workflow_id"]] = wf
            finally:
                session.close()
        except Exception as exc:
            logger.debug("Failed to load workflows from DB: %s", exc)

    def _load_from_db(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Load a single workflow from DB by ID."""
        try:
            from src.db import _get_session_factory, ProductionWorkflow as PWModel
            factory = _get_session_factory()
            session = factory()
            try:
                row = session.query(PWModel).filter_by(workflow_id=workflow_id).first()
                if not row:
                    return None
                wf = {
                    "workflow_id": row.workflow_id,
                    "name": row.name,
                    "description": row.description,
                    "query_pattern": row.query_pattern,
                    "category": row.category,
                    "steps": row.steps or [],
                    "reference_modules": row.reference_modules or [],
                    "source": row.source,
                    "hitl_status": row.hitl_status,
                    "version": row.version,
                    "parent_workflow_id": row.parent_workflow_id,
                    "metrics": row.metrics or {},
                }
                with self._lock:
                    self._cache[wf["workflow_id"]] = wf
                return wf
            finally:
                session.close()
        except Exception as exc:
            logger.debug("DB load for workflow %s failed: %s", workflow_id, exc)
            return None

    def _persist_to_db(self, workflow: Dict[str, Any]) -> None:
        """Write a workflow to the DB.  Best-effort."""
        try:
            from src.db import _get_session_factory, ProductionWorkflow as PWModel
            factory = _get_session_factory()
            session = factory()
            try:
                existing = session.query(PWModel).filter_by(
                    workflow_id=workflow["workflow_id"],
                ).first()
                if existing:
                    existing.name = workflow.get("name", existing.name)
                    existing.description = workflow.get("description", existing.description)
                    existing.query_pattern = workflow.get("query_pattern", existing.query_pattern)
                    existing.category = workflow.get("category", existing.category)
                    existing.steps = workflow.get("steps", existing.steps)
                    existing.reference_modules = workflow.get("reference_modules", existing.reference_modules)
                    existing.source = workflow.get("source", existing.source)
                    existing.hitl_status = workflow.get("hitl_status", existing.hitl_status)
                    existing.version = workflow.get("version", (existing.version or 0) + 1)
                    existing.parent_workflow_id = workflow.get("parent_workflow_id")
                    existing.metrics = workflow.get("metrics", existing.metrics)
                else:
                    row = PWModel(
                        workflow_id=workflow["workflow_id"],
                        name=workflow.get("name", ""),
                        description=workflow.get("description", ""),
                        query_pattern=workflow.get("query_pattern", ""),
                        category=workflow.get("category", "general"),
                        steps=workflow.get("steps", []),
                        reference_modules=workflow.get("reference_modules", []),
                        source=workflow.get("source", "auto"),
                        hitl_status=workflow.get("hitl_status", "pending_review"),
                        version=workflow.get("version", 1),
                        parent_workflow_id=workflow.get("parent_workflow_id"),
                        metrics=workflow.get("metrics", {}),
                    )
                    session.add(row)
                session.commit()
            except Exception as exc:
                session.rollback()
                logger.debug("DB persist failed: %s", exc)
            finally:
                session.close()
        except Exception as exc:
            logger.debug("DB connection unavailable for persist: %s", exc)

    @staticmethod
    def _score_match(intent: str, workflow: Dict[str, Any]) -> float:
        """Score how well a workflow matches a user intent.

        Combines regex pattern matching on ``query_pattern`` with
        SequenceMatcher similarity on name + description.
        """
        pattern = workflow.get("query_pattern", "")
        name = workflow.get("name", "")
        desc = workflow.get("description", "")

        # Pattern match (regex keywords separated by |)
        pattern_score = 0.0
        if pattern:
            try:
                if re.search(pattern, intent, re.IGNORECASE):
                    pattern_score = 0.4
            except re.error:  # PROD-HARD A2: invalid registry regex shouldn't block scoring, but log for operator
                logger.warning("Invalid match_pattern %r in workflow %s; skipping pattern-score", pattern, name)

        # Similarity to name + description
        combined = f"{name} {desc}".lower()
        sim = SequenceMatcher(None, intent, combined).ratio()

        # Category keyword boost
        category_boost = 0.0
        cat = workflow.get("category", "")
        if cat and cat != "general" and cat.replace("_", " ") in intent:
            category_boost = 0.1

        return min(1.0, pattern_score + sim * 0.5 + category_boost)

    @staticmethod
    def _pick_best(
        db_result: Tuple[Optional[Dict[str, Any]], float],
        builtin_result: Tuple[Optional[Dict[str, Any]], float],
    ) -> Tuple[Optional[Dict[str, Any]], float]:
        """Pick the best match between DB and builtin results."""
        db_wf, db_score = db_result
        bi_wf, bi_score = builtin_result
        if db_score >= bi_score and db_wf is not None:
            return db_wf, db_score
        if bi_wf is not None:
            return bi_wf, bi_score
        return None, 0.0

    def _create_workflow_from_query(
        self,
        query: str,
        intent: str,
    ) -> Dict[str, Any]:
        """Create a new production workflow from a user query.

        Uses Murphy System's own architecture as the template: every new
        workflow starts with the standard MFGC → MSS → LLM pipeline and
        adds domain-specific steps based on query analysis.
        """
        # Start from the general deliverable template (Murphy's own pattern)
        base = dict(_BUILTIN_WORKFLOWS[0])
        base_steps = [dict(s) for s in base["steps"]]

        # Detect domain-specific needs and add extra steps
        q_lower = query.lower()

        # Automation / DevOps queries get org-intake + compliance steps
        if any(kw in q_lower for kw in ("automat", "pipeline", "deploy", "ci", "cd", "workflow")):
            # Insert org intake before generate step
            org_step = {
                "step_id": "org_intake",
                "name": "Organization Intake",
                "description": "Profile target organization for connector/compliance selection",
                "agent_role": "IntakeAnalyst",
                "module_ref": "workflow_template",
                "inputs": ["user_query", "magnify_result"],
                "outputs": ["org_profile"],
            }
            compliance_step = {
                "step_id": "compliance",
                "name": "Compliance Check",
                "description": "EU AI Act + domain compliance assessment",
                "agent_role": "ComplianceChecker",
                "module_ref": "eu_compliance",
                "inputs": ["solidify_result", "org_profile"],
                "outputs": ["compliance_result"],
            }
            # Insert before the generate step
            gen_idx = next(
                (i for i, s in enumerate(base_steps) if s["step_id"] == "generate"),
                len(base_steps) - 1,
            )
            base_steps.insert(gen_idx, compliance_step)
            base_steps.insert(gen_idx, org_step)
            base["category"] = "devops"

        # Content / Education queries get domain-research step
        if any(kw in q_lower for kw in ("course", "training", "curriculum", "book", "lesson", "tutorial")):
            base["category"] = "content_management"

        # Financial queries
        if any(kw in q_lower for kw in ("financ", "invoice", "cost", "pricing", "budget", "revenue")):
            base["category"] = "financial_reporting"

        # Security / compliance
        if any(kw in q_lower for kw in ("security", "audit", "compliance", "gdpr", "hipaa", "soc")):
            base["category"] = "security_compliance"

        # Derive name from query
        name_words = intent.split()[:6]
        wf_name = " ".join(w.capitalize() for w in name_words) + " Workflow"

        wf = {
            "workflow_id": self._make_id(wf_name),
            "name": wf_name,
            "description": f"Auto-generated workflow for: {query[:120]}",
            "query_pattern": intent[:200],
            "category": base.get("category", "general"),
            "steps": base_steps,
            "reference_modules": base.get("reference_modules", []),
            "source": "auto",
            "hitl_status": "pending_review",
            "version": 1,
            "parent_workflow_id": None,
            "metrics": {
                "times_used": 0,
                "avg_quality_score": 0.0,
                "last_used_at": None,
                "hitl_rejections": 0,
            },
        }
        return wf

    @staticmethod
    def _make_id(name: str) -> str:
        """Generate a stable workflow ID from a name."""
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower().strip()).strip("-")
        h = hashlib.sha256(slug.encode()).hexdigest()[:8]
        return f"pwf-{h}"


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_registry: Optional[ProductionWorkflowRegistry] = None
_registry_lock = threading.Lock()


def get_workflow_registry() -> ProductionWorkflowRegistry:
    """Return the module-level workflow registry singleton."""
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = ProductionWorkflowRegistry()
    return _registry

"""
Integration Bus — wires src/ modules together and provides a single
``process(request_type, payload)`` entry-point for the runtime.

Routing logic
-------------
* ``"chat"``    → LLMIntegrationLayer → LLMController → LLMOutputValidator → response
* ``"execute"`` → DomainEngine → SwarmSystem → ExecutionOrchestrator → FeedbackIntegrator

Graceful degradation: if any module in the chain cannot be loaded, the step
is skipped with a warning and the next module is tried.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _try_import(dotted_path: str) -> Optional[Any]:
    """Import *dotted_path* and return the module, or ``None`` on failure."""
    try:
        return importlib.import_module(dotted_path)
    except Exception as exc:
        logger.warning("IntegrationBus: could not import '%s': %s", dotted_path, exc)
        return None


def _safe_get_class(module: Any, *class_names: str) -> Optional[Any]:
    """Return the first class found in *module* from *class_names*, or ``None``."""
    for name in class_names:
        cls = getattr(module, name, None)
        if cls is not None:
            return cls
    return None


# ---------------------------------------------------------------------------
# IntegrationBus
# ---------------------------------------------------------------------------


class IntegrationBus:
    """Wires src/ modules together and routes requests through processing chains.

    The bus lazily loads each module on first use and caches the result.
    If a module fails to load it is skipped (graceful degradation).
    """

    def __init__(self) -> None:
        # Lazy-loaded module references (None means not yet attempted)
        self._llm_integration_layer: Optional[Any] = None
        self._llm_controller: Optional[Any] = None
        self._llm_output_validator: Optional[Any] = None
        self._domain_engine: Optional[Any] = None
        self._swarm_system: Optional[Any] = None
        self._feedback_integrator: Optional[Any] = None
        # New modules from PR #195
        self._shadow_knostalgia_bridge: Optional[Any] = None
        self._dynamic_assist_engine: Optional[Any] = None
        self._kfactor_calculator: Optional[Any] = None
        self._onboarding_team_pipeline: Optional[Any] = None
        # Librarian-driven routing (replaces hardcoded chains when available)
        self._task_router: Optional[Any] = None
        self._initialized: bool = False

        # Load attempts so we don't keep retrying broken imports
        self._load_attempted: Dict[str, bool] = {}

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Pre-load all integration modules.  Safe to call multiple times."""
        if self._initialized:
            return
        self._load_all()
        self._initialized = True
        logger.info(
            "IntegrationBus initialised — llm_integration_layer=%s, "
            "llm_controller=%s, llm_output_validator=%s, "
            "domain_engine=%s, swarm=%s, feedback_integrator=%s, "
            "shadow_knostalgia_bridge=%s, dynamic_assist_engine=%s, "
            "kfactor_calculator=%s, onboarding_team_pipeline=%s, "
            "task_router=%s",
            self._llm_integration_layer is not None,
            self._llm_controller is not None,
            self._llm_output_validator is not None,
            self._domain_engine is not None,
            self._swarm_system is not None,
            self._feedback_integrator is not None,
            self._shadow_knostalgia_bridge is not None,
            self._dynamic_assist_engine is not None,
            self._kfactor_calculator is not None,
            self._onboarding_team_pipeline is not None,
            self._task_router is not None,
        )

    def _load_all(self) -> None:
        self._llm_integration_layer = self._load_llm_integration_layer()
        self._llm_controller = self._load_llm_controller()
        self._llm_output_validator = self._load_llm_output_validator()
        self._domain_engine = self._load_domain_engine()
        self._swarm_system = self._load_swarm_system()
        self._feedback_integrator = self._load_feedback_integrator()
        # Load dependencies first so the bridge can reference them
        self._dynamic_assist_engine = self._load_dynamic_assist_engine()
        self._kfactor_calculator = self._load_kfactor_calculator()
        self._shadow_knostalgia_bridge = self._load_shadow_knostalgia_bridge()
        self._onboarding_team_pipeline = self._load_onboarding_team_pipeline()
        # Librarian-driven routing — loaded last so it can use the modules above
        self._task_router = self._load_task_router()

    # ------------------------------------------------------------------
    # Module loaders
    # ------------------------------------------------------------------

    def _load_llm_integration_layer(self) -> Optional[Any]:
        if self._load_attempted.get("llm_integration_layer"):
            return self._llm_integration_layer
        self._load_attempted["llm_integration_layer"] = True
        mod = _try_import("src.llm_integration_layer")
        if mod is None:
            return None
        cls = _safe_get_class(mod, "LLMIntegrationLayer")
        if cls is None:
            return None
        try:
            return cls()
        except Exception as exc:
            logger.warning("IntegrationBus: failed to instantiate LLMIntegrationLayer: %s", exc)
            return None

    def _load_llm_controller(self) -> Optional[Any]:
        if self._load_attempted.get("llm_controller"):
            return self._llm_controller
        self._load_attempted["llm_controller"] = True
        mod = _try_import("src.llm_controller")
        if mod is None:
            return None
        cls = _safe_get_class(mod, "LLMController", "MurphyLLMController")
        if cls is None:
            return None
        try:
            return cls()
        except Exception as exc:
            logger.warning("IntegrationBus: failed to instantiate LLMController: %s", exc)
            return None

    def _load_llm_output_validator(self) -> Optional[Any]:
        if self._load_attempted.get("llm_output_validator"):
            return self._llm_output_validator
        self._load_attempted["llm_output_validator"] = True
        mod = _try_import("src.llm_output_validator")
        if mod is None:
            return None
        cls = _safe_get_class(mod, "LLMOutputValidator")
        if cls is None:
            return None
        try:
            return cls()
        except Exception as exc:
            logger.warning("IntegrationBus: failed to instantiate LLMOutputValidator: %s", exc)
            return None

    def _load_domain_engine(self) -> Optional[Any]:
        if self._load_attempted.get("domain_engine"):
            return self._domain_engine
        self._load_attempted["domain_engine"] = True
        mod = _try_import("src.domain_engine")
        if mod is None:
            return None
        cls = _safe_get_class(mod, "DomainEngine", "GenerativeDomainEngine")
        if cls is None:
            return None
        try:
            return cls()
        except Exception as exc:
            logger.warning("IntegrationBus: failed to instantiate DomainEngine: %s", exc)
            return None

    def _load_swarm_system(self) -> Optional[Any]:
        if self._load_attempted.get("swarm_system"):
            return self._swarm_system
        self._load_attempted["swarm_system"] = True
        for module_path, class_names in (
            ("src.true_swarm_system", ("TrueSwarmSystem", "SwarmSystem")),
            ("src.advanced_swarm_system", ("AdvancedSwarmSystem",)),
            ("src.durable_swarm_orchestrator", ("DurableSwarmOrchestrator",)),
        ):
            mod = _try_import(module_path)
            if mod is None:
                continue
            cls = _safe_get_class(mod, *class_names)
            if cls is None:
                continue
            try:
                return cls()
            except Exception as exc:
                logger.warning(
                    "IntegrationBus: failed to instantiate %s from %s: %s",
                    class_names[0], module_path, exc,
                )
        return None

    def _load_feedback_integrator(self) -> Optional[Any]:
        if self._load_attempted.get("feedback_integrator"):
            return self._feedback_integrator
        self._load_attempted["feedback_integrator"] = True
        mod = _try_import("src.feedback_integrator")
        if mod is None:
            return None
        cls = _safe_get_class(mod, "FeedbackIntegrator")
        if cls is None:
            return None
        try:
            return cls()
        except Exception as exc:
            logger.warning("IntegrationBus: failed to instantiate FeedbackIntegrator: %s", exc)
            return None

    def _load_shadow_knostalgia_bridge(self) -> Optional[Any]:
        if self._load_attempted.get("shadow_knostalgia_bridge"):
            return self._shadow_knostalgia_bridge
        self._load_attempted["shadow_knostalgia_bridge"] = True
        mod = _try_import("src.shadow_knostalgia_bridge")
        if mod is None:
            return None
        cls = _safe_get_class(mod, "ShadowKnostalgiaBridge")
        if cls is None:
            return None
        try:
            # Use already-loaded dependencies if available; the constructor
            # creates defaults (KFactorCalculator(), DynamicAssistEngine())
            # when passed None, so it is safe to forward None here.
            return cls(
                kfactor_calculator=self._kfactor_calculator,
                dynamic_assist_engine=self._dynamic_assist_engine,
            )
        except Exception as exc:
            logger.warning("IntegrationBus: failed to instantiate ShadowKnostalgiaBridge: %s", exc)
            return None

    def _load_dynamic_assist_engine(self) -> Optional[Any]:
        if self._load_attempted.get("dynamic_assist_engine"):
            return self._dynamic_assist_engine
        self._load_attempted["dynamic_assist_engine"] = True
        mod = _try_import("src.dynamic_assist_engine")
        if mod is None:
            return None
        cls = _safe_get_class(mod, "DynamicAssistEngine")
        if cls is None:
            return None
        try:
            return cls()
        except Exception as exc:
            logger.warning("IntegrationBus: failed to instantiate DynamicAssistEngine: %s", exc)
            return None

    def _load_kfactor_calculator(self) -> Optional[Any]:
        if self._load_attempted.get("kfactor_calculator"):
            return self._kfactor_calculator
        self._load_attempted["kfactor_calculator"] = True
        mod = _try_import("src.kfactor_calculator")
        if mod is None:
            return None
        cls = _safe_get_class(mod, "KFactorCalculator")
        if cls is None:
            return None
        try:
            return cls()
        except Exception as exc:
            logger.warning("IntegrationBus: failed to instantiate KFactorCalculator: %s", exc)
            return None

    def _load_onboarding_team_pipeline(self) -> Optional[Any]:
        if self._load_attempted.get("onboarding_team_pipeline"):
            return self._onboarding_team_pipeline
        self._load_attempted["onboarding_team_pipeline"] = True
        mod = _try_import("src.onboarding_team_pipeline")
        if mod is None:
            return None
        cls = _safe_get_class(mod, "OnboardingTeamPipeline")
        if cls is None:
            return None
        try:
            return cls()
        except Exception as exc:
            logger.warning("IntegrationBus: failed to instantiate OnboardingTeamPipeline: %s", exc)
            return None

    def _load_task_router(self) -> Optional[Any]:
        """Build and return a :class:`~task_router.TaskRouter` instance.

        Wires :class:`~system_librarian.SystemLibrarian`,
        :class:`~solution_path_registry.SolutionPathRegistry`, and the
        :class:`~feedback_integrator.FeedbackIntegrator` into the router.
        Falls back to ``None`` gracefully so that the old hardcoded chains
        remain active if any dependency cannot be loaded.
        """
        if self._load_attempted.get("task_router"):
            return self._task_router
        self._load_attempted["task_router"] = True

        router_mod = _try_import("src.task_router")
        if router_mod is None:
            return None
        router_cls = _safe_get_class(router_mod, "TaskRouter")
        if router_cls is None:
            return None

        librarian_mod = _try_import("src.system_librarian")
        librarian_cls = _safe_get_class(librarian_mod, "SystemLibrarian") if librarian_mod else None

        registry_mod = _try_import("src.solution_path_registry")
        registry_cls = _safe_get_class(registry_mod, "SolutionPathRegistry") if registry_mod else None

        if librarian_cls is None or registry_cls is None:
            return None

        try:
            librarian = librarian_cls()
            solution_registry = registry_cls(feedback_integrator=self._feedback_integrator)
            return router_cls(
                librarian=librarian,
                solution_registry=solution_registry,
                governance=None,
                feedback=self._feedback_integrator,
            )
        except Exception as exc:
            logger.warning("IntegrationBus: failed to build TaskRouter: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Validation helper
    # ------------------------------------------------------------------

    def _apply_output_validation(self, response_text: str) -> Dict[str, Any]:
        """Run *response_text* through the LLM output validator.

        Returns a dict with keys ``validated``, ``text``, and ``errors``.
        Falls back gracefully when the validator is unavailable.
        """
        if self._llm_output_validator is None:
            return {"validated": False, "text": response_text, "errors": []}

        try:
            validate_fn = getattr(self._llm_output_validator, "validate_envelope", None)
            if validate_fn is not None:
                result = validate_fn({"raw_output": response_text, "output_type": "text"})
                valid = getattr(result, "valid", True)
                errors: List[str] = list(getattr(result, "errors", []))
                return {"validated": True, "text": response_text, "errors": errors, "valid": valid}
        except Exception as exc:
            logger.warning("IntegrationBus: output validation failed: %s", exc)

        return {"validated": False, "text": response_text, "errors": []}

    # ------------------------------------------------------------------
    # Core routing
    # ------------------------------------------------------------------

    def process(self, request_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Route *payload* through the appropriate module chain.

        Parameters
        ----------
        request_type:
            One of ``"chat"`` or ``"execute"``.
        payload:
            Request data (contents depend on *request_type*).

        Returns
        -------
        Dict[str, Any]
            Response dict with at least the keys ``"success"`` and
            ``"response"``.
        """
        if not self._initialized:
            self.initialize()

        if request_type == "chat":
            return self._process_chat(payload)
        if request_type == "execute":
            return self._process_execute(payload)

        logger.warning("IntegrationBus.process: unknown request_type '%s'", request_type)
        return {
            "success": False,
            "error": f"Unknown request type: {request_type}",
            "response": "",
            "bus_routed": False,
        }

    # ------------------------------------------------------------------
    # Chat chain: LLMIntegrationLayer → LLMController → LLMOutputValidator
    # ------------------------------------------------------------------

    def _process_chat(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        message = payload.get("message", "")
        context = payload.get("context") or {}
        domain = payload.get("domain", "general")

        raw_response: Optional[str] = None
        provider_used: Optional[str] = None
        chain_steps: List[str] = []

        # Step 1: LLMIntegrationLayer
        if self._llm_integration_layer is not None:
            try:
                route_fn = getattr(self._llm_integration_layer, "route_request", None)
                if route_fn is not None:
                    llm_resp = route_fn(
                        prompt=message,
                        domain=domain,
                        context=context,
                    )
                    raw_response = getattr(llm_resp, "response", None) or str(llm_resp)
                    provider_used = str(getattr(llm_resp, "provider", "integration_layer"))
                    chain_steps.append("llm_integration_layer")
            except Exception as exc:
                logger.warning("IntegrationBus chat: LLMIntegrationLayer failed: %s", exc)

        # Step 2: LLMController (fallback or supplemental)
        if raw_response is None and self._llm_controller is not None:
            try:
                ctrl_fn = (
                    getattr(self._llm_controller, "route_request", None)
                    or getattr(self._llm_controller, "process_request", None)
                    or getattr(self._llm_controller, "generate", None)
                )
                if ctrl_fn is not None:
                    ctrl_resp = ctrl_fn(message)
                    raw_response = getattr(ctrl_resp, "response", None) or str(ctrl_resp)
                    provider_used = provider_used or "llm_controller"
                    chain_steps.append("llm_controller")
            except Exception as exc:
                logger.warning("IntegrationBus chat: LLMController failed: %s", exc)

        # Step 3: LLMOutputValidator — applied to whatever raw_response we have
        validation_info = self._apply_output_validation(raw_response or "")
        if raw_response is not None:
            chain_steps.append("llm_output_validator")

        return {
            "success": True,
            "response": raw_response or "",
            "provider": provider_used,
            "chain_steps": chain_steps,
            "validation": validation_info,
            "bus_routed": True,
        }

    # ------------------------------------------------------------------
    # Execute chain: TaskRouter (Librarian-first) → DomainEngine → SwarmSystem → FeedbackIntegrator
    # ------------------------------------------------------------------

    def _process_execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        task_description = payload.get("task_description", "")
        task_type = payload.get("task_type", "general")
        parameters = payload.get("parameters") or {}

        # ------------------------------------------------------------------
        # Librarian-first routing: attempt dynamic routing via TaskRouter.
        # When the router is available, it replaces the hardcoded chain below.
        # On failure the legacy chain is used as fallback (graceful degradation).
        # ------------------------------------------------------------------
        if self._task_router is not None:
            try:
                route_task = {
                    "task": task_description,
                    "task_type": task_type,
                    "parameters": parameters,
                    "department_id": payload.get("department_id", "default"),
                }
                result = self._task_router.route_sync(route_task)
                route_status = getattr(result, "status", None)
                status_val = route_status.value if hasattr(route_status, "value") else str(route_status)
                solution_path = getattr(result, "solution_path", None)
                return {
                    "success": status_val in ("approved", "hitl_required"),
                    "task_description": task_description,
                    "route_status": status_val,
                    "capability_id": (
                        getattr(solution_path, "capability_id", None)
                        if solution_path else None
                    ),
                    "confidence": getattr(result, "confidence", 0.0),
                    "gate_results": getattr(result, "gate_results", {}),
                    "chain_steps": ["task_router"],
                    "bus_routed": True,
                    "librarian_routed": True,
                }
            except Exception as exc:
                logger.warning(
                    "IntegrationBus execute: TaskRouter failed, falling back to legacy chain: %s",
                    exc,
                )

        # ------------------------------------------------------------------
        # Legacy hardcoded chain (fallback / backwards compatibility)
        # ------------------------------------------------------------------
        domain_result: Optional[Dict[str, Any]] = None
        swarm_result: Optional[Dict[str, Any]] = None
        chain_steps: List[str] = []

        # Step 1: DomainEngine — classify the task domain
        if self._domain_engine is not None:
            try:
                classify_fn = (
                    getattr(self._domain_engine, "classify_domain", None)
                    or getattr(self._domain_engine, "infer_domain", None)
                    or getattr(self._domain_engine, "get_domain", None)
                )
                if classify_fn is not None:
                    domain_result = classify_fn(task_description)
                    if not isinstance(domain_result, dict):
                        domain_result = {"domain": str(domain_result)}
                    chain_steps.append("domain_engine")
            except Exception as exc:
                logger.warning("IntegrationBus execute: DomainEngine failed: %s", exc)

        # Step 2: SwarmSystem — coordinate agents for execution
        if self._swarm_system is not None:
            try:
                exec_fn = (
                    getattr(self._swarm_system, "execute", None)
                    or getattr(self._swarm_system, "run_task", None)
                    or getattr(self._swarm_system, "process", None)
                )
                if exec_fn is not None:
                    swarm_result = exec_fn(task_description, parameters)
                    if not isinstance(swarm_result, dict):
                        swarm_result = {"result": str(swarm_result)}
                    chain_steps.append("swarm_system")
            except Exception as exc:
                logger.warning("IntegrationBus execute: SwarmSystem failed: %s", exc)

        # Step 3: FeedbackIntegrator — capture implicit signal for closed-loop learning
        if self._feedback_integrator is not None:
            try:
                learn_fn = (
                    getattr(self._feedback_integrator, "record_execution", None)
                    or getattr(self._feedback_integrator, "capture_signal", None)
                )
                if learn_fn is not None:
                    learn_fn(
                        task_type=task_type,
                        success=True,
                        domain=domain_result.get("domain") if domain_result else None,
                    )
                    chain_steps.append("feedback_integrator")
            except Exception as exc:
                logger.warning("IntegrationBus execute: FeedbackIntegrator signal failed: %s", exc)

        return {
            "success": True,
            "task_description": task_description,
            "domain": domain_result,
            "swarm_result": swarm_result,
            "chain_steps": chain_steps,
            "bus_routed": True,
        }

    # ------------------------------------------------------------------
    # Feedback submission (from /api/feedback endpoint)
    # ------------------------------------------------------------------

    def submit_feedback(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process an explicit feedback signal submitted via the API.

        Parameters
        ----------
        payload:
            Dict containing at least ``"signal_type"`` (e.g. ``"correction"``,
            ``"feedback"``) and ``"task_id"``.
        """
        if not self._initialized:
            self.initialize()

        signal_type = payload.get("signal_type", "feedback")
        task_id = payload.get("task_id", "unknown")
        confidence = float(payload.get("original_confidence", 0.5))
        corrected = payload.get("corrected_confidence")
        affected = list(payload.get("affected_state_variables", []))

        if self._feedback_integrator is None:
            return {
                "success": True,
                "message": "Feedback recorded (integrator not available)",
                "bus_routed": False,
            }

        try:
            mod = _try_import("src.feedback_integrator")
            signal_cls = _safe_get_class(mod, "FeedbackSignal") if mod else None
            state_mod = _try_import("src.state_schema")
            state_cls = (
                _safe_get_class(state_mod, "TypedStateVector") if state_mod else None
            )

            if signal_cls is not None and state_cls is not None:
                signal = signal_cls(
                    signal_type=signal_type,
                    source_task_id=task_id,
                    original_confidence=confidence,
                    corrected_confidence=float(corrected) if corrected is not None else None,
                    affected_state_variables=affected,
                )
                state = state_cls()
                self._feedback_integrator.integrate(signal, state)
                return {
                    "success": True,
                    "message": "Feedback integrated into state vector",
                    "signal_type": signal_type,
                    "task_id": task_id,
                    "bus_routed": True,
                }
        except Exception as exc:
            logger.warning("IntegrationBus.submit_feedback: integration failed: %s", exc)

        return {
            "success": True,
            "message": "Feedback received",
            "signal_type": signal_type,
            "task_id": task_id,
            "bus_routed": False,
        }

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """Return a health summary of all wired modules."""
        return {
            "initialized": self._initialized,
            "modules": {
                "llm_integration_layer": self._llm_integration_layer is not None,
                "llm_controller": self._llm_controller is not None,
                "llm_output_validator": self._llm_output_validator is not None,
                "domain_engine": self._domain_engine is not None,
                "swarm_system": self._swarm_system is not None,
                "feedback_integrator": self._feedback_integrator is not None,
                "shadow_knostalgia_bridge": self._shadow_knostalgia_bridge is not None,
                "dynamic_assist_engine": self._dynamic_assist_engine is not None,
                "kfactor_calculator": self._kfactor_calculator is not None,
                "onboarding_team_pipeline": self._onboarding_team_pipeline is not None,
                "task_router": self._task_router is not None,
            },
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

integration_bus = IntegrationBus()

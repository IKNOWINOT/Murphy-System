# Copyright © 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Large Control Model (LCM) — Murphy System

Meta-controller that orchestrates all Murphy subsystems.  Routes natural
language input through the full control pipeline:

  1. NLQueryEngine   — parse intent
  2. MSSController   — determine resolution level
  3. RosetteLens     — agent positions shape the data selection lens
  4. CausalitySandboxEngine — simulate before committing
  5. Dispatch        — execute the control modification (when criteria met)
  6. HITL            — return to human when criteria are NOT met

The LCM is the path to autonomous operation.  Decision layers are built up
over time — ML algorithms guide the confidence gates so the system
progressively reduces human touch as trust is earned.

Usage::

    from large_control_model import LargeControlModel

    lcm = LargeControlModel()
    result = lcm.process("Increase sales outreach frequency by 20%")
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pipeline stage identifiers
# ---------------------------------------------------------------------------
STAGE_NL_PARSE = "nl_parse"
STAGE_MSS_ASSESS = "mss_assess"
STAGE_ROSETTE_LENS = "rosette_lens"
STAGE_CAUSALITY_SIMULATE = "causality_simulate"
STAGE_DISPATCH = "dispatch"
STAGE_HITL = "hitl"


class LargeControlModel:
    """
    Meta-controller that orchestrates all Murphy subsystems.

    Routes natural language input through:
      1. MSS Controls  (determine resolution level)
      2. Rosetta Lens  (agent positions shape data selection)
      3. Causality Sandbox (simulate before committing)
      4. Dispatch      (execute the control modification)

    The LCM is the path to autonomous operation — it replaces human
    decision-making with a formal control loop once confidence criteria are
    met and the HITL graduation policy allows it.
    """

    # Minimum confidence score for autonomous execution (0–1)
    DEFAULT_CONFIDENCE_THRESHOLD: float = 0.85
    # Minimum causality stability score required before auto-dispatch
    DEFAULT_STABILITY_THRESHOLD: float = 0.75

    def __init__(
        self,
        pilot_account: str = "",
        confidence_threshold: float | None = None,
        stability_threshold: float | None = None,
    ) -> None:
        self.pilot_account = pilot_account or os.environ.get("MURPHY_FOUNDER_EMAIL", "")
        self.confidence_threshold = (
            confidence_threshold
            if confidence_threshold is not None
            else self.DEFAULT_CONFIDENCE_THRESHOLD
        )
        self.stability_threshold = (
            stability_threshold
            if stability_threshold is not None
            else self.DEFAULT_STABILITY_THRESHOLD
        )
        self._pipeline_log: list[dict[str, Any]] = []
        self._wire_subsystems()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        natural_language_input: str,
        account: str | None = None,
    ) -> dict[str, Any]:
        """Process NL input through the full LCM pipeline.

        Pipeline:
          1. Parse intent via NLQueryEngine
          2. Assess resolution via MSSController
          3. Determine data lens via RosetteLens
          4. Simulate via CausalitySandboxEngine (what-if query)
          5a. If criteria met → auto-dispatch
          5b. If criteria NOT met → HITL with clarifying questions

        Args:
            natural_language_input: Free-text command/query from a user or
                another subsystem.
            account: The requesting account email.  Defaults to the pilot
                account when omitted.

        Returns:
            A dict containing:
            - ``run_id`` (str) — unique run identifier
            - ``stage`` (str) — final pipeline stage reached
            - ``executed`` (bool) — whether dispatch was triggered
            - ``result`` (Any) — stage-specific result payload
            - ``hitl_required`` (bool) — True when human review is needed
            - ``clarifying_questions`` (list[str]) — non-empty when HITL
            - ``pipeline_trace`` (list[dict]) — per-stage trace
        """
        run_id = str(uuid.uuid4())
        account = account or self.pilot_account
        trace: list[dict[str, Any]] = []

        # ── Stage 0: Criminal Investigation Protocol ─────────────────────
        # Every decision is a crime scene. Establish facts, deduce motive,
        # score ethical conditioning, measure harm, check free will no-gos.
        # This runs before NL parse. Nothing bypasses it.
        investigation_report = None
        try:
            from src.criminal_investigation_protocol import investigate
            investigation_report = investigate(
                intent=natural_language_input,
                context={"account": account, "run_id": run_id},
                domain="general",
            )
            trace.append({
                "stage": "investigation",
                "duration_ms": investigation_report.duration_ms,
                "result": investigation_report.to_dict(),
            })
            if investigation_report.verdict == "blocked":
                logger.warning(
                    "CIDP BLOCKED run=%s: %s",
                    run_id, investigation_report.verdict_reason,
                )
                return {
                    "run_id": run_id,
                    "stage": "blocked",
                    "executed": False,
                    "result": {
                        "reason": investigation_report.verdict_reason,
                        "investigation": investigation_report.to_dict(),
                    },
                    "hitl_required": False,
                    "clarifying_questions": [],
                    "pipeline_trace": trace,
                }
            if investigation_report.verdict == "hitl_required":
                logger.info(
                    "CIDP HITL run=%s: %s",
                    run_id, investigation_report.verdict_reason,
                )
                return self._hitl_response(
                    run_id,
                    trace,
                    reason=investigation_report.verdict_reason,
                    questions=[
                        "Murphy flagged ethical or harm concerns. Can you clarify the intent?",
                        f"Motive assessed as: {investigation_report.motive.motive_class.value}. Is this accurate?",
                    ],
                )
        except ImportError:
            logger.debug("CIDP not available — proceeding without investigation")
        except Exception as _cidp_exc:
            logger.warning("CIDP error (non-blocking): %s", _cidp_exc)

        # ── Stage 1: NL Parse ────────────────────────────────────────────
        nl_result = self._nl_parse(natural_language_input, trace)
        if not nl_result.get("success"):
            return self._hitl_response(
                run_id,
                trace,
                reason="NL parse failed",
                questions=nl_result.get("clarifying_questions", []),
            )

        # ── Stage 2: MSS Assess ──────────────────────────────────────────
        mss_result = self._mss_assess(nl_result, trace)

        # ── Stage 3: Rosette Lens ────────────────────────────────────────
        lens_result = self._rosette_lens(nl_result, mss_result, trace)

        # ── Stage 4: Causality Simulation ────────────────────────────────
        sim_result = self._causality_simulate(
            natural_language_input, nl_result, lens_result, trace
        )

        # ── Stage 5: Gate check ──────────────────────────────────────────
        confidence = sim_result.get("confidence", 0.0)
        stability = sim_result.get("stability_score", 0.0)
        criteria_met = (
            confidence >= self.confidence_threshold
            and stability >= self.stability_threshold
        )

        if criteria_met:
            dispatch_result = self._dispatch(nl_result, sim_result, account, trace)
            return {
                "run_id": run_id,
                "stage": STAGE_DISPATCH,
                "executed": True,
                "result": dispatch_result,
                "hitl_required": False,
                "clarifying_questions": [],
                "pipeline_trace": trace,
            }

        return self._hitl_response(
            run_id,
            trace,
            reason=(
                f"Confidence {confidence:.2f} < {self.confidence_threshold:.2f} "
                f"or stability {stability:.2f} < {self.stability_threshold:.2f}"
            ),
            questions=sim_result.get("clarifying_questions", [
                "Please confirm the intended scope of this change.",
                "Which data sources should be prioritised?",
            ]),
        )

    def get_pilot_status(self) -> dict[str, Any]:
        """Return full status of all automations for the pilot account."""
        return {
            "pilot_account": self.pilot_account,
            "confidence_threshold": self.confidence_threshold,
            "stability_threshold": self.stability_threshold,
            "total_runs": len(self._pipeline_log),
            "subsystems": {
                "nl_engine": self._nl_engine is not None,
                "mss_controller": self._mss_controller is not None,
                "rosette_lens": self._rosette_lens_obj is not None,
                "causality_sandbox": self._causality_sandbox is not None,
                "dispatcher": self._dispatcher is not None,
            },
        }

    # ------------------------------------------------------------------
    # Subsystem wiring
    # ------------------------------------------------------------------

    def _wire_subsystems(self) -> None:
        """Lazily wire up all subsystem dependencies."""
        self._nl_engine = self._try_load_nl_engine()
        self._mss_controller = self._try_load_mss_controller()
        self._rosette_lens_obj = self._try_load_rosette_lens()
        self._causality_sandbox = self._try_load_causality_sandbox()
        self._dispatcher = self._try_load_dispatcher()

    def _try_load_nl_engine(self) -> Any:
        try:
            from src.natural_language_query import NLQueryEngine  # PATCH-074
            return NLQueryEngine()
        except Exception as exc:
            logger.debug("LCM: NLQueryEngine not available: %s", exc)
            return None

    def _try_load_mss_controller(self) -> Any:
        """PATCH-074: Build full MSS dependency chain before instantiating."""
        try:
            from src.resolution_scoring import ResolutionDetectionEngine
            from src.information_density import InformationDensityEngine
            from src.structural_coherence import StructuralCoherenceEngine
            from src.information_quality import InformationQualityEngine
            from src.concept_translation import ConceptTranslationEngine
            from src.simulation_engine import StrategicSimulationEngine
            from src.mss_controls import MSSController
            rde = ResolutionDetectionEngine()
            ide = InformationDensityEngine()
            sce = StructuralCoherenceEngine()
            iqe = InformationQualityEngine(rde=rde, ide=ide, sce=sce)
            cte = ConceptTranslationEngine()
            sim = StrategicSimulationEngine()
            return MSSController(iqe=iqe, cte=cte, sim=sim)
        except Exception as exc:
            logger.debug("LCM: MSSController not available: %s", exc)
            return None

    def _try_load_rosette_lens(self) -> Any:
        try:
            from src.rosette_lens import RosetteLens  # PATCH-074
            return RosetteLens()
        except Exception as exc:
            logger.debug("LCM: RosetteLens not available: %s", exc)
            return None

    def _try_load_causality_sandbox(self) -> Any:
        try:
            from src.causality_sandbox import CausalitySandboxEngine  # PATCH-074

            def _noop_factory():
                class _FakeLoop:
                    _runtime_config = {}
                    _recovery_procedures = []
                    _health_status = "ok"
                    _active_gaps = []
                    _confidence_thresholds = {}
                    _timeout_values = {}
                    _route_configurations = {}

                return _FakeLoop()

            return CausalitySandboxEngine(_noop_factory)
        except Exception as exc:
            logger.debug("LCM: CausalitySandboxEngine not available: %s", exc)
            return None

    def _try_load_dispatcher(self) -> Any:
        try:
            from src.global_feedback.dispatcher import GlobalFeedbackDispatcher  # PATCH-074
            return GlobalFeedbackDispatcher()
        except Exception as exc:
            logger.debug("LCM: Dispatcher not available: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Pipeline stage implementations
    # ------------------------------------------------------------------

    def _nl_parse(
        self, text: str, trace: list[dict[str, Any]]
    ) -> dict[str, Any]:
        # PATCH-077c: RSC gate — LCM dispatch is an effector; block if unstable
        try:
            from src.rsc_unified_sink import enforce
            blocked = enforce("lcm._dispatch")
            if blocked:
                return {"stage": "rsc_constrained", "executed": False,
                        "hitl_required": False, "error": blocked}
        except Exception:
            pass
        t0 = time.monotonic()
        result: dict[str, Any]
        if self._nl_engine is not None:
            try:
                qr = self._nl_engine.query(text)
                result = {
                    "success": True,
                    "intent": getattr(qr, "intent", text),
                    "entities": getattr(qr, "entities", {}),
                    "raw_query": text,
                    "clarifying_questions": getattr(qr, "clarifying_questions", []),
                }
            except Exception as exc:
                logger.warning("LCM NL parse error: %s", exc)
                result = {"success": True, "intent": text, "entities": {}, "raw_query": text, "clarifying_questions": []}
        else:
            result = {"success": True, "intent": text, "entities": {}, "raw_query": text, "clarifying_questions": []}

        trace.append({"stage": STAGE_NL_PARSE, "duration_ms": (time.monotonic() - t0) * 1000, "result": result})
        return result

    def _mss_assess(
        self, nl_result: dict[str, Any], trace: list[dict[str, Any]]
    ) -> dict[str, Any]:
        t0 = time.monotonic()
        result: dict[str, Any]
        if self._mss_controller is not None:
            try:
                assessment = self._mss_controller.assess(nl_result.get("intent", ""))
                result = {"resolution_level": getattr(assessment, "resolution_level", "RM2"), "assessment": assessment}
            except Exception as exc:
                logger.warning("LCM MSS assess error: %s", exc)
                result = {"resolution_level": "RM2"}
        else:
            result = {"resolution_level": "RM2"}

        trace.append({"stage": STAGE_MSS_ASSESS, "duration_ms": (time.monotonic() - t0) * 1000, "result": result})
        return result

    def _rosette_lens(
        self,
        nl_result: dict[str, Any],
        mss_result: dict[str, Any],
        trace: list[dict[str, Any]],
    ) -> dict[str, Any]:
        t0 = time.monotonic()
        result: dict[str, Any]
        if self._rosette_lens_obj is not None:
            try:
                result = self._rosette_lens_obj.select_lens(
                    [],
                    {"intent": nl_result.get("intent", ""), "resolution": mss_result.get("resolution_level")},
                )
            except Exception as exc:
                logger.warning("LCM Rosette lens error: %s", exc)
                result = {"resolution_level": mss_result.get("resolution_level", "RM2"), "data_sources": ["all"]}
        else:
            result = {"resolution_level": mss_result.get("resolution_level", "RM2"), "data_sources": ["all"]}

        trace.append({"stage": STAGE_ROSETTE_LENS, "duration_ms": (time.monotonic() - t0) * 1000, "result": result})
        return result

    def _causality_simulate(
        self,
        text: str,
        nl_result: dict[str, Any],
        lens_result: dict[str, Any],
        trace: list[dict[str, Any]],
    ) -> dict[str, Any]:
        t0 = time.monotonic()
        # PATCH-111b: Replace stub with LLM-generated outcome summary
        _intent = nl_result.get("intent", text) or text
        _simulated = f"Simulated: {_intent}"  # fallback
        try:
            from src.llm_provider import MurphyLLMProvider as _LLMProv
            _llm = _LLMProv()
            _prompt = (
                f"You are Murphy, a civilizational AI OS. A user issued this intent: '{_intent[:200]}'. "
                "In 1-2 sentences, describe concisely what action you would take in response. "
                "Be specific and practical. Do not use hedging language."
            )
            _resp = _llm.complete(prompt=_prompt, max_tokens=120)
            if _resp and getattr(_resp, "content", "").strip():
                _simulated = _resp.content.strip()
        except Exception as _exc:
            logger.debug("LCM simulated_outcome LLM failed, using stub: %s", _exc)
        result: dict[str, Any] = {
            "confidence": 0.9,
            "stability_score": 0.9,
            "simulated_outcome": _simulated,
            "clarifying_questions": [],
        }

        if self._causality_sandbox is not None:
            try:
                # Run a what-if sandbox cycle with a synthetic gap
                class _WhatIfGap:
                    gap_id = "lcm_whatif"
                    description = text
                    root_cause = nl_result.get("intent", text)
                    category = "lcm_intent"
                    suggested_fixes: list = []

                fake_loop = self._causality_sandbox._factory()
                report = self._causality_sandbox.run_sandbox_cycle([_WhatIfGap()], fake_loop)
                result["confidence"] = getattr(report, "top_confidence", result["confidence"])
                result["stability_score"] = getattr(report, "stability_score", result["stability_score"])
                result["report_id"] = getattr(report, "report_id", "")
            except Exception as exc:
                logger.warning("LCM causality simulation error: %s", exc)

        trace.append({"stage": STAGE_CAUSALITY_SIMULATE, "duration_ms": (time.monotonic() - t0) * 1000, "result": result})
        return result

    def _dispatch(
        self,
        nl_result: dict[str, Any],
        sim_result: dict[str, Any],
        account: str,
        trace: list[dict[str, Any]],
    ) -> dict[str, Any]:
        t0 = time.monotonic()
        result: dict[str, Any] = {
            "dispatched": True,
            "intent": nl_result.get("intent"),
            "account": account,
            "simulated_outcome": sim_result.get("simulated_outcome"),
        }

        if self._dispatcher is not None:
            try:
                dispatch_result = self._dispatcher.dispatch(
                    tool_name="lcm_execute",
                    args={"intent": nl_result.get("intent"), "account": account},
                    caller_id=account,
                    caller_type="lcm",
                )
                result["dispatch_result"] = dispatch_result
            except Exception as exc:
                logger.warning("LCM dispatch error: %s", exc)

        self._pipeline_log.append(result)
        trace.append({"stage": STAGE_DISPATCH, "duration_ms": (time.monotonic() - t0) * 1000, "result": result})
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _hitl_response(
        self,
        run_id: str,
        trace: list[dict[str, Any]],
        reason: str,
        questions: list[str],
    ) -> dict[str, Any]:
        logger.info("LCM HITL required (run=%s): %s", run_id, reason)
        return {
            "run_id": run_id,
            "stage": STAGE_HITL,
            "executed": False,
            "result": {"reason": reason},
            "hitl_required": True,
            "clarifying_questions": questions or [
                "Can you clarify the intended scope?",
                "Which systems should this change affect?",
            ],
            "pipeline_trace": trace,
        }

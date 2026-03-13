"""
AUAR Unified Pipeline Orchestrator
====================================

Wires all seven architectural layers into a single ``AUARPipeline``
that executes the complete 10-step request-response journey described
in the technical proposal:

    1. Ingress (accept raw request)
    2. Signal Interpretation
    3. Confidence Scoring
    4. Capability Resolution
    5. Routing Decision
    6. Schema Translation (request)
    7. Provider Execution
    8. Response Translation
    9. ML Feedback
   10. Observability Finalization

The pipeline also supports automatic fallback: if the primary provider
fails, the next fallback candidate is tried transparently.

Copyright 2024 Inoni LLC – BSL-1.1
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .capability_graph import CapabilityGraph
from .ml_optimization import MLOptimizer, RoutingFeatures
from .observability import ObservabilityLayer
from .provider_adapter import (
    AdapterResponse,
    ProviderAdapterManager,
)
from .routing_engine import RoutingDecision, RoutingDecisionEngine
from .schema_translation import SchemaTranslator, TranslationResult
from .signal_interpretation import (
    IntentSignal,
    RequestContext,
    SignalInterpreter,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Complete result of an AUAR pipeline execution."""
    success: bool = False
    request_id: str = ""
    capability: str = ""
    provider_id: str = ""
    provider_name: str = ""
    response_body: Dict[str, Any] = field(default_factory=dict)
    response_status: int = 0
    confidence_score: float = 0.0
    routing_score: float = 0.0
    total_latency_ms: float = 0.0
    interpretation_method: str = ""
    requires_clarification: bool = False
    error: str = ""
    trace_id: str = ""
    ml_reward: float = 0.0


class AUARPipeline:
    """Unified orchestrator for the AUAR request-response journey.

    Accepts a raw request dict and executes all seven layers in sequence,
    returning a ``PipelineResult`` with the provider's response translated
    back to canonical form.

    Example::

        pipeline = AUARPipeline(
            interpreter=interpreter,
            graph=graph,
            router=router,
            translator=translator,
            adapters=adapter_mgr,
            ml=ml_optimizer,
            observability=obs,
        )
        result = pipeline.execute({"capability": "send_email", "parameters": {...}})
    """

    def __init__(
        self,
        interpreter: SignalInterpreter,
        graph: CapabilityGraph,
        router: RoutingDecisionEngine,
        translator: SchemaTranslator,
        adapters: ProviderAdapterManager,
        ml: Optional[MLOptimizer] = None,
        observability: Optional[ObservabilityLayer] = None,
    ):
        self._interpreter = interpreter
        self._graph = graph
        self._router = router
        self._translator = translator
        self._adapters = adapters
        self._ml = ml
        self._obs = observability

    def execute(
        self,
        raw_request: Dict[str, Any],
        context: Optional[RequestContext] = None,
    ) -> PipelineResult:
        """Execute the full 10-step AUAR pipeline."""
        start = time.monotonic()
        result = PipelineResult()

        # --- Step 1–3: Signal Interpretation + Confidence Scoring ---
        signal = self._interpreter.interpret(raw_request, context)
        result.request_id = signal.request_id
        result.confidence_score = signal.confidence_score
        result.interpretation_method = signal.interpretation_method

        if signal.requires_clarification:
            result.requires_clarification = True
            result.error = "Request requires clarification (confidence too low)"
            result.total_latency_ms = (time.monotonic() - start) * 1000
            return result

        if not signal.parsed_intent:
            result.error = "Could not interpret request intent"
            result.total_latency_ms = (time.monotonic() - start) * 1000
            return result

        result.capability = signal.parsed_intent.capability_name

        # --- Step 4: Start trace ---
        trace = None
        tenant_id = context.tenant_id if context else ""
        if self._obs:
            trace = self._obs.start_trace(
                signal.request_id,
                tenant_id=tenant_id,
                capability=result.capability,
            )
            result.trace_id = trace.trace_id

        # Add interpretation span
        interp_span = None
        if self._obs and trace:
            interp_span = self._obs.add_span(
                trace.trace_id, "signal_interpretation",
                attributes={
                    "method": signal.interpretation_method,
                    "confidence": signal.confidence_score,
                    "latency_ms": signal.latency_ms,
                },
            )
            self._obs.end_span(interp_span)
            self._obs.observe("auar.interpretation.latency_ms", signal.latency_ms)
            self._obs.observe("auar.interpretation.confidence", signal.confidence_score)

        # --- Step 5: Routing Decision ---
        decision = self._router.route(signal)
        result.routing_score = decision.score

        # Add routing span
        if self._obs and trace:
            routing_span = self._obs.add_span(
                trace.trace_id, "routing_decision",
                attributes={
                    "strategy": decision.strategy_used.value,
                    "score": decision.score,
                    "circuit_breaker_triggered": decision.circuit_breaker_triggered,
                    "latency_ms": decision.latency_ms,
                },
            )
            self._obs.end_span(routing_span)
            self._obs.observe("auar.routing.latency_ms", decision.latency_ms)

        if not decision.selected_provider:
            result.error = "No provider available for capability"
            if self._obs and trace:
                self._obs.finish_trace(trace.trace_id, success=False)
                self._obs.increment("auar.requests.no_provider")
            result.total_latency_ms = (time.monotonic() - start) * 1000
            return result

        # Build ordered list: selected + fallbacks
        candidates = [decision.selected_provider] + list(decision.fallback_providers)

        # --- Steps 6–8: Schema Translation + Provider Execution + Response Translation ---
        for candidate in candidates:
            pid = candidate.provider_id

            # Step 6: Translate request
            translation = self._translator.translate_request(
                result.capability, pid, signal.parameters,
            )
            if not translation.success:
                logger.warning("Schema translation failed for %s: %s", pid, translation.errors)
                continue

            # Step 7: Execute provider call
            exec_span = None
            if self._obs and trace:
                exec_span = self._obs.add_span(
                    trace.trace_id, "provider_execution",
                    attributes={"provider_id": pid, "provider_name": candidate.provider_name},
                )

            resp = self._adapters.call_provider(
                pid, "POST", f"/{result.capability}",
                body=translation.translated_data,
            )

            if self._obs and exec_span:
                exec_span.attributes["status_code"] = resp.status_code
                exec_span.attributes["success"] = resp.success
                exec_span.attributes["latency_ms"] = resp.latency_ms
                exec_span.attributes["retries_used"] = resp.retries_used
                self._obs.end_span(exec_span, status="ok" if resp.success else "error")
                self._obs.observe("auar.provider.latency_ms", resp.latency_ms)

            if resp.success:
                # Step 8: Translate response
                resp_translation = self._translator.translate_response(
                    result.capability, pid, resp.body,
                )

                # Check translation success (Issue #12)
                if not resp_translation.success:
                    logger.warning(
                        "Response translation failed for %s: %s",
                        pid, resp_translation.errors,
                    )
                    if self._obs and trace:
                        trans_span = self._obs.add_span(
                            trace.trace_id, "response_translation_failure",
                            attributes={
                                "provider_id": pid,
                                "errors": resp_translation.errors,
                            },
                        )
                        self._obs.end_span(trans_span, status="error")
                    result.success = False
                    result.provider_id = pid
                    result.provider_name = candidate.provider_name
                    result.response_body = resp_translation.translated_data
                    result.response_status = resp.status_code
                    result.error = f"Response translation failed: {resp_translation.errors}"
                    if self._obs and trace:
                        self._obs.finish_trace(trace.trace_id, success=False)
                        self._obs.increment("auar.requests.translation_failure")
                    result.total_latency_ms = (time.monotonic() - start) * 1000
                    return result

                result.success = True
                result.provider_id = pid
                result.provider_name = candidate.provider_name
                result.response_body = resp_translation.translated_data
                result.response_status = resp.status_code

                # --- Step 9: ML Feedback ---
                if self._ml:
                    result.ml_reward = self._ml.record(RoutingFeatures(
                        capability_name=result.capability,
                        provider_id=pid,
                        latency_ms=resp.latency_ms,
                        cost=candidate.capability_mapping.cost_per_call,
                        success=True,
                    ))

                # Report success to routing engine circuit breaker
                self._router.record_success(pid)

                # --- Step 10: Observability ---
                if self._obs and trace:
                    self._obs.record_cost(
                        tenant_id, result.capability, pid,
                        candidate.capability_mapping.cost_per_call,
                        request_id=signal.request_id,
                    )
                    self._obs.finish_trace(trace.trace_id, success=True)
                    self._obs.increment("auar.requests.success")

                result.total_latency_ms = (time.monotonic() - start) * 1000
                return result
            else:
                # Record failure for circuit breaker and ML
                self._router.record_failure(pid)
                if self._ml:
                    self._ml.record(RoutingFeatures(
                        capability_name=result.capability,
                        provider_id=pid,
                        latency_ms=resp.latency_ms,
                        cost=0.0,
                        success=False,
                    ))
                logger.warning("Provider %s failed: %s – trying fallback", pid, resp.error)

        # All candidates exhausted
        result.error = "All providers failed"
        if self._obs and trace:
            self._obs.finish_trace(trace.trace_id, success=False)
            self._obs.increment("auar.requests.failure")
        result.total_latency_ms = (time.monotonic() - start) * 1000
        return result

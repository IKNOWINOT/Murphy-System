# Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
integrations/langchain_safety_layer.py
========================================
LangChain-compatible safety layer for the Murphy Confidence Engine.

Works WITHOUT LangChain installed — uses duck-typing for full compatibility.

Classes
-------
MurphyConfidenceCallback
    Drop-in LangChain callback handler that scores every LLM output.

MurphySafetyGateChain
    Wraps any LangChain chain and interposes Murphy safety gates before
    output is returned to the caller.

MurphyConfidenceRunnable
    Composable unit for LangGraph pipelines; implements ``invoke`` /
    ``batch`` / ``stream`` interface.

Usage (with LangChain installed)::

    from langchain.callbacks import CallbackManager
    from integrations.langchain_safety_layer import MurphyConfidenceCallback

    callback = MurphyConfidenceCallback(phase=Phase.EXECUTE, hazard_floor=0.10)
    manager  = CallbackManager(handlers=[callback])
    llm      = OpenAI(callback_manager=manager)
    result   = llm("Recommend a drug dosage for patient 42.")
    # If confidence < threshold the callback raises MurphyGateBlockedError.

Usage (without LangChain)::

    runnable = MurphyConfidenceRunnable(
        inner_fn=lambda x: {"output": x["input"].upper()},
        phase=Phase.EXECUTE,
        goodness_fn=lambda x, y: 0.85,
        domain_fn=lambda x, y: 0.80,
        hazard_fn=lambda x, y: 0.05,
    )
    output = runnable.invoke({"input": "hello"})
"""

from __future__ import annotations

import sys
import os
import logging
from typing import Any, Callable, Dict, List, Optional, Union

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from murphy_confidence import compute_confidence, GateCompiler, SafetyGate
from murphy_confidence.types import Phase, GateAction, GateType, ConfidenceResult, GateResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class MurphyGateBlockedError(RuntimeError):
    """Raised when a blocking safety gate prevents execution."""

    def __init__(self, gate_result: GateResult, confidence_result: ConfidenceResult) -> None:
        self.gate_result       = gate_result
        self.confidence_result = confidence_result
        super().__init__(gate_result.message)


# ---------------------------------------------------------------------------
# MurphyConfidenceCallback
# ---------------------------------------------------------------------------

class MurphyConfidenceCallback:
    """
    LangChain-compatible callback handler that scores LLM outputs through
    the Murphy confidence engine.

    Compatible with ``langchain.callbacks.base.BaseCallbackHandler`` via
    duck-typing — no LangChain import required.

    Parameters
    ----------
    phase:
        Pipeline phase to use for scoring (default: ``Phase.EXECUTE``).
    hazard_floor:
        Minimum hazard score injected regardless of per-call value.
    blocking_threshold:
        Confidence score below which a blocking gate fires.
    goodness_fn:
        ``(prompt, output) → float`` — computes G(x).  Defaults to constant 0.75.
    domain_fn:
        ``(prompt, output) → float`` — computes D(x).  Defaults to constant 0.75.
    hazard_fn:
        ``(prompt, output) → float`` — computes H(x).  Defaults to ``hazard_floor``.
    """

    def __init__(
        self,
        phase: Phase = Phase.EXECUTE,
        hazard_floor: float = 0.05,
        blocking_threshold: float = 0.70,
        goodness_fn: Optional[Callable[[str, str], float]] = None,
        domain_fn:   Optional[Callable[[str, str], float]] = None,
        hazard_fn:   Optional[Callable[[str, str], float]] = None,
    ) -> None:
        self.phase               = phase
        self.hazard_floor        = hazard_floor
        self.blocking_threshold  = blocking_threshold
        self._goodness_fn = goodness_fn or (lambda p, o: 0.75)
        self._domain_fn   = domain_fn   or (lambda p, o: 0.75)
        self._hazard_fn   = hazard_fn   or (lambda p, o: hazard_floor)
        self._last_result: Optional[ConfidenceResult] = None

    # -- LangChain callback interface (duck-typed) ---------------------------

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        self._current_prompts = prompts

    def on_llm_end(self, response: Any, **kwargs: Any) -> None:
        prompt = getattr(self, "_current_prompts", [""])[0]
        try:
            output_text = response.generations[0][0].text
        except (AttributeError, IndexError):
            output_text = str(response)

        goodness = self._goodness_fn(prompt, output_text)
        domain   = self._domain_fn(prompt, output_text)
        hazard   = max(self.hazard_floor, self._hazard_fn(prompt, output_text))

        result = compute_confidence(goodness, domain, hazard, self.phase)
        self._last_result = result
        logger.info("MurphyCallback: %s", result.rationale)

        if result.score < self.blocking_threshold:
            # Synthesise a blocking executive gate
            gate    = SafetyGate("callback_exec", GateType.EXECUTIVE, blocking=True,
                                 threshold=self.blocking_threshold)
            gr      = gate.evaluate(result)
            raise MurphyGateBlockedError(gr, result)

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        logger.error("LLM error in MurphyConfidenceCallback: %s", error)

    def on_chain_start(self, *args: Any, **kwargs: Any) -> None:
        pass

    def on_chain_end(self, *args: Any, **kwargs: Any) -> None:
        pass

    def on_chain_error(self, error: BaseException, **kwargs: Any) -> None:
        logger.error("Chain error in MurphyConfidenceCallback: %s", error)

    @property
    def last_confidence_result(self) -> Optional[ConfidenceResult]:
        """The most recent :class:`ConfidenceResult` produced by this handler."""
        return self._last_result


# ---------------------------------------------------------------------------
# MurphySafetyGateChain
# ---------------------------------------------------------------------------

class MurphySafetyGateChain:
    """
    Wraps any LangChain chain (or plain callable) with Murphy safety gates.

    Usage::

        wrapped = MurphySafetyGateChain(
            chain=my_llm_chain,
            phase=Phase.EXECUTE,
            gates=[SafetyGate("hipaa", GateType.COMPLIANCE)],
        )
        output = wrapped.run({"question": "What medication should I prescribe?"})

    Parameters
    ----------
    chain:
        Any object with a ``run(input)`` or ``__call__(input)`` method.
    phase:
        Pipeline phase for confidence scoring.
    gates:
        Pre-configured list of :class:`SafetyGate` objects to evaluate.
        If ``None`` the compiler auto-generates gates.
    goodness_fn:
        ``(input, output) → float`` — computes G(x).
    domain_fn:
        ``(input, output) → float`` — computes D(x).
    hazard_fn:
        ``(input, output) → float`` — computes H(x).
    """

    def __init__(
        self,
        chain: Any,
        phase: Phase = Phase.EXECUTE,
        gates: Optional[List[SafetyGate]] = None,
        goodness_fn: Optional[Callable] = None,
        domain_fn:   Optional[Callable] = None,
        hazard_fn:   Optional[Callable] = None,
    ) -> None:
        self._chain      = chain
        self.phase       = phase
        self._gates      = gates
        self._compiler   = GateCompiler()
        self._goodness_fn = goodness_fn or (lambda i, o: 0.80)
        self._domain_fn   = domain_fn   or (lambda i, o: 0.80)
        self._hazard_fn   = hazard_fn   or (lambda i, o: 0.10)

    def run(self, chain_input: Any) -> Any:
        """Run the inner chain and evaluate Murphy safety gates on the output."""
        if hasattr(self._chain, "run"):
            output = self._chain.run(chain_input)
        else:
            output = self._chain(chain_input)

        input_str  = str(chain_input)
        output_str = str(output)

        goodness = self._goodness_fn(input_str, output_str)
        domain   = self._domain_fn(input_str, output_str)
        hazard   = self._hazard_fn(input_str, output_str)

        confidence_result = compute_confidence(goodness, domain, hazard, self.phase)

        gates = self._gates or self._compiler.compile_gates(confidence_result)
        for gate in gates:
            gr = gate.evaluate(confidence_result)
            logger.info("Gate %s: %s", gate.gate_id, gr.message)
            if gate.blocking and not gr.passed:
                raise MurphyGateBlockedError(gr, confidence_result)

        return output

    __call__ = run


# ---------------------------------------------------------------------------
# MurphyConfidenceRunnable
# ---------------------------------------------------------------------------

class MurphyConfidenceRunnable:
    """
    Composable unit compatible with LangGraph / LCEL pipelines.

    Implements ``invoke`` / ``batch`` / ``stream`` interface so it can be
    inserted into any ``|``-composed pipeline.

    Usage in a pipeline::

        chain = prompt | llm | MurphyConfidenceRunnable(inner_fn=parser)
        result = chain.invoke({"topic": "medicine"})

    Parameters
    ----------
    inner_fn:
        ``(input_dict) → output_dict`` — the wrapped computation.
    phase:
        Pipeline phase for scoring.
    goodness_fn / domain_fn / hazard_fn:
        ``(input_dict, output_dict) → float`` scorers.
    extra_gates:
        Additional :class:`SafetyGate` objects merged with compiled gates.
    """

    def __init__(
        self,
        inner_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
        phase: Phase = Phase.EXECUTE,
        goodness_fn: Optional[Callable] = None,
        domain_fn:   Optional[Callable] = None,
        hazard_fn:   Optional[Callable] = None,
        extra_gates: Optional[List[SafetyGate]] = None,
    ) -> None:
        self._inner      = inner_fn
        self.phase       = phase
        self._compiler   = GateCompiler()
        self._goodness_fn = goodness_fn or (lambda i, o: 0.80)
        self._domain_fn   = domain_fn   or (lambda i, o: 0.80)
        self._hazard_fn   = hazard_fn   or (lambda i, o: 0.10)
        self._extra_gates = extra_gates or []

    # -- LCEL-compatible interface -------------------------------------------

    def invoke(self, input_data: Dict[str, Any], config: Any = None) -> Dict[str, Any]:
        output = self._inner(input_data)
        self._evaluate_gates(input_data, output)
        return output

    def batch(
        self,
        inputs: List[Dict[str, Any]],
        config: Any = None,
    ) -> List[Dict[str, Any]]:
        return [self.invoke(inp, config) for inp in inputs]

    def stream(self, input_data: Dict[str, Any], config: Any = None):
        output = self.invoke(input_data, config)
        yield output

    def __or__(self, other: Any) -> "_ComposedRunnable":
        return _ComposedRunnable(self, other)

    # -- Internal ------------------------------------------------------------

    def _evaluate_gates(
        self,
        input_data: Dict[str, Any],
        output_data: Dict[str, Any],
    ) -> None:
        goodness = self._goodness_fn(input_data, output_data)
        domain   = self._domain_fn(input_data, output_data)
        hazard   = self._hazard_fn(input_data, output_data)

        confidence_result = compute_confidence(goodness, domain, hazard, self.phase)
        gates = self._compiler.compile_gates(
            confidence_result,
            context={"extra_gates": self._extra_gates} if self._extra_gates else None,
        )
        for gate in gates:
            gr = gate.evaluate(confidence_result)
            logger.info("Runnable gate %s: %s", gate.gate_id, gr.message)
            if gate.blocking and not gr.passed:
                raise MurphyGateBlockedError(gr, confidence_result)


class _ComposedRunnable:
    """Minimal composition helper (mirrors LCEL pipe operator)."""

    def __init__(self, first: Any, second: Any) -> None:
        self._first  = first
        self._second = second

    def invoke(self, input_data: Any, config: Any = None) -> Any:
        intermediate = self._first.invoke(input_data, config)
        return self._second.invoke(intermediate, config)

    def __or__(self, other: Any) -> "_ComposedRunnable":
        return _ComposedRunnable(self, other)

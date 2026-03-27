"""Composite planning engine combining Valon utilities."""
from __future__ import annotations

from typing import List, Optional
import numpy as np

from .valon import Plan, prioritize, Prioritizer, ml_prioritize
from .plan_structurer_bot import SubPlan
from .plan_structurer_bot import PlanStructurerBot
from .recursive_executor_bot import RecursiveExecutorBot
from .clarifier_bot import ClarifierBot, PromptRefinerBot
from .local_summarizer_bot import LocalSummarizerBot, SummaryEvaluatorBot


class ValonEngine:
    def __init__(self, coef: Optional[np.ndarray] = None, model_path: str | None = None) -> None:
        self.prioritizer = Prioritizer(coef) if coef is not None else None
        self.model_path = model_path
        self.structurer = PlanStructurerBot()
        self.executor = RecursiveExecutorBot()
        self.clarifier = ClarifierBot()
        self.refiner = PromptRefinerBot()
        self.summarizer = LocalSummarizerBot()
        self.evaluator = SummaryEvaluatorBot()

    # -- planning ----------------------------------------------------------
    def prioritize_plans(self, plans: List[Plan], features: np.ndarray) -> List[Plan]:
        if self.model_path:
            return ml_prioritize(plans, features, self.model_path)
        if self.prioritizer:
            return self.prioritizer.prioritize(plans, features)
        return prioritize(plans, features)

    def create_subplans(self, plan_id: str, steps: List[str], chunk: int = 2) -> List[SubPlan]:
        return self.structurer.create_subplans(plan_id, steps, chunk)

    def execute_subplan(self, subplan: SubPlan) -> List[str]:
        return self.executor.execute(subplan)

    # -- NLP utilities -----------------------------------------------------
    class ValonNLPServices:
        def __init__(self, clarifier: ClarifierBot, refiner: PromptRefinerBot, summarizer: LocalSummarizerBot) -> None:
            self.clarifier = clarifier
            self.refiner = refiner
            self.summarizer = summarizer

        def clarify_prompt(self, prompt: str) -> str | None:
            return self.clarifier.maybe_clarify(prompt)

        def summarize(self, text: str) -> str:
            return self.summarizer.summarize(text)

    @property
    def nlp(self) -> "ValonEngine.ValonNLPServices":
        return ValonEngine.ValonNLPServices(self.clarifier, self.refiner, self.summarizer)

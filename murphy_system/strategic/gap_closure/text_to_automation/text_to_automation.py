# Copyright © 2020-2026 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
text_to_automation.py — Murphy System "Describe → Execute" Engine

Converts plain-English descriptions into governed, validated automation
workflows.  This is the core evidence for the No-Code/Low-Code UX gap
closure: Murphy's text-to-automation paradigm is *superior* to traditional
drag-and-drop no-code builders because users describe intent in natural
language and receive a fully-wired, safety-gated DAG — no visual wiring
required.

Flow:
  1. User describes an automation in plain English.
  2. Engine parses keywords, matches templates, infers steps.
  3. Dependencies are resolved; safety gates are injected.
  4. A governed workflow DAG is returned ready for execution.

Standalone — uses only Python stdlib.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Step types
# ---------------------------------------------------------------------------

class StepType(Enum):
    DATA_RETRIEVAL = "data_retrieval"
    DATA_TRANSFORMATION = "data_transformation"
    VALIDATION = "validation"
    NOTIFICATION = "notification"
    DATA_OUTPUT = "data_output"
    ANALYSIS = "analysis"
    COMPUTATION = "computation"
    DEPLOYMENT = "deployment"
    APPROVAL = "approval"
    EXECUTION = "execution"
    SECURITY = "security"
    SCHEDULING = "scheduling"
    ERROR_HANDLING = "error_handling"
    GOVERNANCE_GATE = "governance_gate"


# ---------------------------------------------------------------------------
# Keyword → step type mapping
# ---------------------------------------------------------------------------

KEYWORD_MAP: Dict[str, StepType] = {
    # retrieval
    "fetch": StepType.DATA_RETRIEVAL, "get": StepType.DATA_RETRIEVAL,
    "pull": StepType.DATA_RETRIEVAL, "download": StepType.DATA_RETRIEVAL,
    "read": StepType.DATA_RETRIEVAL, "collect": StepType.DATA_RETRIEVAL,
    "extract": StepType.DATA_RETRIEVAL, "ingest": StepType.DATA_RETRIEVAL,
    "monitor": StepType.DATA_RETRIEVAL, "watch": StepType.DATA_RETRIEVAL,
    # transformation
    "transform": StepType.DATA_TRANSFORMATION,
    "convert": StepType.DATA_TRANSFORMATION,
    "parse": StepType.DATA_TRANSFORMATION,
    "format": StepType.DATA_TRANSFORMATION,
    "clean": StepType.DATA_TRANSFORMATION,
    "normalize": StepType.DATA_TRANSFORMATION,
    "map": StepType.DATA_TRANSFORMATION,
    # validation
    "validate": StepType.VALIDATION, "check": StepType.VALIDATION,
    "verify": StepType.VALIDATION, "ensure": StepType.VALIDATION,
    "test": StepType.VALIDATION,
    # notification
    "send": StepType.NOTIFICATION, "notify": StepType.NOTIFICATION,
    "alert": StepType.NOTIFICATION, "email": StepType.NOTIFICATION,
    "slack": StepType.NOTIFICATION, "message": StepType.NOTIFICATION,
    # output
    "write": StepType.DATA_OUTPUT, "save": StepType.DATA_OUTPUT,
    "store": StepType.DATA_OUTPUT, "export": StepType.DATA_OUTPUT,
    "upload": StepType.DATA_OUTPUT, "publish": StepType.DATA_OUTPUT,
    # analysis
    "analyze": StepType.ANALYSIS, "report": StepType.ANALYSIS,
    "summarize": StepType.ANALYSIS, "aggregate": StepType.ANALYSIS,
    # computation
    "calculate": StepType.COMPUTATION, "compute": StepType.COMPUTATION,
    "process": StepType.COMPUTATION,
    # deployment
    "deploy": StepType.DEPLOYMENT, "release": StepType.DEPLOYMENT,
    "provision": StepType.DEPLOYMENT, "launch": StepType.DEPLOYMENT,
    # approval
    "approve": StepType.APPROVAL, "review": StepType.APPROVAL,
    # security
    "encrypt": StepType.SECURITY, "authenticate": StepType.SECURITY,
    # scheduling
    "schedule": StepType.SCHEDULING, "cron": StepType.SCHEDULING,
}

# Implicit dependency rules — step type B depends on step type A
DEPENDENCY_RULES: Dict[StepType, List[StepType]] = {
    StepType.DATA_TRANSFORMATION: [StepType.DATA_RETRIEVAL],
    StepType.VALIDATION: [StepType.DATA_RETRIEVAL, StepType.DATA_TRANSFORMATION],
    StepType.ANALYSIS: [StepType.DATA_RETRIEVAL, StepType.DATA_TRANSFORMATION],
    StepType.COMPUTATION: [StepType.DATA_RETRIEVAL],
    StepType.DATA_OUTPUT: [StepType.DATA_TRANSFORMATION, StepType.COMPUTATION, StepType.ANALYSIS],
    StepType.NOTIFICATION: [StepType.VALIDATION, StepType.ANALYSIS, StepType.DATA_OUTPUT, StepType.DEPLOYMENT],
    StepType.DEPLOYMENT: [StepType.VALIDATION, StepType.DATA_OUTPUT],
    StepType.APPROVAL: [StepType.ANALYSIS, StepType.VALIDATION],
    StepType.ERROR_HANDLING: [StepType.EXECUTION, StepType.DEPLOYMENT],
}


# ---------------------------------------------------------------------------
# Templates — common automation patterns
# ---------------------------------------------------------------------------

AUTOMATION_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "etl_pipeline": {
        "description": "Extract-Transform-Load data pipeline",
        "keywords": ["etl", "pipeline", "extract", "transform", "load", "data"],
        "steps": [
            {"name": "extract", "type": "data_retrieval", "label": "Extract data from source"},
            {"name": "transform", "type": "data_transformation", "label": "Transform and clean data"},
            {"name": "validate", "type": "validation", "label": "Validate transformed data"},
            {"name": "load", "type": "data_output", "label": "Load data into destination"},
        ],
    },
    "monitoring_alert": {
        "description": "Monitor metrics and send alerts",
        "keywords": ["monitor", "alert", "notify", "watch", "metric", "threshold"],
        "steps": [
            {"name": "monitor", "type": "data_retrieval", "label": "Monitor data source"},
            {"name": "analyze", "type": "analysis", "label": "Analyze against thresholds"},
            {"name": "alert", "type": "notification", "label": "Send alert notifications"},
        ],
    },
    "report_generation": {
        "description": "Collect data and generate reports",
        "keywords": ["report", "summary", "weekly", "daily", "analytics", "dashboard"],
        "steps": [
            {"name": "collect", "type": "data_retrieval", "label": "Collect data from sources"},
            {"name": "analyze", "type": "analysis", "label": "Analyze and summarize data"},
            {"name": "generate", "type": "data_output", "label": "Generate report"},
            {"name": "distribute", "type": "notification", "label": "Distribute to recipients"},
        ],
    },
    "ci_cd_pipeline": {
        "description": "Continuous integration and deployment",
        "keywords": ["ci", "cd", "build", "test", "deploy", "release"],
        "steps": [
            {"name": "fetch_code", "type": "data_retrieval", "label": "Fetch latest code"},
            {"name": "run_tests", "type": "validation", "label": "Run test suite"},
            {"name": "build", "type": "computation", "label": "Build artifacts"},
            {"name": "approval_gate", "type": "approval", "label": "Approval for production"},
            {"name": "deploy", "type": "deployment", "label": "Deploy to production"},
        ],
    },
    "customer_onboarding": {
        "description": "Automated customer onboarding",
        "keywords": ["onboard", "customer", "welcome", "account", "setup"],
        "steps": [
            {"name": "validate_info", "type": "validation", "label": "Validate customer info"},
            {"name": "provision", "type": "deployment", "label": "Provision account"},
            {"name": "welcome", "type": "notification", "label": "Send welcome email"},
        ],
    },
    "incident_response": {
        "description": "Automated incident detection and response",
        "keywords": ["incident", "alert", "respond", "triage", "outage", "escalate"],
        "steps": [
            {"name": "detect", "type": "data_retrieval", "label": "Detect incident"},
            {"name": "triage", "type": "analysis", "label": "Assess severity"},
            {"name": "notify_team", "type": "notification", "label": "Alert on-call team"},
            {"name": "remediate", "type": "execution", "label": "Apply automated fix"},
            {"name": "verify", "type": "validation", "label": "Verify resolution"},
        ],
    },
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AutomationStep:
    """A single step in a generated automation."""
    name: str
    step_type: str
    label: str
    depends_on: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    governance_gate: bool = False


@dataclass
class AutomationWorkflow:
    """A complete automation generated from a text description."""
    workflow_id: str
    name: str
    description: str
    strategy: str
    template_used: Optional[str]
    steps: List[AutomationStep]
    governance_gates: List[str]
    generated_at: str
    valid: bool = True
    warnings: List[str] = field(default_factory=list)

    @property
    def step_count(self) -> int:
        return len(self.steps)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["step_count"] = self.step_count
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def execution_order(self) -> List[str]:
        """Return step names in dependency-resolved order."""
        visited: set = set()
        order: List[str] = []
        name_to_step = {s.name: s for s in self.steps}

        def _visit(name: str) -> None:
            if name in visited:
                return
            visited.add(name)
            step = name_to_step.get(name)
            if step:
                for dep in step.depends_on:
                    _visit(dep)
            order.append(name)

        for s in self.steps:
            _visit(s.name)
        return order


# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------

class TextToAutomationEngine:
    """
    Murphy System "Describe → Execute" engine.

    Converts plain-English descriptions into governed automation workflows:
      1. Template matching — known patterns (ETL, CI/CD, monitoring, etc.)
      2. Keyword inference — extracts action verbs and maps to step types
      3. Dependency resolution — wires steps into a DAG
      4. Governance injection — inserts safety gates at critical junctures
    """

    def __init__(self, *, inject_governance: bool = True) -> None:
        self._templates: Dict[str, Dict[str, Any]] = dict(AUTOMATION_TEMPLATES)
        self._inject_governance = inject_governance
        self._history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def describe(self, text: str) -> AutomationWorkflow:
        """Convert a plain-English description into an AutomationWorkflow.

        This is the primary entry point — the "Describe" in "Describe → Execute".

        Args:
            text: A natural-language description of the desired automation.
                  e.g. "Monitor sales data and send a weekly summary to Slack."

        Returns:
            An ``AutomationWorkflow`` ready for execution/review.
        """
        text_lower = text.lower().strip()
        if not text_lower:
            return self._empty_workflow(text)

        # 1. Template match
        match = self._match_template(text_lower)

        # 2. Keyword inference
        inferred = self._infer_steps(text_lower)

        # 3. Decide strategy
        if match and match["score"] >= 0.5:
            steps = self._steps_from_template(match["template"])
            strategy = "template_match"
            template_name: Optional[str] = match["name"]
        elif inferred:
            steps = self._steps_from_inference(inferred, text_lower)
            strategy = "keyword_inference"
            template_name = None
        else:
            steps = self._generic_steps(text_lower)
            strategy = "generic_fallback"
            template_name = None

        # 4. Resolve dependencies
        steps = self._resolve_deps(steps)

        # 5. Inject governance gates
        gates: List[str] = []
        if self._inject_governance:
            steps, gates = self._inject_gates(steps)

        # 6. Validate
        warnings = self._validate(steps)

        # 7. Build workflow
        wf_id = hashlib.sha256(
            f"{text}:{uuid.uuid4().hex}".encode()
        ).hexdigest()[:12]

        wf = AutomationWorkflow(
            workflow_id=wf_id,
            name=self._name_from_description(text),
            description=text,
            strategy=strategy,
            template_used=template_name,
            steps=steps,
            governance_gates=gates,
            generated_at=datetime.now(timezone.utc).isoformat(),
            valid=len([w for w in warnings if w.startswith("ERROR")]) == 0,
            warnings=warnings,
        )

        self._history.append({
            "workflow_id": wf.workflow_id,
            "description": text[:200],
            "strategy": strategy,
            "step_count": wf.step_count,
            "gates": len(gates),
            "timestamp": wf.generated_at,
        })

        return wf

    def add_template(self, name: str, template: Dict[str, Any]) -> bool:
        """Register a custom automation template."""
        required = {"description", "keywords", "steps"}
        if not required.issubset(template.keys()):
            return False
        self._templates[name] = template
        return True

    def list_templates(self) -> List[Dict[str, str]]:
        """List available automation templates."""
        return [
            {"name": n, "description": t["description"], "step_count": str(len(t["steps"]))}
            for n, t in self._templates.items()
        ]

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent generation history."""
        return list(self._history[-limit:])

    # ------------------------------------------------------------------
    # Template matching
    # ------------------------------------------------------------------

    def _match_template(self, text: str) -> Optional[Dict[str, Any]]:
        best: Optional[Dict[str, Any]] = None
        best_score = 0.0
        for name, tmpl in self._templates.items():
            kws = tmpl.get("keywords", [])
            if not kws:
                continue
            hits = sum(1 for kw in kws if kw in text)
            score = hits / len(kws)
            if score > best_score:
                best_score = score
                best = {"name": name, "template": tmpl, "score": score}
        return best

    # ------------------------------------------------------------------
    # Keyword inference
    # ------------------------------------------------------------------

    def _infer_steps(self, text: str) -> List[Tuple[str, StepType]]:
        words = re.findall(r"\b[a-z]+(?:-[a-z]+)*\b", text)
        found: List[Tuple[str, StepType]] = []
        seen: set = set()
        for w in words:
            if w in KEYWORD_MAP:
                st = KEYWORD_MAP[w]
                if st not in seen:
                    seen.add(st)
                    found.append((w, st))
        return found

    # ------------------------------------------------------------------
    # Step builders
    # ------------------------------------------------------------------

    def _steps_from_template(self, tmpl: Dict[str, Any]) -> List[AutomationStep]:
        return [
            AutomationStep(
                name=s["name"],
                step_type=s["type"],
                label=s["label"],
            )
            for s in tmpl["steps"]
        ]

    def _steps_from_inference(self, inferred: List[Tuple[str, StepType]],
                              text: str) -> List[AutomationStep]:
        steps: List[AutomationStep] = []
        for keyword, stype in inferred:
            ctx = self._context_around(text, keyword)
            steps.append(AutomationStep(
                name=f"{keyword}_{stype.value}",
                step_type=stype.value,
                label=f"{keyword.title()}: {ctx}" if ctx else f"{keyword.title()} step",
            ))
        return steps

    def _generic_steps(self, text: str) -> List[AutomationStep]:
        return [
            AutomationStep(name="input", step_type="data_retrieval",
                           label=f"Process input: {text[:60]}"),
            AutomationStep(name="execute", step_type="execution",
                           label="Execute main task"),
            AutomationStep(name="output", step_type="data_output",
                           label="Generate output"),
        ]

    def _context_around(self, text: str, keyword: str) -> str:
        idx = text.find(keyword)
        if idx == -1:
            return ""
        start = max(0, idx - 20)
        end = min(len(text), idx + len(keyword) + 20)
        return text[start:end].strip()

    # ------------------------------------------------------------------
    # Dependency resolution
    # ------------------------------------------------------------------

    def _resolve_deps(self, steps: List[AutomationStep]) -> List[AutomationStep]:
        name_to_type: Dict[str, str] = {s.name: s.step_type for s in steps}
        type_to_names: Dict[str, List[str]] = {}
        for s in steps:
            type_to_names.setdefault(s.step_type, []).append(s.name)

        for s in steps:
            try:
                stype = StepType(s.step_type)
            except ValueError:
                continue
            dep_types = DEPENDENCY_RULES.get(stype, [])
            for dt in dep_types:
                candidates = type_to_names.get(dt.value, [])
                for c in candidates:
                    if c != s.name and c not in s.depends_on:
                        s.depends_on.append(c)
        return steps

    # ------------------------------------------------------------------
    # Governance gate injection
    # ------------------------------------------------------------------

    def _inject_gates(self, steps: List[AutomationStep]) -> Tuple[List[AutomationStep], List[str]]:
        """Insert governance gates before critical steps (deployment, notification, security)."""
        critical_types = {"deployment", "notification", "security"}
        augmented: List[AutomationStep] = []
        gates: List[str] = []

        for s in steps:
            if s.step_type in critical_types:
                gate_name = f"gate_before_{s.name}"
                gate = AutomationStep(
                    name=gate_name,
                    step_type="governance_gate",
                    label=f"Safety gate before {s.label}",
                    depends_on=list(s.depends_on),
                    governance_gate=True,
                )
                augmented.append(gate)
                gates.append(gate_name)
                # Make the critical step depend on its gate
                s.depends_on = [gate_name]
            augmented.append(s)

        return augmented, gates

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate(self, steps: List[AutomationStep]) -> List[str]:
        warnings: List[str] = []
        names = {s.name for s in steps}
        for s in steps:
            for dep in s.depends_on:
                if dep not in names:
                    warnings.append(f"WARNING: Step '{s.name}' depends on unknown step '{dep}'")
        if not steps:
            warnings.append("ERROR: No steps generated")
        return warnings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _name_from_description(self, text: str) -> str:
        words = re.findall(r"\b[a-zA-Z]+\b", text)
        slug = "_".join(words[:5]).lower()
        return slug or "automation"

    def _empty_workflow(self, text: str) -> AutomationWorkflow:
        return AutomationWorkflow(
            workflow_id="empty",
            name="empty",
            description=text,
            strategy="none",
            template_used=None,
            steps=[],
            governance_gates=[],
            generated_at=datetime.now(timezone.utc).isoformat(),
            valid=False,
            warnings=["ERROR: No steps generated"],
        )


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------

def main() -> None:
    engine = TextToAutomationEngine()

    examples = [
        "Monitor my sales data and send a weekly summary to Slack.",
        "Set up a CI/CD pipeline: fetch code, run tests, build, deploy to production.",
        "Extract customer records, transform to CSV, validate emails, then upload to S3.",
        "When a new incident is detected, triage severity, notify the on-call team.",
    ]

    print("=" * 70)
    print("  MURPHY SYSTEM — Text-to-Automation Engine")
    print("  'Describe → Execute' — Superior to drag-and-drop no-code")
    print("=" * 70)

    for desc in examples:
        wf = engine.describe(desc)
        print(f"\n  📝 \"{desc}\"")
        print(f"     Strategy   : {wf.strategy}")
        print(f"     Template   : {wf.template_used or '—'}")
        print(f"     Steps      : {wf.step_count}")
        print(f"     Gov. Gates : {len(wf.governance_gates)}")
        print(f"     Valid      : {'✅' if wf.valid else '❌'}")
        for s in wf.steps:
            gate_marker = " 🛡️" if s.governance_gate else ""
            deps = f" (← {', '.join(s.depends_on)})" if s.depends_on else ""
            print(f"       → [{s.step_type:>22}] {s.label}{gate_marker}{deps}")

    print("\n" + "=" * 70)
    print(f"  Total automations generated: {len(engine.get_history())}")
    print("=" * 70)


if __name__ == "__main__":
    main()

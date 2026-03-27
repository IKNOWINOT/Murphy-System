"""
Concept Translation Engine — Nontechnical-to-Technical Mapping

Design Label: CTE-001 — Concept Translation Engine
Owner: Systems Engineering
Dependencies: None (standard library only)

Purpose:
    Translates nontechnical language into structured technical analogues
    suitable for the Murphy System. Performs concept extraction, regulatory
    domain detection, reasoning-method classification, and system-model
    generation using deterministic heuristics.

Flow:
    1. Receive free-form text input.
    2. Extract actor-action-goal-constraint tuples from sentences.
    3. Map nontechnical phrases to technical analogues via the normalization table.
    4. Detect applicable regulatory domains and generate module specs.
    5. Classify reasoning method (deduction vs. induction).
    6. Build a preliminary system model from extracted concepts.
    7. Return a fully populated TechnicalAnalogue dataclass.

Safety invariants:
    - Thread-safe: all mutable shared state guarded by threading.Lock.
    - Deterministic: no randomness, no LLM calls.
    - Pure standard-library implementation.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Domain Normalization Table
# ---------------------------------------------------------------------------

NORMALIZATION_TABLE: List[Dict[str, str]] = [
    # High-level phrases
    {"nontechnical": "improve speed", "technical_analogue": "optimization", "structural_category": "operational_element", "murphy_module": "optimization_engine"},
    {"nontechnical": "track things", "technical_analogue": "monitoring system", "structural_category": "component", "murphy_module": "monitoring_engine"},
    {"nontechnical": "send messages", "technical_analogue": "communication protocol", "structural_category": "component", "murphy_module": "event_backbone"},
    {"nontechnical": "manage people", "technical_analogue": "workflow management", "structural_category": "process", "murphy_module": "workflow_engine"},
    {"nontechnical": "make sure rules followed", "technical_analogue": "compliance engine", "structural_category": "component", "murphy_module": "compliance_engine"},
    {"nontechnical": "keep safe", "technical_analogue": "safety monitoring", "structural_category": "component", "murphy_module": "security_engine"},
    {"nontechnical": "save money", "technical_analogue": "cost optimization", "structural_category": "process", "murphy_module": "budget_optimizer"},
    # Structural elements
    {"nontechnical": "module", "technical_analogue": "structural element", "structural_category": "component", "murphy_module": "module_manager"},
    {"nontechnical": "instrument", "technical_analogue": "structural element", "structural_category": "component", "murphy_module": "module_manager"},
    {"nontechnical": "service", "technical_analogue": "structural element", "structural_category": "component", "murphy_module": "module_manager"},
    {"nontechnical": "component", "technical_analogue": "structural element", "structural_category": "component", "murphy_module": "module_manager"},
    {"nontechnical": "asset", "technical_analogue": "structural element", "structural_category": "component", "murphy_module": "module_manager"},
    {"nontechnical": "function", "technical_analogue": "structural element", "structural_category": "component", "murphy_module": "module_manager"},
    # Operational elements
    {"nontechnical": "process", "technical_analogue": "operational element", "structural_category": "process", "murphy_module": "workflow_engine"},
    {"nontechnical": "transaction", "technical_analogue": "operational element", "structural_category": "process", "murphy_module": "workflow_engine"},
    {"nontechnical": "workflow", "technical_analogue": "operational element", "structural_category": "process", "murphy_module": "workflow_engine"},
    # Validation elements
    {"nontechnical": "test", "technical_analogue": "validation element", "structural_category": "validation", "murphy_module": "validation_engine"},
    {"nontechnical": "audit", "technical_analogue": "validation element", "structural_category": "validation", "murphy_module": "compliance_engine"},
    {"nontechnical": "inspection", "technical_analogue": "validation element", "structural_category": "validation", "murphy_module": "validation_engine"},
    # Environmental / Sustainability concepts
    {"nontechnical": "go green", "technical_analogue": "sustainability_engine", "structural_category": "process", "murphy_module": "sustainability_engine"},
    {"nontechnical": "reduce waste", "technical_analogue": "waste_optimization", "structural_category": "process", "murphy_module": "waste_optimization"},
    {"nontechnical": "clean energy", "technical_analogue": "energy_optimization", "structural_category": "process", "murphy_module": "energy_optimization"},
    {"nontechnical": "fair wages", "technical_analogue": "labor_compliance", "structural_category": "component", "murphy_module": "labor_compliance"},
    {"nontechnical": "recycle", "technical_analogue": "circular_economy_module", "structural_category": "process", "murphy_module": "circular_economy_module"},
    {"nontechnical": "carbon footprint", "technical_analogue": "emissions_tracking", "structural_category": "component", "murphy_module": "emissions_tracking"},
    {"nontechnical": "social responsibility", "technical_analogue": "social_impact_engine", "structural_category": "process", "murphy_module": "social_impact_engine"},
]

# ---------------------------------------------------------------------------
# Regulatory Domain Definitions
# ---------------------------------------------------------------------------

REGULATORY_DOMAINS: Dict[str, Dict[str, Any]] = {
    "aviation": {
        "keywords": ["drone", "flight", "airspace", "aircraft", "pilot", "aviation", "runway", "aerospace"],
        "frameworks": ["FAA", "aviation safety"],
    },
    "healthcare": {
        "keywords": ["health", "patient", "medical", "hospital", "clinical", "diagnosis", "treatment", "pharmacy"],
        "frameworks": ["HIPAA", "FDA"],
    },
    "finance": {
        "keywords": ["financial", "payment", "banking", "trading", "investment", "portfolio", "stock", "bond", "loan"],
        "frameworks": ["PCI-DSS", "SOX"],
    },
    "privacy": {
        "keywords": ["personal data", "privacy", "consent", "data subject", "right to be forgotten", "GDPR", "data protection"],
        "frameworks": ["GDPR"],
    },
    "industrial": {
        "keywords": ["industrial", "worker", "factory", "manufacturing", "assembly", "hazard", "safety equipment", "warehouse"],
        "frameworks": ["OSHA"],
    },
    "technology": {
        "keywords": ["software", "cloud", "data center", "server", "SaaS", "infrastructure", "cyber", "network"],
        "frameworks": ["SOC2", "ISO27001"],
    },
    "environmental": {
        "keywords": ["environmental", "pollution", "emissions", "sustainability", "green", "EPA", "ISO14001", "waste management", "ecological"],
        "frameworks": ["EPA", "ISO14001"],
    },
    "energy": {
        "keywords": ["energy", "power grid", "renewable", "solar", "wind", "FERC", "DOE", "electricity", "utility"],
        "frameworks": ["FERC", "DOE"],
    },
    "social_impact": {
        "keywords": ["social impact", "fair labor", "ILO", "human rights", "community", "equity", "inclusion", "diversity"],
        "frameworks": ["ILO", "fair labor"],
    },
}

# ---------------------------------------------------------------------------
# Regulatory Module Templates
# ---------------------------------------------------------------------------

_REGULATORY_MODULE_TEMPLATES: Dict[str, Dict[str, str]] = {
    "FAA": {
        "module_name": "faa_compliance_monitor",
        "purpose": "Monitor aviation operations for FAA regulatory compliance",
        "rules": "Airspace authorization, pilot certification, maintenance logging, incident reporting",
    },
    "aviation safety": {
        "module_name": "aviation_safety_monitor",
        "purpose": "Enforce aviation safety standards across flight operations",
        "rules": "Pre-flight checks, crew rest requirements, weather minimums, emergency procedures",
    },
    "HIPAA": {
        "module_name": "hipaa_compliance_monitor",
        "purpose": "Monitor healthcare data handling for HIPAA compliance",
        "rules": "PHI encryption, access logging, breach notification",
    },
    "FDA": {
        "module_name": "fda_compliance_monitor",
        "purpose": "Ensure medical products and processes meet FDA regulations",
        "rules": "Clinical trial tracking, adverse event reporting, labeling compliance",
    },
    "PCI-DSS": {
        "module_name": "pci_dss_compliance_monitor",
        "purpose": "Enforce payment card data security standards",
        "rules": "Cardholder data encryption, access control, network segmentation, vulnerability scanning",
    },
    "SOX": {
        "module_name": "sox_compliance_monitor",
        "purpose": "Ensure financial reporting meets Sarbanes-Oxley requirements",
        "rules": "Internal controls, audit trails, financial disclosure accuracy",
    },
    "GDPR": {
        "module_name": "gdpr_compliance_monitor",
        "purpose": "Enforce EU data protection and privacy regulations",
        "rules": "Consent management, data subject rights, data minimization, breach notification",
    },
    "OSHA": {
        "module_name": "osha_compliance_monitor",
        "purpose": "Monitor workplace safety for OSHA compliance",
        "rules": "Hazard communication, PPE requirements, incident reporting, safety training",
    },
    "SOC2": {
        "module_name": "soc2_compliance_monitor",
        "purpose": "Enforce SOC 2 trust service criteria for technology services",
        "rules": "Security controls, availability monitoring, processing integrity, confidentiality",
    },
    "ISO27001": {
        "module_name": "iso27001_compliance_monitor",
        "purpose": "Ensure information security management meets ISO 27001 standards",
        "rules": "Risk assessment, access control, incident management, continuous improvement",
    },
    "EPA": {
        "module_name": "epa_compliance_monitor",
        "purpose": "Monitor environmental operations for EPA regulatory alignment",
        "rules": "Emissions tracking, waste disposal compliance, environmental impact assessment, reporting",
    },
    "ISO14001": {
        "module_name": "iso14001_compliance_monitor",
        "purpose": "Ensure environmental management system meets ISO 14001 standards",
        "rules": "Environmental policy, planning, implementation, performance evaluation, improvement",
    },
    "FERC": {
        "module_name": "ferc_compliance_monitor",
        "purpose": "Monitor energy operations for FERC regulatory alignment",
        "rules": "Market rules, reliability standards, tariff compliance, reporting requirements",
    },
    "DOE": {
        "module_name": "doe_compliance_monitor",
        "purpose": "Ensure energy programs align with DOE standards and regulations",
        "rules": "Energy efficiency standards, nuclear safety, environmental remediation",
    },
    "ILO": {
        "module_name": "ilo_compliance_monitor",
        "purpose": "Monitor labor practices for ILO convention alignment",
        "rules": "Freedom of association, forced labor prohibition, child labor elimination, non-discrimination",
    },
    "fair labor": {
        "module_name": "fair_labor_compliance_monitor",
        "purpose": "Enforce fair labor standards across operations",
        "rules": "Minimum wage, overtime, working conditions, worker safety, equal pay",
    },
}

# ---------------------------------------------------------------------------
# Heuristic word lists for concept extraction
# ---------------------------------------------------------------------------

_ACTION_WORDS: set[str] = {
    "build", "create", "deploy", "manage", "monitor", "track", "send",
    "receive", "process", "validate", "verify", "check", "test", "audit",
    "inspect", "review", "analyze", "optimize", "improve", "reduce",
    "increase", "maintain", "update", "delete", "remove", "add", "configure",
    "install", "run", "execute", "start", "stop", "restart", "schedule",
    "report", "notify", "alert", "log", "record", "store", "retrieve",
    "transfer", "transform", "convert", "encrypt", "decrypt", "sign",
    "authenticate", "authorize", "enforce", "comply", "regulate", "govern",
    "control", "prevent", "detect", "respond", "recover", "ensure",
    "provide", "deliver", "support", "handle", "route", "dispatch",
    "generate", "compute", "calculate", "measure", "assess", "evaluate",
}

_CONSTRAINT_MARKERS: list[str] = [
    "with", "within", "limited to", "must", "shall", "should",
    "no more than", "at least", "not exceeding", "required to",
    "subject to", "constrained by", "restricted to",
]

_GOAL_MARKERS: list[str] = ["to", "for", "in order to", "so that", "such that"]

# Pre-compiled pattern for deduction indicators
_DEDUCTION_INDICATORS: re.Pattern[str] = re.compile(
    r"\b(?:according to|per|as defined by|standard|regulation|specification|"
    r"requirement|protocol|policy|framework|compliance|ISO|NIST|IEEE|RFC|"
    r"FAA|OSHA|HIPAA|GDPR|PCI|SOX|SOC)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# TechnicalAnalogue dataclass
# ---------------------------------------------------------------------------

@dataclass
class TechnicalAnalogue:
    """Result of translating nontechnical text into Murphy System concepts.

    Attributes:
        original_text: The verbatim input text.
        extracted_concepts: Actor-action-goal-constraint tuples extracted
            from the input.
        technical_mapping: Nontechnical-to-technical translations found
            via the normalization table.
        regulatory_frameworks: Names of detected regulatory frameworks
            (e.g. ``"OSHA"``, ``"GDPR"``).
        regulatory_modules: Module specifications generated for each
            detected framework.
        reasoning_method: ``"deduction"`` when the text references known
            standards; ``"induction"`` otherwise.
        system_model: Preliminary system model derived from extracted
            concepts, containing components, data flows, control logic,
            and validation methods.
    """

    original_text: str
    extracted_concepts: List[Dict[str, str]] = field(default_factory=list)
    technical_mapping: List[Dict[str, str]] = field(default_factory=list)
    regulatory_frameworks: List[str] = field(default_factory=list)
    regulatory_modules: List[Dict[str, str]] = field(default_factory=list)
    reasoning_method: str = "induction"
    system_model: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# ConceptTranslationEngine
# ---------------------------------------------------------------------------

class ConceptTranslationEngine:
    """Deterministic engine that translates nontechnical text into structured
    technical analogues for consumption by downstream Murphy System modules.

    Thread-safe: a ``threading.Lock`` guards all mutable instance state so
    the engine may be shared across threads.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._translation_count: int = 0
        logger.info("ConceptTranslationEngine initialized")

    # -- public API ---------------------------------------------------------

    def translate(self, text: str, context: Optional[Dict[str, Any]] = None) -> TechnicalAnalogue:
        """Translate *text* into a :class:`TechnicalAnalogue`.

        Args:
            text: Free-form nontechnical input.
            context: Optional dictionary of additional context hints
                (currently reserved for future use).

        Returns:
            A fully populated ``TechnicalAnalogue`` instance.
        """
        if not text or not text.strip():
            logger.warning("Empty text received for translation")
            return TechnicalAnalogue(original_text=text or "")

        normalized_text = text.strip()
        logger.debug("Translating text of length %d", len(normalized_text))

        sentences = self._split_sentences(normalized_text)

        extracted_concepts = self._extract_concepts(sentences)
        technical_mapping = self._map_to_technical(normalized_text)
        regulatory_frameworks = self._detect_regulatory_frameworks(normalized_text)
        regulatory_modules = self._build_regulatory_modules(regulatory_frameworks)
        reasoning_method = self._classify_reasoning(normalized_text)
        system_model = self._build_system_model(
            extracted_concepts, technical_mapping, regulatory_frameworks,
        )

        with self._lock:
            self._translation_count += 1
            count = self._translation_count

        logger.info(
            "Translation #%d complete: %d concepts, %d mappings, %d frameworks",
            count,
            len(extracted_concepts),
            len(technical_mapping),
            len(regulatory_frameworks),
        )

        return TechnicalAnalogue(
            original_text=normalized_text,
            extracted_concepts=extracted_concepts,
            technical_mapping=technical_mapping,
            regulatory_frameworks=regulatory_frameworks,
            regulatory_modules=regulatory_modules,
            reasoning_method=reasoning_method,
            system_model=system_model,
        )

    @property
    def translation_count(self) -> int:
        """Return the number of translations performed so far."""
        with self._lock:
            return self._translation_count

    # -- sentence splitting -------------------------------------------------

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Split *text* into sentence-like fragments.

        Splits on ``. ``, ``; ``, and newlines, then strips whitespace and
        drops empty fragments.
        """
        fragments = re.split(r"\.\s+|;\s+|\n+", text)
        return [f.strip() for f in fragments if f.strip()]

    # -- concept extraction -------------------------------------------------

    def _extract_concepts(self, sentences: List[str]) -> List[Dict[str, str]]:
        """Extract actor-action-goal-constraint tuples from *sentences*.

        Uses simple keyword heuristics rather than full NLP parsing.
        """
        concepts: List[Dict[str, str]] = []
        for sentence in sentences:
            concept = self._parse_sentence(sentence)
            if any(concept.get(k) for k in ("actor", "action", "goal", "constraint")):
                concepts.append(concept)
        return concepts

    @staticmethod
    def _parse_sentence(sentence: str) -> Dict[str, str]:
        """Parse a single sentence into an actor-action-goal-constraint dict."""
        words = sentence.split()
        lower_words = [w.lower().rstrip(".,;:!?") for w in words]
        lower_sentence = sentence.lower()

        # --- action: find the first recognised action word ---
        action = ""
        action_idx = -1
        for idx, lw in enumerate(lower_words):
            if lw in _ACTION_WORDS:
                action = lw
                action_idx = idx
                break

        # --- actor: words before the action verb ---
        actor = ""
        if action_idx > 0:
            actor = " ".join(words[:action_idx])

        # --- constraint: text following a constraint marker ---
        constraint = ""
        for marker in _CONSTRAINT_MARKERS:
            marker_pos = lower_sentence.find(marker)
            if marker_pos != -1:
                after_marker = sentence[marker_pos + len(marker):].strip()
                if after_marker:
                    constraint = after_marker.rstrip(".,;:!?")
                    break

        # --- goal: text after goal marker, or text after the action verb ---
        goal = ""
        for marker in _GOAL_MARKERS:
            # Only match the marker as a standalone word boundary
            pattern = rf"\b{re.escape(marker)}\b"
            match = re.search(pattern, lower_sentence)
            if match:
                after_goal = sentence[match.end():].strip()
                # Trim off any constraint portion already captured
                if constraint:
                    constraint_pos = after_goal.lower().find(constraint.lower())
                    if constraint_pos > 0:
                        after_goal = after_goal[:constraint_pos].strip()
                        after_goal = after_goal.rstrip(".,;:!?")
                if after_goal:
                    goal = after_goal.rstrip(".,;:!?")
                    break

        if not goal and action_idx >= 0 and action_idx + 1 < len(words):
            remaining = " ".join(words[action_idx + 1:])
            # Strip constraint part
            if constraint:
                constraint_pos = remaining.lower().find(constraint.lower())
                if constraint_pos > 0:
                    remaining = remaining[:constraint_pos].strip()
                    remaining = remaining.rstrip(".,;:!?")
            goal = remaining.rstrip(".,;:!?") if remaining.strip() else ""

        return {
            "actor": actor.strip(),
            "action": action.strip(),
            "goal": goal.strip(),
            "constraint": constraint.strip(),
        }

    # -- normalization mapping ----------------------------------------------

    @staticmethod
    def _map_to_technical(text: str) -> List[Dict[str, str]]:
        """Match phrases from the normalization table against *text*.

        Returns one mapping dict per matched phrase, sorted longest-match
        first to avoid false positives on sub-strings.
        """
        lower_text = text.lower()
        results: List[Dict[str, str]] = []
        seen: set[str] = set()

        # Sort by phrase length descending so longer phrases match first
        sorted_table = sorted(
            NORMALIZATION_TABLE, key=lambda e: len(e["nontechnical"]), reverse=True,
        )

        for entry in sorted_table:
            phrase = entry["nontechnical"]
            if phrase in seen:
                continue
            if phrase.lower() in lower_text:
                results.append({
                    "nontechnical": phrase,
                    "technical_analogue": entry["technical_analogue"],
                    "murphy_module": entry["murphy_module"],
                })
                seen.add(phrase)

        return results

    # -- regulatory detection -----------------------------------------------

    @staticmethod
    def _detect_regulatory_frameworks(text: str) -> List[str]:
        """Detect regulatory frameworks applicable to *text*.

        Scans for domain-specific keywords and returns deduplicated
        framework names.
        """
        lower_text = text.lower()
        frameworks: List[str] = []
        seen: set[str] = set()

        for _domain, info in REGULATORY_DOMAINS.items():
            for keyword in info["keywords"]:
                if keyword.lower() in lower_text:
                    for fw in info["frameworks"]:
                        if fw not in seen:
                            frameworks.append(fw)
                            seen.add(fw)
                    break  # one keyword match is sufficient per domain

        return frameworks

    @staticmethod
    def _build_regulatory_modules(frameworks: List[str]) -> List[Dict[str, str]]:
        """Generate module specifications for each detected framework."""
        modules: List[Dict[str, str]] = []
        for fw in frameworks:
            template = _REGULATORY_MODULE_TEMPLATES.get(fw)
            if template:
                modules.append(dict(template))
            else:
                modules.append({
                    "module_name": f"{fw.lower().replace('-', '_')}_compliance_monitor",
                    "purpose": f"Monitor compliance with {fw} regulations",
                    "rules": f"{fw} standard requirements",
                })
        return modules

    # -- reasoning classification -------------------------------------------

    @staticmethod
    def _classify_reasoning(text: str) -> str:
        """Classify the reasoning method as deduction or induction.

        ``"deduction"`` is returned when the text references established
        standards or frameworks; ``"induction"`` otherwise.
        """
        if _DEDUCTION_INDICATORS.search(text):
            return "deduction"
        return "induction"

    # -- system model generation --------------------------------------------

    @staticmethod
    def _build_system_model(
        concepts: List[Dict[str, str]],
        mappings: List[Dict[str, str]],
        frameworks: List[str],
    ) -> Dict[str, Any]:
        """Synthesise a preliminary system model from extracted artefacts.

        Returns a dict with ``components``, ``data_flows``,
        ``control_logic``, and ``validation_methods``.
        """
        components: List[str] = []
        data_flows: List[str] = []
        control_logic: List[str] = []
        validation_methods: List[str] = []

        seen_components: set[str] = set()

        # Derive components from mappings
        for mapping in mappings:
            mod = mapping.get("murphy_module", "")
            if mod and mod not in seen_components:
                components.append(mod)
                seen_components.add(mod)

        # Derive components and flows from concepts
        for concept in concepts:
            actor = concept.get("actor", "")
            action = concept.get("action", "")
            goal = concept.get("goal", "")
            constraint = concept.get("constraint", "")

            if actor and actor not in seen_components:
                components.append(actor)
                seen_components.add(actor)

            if actor and goal:
                flow = f"{actor} \u2192 {goal}"
                if flow not in data_flows:
                    data_flows.append(flow)

            if constraint:
                rule = f"If {action}: {constraint}" if action else f"Constraint: {constraint}"
                if rule not in control_logic:
                    control_logic.append(rule)

        # Add regulatory-derived control logic
        for fw in frameworks:
            rule = f"Enforce {fw} compliance"
            if rule not in control_logic:
                control_logic.append(rule)

        # Derive validation methods from concepts
        for concept in concepts:
            action = concept.get("action", "")
            if action in {"validate", "verify", "check", "test", "audit", "inspect", "review"}:
                method = f"{action} {concept.get('goal', 'system')}".strip()
                if method not in validation_methods:
                    validation_methods.append(method)

        # If no explicit validation found, add defaults based on frameworks
        if not validation_methods and frameworks:
            for fw in frameworks:
                validation_methods.append(f"{fw} compliance validation")

        return {
            "components": components,
            "data_flows": data_flows,
            "control_logic": control_logic,
            "validation_methods": validation_methods,
        }

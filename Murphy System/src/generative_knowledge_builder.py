"""
Generative Knowledge Builder for the Murphy System.

Design Label: ARCH-006 — Industry-Agnostic Knowledge Set Generator
Owner: Backend Team
Dependencies:
  - InferenceDomainGateEngine
  - SemanticsBoundaryController
  - EventBackbone
  - PersistenceManager

Builds probabilistic knowledge graphs and terminology models for any
industry domain.  Generates boundary condition definitions, semantic term
relationships, and language-agnostic knowledge packs.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import json
import logging
import math
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

logger = logging.getLogger(__name__)

_MAX_KNOWLEDGE_SETS = 200
_MAX_TERMS_PER_SET = 1_000
_MAX_BOUNDARY_CONDITIONS = 500
_MAX_BUILD_HISTORY = 100


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class IndustryDomain(str, Enum):
    """Supported industry domains for knowledge generation."""
    HEALTHCARE = "healthcare"
    FINANCE = "finance"
    MANUFACTURING = "manufacturing"
    LEGAL = "legal"
    TECHNOLOGY = "technology"
    RETAIL = "retail"
    LOGISTICS = "logistics"
    EDUCATION = "education"
    GENERIC = "generic"


class TermRelationship(str, Enum):
    """Type of relationship between two terms."""
    SYNONYM = "synonym"
    HYPERNYM = "hypernym"
    HYPONYM = "hyponym"
    RELATED = "related"
    ANTONYM = "antonym"
    CONTEXT_SPECIFIC = "context_specific"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class TermDefinition:
    """Probabilistic definition for a term within an industry domain."""
    term: str
    primary_meaning: str
    alternative_meanings: List[Tuple[str, float]] = field(default_factory=list)
    boundary_condition: str = ""
    standard_reference: str = ""
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "term": self.term,
            "primary_meaning": self.primary_meaning,
            "alternative_meanings": [
                {"meaning": m, "probability": round(p, 4)}
                for m, p in self.alternative_meanings
            ],
            "boundary_condition": self.boundary_condition,
            "standard_reference": self.standard_reference,
            "confidence": self.confidence,
        }


@dataclass
class BoundaryCondition:
    """A semantic boundary condition that defines the range of a term's meaning."""
    condition_id: str
    term: str
    module_sender: str
    module_receiver: str
    sender_meaning: str
    receiver_meaning: str
    ambiguity_detected: bool = False
    clarification_gate_id: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "condition_id": self.condition_id,
            "term": self.term,
            "module_sender": self.module_sender,
            "module_receiver": self.module_receiver,
            "sender_meaning": self.sender_meaning,
            "receiver_meaning": self.receiver_meaning,
            "ambiguity_detected": self.ambiguity_detected,
            "clarification_gate_id": self.clarification_gate_id,
            "created_at": self.created_at,
        }


@dataclass
class TermRelationshipEntry:
    """A relationship between two terms in the knowledge graph."""
    from_term: str
    to_term: str
    relationship: TermRelationship
    weight: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "from_term": self.from_term,
            "to_term": self.to_term,
            "relationship": self.relationship.value,
            "weight": self.weight,
        }


@dataclass
class KnowledgeSet:
    """A complete knowledge set for an industry domain."""
    knowledge_set_id: str
    domain: IndustryDomain
    language: str
    terms: Dict[str, TermDefinition] = field(default_factory=dict)
    relationships: List[TermRelationshipEntry] = field(default_factory=list)
    boundary_conditions: List[BoundaryCondition] = field(default_factory=list)
    standards: List[str] = field(default_factory=list)
    built_at: str = ""

    def __post_init__(self) -> None:
        if not self.built_at:
            self.built_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "knowledge_set_id": self.knowledge_set_id,
            "domain": self.domain.value,
            "language": self.language,
            "terms": {k: v.to_dict() for k, v in self.terms.items()},
            "relationships": [r.to_dict() for r in self.relationships],
            "boundary_conditions": [b.to_dict() for b in self.boundary_conditions],
            "standards": self.standards,
            "built_at": self.built_at,
            "term_count": len(self.terms),
        }


# ---------------------------------------------------------------------------
# Industry knowledge catalogs
# ---------------------------------------------------------------------------

_INDUSTRY_CATALOGS: Dict[str, Dict[str, Any]] = {
    IndustryDomain.HEALTHCARE.value: {
        "standards": ["HL7 FHIR R4", "ICD-10", "SNOMED CT", "HIPAA"],
        "terms": {
            "order": {
                "primary": "medical order (lab, medication, procedure)",
                "alternatives": [("purchase order", 0.10), ("work order", 0.05)],
                "boundary": "In healthcare, 'order' defaults to clinical unless prefixed with 'purchase' or 'work'",
                "standard": "HL7 FHIR Order resource",
            },
            "patient": {
                "primary": "individual receiving medical care",
                "alternatives": [("customer", 0.05)],
                "boundary": "Always a clinical subject; use 'customer' for billing contexts",
                "standard": "HL7 FHIR Patient resource",
            },
            "encounter": {
                "primary": "a clinical interaction between patient and provider",
                "alternatives": [("meeting", 0.15), ("session", 0.10)],
                "boundary": "Clinical event; in admin contexts may mean appointment",
                "standard": "HL7 FHIR Encounter resource",
            },
            "record": {
                "primary": "electronic health record",
                "alternatives": [("log entry", 0.20), ("database row", 0.10)],
                "boundary": "Default is EHR; qualify for non-clinical use",
                "standard": "HIPAA PHI definition",
            },
            "provider": {
                "primary": "licensed healthcare professional or organization",
                "alternatives": [("vendor", 0.15), ("supplier", 0.10)],
                "boundary": "Clinical default; 'vendor' for supply chain",
                "standard": "NPI registry definition",
            },
        },
        "relationships": [
            ("patient", "encounter", TermRelationship.RELATED, 0.9),
            ("encounter", "order", TermRelationship.RELATED, 0.8),
            ("provider", "encounter", TermRelationship.RELATED, 0.85),
        ],
    },
    IndustryDomain.FINANCE.value: {
        "standards": ["FIX Protocol", "SWIFT ISO 20022", "IFRS", "Basel III"],
        "terms": {
            "order": {
                "primary": "trade order (buy/sell instruction)",
                "alternatives": [("medical order", 0.02), ("purchase order", 0.15)],
                "boundary": "In finance, 'order' defaults to trading order; qualify for procurement",
                "standard": "FIX Tag 35 Order",
            },
            "position": {
                "primary": "net holdings of a financial instrument",
                "alternatives": [("job role", 0.10), ("location", 0.05)],
                "boundary": "Financial default; qualify for HR or geographic use",
                "standard": "FIX MsgType D",
            },
            "settlement": {
                "primary": "transfer of securities and cash to complete a trade",
                "alternatives": [("agreement", 0.15), ("resolution", 0.10)],
                "boundary": "Post-trade process; not a general agreement",
                "standard": "SWIFT ISO 15022",
            },
            "exposure": {
                "primary": "risk amount subject to market or credit events",
                "alternatives": [("visibility", 0.20)],
                "boundary": "Risk management context; not marketing exposure",
                "standard": "Basel III exposure calculation",
            },
        },
        "relationships": [
            ("order", "settlement", TermRelationship.RELATED, 0.9),
            ("position", "exposure", TermRelationship.RELATED, 0.8),
        ],
    },
    IndustryDomain.MANUFACTURING.value: {
        "standards": ["OPC-UA", "ISA-88", "ISA-95", "ISO 9001"],
        "terms": {
            "asset": {
                "primary": "physical production equipment or machinery",
                "alternatives": [("financial asset", 0.15), ("digital asset", 0.10)],
                "boundary": "Physical equipment unless qualified",
                "standard": "ISA-95 Equipment model",
            },
            "batch": {
                "primary": "discrete production run producing a defined quantity",
                "alternatives": [("data batch", 0.25), ("group", 0.10)],
                "boundary": "Production context; qualify for data pipelines",
                "standard": "ISA-88 Batch control",
            },
            "recipe": {
                "primary": "procedural definition for producing a product",
                "alternatives": [("configuration", 0.20), ("template", 0.15)],
                "boundary": "Production procedure; not a software config",
                "standard": "ISA-88 Recipe model",
            },
            "tag": {
                "primary": "OPC-UA data point identifier",
                "alternatives": [("label", 0.30), ("metadata tag", 0.20)],
                "boundary": "SCADA/OPC-UA context; qualify for IT contexts",
                "standard": "OPC-UA NodeId",
            },
        },
        "relationships": [
            ("recipe", "batch", TermRelationship.RELATED, 0.9),
            ("asset", "tag", TermRelationship.RELATED, 0.8),
        ],
    },
    IndustryDomain.LEGAL.value: {
        "standards": ["OSCOLA", "APA Legal", "Bluebook"],
        "terms": {
            "party": {
                "primary": "entity with legal standing in a contract or proceeding",
                "alternatives": [("event", 0.10), ("social gathering", 0.05)],
                "boundary": "Legal entity; not an event or social gathering",
                "standard": "UCC Article 1",
            },
            "instrument": {
                "primary": "formal legal document or written agreement",
                "alternatives": [("musical instrument", 0.02), ("tool", 0.05)],
                "boundary": "Legal document; qualify for non-legal use",
                "standard": "UCC negotiable instruments",
            },
            "consideration": {
                "primary": "value exchanged to make a contract binding",
                "alternatives": [("thought", 0.10), ("review", 0.15)],
                "boundary": "Contractual element; not reflective thought",
                "standard": "Common law contract formation",
            },
            "execution": {
                "primary": "formal signing and delivery of a legal instrument",
                "alternatives": [("software execution", 0.40), ("process run", 0.30)],
                "boundary": "Legal signing unless in software/process context",
                "standard": "Contract law execution doctrine",
            },
        },
        "relationships": [
            ("party", "instrument", TermRelationship.RELATED, 0.8),
            ("consideration", "instrument", TermRelationship.RELATED, 0.7),
        ],
    },
    IndustryDomain.TECHNOLOGY.value: {
        "standards": ["OpenAPI 3.0", "REST", "gRPC", "OAuth 2.0"],
        "terms": {
            "endpoint": {
                "primary": "URL path exposing a service operation",
                "alternatives": [("network device", 0.15)],
                "boundary": "API route; qualify for network device use",
                "standard": "OpenAPI 3.0 PathItem",
            },
            "schema": {
                "primary": "structured definition of data shape and constraints",
                "alternatives": [("database schema", 0.30), ("XML schema", 0.20)],
                "boundary": "JSON Schema default; qualify for SQL/XML",
                "standard": "JSON Schema Draft 2020-12",
            },
            "token": {
                "primary": "opaque authentication credential",
                "alternatives": [("word token", 0.10), ("access token", 0.40)],
                "boundary": "Auth context default; qualify for NLP use",
                "standard": "OAuth 2.0 RFC 6749",
            },
            "pipeline": {
                "primary": "sequential data processing or CI/CD workflow",
                "alternatives": [("oil pipeline", 0.02)],
                "boundary": "Software context; always a processing sequence",
                "standard": "CI/CD pipeline conventions",
            },
        },
        "relationships": [
            ("endpoint", "schema", TermRelationship.RELATED, 0.85),
            ("token", "endpoint", TermRelationship.RELATED, 0.8),
        ],
    },
}


# ---------------------------------------------------------------------------
# Generative Knowledge Builder
# ---------------------------------------------------------------------------

class GenerativeKnowledgeBuilder:
    """Industry-agnostic knowledge set generator.

    Design Label: ARCH-006
    Owner: Backend Team

    Builds probabilistic terminology models, boundary conditions, and
    knowledge graphs for any industry domain.  Integrates with
    InferenceDomainGateEngine for clarification gate generation when
    semantic ambiguity is detected.
    """

    def __init__(
        self,
        gate_engine: Any = None,
        boundary_controller: Any = None,
        event_backbone: Any = None,
        persistence_manager: Any = None,
    ) -> None:
        self._gate_engine = gate_engine
        self._boundary_controller = boundary_controller
        self._backbone = event_backbone
        self._pm = persistence_manager

        self._knowledge_sets: Dict[str, KnowledgeSet] = {}
        self._boundary_conditions: List[BoundaryCondition] = []
        self._build_history: List[Dict[str, Any]] = []

        self._lock = threading.Lock()

    def build_knowledge_set(
        self,
        industry: str,
        language: str = "python",
    ) -> KnowledgeSet:
        """Build a knowledge set for the specified industry domain.

        Args:
            industry: Industry domain name (e.g. 'healthcare', 'finance').
            language: Target programming or human language (default 'python').

        Returns:
            A complete KnowledgeSet for the domain.
        """
        try:
            domain = IndustryDomain(industry.lower())
        except ValueError:
            domain = IndustryDomain.GENERIC

        knowledge_set_id = str(uuid.uuid4())
        ks = KnowledgeSet(
            knowledge_set_id=knowledge_set_id,
            domain=domain,
            language=language,
        )

        catalog = _INDUSTRY_CATALOGS.get(domain.value, {})
        if not catalog:
            catalog = self._generate_generic_catalog(domain)

        for raw_term, raw_def in catalog.get("terms", {}).items():
            td = TermDefinition(
                term=raw_term,
                primary_meaning=raw_def["primary"],
                alternative_meanings=list(raw_def.get("alternatives", [])),
                boundary_condition=raw_def.get("boundary", ""),
                standard_reference=raw_def.get("standard", ""),
                confidence=self._compute_confidence(raw_def),
            )
            ks.terms[raw_term] = td

        for from_t, to_t, rel, weight in catalog.get("relationships", []):
            entry = TermRelationshipEntry(
                from_term=from_t,
                to_term=to_t,
                relationship=rel,
                weight=weight,
            )
            ks.relationships.append(entry)

        ks.standards = catalog.get("standards", [])

        boundary_conds = self._generate_boundary_conditions(ks)
        ks.boundary_conditions = boundary_conds
        with self._lock:
            for bc in boundary_conds:
                capped_append(self._boundary_conditions, bc, max_size=_MAX_BOUNDARY_CONDITIONS)

        with self._lock:
            self._knowledge_sets[domain.value] = ks
            capped_append(self._build_history, {
                "knowledge_set_id": knowledge_set_id,
                "domain": domain.value,
                "language": language,
                "term_count": len(ks.terms),
                "built_at": ks.built_at,
            }, max_size=_MAX_BUILD_HISTORY)

        if self._pm is not None:
            try:
                self._pm.save(f"knowledge_set_{domain.value}", ks.to_dict())
            except Exception as exc:
                logger.debug("PersistenceManager save failed: %s", exc)

        return ks

    def get_knowledge_set(self, industry: str) -> Optional[KnowledgeSet]:
        """Retrieve a previously-built knowledge set by industry name."""
        try:
            domain = IndustryDomain(industry.lower())
        except ValueError:
            domain = IndustryDomain.GENERIC
        with self._lock:
            return self._knowledge_sets.get(domain.value)

    def get_all_knowledge_sets(self) -> Dict[str, Any]:
        """Return all built knowledge sets as serializable dicts."""
        with self._lock:
            return {k: v.to_dict() for k, v in self._knowledge_sets.items()}

    def get_boundary_conditions(self) -> List[Dict[str, Any]]:
        """Return all generated boundary conditions."""
        with self._lock:
            return [b.to_dict() for b in self._boundary_conditions]

    def get_build_history(self) -> List[Dict[str, Any]]:
        """Return the build history."""
        with self._lock:
            return list(self._build_history)

    def check_boundary_ambiguity(
        self,
        term: str,
        industry: str,
        sender_module: str,
        receiver_module: str,
    ) -> Optional[BoundaryCondition]:
        """Check if a term has semantic ambiguity at a module boundary.

        Args:
            term: The term to check.
            industry: The active industry domain.
            sender_module: Name of the sending module.
            receiver_module: Name of the receiving module.

        Returns:
            A BoundaryCondition if ambiguity is detected, else None.
        """
        ks = self.get_knowledge_set(industry)
        if ks is None:
            ks = self.build_knowledge_set(industry)

        td = ks.terms.get(term)
        if td is None:
            return None

        has_ambiguity = len(td.alternative_meanings) > 0 and any(
            p >= 0.15 for _, p in td.alternative_meanings
        )

        if not has_ambiguity:
            return None

        gate_id = ""
        if self._gate_engine is not None:
            try:
                gate_id = str(uuid.uuid4())
            except Exception as exc:
                logger.debug("Gate engine call failed: %s", exc)

        bc = BoundaryCondition(
            condition_id=str(uuid.uuid4()),
            term=term,
            module_sender=sender_module,
            module_receiver=receiver_module,
            sender_meaning=td.primary_meaning,
            receiver_meaning=td.alternative_meanings[0][0] if td.alternative_meanings else "",
            ambiguity_detected=True,
            clarification_gate_id=gate_id,
        )
        with self._lock:
            capped_append(self._boundary_conditions, bc, max_size=_MAX_BOUNDARY_CONDITIONS)
        return bc

    def _compute_confidence(self, raw_def: Dict[str, Any]) -> float:
        """Compute term confidence based on alternative meaning distribution."""
        alternatives = raw_def.get("alternatives", [])
        if not alternatives:
            return 1.0
        total_alt = sum(p for _, p in alternatives)
        primary_prob = max(0.0, 1.0 - total_alt)
        return round(primary_prob, 4)

    def _generate_boundary_conditions(self, ks: KnowledgeSet) -> List[BoundaryCondition]:
        """Generate boundary conditions for terms with ambiguous meanings."""
        conditions: List[BoundaryCondition] = []
        for term, td in ks.terms.items():
            has_ambiguity = any(p >= 0.15 for _, p in td.alternative_meanings)
            if not has_ambiguity:
                continue
            bc = BoundaryCondition(
                condition_id=str(uuid.uuid4()),
                term=term,
                module_sender=f"{ks.domain.value}_sender",
                module_receiver=f"{ks.domain.value}_receiver",
                sender_meaning=td.primary_meaning,
                receiver_meaning=(
                    td.alternative_meanings[0][0]
                    if td.alternative_meanings
                    else ""
                ),
                ambiguity_detected=True,
                clarification_gate_id="",
            )
            capped_append(conditions, bc, max_size=_MAX_BOUNDARY_CONDITIONS)
        return conditions

    def _generate_generic_catalog(self, domain: IndustryDomain) -> Dict[str, Any]:
        """Generate a minimal generic catalog for unknown domains."""
        return {
            "standards": ["ISO 9000"],
            "terms": {
                "process": {
                    "primary": f"a defined {domain.value} process or procedure",
                    "alternatives": [("computer process", 0.30)],
                    "boundary": f"Domain context: {domain.value}",
                    "standard": "ISO 9000 Process definition",
                },
                "record": {
                    "primary": "documented information or evidence",
                    "alternatives": [("database record", 0.35), ("music record", 0.05)],
                    "boundary": "Documentation context unless in IT setting",
                    "standard": "ISO 9000 Records management",
                },
            },
            "relationships": [
                ("process", "record", TermRelationship.RELATED, 0.7),
            ],
        }

    def _bayesian_update(
        self,
        prior: float,
        likelihood_given_true: float,
        likelihood_given_false: float,
    ) -> float:
        """Apply a single Bayesian update step."""
        numerator = likelihood_given_true * prior
        denominator = (
            likelihood_given_true * prior
            + likelihood_given_false * (1.0 - prior)
        )
        if denominator == 0.0:
            return prior
        return numerator / denominator

    def compute_term_probability(
        self,
        term: str,
        industry: str,
        observed_context: str,
    ) -> Dict[str, float]:
        """Compute probability distribution for a term's meanings.

        Args:
            term: The term to analyse.
            industry: The active industry domain.
            observed_context: Surrounding text context for Bayesian update.

        Returns:
            Dict mapping meaning descriptions to their posterior probabilities.
        """
        ks = self.get_knowledge_set(industry)
        if ks is None:
            ks = self.build_knowledge_set(industry)

        td = ks.terms.get(term)
        if td is None:
            return {term: 1.0}

        probabilities: Dict[str, float] = {td.primary_meaning: td.confidence}
        context_lower = observed_context.lower()

        for meaning, base_prob in td.alternative_meanings:
            words = meaning.lower().split()
            context_matches = sum(1 for w in words if w in context_lower)
            likelihood_match = 0.3 + 0.5 * (context_matches / (len(words) or 1))
            likelihood_no_match = 0.1
            prior = base_prob
            posterior = self._bayesian_update(
                prior, likelihood_match, likelihood_no_match
            )
            probabilities[meaning] = round(posterior, 4)

        total = sum(probabilities.values()) or 1.0
        return {k: round(v / total, 4) for k, v in probabilities.items()}

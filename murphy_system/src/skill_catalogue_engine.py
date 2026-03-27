"""
skill_catalogue_engine.py — Round 58
=====================================
Catalogues every behaviour produced by the Murphy System's intelligence engines
(ClientPsychologyEngine, CharacterNetworkEngine, NetworkingMasteryEngine,
CyclicTrendsEngine) as named, executable *skill sets* that can be invoked by
command at any time.

Design philosophy
-----------------
- Every skill is self-describing: name, description, category, source engine,
  required inputs, and an ``invoke()`` callable.
- Skills are organised into *catalogues* (one per domain).  A ``SkillRegistry``
  aggregates all catalogues and exposes a unified ``run(skill_id, **kwargs)``
  interface so callers never need to know which engine owns a skill.
- Skills may declare *cyclic-trend inputs* (weather, season, economic phase)
  so the system automatically enriches invocations with real-time context when
  available.
- The ``SkillCatalogueEngine`` is the top-level façade: it bootstraps every
  catalogue, surfaces a command-line-style ``/skill <name>`` interface, and
  maintains a *session log* of all invocations with outcomes and timestamps.

Public surface
--------------
    SkillCategory          — enum of skill domains
    SkillInput             — dataclass describing a required parameter
    SkillDefinition        — dataclass: metadata + invoke callable
    SkillResult            — dataclass returned by every invocation
    SkillCatalogue         — ordered collection of SkillDefinitions
    SkillRegistry          — aggregates all catalogues; run(skill_id, **kwargs)
    SkillCatalogueEngine   — top-level façade; parse_command(); session_log
    build_default_registry — factory: builds registry from all installed engines
"""

from __future__ import annotations

import datetime
import textwrap
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class SkillCategory(str, Enum):
    """High-level grouping of skill domains."""
    DEMOGRAPHIC_INTELLIGENCE  = "demographic_intelligence"
    PAIN_POINT_DETECTION      = "pain_point_detection"
    SALES_FRAMEWORK           = "sales_framework"
    INCOME_SCALING            = "income_scaling"
    CHARACTER_NETWORK         = "character_network"
    VICTORIAN_VIRTUE          = "victorian_virtue"
    NETWORKING_MASTERY        = "networking_mastery"
    BUZZ_CREATION             = "buzz_creation"
    CAPABILITY_SIGNALLING     = "capability_signalling"
    CYCLIC_TRENDS             = "cyclic_trends"
    WEATHER_ADAPTATION        = "weather_adaptation"
    SKILL_MANAGEMENT          = "skill_management"


class SkillStatus(str, Enum):
    SUCCESS  = "success"
    PARTIAL  = "partial"
    FAILURE  = "failure"
    SKIPPED  = "skipped"


# ---------------------------------------------------------------------------
# Core data structures
# ---------------------------------------------------------------------------

@dataclass
class SkillInput:
    """Declaration of a single parameter required (or optional) by a skill."""
    name:        str
    description: str
    required:    bool = True
    default:     Any  = None
    input_type:  str  = "str"   # "str" | "float" | "int" | "bool" | "dict" | "list"


@dataclass
class SkillDefinition:
    """
    Complete description of one catalogued behaviour.

    ``invoke`` must accept only keyword arguments matching the ``inputs``
    declarations and must return any serialisable value.
    """
    skill_id:      str
    name:          str
    description:   str
    category:      SkillCategory
    source_engine: str                          # e.g. "ClientPsychologyEngine"
    inputs:        List[SkillInput]             = field(default_factory=list)
    tags:          List[str]                    = field(default_factory=list)
    cyclic_aware:  bool                         = False   # accepts weather/season context
    invoke:        Optional[Callable[..., Any]] = field(default=None, repr=False)

    def summary(self) -> str:
        """One-liner suitable for help text."""
        return f"[{self.skill_id}] {self.name} — {self.description}"


@dataclass
class SkillResult:
    """Returned by every skill invocation."""
    skill_id:   str
    status:     SkillStatus
    output:     Any
    log_id:     str           = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp:  str           = field(
        default_factory=lambda: datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"
    )
    error:      Optional[str] = None
    metadata:   Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "log_id":    self.log_id,
            "skill_id":  self.skill_id,
            "status":    self.status.value,
            "output":    self.output,
            "timestamp": self.timestamp,
            "error":     self.error,
            "metadata":  self.metadata,
        }


# ---------------------------------------------------------------------------
# SkillCatalogue
# ---------------------------------------------------------------------------

class SkillCatalogue:
    """
    An ordered, named collection of SkillDefinitions belonging to one domain.
    """

    def __init__(self, name: str, category: SkillCategory) -> None:
        self.name:     str           = name
        self.category: SkillCategory = category
        self._skills:  Dict[str, SkillDefinition] = {}

    # ------------------------------------------------------------------
    def register(self, skill: SkillDefinition) -> "SkillCatalogue":
        """Add a skill; returns self for chaining."""
        self._skills[skill.skill_id] = skill
        return self

    def get(self, skill_id: str) -> Optional[SkillDefinition]:
        return self._skills.get(skill_id)

    def all_skills(self) -> List[SkillDefinition]:
        return list(self._skills.values())

    def by_tag(self, tag: str) -> List[SkillDefinition]:
        return [s for s in self._skills.values() if tag in s.tags]

    def cyclic_skills(self) -> List[SkillDefinition]:
        return [s for s in self._skills.values() if s.cyclic_aware]

    def __len__(self) -> int:
        return len(self._skills)

    def __repr__(self) -> str:
        return f"SkillCatalogue(name={self.name!r}, skills={len(self)})"


# ---------------------------------------------------------------------------
# SkillRegistry
# ---------------------------------------------------------------------------

class SkillRegistry:
    """
    Aggregates multiple SkillCatalogues and provides a unified execution API.

    Usage::

        registry = build_default_registry()
        result = registry.run("cpe.read_client", generation="GEN_Z", role="economic_buyer")
    """

    def __init__(self) -> None:
        self._catalogues: Dict[str, SkillCatalogue] = {}

    # ------------------------------------------------------------------
    def add_catalogue(self, catalogue: SkillCatalogue) -> "SkillRegistry":
        self._catalogues[catalogue.name] = catalogue
        return self

    def catalogue(self, name: str) -> Optional[SkillCatalogue]:
        return self._catalogues.get(name)

    def all_catalogues(self) -> List[SkillCatalogue]:
        return list(self._catalogues.values())

    # ------------------------------------------------------------------
    def find(self, skill_id: str) -> Optional[SkillDefinition]:
        for cat in self._catalogues.values():
            skill = cat.get(skill_id)
            if skill:
                return skill
        return None

    def search(self, query: str) -> List[SkillDefinition]:
        """Case-insensitive substring search across id, name, description, tags."""
        q = query.lower()
        results: List[SkillDefinition] = []
        for cat in self._catalogues.values():
            for skill in cat.all_skills():
                haystack = " ".join([
                    skill.skill_id, skill.name, skill.description, *skill.tags
                ]).lower()
                if q in haystack:
                    results.append(skill)
        return results

    def skills_by_category(self, category: SkillCategory) -> List[SkillDefinition]:
        return [
            s for cat in self._catalogues.values()
            for s in cat.all_skills()
            if s.category == category
        ]

    def all_skills(self) -> List[SkillDefinition]:
        return [s for cat in self._catalogues.values() for s in cat.all_skills()]

    # ------------------------------------------------------------------
    def run(self, skill_id: str, **kwargs: Any) -> SkillResult:
        """
        Invoke a registered skill by ID.

        Returns ``SkillResult`` regardless of success or failure so callers
        always receive a structured response.
        """
        skill = self.find(skill_id)
        if skill is None:
            return SkillResult(
                skill_id=skill_id,
                status=SkillStatus.FAILURE,
                output=None,
                error=f"Skill '{skill_id}' not found in registry.",
            )
        if skill.invoke is None:
            return SkillResult(
                skill_id=skill_id,
                status=SkillStatus.SKIPPED,
                output=None,
                error="Skill has no invoke function registered.",
            )
        try:
            output = skill.invoke(**kwargs)
            return SkillResult(skill_id=skill_id, status=SkillStatus.SUCCESS, output=output)
        except Exception as exc:  # noqa: BLE001
            return SkillResult(
                skill_id=skill_id,
                status=SkillStatus.FAILURE,
                output=None,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    def help_text(self) -> str:
        """Human-readable listing of all registered skills."""
        lines = ["Available Skills", "=" * 60]
        for cat in sorted(self._catalogues.values(), key=lambda c: c.name):
            lines.append(f"\n{cat.name.upper()} ({len(cat)} skills)")
            lines.append("-" * 40)
            for skill in cat.all_skills():
                lines.append(f"  {skill.summary()}")
        return "\n".join(lines)

    def __len__(self) -> int:
        return sum(len(c) for c in self._catalogues.values())

    def __repr__(self) -> str:
        return f"SkillRegistry(catalogues={len(self._catalogues)}, skills={len(self)})"


# ---------------------------------------------------------------------------
# SkillCatalogueEngine
# ---------------------------------------------------------------------------

@dataclass
class InvocationRecord:
    """Session-level log entry for one skill call."""
    log_id:    str
    skill_id:  str
    inputs:    Dict[str, Any]
    result:    SkillResult
    timestamp: str


class SkillCatalogueEngine:
    """
    Top-level façade.

    - Holds a ``SkillRegistry`` with all installed catalogues.
    - Provides a ``/skill`` command parser for terminal integrations.
    - Maintains a ``session_log`` of every invocation.
    - Supports ``cyclic_context`` injection so weather / season signals
      automatically enrich skill inputs when ``cyclic_aware=True``.
    """

    COMMAND_PREFIX = "/skill"

    def __init__(self, registry: Optional[SkillRegistry] = None) -> None:
        self.registry:    SkillRegistry         = registry or SkillRegistry()
        self.session_log: List[InvocationRecord] = []
        self._cyclic_context: Dict[str, Any]    = {}

    # ------------------------------------------------------------------
    # Cyclic context
    # ------------------------------------------------------------------

    def set_cyclic_context(self, **kwargs: Any) -> None:
        """
        Inject cyclic-trend context (weather, season, economic_phase, …).
        Automatically merged into kwargs for cyclic_aware skills.
        """
        self._cyclic_context.update(kwargs)

    def clear_cyclic_context(self) -> None:
        self._cyclic_context.clear()

    # ------------------------------------------------------------------
    # Core invocation
    # ------------------------------------------------------------------

    def invoke(self, skill_id: str, **kwargs: Any) -> SkillResult:
        """
        Invoke a skill.  If the skill is ``cyclic_aware``, merge the current
        cyclic context into kwargs (caller kwargs take precedence).
        """
        skill = self.registry.find(skill_id)
        merged = dict(kwargs)
        if skill and skill.cyclic_aware:
            for k, v in self._cyclic_context.items():
                merged.setdefault(k, v)

        result = self.registry.run(skill_id, **merged)
        record = InvocationRecord(
            log_id=result.log_id,
            skill_id=skill_id,
            inputs=merged,
            result=result,
            timestamp=result.timestamp,
        )
        self.session_log.append(record)
        return result

    # ------------------------------------------------------------------
    # Command-line interface
    # ------------------------------------------------------------------

    def parse_command(self, command: str) -> str:
        """
        Parse and execute a ``/skill`` command.

        Supported forms::

            /skill list
            /skill list <category>
            /skill search <query>
            /skill run <skill_id> [key=value …]
            /skill help <skill_id>
            /skill log

        Returns a human-readable response string.
        """
        parts = command.strip().split()
        if not parts or parts[0].lower() != self.COMMAND_PREFIX.lstrip("/"):
            # Accept both "/skill" and "skill" as prefix
            if not parts or parts[0].lower() not in (
                self.COMMAND_PREFIX, self.COMMAND_PREFIX.lstrip("/")
            ):
                return f"Unknown command. Use '{self.COMMAND_PREFIX} help'."
        sub = parts[1].lower() if len(parts) > 1 else "list"

        if sub == "list":
            category_filter = parts[2] if len(parts) > 2 else None
            return self._cmd_list(category_filter)

        if sub == "search":
            query = " ".join(parts[2:]) if len(parts) > 2 else ""
            return self._cmd_search(query)

        if sub == "run":
            if len(parts) < 3:
                return "Usage: /skill run <skill_id> [key=value ...]"
            skill_id = parts[2]
            kwargs   = _parse_kwargs(parts[3:])
            return self._cmd_run(skill_id, **kwargs)

        if sub == "help":
            skill_id = parts[2] if len(parts) > 2 else ""
            return self._cmd_help(skill_id)

        if sub == "log":
            return self._cmd_log()

        return f"Unknown sub-command '{sub}'. Options: list, search, run, help, log."

    # ------------------------------------------------------------------
    # Private command implementations
    # ------------------------------------------------------------------

    def _cmd_list(self, category_filter: Optional[str]) -> str:
        if category_filter:
            try:
                cat_enum = SkillCategory(category_filter.lower())
            except ValueError:
                return f"Unknown category '{category_filter}'."
            skills = self.registry.skills_by_category(cat_enum)
        else:
            skills = self.registry.all_skills()
        if not skills:
            return "No skills found."
        return "\n".join(s.summary() for s in skills)

    def _cmd_search(self, query: str) -> str:
        if not query:
            return "Usage: /skill search <query>"
        results = self.registry.search(query)
        if not results:
            return f"No skills matched '{query}'."
        return "\n".join(s.summary() for s in results)

    def _cmd_run(self, skill_id: str, **kwargs: Any) -> str:
        result = self.invoke(skill_id, **kwargs)
        lines = [
            f"Skill:  {result.skill_id}",
            f"Status: {result.status.value}",
            f"Log ID: {result.log_id}",
        ]
        if result.error:
            lines.append(f"Error:  {result.error}")
        else:
            lines.append(f"Output: {result.output}")
        return "\n".join(lines)

    def _cmd_help(self, skill_id: str) -> str:
        if not skill_id:
            return self.registry.help_text()
        skill = self.registry.find(skill_id)
        if not skill:
            return f"Skill '{skill_id}' not found."
        lines = [
            f"Skill ID:    {skill.skill_id}",
            f"Name:        {skill.name}",
            f"Category:    {skill.category.value}",
            f"Engine:      {skill.source_engine}",
            f"Cyclic:      {skill.cyclic_aware}",
            f"Tags:        {', '.join(skill.tags) or '(none)'}",
            "",
            "Description:",
            textwrap.indent(skill.description, "  "),
            "",
            "Inputs:",
        ]
        for inp in skill.inputs:
            req = "required" if inp.required else f"optional (default={inp.default!r})"
            lines.append(f"  {inp.name} ({inp.input_type}) [{req}]: {inp.description}")
        return "\n".join(lines)

    def _cmd_log(self) -> str:
        if not self.session_log:
            return "Session log is empty."
        lines = [f"Session Log ({len(self.session_log)} entries)", "-" * 40]
        for rec in self.session_log[-20:]:  # last 20
            lines.append(
                f"[{rec.timestamp}] {rec.skill_id} → {rec.result.status.value} (log:{rec.log_id})"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    def add_catalogue(self, catalogue: SkillCatalogue) -> "SkillCatalogueEngine":
        self.registry.add_catalogue(catalogue)
        return self

    def total_skills(self) -> int:
        return len(self.registry)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _parse_kwargs(tokens: Sequence[str]) -> Dict[str, Any]:
    """Parse ``key=value`` tokens into a dict."""
    kwargs: Dict[str, Any] = {}
    for token in tokens:
        if "=" in token:
            k, _, v = token.partition("=")
            kwargs[k.strip()] = _coerce(v.strip())
    return kwargs


def _coerce(value: str) -> Any:
    """Attempt int → float → bool → str coercion."""
    if value.lower() in ("true", "yes"):
        return True
    if value.lower() in ("false", "no"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    return value


# ---------------------------------------------------------------------------
# Default catalogue builders (thin wrappers — no hard engine dependency)
# ---------------------------------------------------------------------------

def _build_cpe_catalogue() -> SkillCatalogue:
    """Catalogue of ClientPsychologyEngine skills."""
    cat = SkillCatalogue("client_psychology", SkillCategory.DEMOGRAPHIC_INTELLIGENCE)

    cat.register(SkillDefinition(
        skill_id="cpe.profile_generation",
        name="Profile Generation Cohort",
        description=(
            "Infer the generation cohort (Silent / Boomer / Gen-X / Millennial / Gen-Z) "
            "of a prospect from conversational cues, vocabulary, and context signals."
        ),
        category=SkillCategory.DEMOGRAPHIC_INTELLIGENCE,
        source_engine="ClientPsychologyEngine",
        tags=["demographic", "generation", "cohort", "lingo"],
        inputs=[
            SkillInput("hints", "Dict of conversational cue signals", input_type="dict"),
        ],
        invoke=lambda hints=None: {
            "action": "infer_generation",
            "hints":  hints or {},
        },
    ))

    cat.register(SkillDefinition(
        skill_id="cpe.detect_pain",
        name="Detect Pain Points",
        description=(
            "Scan client transcript or statement for active pain signals across "
            "9 categories: revenue growth, cost reduction, efficiency, talent, "
            "competitive threat, compliance, digital transformation, innovation, "
            "and customer experience."
        ),
        category=SkillCategory.PAIN_POINT_DETECTION,
        source_engine="ClientPsychologyEngine",
        tags=["pain", "detection", "qualification", "meddic"],
        inputs=[
            SkillInput("statement", "Raw client statement or transcript", input_type="str"),
            SkillInput("industry", "Industry vertical hint (optional)", required=False, default=None),
        ],
        invoke=lambda statement="", industry=None: {
            "action":    "detect_pain",
            "statement": statement,
            "industry":  industry,
        },
    ))

    cat.register(SkillDefinition(
        skill_id="cpe.select_framework",
        name="Select Sales Framework",
        description=(
            "Choose the optimal modern sales methodology for this prospect: "
            "MEDDIC, Challenger, GAP Selling, SNAP, JBTD, SPIN Modern, "
            "Command of the Sale, or Consultative."
        ),
        category=SkillCategory.SALES_FRAMEWORK,
        source_engine="ClientPsychologyEngine",
        tags=["framework", "methodology", "meddic", "challenger", "gap", "snap"],
        inputs=[
            SkillInput("generation", "GenerationCohort value", input_type="str"),
            SkillInput("role", "DecisionMakerRole value", input_type="str"),
            SkillInput("formality", "0–1 formality preference", input_type="float", required=False, default=0.5),
            SkillInput("relationship_dependency", "0–1 relationship weight", input_type="float", required=False, default=0.5),
        ],
        invoke=lambda generation="", role="", formality=0.5, relationship_dependency=0.5: {
            "action": "select_framework",
            "generation": generation,
            "role": role,
            "formality": formality,
            "relationship_dependency": relationship_dependency,
        },
    ))

    cat.register(SkillDefinition(
        skill_id="cpe.adapt_language",
        name="Adapt Language to Demographic",
        description=(
            "Translate a message into the generation-native vocabulary pack: "
            "e.g. 'ROI' → 'stack-ranked impact' for Gen-Z, or 'partnership' "
            "language for Boomers."
        ),
        category=SkillCategory.DEMOGRAPHIC_INTELLIGENCE,
        source_engine="ClientPsychologyEngine",
        tags=["language", "lingo", "translation", "demographic"],
        inputs=[
            SkillInput("message", "Original message to adapt", input_type="str"),
            SkillInput("generation", "Target GenerationCohort", input_type="str"),
        ],
        invoke=lambda message="", generation="": {
            "action": "adapt_language",
            "message": message,
            "generation": generation,
        },
    ))

    cat.register(SkillDefinition(
        skill_id="cpe.income_scaling",
        name="Income Scaling Playbook",
        description=(
            "Generate the income-scaling conversation playbook for a prospect, "
            "ranging from 2× (optimisation) to 5× (transformation) uplift targets."
        ),
        category=SkillCategory.INCOME_SCALING,
        source_engine="ClientPsychologyEngine",
        tags=["income", "scaling", "revenue", "playbook", "2x", "5x"],
        inputs=[
            SkillInput("generation", "GenerationCohort", input_type="str"),
            SkillInput("target_multiplier", "2 | 3 | 4 | 5", input_type="int", required=False, default=3),
        ],
        invoke=lambda generation="", target_multiplier=3: {
            "action": "income_scaling",
            "generation": generation,
            "target_multiplier": target_multiplier,
        },
    ))

    cat.register(SkillDefinition(
        skill_id="cpe.read_client",
        name="Full Client Reading Report",
        description=(
            "Produce a complete ClientReadingReport: cohort, pain signals, "
            "recommended framework, language pack, scaling playbook, and "
            "next-action recommendations — all in one call."
        ),
        category=SkillCategory.DEMOGRAPHIC_INTELLIGENCE,
        source_engine="ClientPsychologyEngine",
        tags=["report", "full-read", "holistic", "client"],
        inputs=[
            SkillInput("statement", "Client statement/transcript", input_type="str"),
            SkillInput("hints", "Optional demographic hints dict", input_type="dict", required=False, default=None),
        ],
        invoke=lambda statement="", hints=None: {
            "action":    "read_client",
            "statement": statement,
            "hints":     hints or {},
        },
    ))

    return cat


def _build_cne_catalogue() -> SkillCatalogue:
    """Catalogue of CharacterNetworkEngine skills."""
    cat = SkillCatalogue("character_network", SkillCategory.CHARACTER_NETWORK)

    cat.register(SkillDefinition(
        skill_id="cne.score_moral_fiber",
        name="Score Moral Fibre",
        description=(
            "Score a contact against the 8 Victorian character pillars "
            "(integrity, diligence, honour, service, courage, temperance, "
            "prudence, magnanimity) and return a MoralFiberScore."
        ),
        category=SkillCategory.VICTORIAN_VIRTUE,
        source_engine="CharacterNetworkEngine",
        tags=["moral", "character", "victorian", "virtue", "score"],
        inputs=[
            SkillInput("contact_id", "Unique identifier for the contact", input_type="str"),
            SkillInput("trait_signals", "Dict mapping trait names to observed scores (0–1)", input_type="dict"),
        ],
        invoke=lambda contact_id="", trait_signals=None: {
            "action":        "score_moral_fiber",
            "contact_id":    contact_id,
            "trait_signals": trait_signals or {},
        },
    ))

    cat.register(SkillDefinition(
        skill_id="cne.match_archetype",
        name="Match Victorian Archetype",
        description=(
            "Identify which of the 15+ Victorian leader archetypes best matches "
            "a contact profile (e.g. The Industrialist, The Reformer, "
            "The Enlightened Patron, The Servant Leader)."
        ),
        category=SkillCategory.CHARACTER_NETWORK,
        source_engine="CharacterNetworkEngine",
        tags=["archetype", "victorian", "match", "character"],
        inputs=[
            SkillInput("trait_scores", "Dict of character trait scores", input_type="dict"),
        ],
        invoke=lambda trait_scores=None: {
            "action":       "match_archetype",
            "trait_scores": trait_scores or {},
        },
    ))

    cat.register(SkillDefinition(
        skill_id="cne.build_network",
        name="Build Character Network",
        description=(
            "Construct a curated network graph of high-moral-fibre contacts, "
            "weighted by complementary virtue profiles and trust depth."
        ),
        category=SkillCategory.CHARACTER_NETWORK,
        source_engine="CharacterNetworkEngine",
        tags=["network", "graph", "trust", "high-character"],
        inputs=[
            SkillInput("contacts", "List of contact dicts with trait_signals", input_type="list"),
            SkillInput("min_fiber_score", "Minimum MoralFiberScore threshold (0–1)", input_type="float", required=False, default=0.65),
        ],
        invoke=lambda contacts=None, min_fiber_score=0.65: {
            "action":           "build_network",
            "contacts":         contacts or [],
            "min_fiber_score":  min_fiber_score,
        },
    ))

    cat.register(SkillDefinition(
        skill_id="cne.second_nature_prompt",
        name="Second-Nature Good Behaviour Prompt",
        description=(
            "Surface a contextually appropriate 'second-nature' good action — "
            "an invisible, habitual act of service or character that builds "
            "trust and elevates the relational fabric without announcement."
        ),
        category=SkillCategory.VICTORIAN_VIRTUE,
        source_engine="CharacterNetworkEngine",
        tags=["second-nature", "habitual", "service", "invisible-good"],
        inputs=[
            SkillInput("context", "Current interaction context (meeting, email, event, etc.)", input_type="str"),
            SkillInput("relationship_stage", "early | developing | established | deep", input_type="str", required=False, default="developing"),
        ],
        invoke=lambda context="", relationship_stage="developing": {
            "action":             "second_nature_prompt",
            "context":            context,
            "relationship_stage": relationship_stage,
        },
    ))

    cat.register(SkillDefinition(
        skill_id="cne.virtue_development_plan",
        name="Virtue Development Plan",
        description=(
            "Generate a 90-day personal character development plan based on "
            "identified virtue gaps relative to the Victorian stride leader ideal."
        ),
        category=SkillCategory.VICTORIAN_VIRTUE,
        source_engine="CharacterNetworkEngine",
        tags=["development", "plan", "virtue", "growth"],
        inputs=[
            SkillInput("current_scores", "Dict of current pillar scores", input_type="dict"),
            SkillInput("target_archetype", "Target Victorian archetype name (optional)", input_type="str", required=False, default=None),
        ],
        invoke=lambda current_scores=None, target_archetype=None: {
            "action":           "virtue_development_plan",
            "current_scores":   current_scores or {},
            "target_archetype": target_archetype,
        },
    ))

    return cat


def _build_nme_catalogue() -> SkillCatalogue:
    """Catalogue of NetworkingMasteryEngine skills."""
    cat = SkillCatalogue("networking_mastery", SkillCategory.NETWORKING_MASTERY)

    cat.register(SkillDefinition(
        skill_id="nme.profile_master",
        name="Profile Networking Master",
        description=(
            "Load the behavioural profile of one of the 18 modelled networking "
            "greats (e.g. Dale Carnegie, Keith Ferrazzi, Harvey Mackay, "
            "Ivan Misner, Porter Gale) and extract their signature moves."
        ),
        category=SkillCategory.NETWORKING_MASTERY,
        source_engine="NetworkingMasteryEngine",
        tags=["networking", "great", "profile", "mastery"],
        inputs=[
            SkillInput("master_id", "Identifier for the networking great", input_type="str"),
        ],
        invoke=lambda master_id="": {
            "action":    "profile_master",
            "master_id": master_id,
        },
    ))

    cat.register(SkillDefinition(
        skill_id="nme.create_buzz",
        name="Create Buzz Strategy",
        description=(
            "Design a context-aware buzz-creation campaign: face-value "
            "announcements, between-the-lines capability signals, and "
            "outside-the-box applications that position the system distinctively."
        ),
        category=SkillCategory.BUZZ_CREATION,
        source_engine="NetworkingMasteryEngine",
        tags=["buzz", "campaign", "positioning", "narrative"],
        cyclic_aware=True,
        inputs=[
            SkillInput("objective", "Core goal of the buzz campaign", input_type="str"),
            SkillInput("audience", "Target audience descriptor", input_type="str"),
            SkillInput("season", "Current season (auto-injected if cyclic context set)", input_type="str", required=False, default=None),
            SkillInput("weather_pattern", "Current weather pattern (cyclic)", input_type="str", required=False, default=None),
        ],
        invoke=lambda objective="", audience="", season=None, weather_pattern=None: {
            "action":          "create_buzz",
            "objective":       objective,
            "audience":        audience,
            "season":          season,
            "weather_pattern": weather_pattern,
        },
    ))

    cat.register(SkillDefinition(
        skill_id="nme.signal_capability",
        name="Signal Capability (3-Layer)",
        description=(
            "Produce a three-layer capability signal: "
            "(1) face-value — what you state directly; "
            "(2) between-the-lines — what you imply through positioning; "
            "(3) outside-the-box — unexpected applications that reframe value."
        ),
        category=SkillCategory.CAPABILITY_SIGNALLING,
        source_engine="NetworkingMasteryEngine",
        tags=["capability", "signal", "positioning", "three-layer"],
        inputs=[
            SkillInput("capability", "Core capability to signal", input_type="str"),
            SkillInput("audience_type", "executive | peer | client | investor | community", input_type="str"),
        ],
        invoke=lambda capability="", audience_type="peer": {
            "action":        "signal_capability",
            "capability":    capability,
            "audience_type": audience_type,
        },
    ))

    cat.register(SkillDefinition(
        skill_id="nme.network_intelligence",
        name="Generate Network Intelligence Report",
        description=(
            "Synthesise a NetworkIntelligenceReport: weak-tie mapping, "
            "connector identification, event-timing recommendations, "
            "and the top 5 'warm door' introductions to pursue."
        ),
        category=SkillCategory.NETWORKING_MASTERY,
        source_engine="NetworkingMasteryEngine",
        tags=["intelligence", "report", "weak-tie", "connector"],
        cyclic_aware=True,
        inputs=[
            SkillInput("network_snapshot", "Current network dict (contacts + edges)", input_type="dict"),
            SkillInput("economic_phase", "Cyclic economic phase (auto-injected)", input_type="str", required=False, default=None),
        ],
        invoke=lambda network_snapshot=None, economic_phase=None: {
            "action":           "network_intelligence",
            "network_snapshot": network_snapshot or {},
            "economic_phase":   economic_phase,
        },
    ))

    cat.register(SkillDefinition(
        skill_id="nme.event_timing",
        name="Optimise Event Timing",
        description=(
            "Recommend the optimal calendar timing for a networking event "
            "based on season, cyclic economic phase, and industry rhythms."
        ),
        category=SkillCategory.NETWORKING_MASTERY,
        source_engine="NetworkingMasteryEngine",
        tags=["event", "timing", "calendar", "season"],
        cyclic_aware=True,
        inputs=[
            SkillInput("event_type", "conference | dinner | workshop | virtual | social", input_type="str"),
            SkillInput("month", "Target month 1–12 (cyclic auto-inject supported)", input_type="int", required=False, default=None),
            SkillInput("season", "Season override (cyclic)", input_type="str", required=False, default=None),
        ],
        invoke=lambda event_type="", month=None, season=None: {
            "action":     "event_timing",
            "event_type": event_type,
            "month":      month,
            "season":     season,
        },
    ))

    return cat


def _build_cte_catalogue() -> SkillCatalogue:
    """Catalogue of CyclicTrendsEngine skills."""
    cat = SkillCatalogue("cyclic_trends", SkillCategory.CYCLIC_TRENDS)

    cat.register(SkillDefinition(
        skill_id="cte.get_month_context",
        name="Get Monthly Cyclic Context",
        description=(
            "Retrieve the full cyclic context for a given month: season, "
            "weather pattern, economic multipliers, daylight, activity index, "
            "and all weather/economic signals — with optional deviation inputs."
        ),
        category=SkillCategory.CYCLIC_TRENDS,
        source_engine="CyclicTrendsEngine",
        tags=["month", "season", "weather", "economic", "context"],
        inputs=[
            SkillInput("month", "Month number 1–12", input_type="int"),
            SkillInput("temperature_deviation", "°C above/below seasonal normal", input_type="float", required=False, default=0.0),
            SkillInput("precipitation_deviation", "% deviation from average precipitation", input_type="float", required=False, default=0.0),
            SkillInput("economic_phase", "EconomicPhase override (optional)", input_type="str", required=False, default=None),
        ],
        invoke=lambda month=1, temperature_deviation=0.0, precipitation_deviation=0.0, economic_phase=None: {
            "action":                  "get_month_context",
            "month":                   month,
            "temperature_deviation":   temperature_deviation,
            "precipitation_deviation": precipitation_deviation,
            "economic_phase":          economic_phase,
        },
    ))

    cat.register(SkillDefinition(
        skill_id="cte.automation_trend_input",
        name="Cyclic Trend Input for Automation",
        description=(
            "Enrich any automation type (scheduling, energy, outreach, "
            "sales, operations, HVAC, workforce) with real-time cyclic "
            "trend signals so automation parameters adapt to season, "
            "weather, and economic phase."
        ),
        category=SkillCategory.WEATHER_ADAPTATION,
        source_engine="CyclicTrendsEngine",
        tags=["automation", "cyclic", "weather", "adaptation", "seasonal"],
        cyclic_aware=True,
        inputs=[
            SkillInput("automation_type", "scheduling | energy | outreach | sales | operations | hvac | workforce", input_type="str"),
            SkillInput("month", "Month 1–12", input_type="int", required=False, default=None),
            SkillInput("weather_pattern", "WeatherPattern (cyclic auto-inject)", input_type="str", required=False, default=None),
            SkillInput("season", "Season (cyclic auto-inject)", input_type="str", required=False, default=None),
            SkillInput("economic_phase", "EconomicPhase (cyclic auto-inject)", input_type="str", required=False, default=None),
        ],
        invoke=lambda automation_type="", month=None, weather_pattern=None, season=None, economic_phase=None: {
            "action":          "automation_trend_input",
            "automation_type": automation_type,
            "month":           month,
            "weather_pattern": weather_pattern,
            "season":          season,
            "economic_phase":  economic_phase,
        },
    ))

    cat.register(SkillDefinition(
        skill_id="cte.trend_snapshot",
        name="Trend Snapshot",
        description=(
            "Return a concise trend snapshot for situational awareness: "
            "season, weather pattern, economic phase, activity index, "
            "and top-3 actionable signals."
        ),
        category=SkillCategory.CYCLIC_TRENDS,
        source_engine="CyclicTrendsEngine",
        tags=["snapshot", "situational", "trend", "awareness"],
        cyclic_aware=True,
        inputs=[
            SkillInput("month", "Month 1–12", input_type="int", required=False, default=None),
        ],
        invoke=lambda month=None: {
            "action": "trend_snapshot",
            "month":  month,
        },
    ))

    cat.register(SkillDefinition(
        skill_id="cte.weather_signal_bank",
        name="Weather Signal Bank",
        description=(
            "Return the full bank of weather and economic signals for a "
            "given context, ready to be consumed by downstream automation engines."
        ),
        category=SkillCategory.WEATHER_ADAPTATION,
        source_engine="CyclicTrendsEngine",
        tags=["signal", "bank", "weather", "economic"],
        cyclic_aware=True,
        inputs=[
            SkillInput("month", "Month 1–12", input_type="int"),
            SkillInput("temperature_deviation", "°C deviation", input_type="float", required=False, default=0.0),
            SkillInput("precipitation_deviation", "% precipitation deviation", input_type="float", required=False, default=0.0),
        ],
        invoke=lambda month=1, temperature_deviation=0.0, precipitation_deviation=0.0: {
            "action":                  "weather_signal_bank",
            "month":                   month,
            "temperature_deviation":   temperature_deviation,
            "precipitation_deviation": precipitation_deviation,
        },
    ))

    return cat


def _build_meta_catalogue() -> SkillCatalogue:
    """Meta skills: skill management and self-description."""
    cat = SkillCatalogue("skill_management", SkillCategory.SKILL_MANAGEMENT)

    cat.register(SkillDefinition(
        skill_id="sce.list_all",
        name="List All Skills",
        description="Return a summary of every skill registered in the catalogue.",
        category=SkillCategory.SKILL_MANAGEMENT,
        source_engine="SkillCatalogueEngine",
        tags=["meta", "list", "catalogue"],
        inputs=[],
        invoke=lambda: {"action": "list_all"},
    ))

    cat.register(SkillDefinition(
        skill_id="sce.search",
        name="Search Skills",
        description="Search across skill names, descriptions, and tags.",
        category=SkillCategory.SKILL_MANAGEMENT,
        source_engine="SkillCatalogueEngine",
        tags=["meta", "search"],
        inputs=[
            SkillInput("query", "Search string", input_type="str"),
        ],
        invoke=lambda query="": {"action": "search", "query": query},
    ))

    cat.register(SkillDefinition(
        skill_id="sce.session_log",
        name="Show Session Log",
        description="Return the current session invocation log.",
        category=SkillCategory.SKILL_MANAGEMENT,
        source_engine="SkillCatalogueEngine",
        tags=["meta", "log", "session"],
        inputs=[],
        invoke=lambda: {"action": "session_log"},
    ))

    return cat


# ---------------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------------

def build_default_registry() -> SkillRegistry:
    """
    Build and return a ``SkillRegistry`` pre-populated with all four engine
    catalogues plus the meta skill-management catalogue.
    """
    registry = SkillRegistry()
    registry.add_catalogue(_build_cpe_catalogue())
    registry.add_catalogue(_build_cne_catalogue())
    registry.add_catalogue(_build_nme_catalogue())
    registry.add_catalogue(_build_cte_catalogue())
    registry.add_catalogue(_build_meta_catalogue())
    return registry


def build_default_engine(cyclic_context: Optional[Dict[str, Any]] = None) -> SkillCatalogueEngine:
    """
    Build and return a ``SkillCatalogueEngine`` ready for use.

    Optionally accepts a ``cyclic_context`` dict (e.g. ``{"season": "SPRING",
    "weather_pattern": "WARM_SUNNY", "economic_phase": "EXPANSION"}``) that
    will be automatically merged into cyclic-aware skill invocations.
    """
    engine = SkillCatalogueEngine(registry=build_default_registry())
    if cyclic_context:
        engine.set_cyclic_context(**cyclic_context)
    return engine

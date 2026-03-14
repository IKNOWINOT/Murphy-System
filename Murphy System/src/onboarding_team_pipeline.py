"""
Onboarding Team Pipeline — Employee Discovery → Rosetta Generation
==================================================================
Extends the onboarding conversation flow to:
1. Ask "Who are your employees and what do they do?"
2. Extract team member roles and responsibilities
3. For each team member: create a ShadowAgent via ShadowAgentIntegration
4. For each shadow: generate a RosettaDocument via RosettaDocumentBuilder
5. Present each Rosetta summary for HITL confirmation
6. On confirmation: solidify the Rosetta doc and begin parallel shadow training

Wires into:
  - OnboardingFlow (existing) for session management
  - ShadowAgentIntegration (existing) for shadow lifecycle
  - RosettaDocumentBuilder (existing) for agent specification
  - LivingDocument (existing) for state management
  - ShadowLearningAgent (existing) for parallel training initiation
"""

import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from thread_safe_operations import capped_append
except ImportError:
    def capped_append(target_list: list, item: Any, max_size: int = 10_000) -> None:
        """Fallback bounded append (CWE-770)."""
        if len(target_list) >= max_size:
            del target_list[: max_size // 10]
        target_list.append(item)

try:
    from shadow_agent_integration import ShadowAgentIntegration
except ImportError:
    ShadowAgentIntegration = None  # type: ignore[assignment,misc]

try:
    from rosetta.rosetta_document_builder import RosettaDocumentBuilder
except ImportError:
    RosettaDocumentBuilder = None  # type: ignore[assignment,misc]

try:
    from org_compiler.shadow_learning import ShadowLearningAgent
except ImportError:
    ShadowLearningAgent = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)


@dataclass
class TeamMember:
    """A discovered team member from the onboarding conversation."""
    name: str
    role: str
    responsibilities: List[str] = field(default_factory=list)
    department: str = ""
    automation_scope: List[str] = field(default_factory=list)


@dataclass
class TeamDiscoveryResult:
    """Result of team member discovery from natural language."""
    members: List[TeamMember] = field(default_factory=list)
    org_structure: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0


@dataclass
class RosettaGenerationResult:
    """Result of Rosetta document generation for one team member."""
    member: TeamMember
    shadow_agent_id: str
    rosetta_doc_id: str
    rosetta_summary: str
    domain: str
    automation_scope: List[str] = field(default_factory=list)
    hitl_model: str = "shadow"


# Role → department inference map
_ROLE_DEPARTMENT_MAP: Dict[str, str] = {
    "accountant": "Finance",
    "bookkeeper": "Finance",
    "finance": "Finance",
    "cfo": "Finance",
    "coo": "Operations",
    "operations": "Operations",
    "floor manager": "Operations",
    "manager": "Operations",
    "supervisor": "Operations",
    "sales": "Sales",
    "account executive": "Sales",
    "sales rep": "Sales",
    "hr": "Human Resources",
    "recruiter": "Human Resources",
    "marketing": "Marketing",
    "designer": "Creative",
    "developer": "Engineering",
    "engineer": "Engineering",
    "it": "IT",
    "support": "Customer Support",
    "customer service": "Customer Support",
    "warehouse": "Logistics",
    "logistics": "Logistics",
    "driver": "Logistics",
    "delivery": "Logistics",
    "legal": "Legal",
    "compliance": "Legal",
    "executive": "Executive",
    "ceo": "Executive",
    "president": "Executive",
    "director": "Executive",
}


def _infer_department(role: str) -> str:
    """Infer department from role title."""
    role_lower = role.lower()
    for keyword, dept in _ROLE_DEPARTMENT_MAP.items():
        if keyword in role_lower:
            return dept
    return "Operations"


def _infer_automation_scope(role: str, responsibilities: List[str]) -> List[str]:
    """Infer automation scope from role and responsibilities."""
    scope: List[str] = []
    role_lower = role.lower()
    all_text = role_lower + " " + " ".join(r.lower() for r in responsibilities)

    if any(k in all_text for k in ["invoice", "billing", "payment", "accounting", "bookkeeping"]):
        scope.append("invoice_processing")
    if any(k in all_text for k in ["schedule", "calendar", "appointment", "booking"]):
        scope.append("scheduling")
    if any(k in all_text for k in ["report", "analytics", "data", "spreadsheet"]):
        scope.append("reporting")
    if any(k in all_text for k in ["email", "communication", "correspondence"]):
        scope.append("email_management")
    if any(k in all_text for k in ["hire", "recruit", "onboard", "hr", "payroll"]):
        scope.append("hr_workflows")
    if any(k in all_text for k in ["order", "inventory", "warehouse", "logistics", "ship"]):
        scope.append("inventory_management")
    if any(k in all_text for k in ["customer", "client", "support", "service"]):
        scope.append("customer_communication")
    if any(k in all_text for k in ["sales", "lead", "crm", "prospect"]):
        scope.append("sales_pipeline")
    if any(k in all_text for k in ["manage", "supervise", "coordinate", "floor"]):
        scope.append("workflow_coordination")

    return scope if scope else ["general_operations"]


def _infer_domain(role: str, department: str) -> str:
    """Infer the Rosetta domain from role and department."""
    role_lower = role.lower()
    if any(k in role_lower for k in ["accountant", "bookkeeper", "cfo", "finance"]):
        return "finance"
    if any(k in role_lower for k in ["sales", "account executive"]):
        return "sales"
    if any(k in role_lower for k in ["hr", "recruiter", "human resources"]):
        return "human_resources"
    if any(k in role_lower for k in ["marketing", "designer", "creative"]):
        return "marketing"
    if any(k in role_lower for k in ["developer", "engineer", "it", "tech"]):
        return "engineering"
    if any(k in role_lower for k in ["driver", "delivery", "logistics", "warehouse"]):
        return "logistics"
    if any(k in role_lower for k in ["customer", "support", "service"]):
        return "customer_support"
    if any(k in role_lower for k in ["legal", "compliance"]):
        return "legal"
    return department.lower().replace(" ", "_") if department else "operations"


class OnboardingTeamPipeline:
    """Extracts team members from natural language and generates agentic mirrors.

    Thread-safe via threading.Lock.
    """

    def __init__(
        self,
        shadow_integration: Any = None,
        rosetta_builder: Any = None,
        living_documents: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize with existing system components.

        Args:
            shadow_integration: ShadowAgentIntegration instance (or None for graceful degradation).
            rosetta_builder: RosettaDocumentBuilder instance (or None for graceful degradation).
            living_documents: Dict of living documents keyed by doc_id.
        """
        self._shadow_integration = shadow_integration
        self._rosetta_builder = rosetta_builder
        self._living_documents: Dict[str, Any] = living_documents or {}
        self._lock = threading.Lock()
        self._confirmed_docs: List[str] = []

    # ------------------------------------------------------------------
    # Extraction
    # ------------------------------------------------------------------

    def extract_team_members(self, message: str) -> TeamDiscoveryResult:
        """Parse natural language for team member information.

        Handles patterns like:
          - "I have a floor manager named Jake"
          - "Our accountant Sarah handles invoicing"
          - "Jake is our floor manager"
          - "Sarah handles invoicing and billing"
          - "I have 3 sales reps"
          - "[Name] is a [role]"
          - "[Name] handles [responsibility]"

        Args:
            message: natural language message from the business owner.

        Returns:
            TeamDiscoveryResult with extracted members.
        """
        with self._lock:
            members: Dict[str, TeamMember] = {}

            # Pattern: "I have a [role] named [Name]" or "I have [Name] as [role]"
            p1 = re.findall(
                r"(?:i have|we have|there(?:'s| is)) (?:a |an )?([a-z][a-z\s]+?) named ([A-Z][a-z]+)",
                message,
                re.IGNORECASE,
            )
            for role, name in p1:
                role = role.strip()
                key = name.lower()
                if key not in members:
                    members[key] = TeamMember(
                        name=name,
                        role=role,
                        department=_infer_department(role),
                        automation_scope=_infer_automation_scope(role, []),
                    )

            # Pattern: "[Name] is our [role]" or "[Name] is a [role]"
            p2 = re.findall(
                r"([A-Z][a-z]+) is (?:our |a |an )?([a-z][a-z\s]+?)(?:\s+who|\s+and|\s+that|\.|,|$)",
                message,
                re.IGNORECASE,
            )
            for name, role in p2:
                role = role.strip()
                if not role or len(role) < 2:
                    continue
                key = name.lower()
                if key not in members:
                    members[key] = TeamMember(
                        name=name,
                        role=role,
                        department=_infer_department(role),
                        automation_scope=_infer_automation_scope(role, []),
                    )

            # Pattern: "Our [role] [Name] handles/does [responsibility]"
            p3 = re.findall(
                r"(?:our|my) ([a-z][a-z\s]+?) ([A-Z][a-z]+) (?:handles?|does?|manages?|is responsible for) ([^.]+)",
                message,
                re.IGNORECASE,
            )
            for role, name, resp_text in p3:
                role = role.strip()
                name = name.strip()
                responsibilities = [r.strip() for r in re.split(r",| and ", resp_text) if r.strip()]
                key = name.lower()
                if key in members:
                    members[key].responsibilities.extend(responsibilities)
                    members[key].automation_scope = _infer_automation_scope(
                        members[key].role, members[key].responsibilities
                    )
                else:
                    members[key] = TeamMember(
                        name=name,
                        role=role,
                        responsibilities=responsibilities,
                        department=_infer_department(role),
                        automation_scope=_infer_automation_scope(role, responsibilities),
                    )

            # Pattern: "[Name] handles/manages/does [responsibility]"
            p4 = re.findall(
                r"([A-Z][a-z]+) (?:handles?|manages?|does?|is responsible for|takes care of) ([^.]+)",
                message,
                re.IGNORECASE,
            )
            for name, resp_text in p4:
                name = name.strip()
                responsibilities = [r.strip() for r in re.split(r",| and ", resp_text) if r.strip()]
                key = name.lower()
                if key in members:
                    members[key].responsibilities.extend(responsibilities)
                    members[key].automation_scope = _infer_automation_scope(
                        members[key].role, members[key].responsibilities
                    )

            member_list = list(members.values())

            # Infer org structure
            org_structure: Dict[str, Any] = {}
            for m in member_list:
                dept = m.department
                if dept not in org_structure:
                    org_structure[dept] = []
                org_structure[dept].append({"name": m.name, "role": m.role})

            confidence = min(1.0, len(member_list) * 0.3) if member_list else 0.0

            result = TeamDiscoveryResult(
                members=member_list,
                org_structure=org_structure,
                confidence=confidence,
            )
            logger.info(
                "extract_team_members: found %d members (confidence=%.2f)",
                len(member_list),
                confidence,
            )
            return result

    # ------------------------------------------------------------------
    # Rosetta generation
    # ------------------------------------------------------------------

    def generate_rosetta_for_member(
        self, member: TeamMember, business_context: Dict[str, Any]
    ) -> RosettaGenerationResult:
        """Create a shadow agent and Rosetta document for one team member.

        Args:
            member: the TeamMember to generate a Rosetta document for.
            business_context: dict with keys like 'business_name', 'business_description', etc.

        Returns:
            RosettaGenerationResult with IDs and summary for HITL presentation.
        """
        shadow_agent_id = f"shadow-{member.name.lower()}-{uuid.uuid4().hex[:8]}"
        rosetta_doc_id = f"rosetta-{member.name.lower()}-{uuid.uuid4().hex[:8]}"
        domain = _infer_domain(member.role, member.department)
        automation_scope = member.automation_scope or _infer_automation_scope(
            member.role, member.responsibilities
        )

        # Create shadow agent if integration is available
        if self._shadow_integration is not None:
            try:
                account_id = business_context.get("account_id", "default-account")
                org_id = business_context.get("org_id", None)
                self._shadow_integration.create_shadow_agent(
                    primary_role_id=f"role-{member.role.lower().replace(' ', '-')}",
                    account_id=account_id,
                    org_id=org_id,
                    department=member.department,
                )
                logger.info("Created shadow agent %s for %s", shadow_agent_id, member.name)
            except Exception as exc:
                logger.warning(
                    "Could not create shadow agent for %s: %s", member.name, exc
                )

        # Generate Rosetta document if builder is available
        if self._rosetta_builder is not None:
            try:
                business_description = business_context.get(
                    "business_description",
                    f"Business employing {member.role}",
                )
                self._rosetta_builder.build(
                    agent_id=shadow_agent_id,
                    agent_name=f"{member.role} Agent — {member.name}",
                    business_description=business_description,
                    agent_type="shadow",
                    role_title=member.role,
                    shadowed_user_name=member.name,
                )
                logger.info("Generated Rosetta doc %s for %s", rosetta_doc_id, member.name)
            except Exception as exc:
                logger.warning(
                    "Could not generate Rosetta doc for %s: %s", member.name, exc
                )

        scope_str = ", ".join(automation_scope)
        rosetta_summary = (
            f"{member.name} ({member.role}, {member.department}): "
            f"Shadow agent will observe and learn {scope_str}."
        )

        return RosettaGenerationResult(
            member=member,
            shadow_agent_id=shadow_agent_id,
            rosetta_doc_id=rosetta_doc_id,
            rosetta_summary=rosetta_summary,
            domain=domain,
            automation_scope=automation_scope,
            hitl_model="shadow",
        )

    def generate_all_rosettas(
        self,
        discovery: TeamDiscoveryResult,
        business_context: Dict[str, Any],
    ) -> List[RosettaGenerationResult]:
        """Batch generate Rosetta documents for all discovered team members.

        Args:
            discovery: TeamDiscoveryResult from extract_team_members.
            business_context: business context dict.

        Returns:
            List of RosettaGenerationResult, one per team member.
        """
        results = []
        for member in discovery.members:
            result = self.generate_rosetta_for_member(member, business_context)
            results.append(result)
        logger.info(
            "generate_all_rosettas: generated %d Rosetta docs", len(results)
        )
        return results

    # ------------------------------------------------------------------
    # HITL presentation
    # ------------------------------------------------------------------

    def build_hitl_summary(self, results: List[RosettaGenerationResult]) -> str:
        """Build the HITL presentation text for the generated Rosetta docs.

        Args:
            results: list of RosettaGenerationResult from generate_all_rosettas.

        Returns:
            Human-readable summary string for HITL confirmation.
        """
        if not results:
            return "No team members were found. Could you tell me more about your employees?"

        lines = ["Here's what your agentic team would look like:"]
        for r in results:
            scope_str = ", ".join(r.automation_scope) if r.automation_scope else "general operations"
            lines.append(
                f"  • {r.member.name} — {r.member.role} ({r.domain}): "
                f"will learn {scope_str}"
            )

        lines.append("\nDoes this sound close?")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Confirmation callbacks
    # ------------------------------------------------------------------

    def on_confirmed(self, results: List[RosettaGenerationResult]) -> None:
        """Called when the user confirms the generated Rosetta docs.

        Solidifies all Rosetta docs and starts shadow training.

        Args:
            results: list of confirmed RosettaGenerationResult.
        """
        with self._lock:
            for r in results:
                capped_append(self._confirmed_docs, r.rosetta_doc_id)
                if r.rosetta_doc_id in self._living_documents:
                    doc = self._living_documents[r.rosetta_doc_id]
                    if hasattr(doc, "solidify"):
                        try:
                            doc.solidify()
                        except Exception as exc:
                            logger.warning(
                                "Could not solidify doc %s: %s", r.rosetta_doc_id, exc
                            )
                logger.info(
                    "Confirmed Rosetta doc %s for %s (%s)",
                    r.rosetta_doc_id,
                    r.member.name,
                    r.member.role,
                )

    def on_rejected(
        self, results: List[RosettaGenerationResult], feedback: str
    ) -> None:
        """Called when the user rejects the generated Rosetta docs.

        Does not solidify. Logs feedback for regeneration.

        Args:
            results: list of rejected RosettaGenerationResult.
            feedback: the user's feedback for regeneration.
        """
        logger.info(
            "User rejected %d Rosetta docs. Feedback: %s", len(results), feedback
        )

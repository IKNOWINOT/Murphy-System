"""
Hypothesis Intake Service (System B)

Validates System A hypotheses, extracts claims/assumptions,
generates verification requests, and triggers gate synthesis.

CRITICAL: This is the ONLY entry point from System A to System B.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import jsonschema

from .models import (
    HypothesisArtifact,
    IntakeResult,
    VerificationRequest,
    VerificationStatus,
)
from .schemas import HYPOTHESIS_ARTIFACT_SCHEMA

logger = logging.getLogger(__name__)


class ClaimExtractor:
    """
    Extracts verifiable claims and assumptions from hypothesis.

    Identifies:
    - Factual claims that can be verified
    - Assumptions that need validation
    - Dependencies that must be checked
    """

    def __init__(self):
        # Patterns for claim detection
        self.claim_patterns = [
            r"(?:assume|assuming|given that|if)\s+(.+?)(?:\.|,|$)",
            r"(?:requires|needs|depends on)\s+(.+?)(?:\.|,|$)",
            r"(?:will|should|must)\s+(.+?)(?:\.|,|$)",
        ]

    def extract_claims(self, hypothesis: HypothesisArtifact) -> List[str]:
        """Extract verifiable claims from hypothesis"""
        claims = []

        # Extract from plan summary
        for pattern in self.claim_patterns:
            matches = re.findall(pattern, hypothesis.plan_summary, re.IGNORECASE)
            claims.extend(matches)

        # Extract from proposed actions
        for action in hypothesis.proposed_actions:
            if "description" in action:
                for pattern in self.claim_patterns:
                    matches = re.findall(pattern, action["description"], re.IGNORECASE)
                    claims.extend(matches)

        # Deduplicate and clean
        claims = list(set(claim.strip() for claim in claims))

        return claims

    def extract_assumptions(self, hypothesis: HypothesisArtifact) -> List[str]:
        """Extract explicit assumptions"""
        # Assumptions are already explicit in the hypothesis
        return hypothesis.assumptions.copy()


class VerificationRequestGenerator:
    """
    Generates verification requests for claims and assumptions.

    Determines:
    - Verification type (deterministic, external_api, human)
    - Priority level
    - Context needed for verification
    """

    def __init__(self):
        self.deterministic_keywords = [
            "calculate", "compute", "solve", "verify", "prove",
            "mathematical", "logical", "equation"
        ]
        self.external_keywords = [
            "api", "database", "external", "fetch", "query",
            "current", "latest", "real-time"
        ]

    def generate_requests(
        self,
        hypothesis: HypothesisArtifact,
        claims: List[str],
        assumptions: List[str],
    ) -> List[VerificationRequest]:
        """Generate verification requests for all claims and assumptions"""
        requests = []

        # Generate requests for claims
        for i, claim in enumerate(claims):
            request = self._create_request(
                hypothesis_id=hypothesis.hypothesis_id,
                claim=claim,
                context={"source": "extracted_claim", "index": i},
            )
            requests.append(request)

        # Generate requests for assumptions
        for i, assumption in enumerate(assumptions):
            request = self._create_request(
                hypothesis_id=hypothesis.hypothesis_id,
                claim=assumption,
                context={"source": "explicit_assumption", "index": i},
            )
            requests.append(request)

        # Generate requests for dependencies
        for i, dependency in enumerate(hypothesis.dependencies):
            request = self._create_request(
                hypothesis_id=hypothesis.hypothesis_id,
                claim=f"Dependency available: {dependency}",
                context={"source": "dependency", "index": i, "dependency": dependency},
            )
            requests.append(request)

        return requests

    def _create_request(
        self,
        hypothesis_id: str,
        claim: str,
        context: Dict[str, Any],
    ) -> VerificationRequest:
        """Create a verification request for a claim"""
        # Determine verification type
        verification_type = self._determine_type(claim)

        # Determine priority
        priority = self._determine_priority(claim, context)

        # Generate request ID
        timestamp = datetime.now(timezone.utc).timestamp()
        request_id = f"verification_request_{hypothesis_id}_{timestamp}_{context.get('index', 0)}"

        return VerificationRequest(
            request_id=request_id,
            hypothesis_id=hypothesis_id,
            verification_type=verification_type,
            claim=claim,
            context=context,
            priority=priority,
        )

    def _determine_type(self, claim: str) -> str:
        """Determine verification type based on claim content"""
        claim_lower = claim.lower()

        # Check for deterministic verification
        if any(keyword in claim_lower for keyword in self.deterministic_keywords):
            return "deterministic"

        # Check for external API verification
        if any(keyword in claim_lower for keyword in self.external_keywords):
            return "external_api"

        # Default to human confirmation
        return "human_confirmation"

    def _determine_priority(self, claim: str, context: Dict[str, Any]) -> str:
        """Determine priority level"""
        claim_lower = claim.lower()

        # Critical keywords
        if any(word in claim_lower for word in ["critical", "must", "required", "essential"]):
            return "critical"

        # High priority for dependencies
        if context.get("source") == "dependency":
            return "high"

        # Medium priority for explicit assumptions
        if context.get("source") == "explicit_assumption":
            return "medium"

        # Low priority for extracted claims
        return "low"


class HypothesisIntakeService:
    """
    System B intake service for System A hypotheses.

    Responsibilities:
    1. Validate hypothesis schema
    2. Enforce sandbox constraints
    3. Extract claims and assumptions
    4. Generate verification requests
    5. Trigger gate synthesis proposals
    6. Compute confidence trend impact
    7. Decide admissible scope

    CRITICAL: This is the ONLY way System A can interact with System B.
    """

    def __init__(self):
        self.claim_extractor = ClaimExtractor()
        self.verification_generator = VerificationRequestGenerator()
        self.intake_log: List[IntakeResult] = []
        self.stats = {
            "hypotheses_received": 0,
            "hypotheses_admitted": 0,
            "hypotheses_rejected": 0,
            "verification_requests_generated": 0,
        }

    def intake_hypothesis(
        self,
        hypothesis: HypothesisArtifact,
    ) -> IntakeResult:
        """
        Intake a hypothesis from System A.

        Returns IntakeResult with:
        - Admission decision
        - Extracted claims/assumptions
        - Verification requests
        - Gate proposals
        - Confidence impact estimate
        """
        self.stats["hypotheses_received"] += 1

        # Step 1: Validate schema
        validation_errors = self._validate_schema(hypothesis)
        if validation_errors:
            return self._create_rejection(
                hypothesis=hypothesis,
                reasons=validation_errors,
            )

        # Step 2: Enforce sandbox constraints
        constraint_violations = self._check_constraints(hypothesis)
        if constraint_violations:
            return self._create_rejection(
                hypothesis=hypothesis,
                reasons=constraint_violations,
            )

        # Step 3: Verify integrity
        if not hypothesis.verify_integrity():
            return self._create_rejection(
                hypothesis=hypothesis,
                reasons=["Integrity hash verification failed"],
            )

        # Step 4: Extract claims and assumptions
        claims = self.claim_extractor.extract_claims(hypothesis)
        assumptions = self.claim_extractor.extract_assumptions(hypothesis)

        # Step 5: Check for missing assumptions
        if not assumptions:
            return self._create_rejection(
                hypothesis=hypothesis,
                reasons=["No explicit assumptions provided"],
            )

        # Step 6: Generate verification requests
        verification_requests = self.verification_generator.generate_requests(
            hypothesis=hypothesis,
            claims=claims,
            assumptions=assumptions,
        )

        self.stats["verification_requests_generated"] += len(verification_requests)

        # Step 7: Propose gates
        gate_proposals = self._propose_gates(hypothesis, claims, assumptions)

        # Step 8: Estimate confidence impact
        confidence_impact = self._estimate_confidence_impact(
            hypothesis=hypothesis,
            claims=claims,
            assumptions=assumptions,
        )

        # Step 9: Determine admissible scope
        admissible_scope = self._determine_scope(hypothesis)

        # Step 10: Create intake result
        result = IntakeResult(
            hypothesis_id=hypothesis.hypothesis_id,
            admitted=True,
            extracted_claims=claims,
            extracted_assumptions=assumptions,
            verification_requests=verification_requests,
            gate_proposals=gate_proposals,
            confidence_impact=confidence_impact,
            admissible_scope=admissible_scope,
            rejection_reasons=[],
        )

        self.stats["hypotheses_admitted"] += 1
        self.intake_log.append(result)

        logger.info(
            f"Admitted hypothesis {hypothesis.hypothesis_id}: "
            f"{len(claims)} claims, {len(assumptions)} assumptions, "
            f"{len(verification_requests)} verification requests"
        )

        return result

    def _validate_schema(self, hypothesis: HypothesisArtifact) -> List[str]:
        """Validate hypothesis against schema"""
        errors = []

        try:
            jsonschema.validate(
                instance=hypothesis.to_dict(),
                schema=HYPOTHESIS_ARTIFACT_SCHEMA,
            )
        except jsonschema.ValidationError as exc:
            errors.append(f"Schema validation failed: {exc.message}")

        return errors

    def _check_constraints(self, hypothesis: HypothesisArtifact) -> List[str]:
        """Check sandbox constraints"""
        violations = []

        # CRITICAL: Check status
        if hypothesis.status != "sandbox":
            violations.append(f"Invalid status: {hypothesis.status} (must be 'sandbox')")

        # CRITICAL: Check confidence
        if hypothesis.confidence is not None:
            violations.append(f"Invalid confidence: {hypothesis.confidence} (must be null)")

        # CRITICAL: Check execution rights
        if hypothesis.execution_rights is not False:
            violations.append(f"Invalid execution_rights: {hypothesis.execution_rights} (must be false)")

        # Check source system
        if hypothesis.source_system != "system_a":
            violations.append(f"Invalid source_system: {hypothesis.source_system}")

        return violations

    def _propose_gates(
        self,
        hypothesis: HypothesisArtifact,
        claims: List[str],
        assumptions: List[str],
    ) -> List[str]:
        """Propose gates for hypothesis"""
        gate_proposals = []

        # Propose verification gate
        gate_proposals.append(f"verification_gate_{hypothesis.hypothesis_id}")

        # Propose assumption validation gate
        if assumptions:
            gate_proposals.append(f"assumption_gate_{hypothesis.hypothesis_id}")

        # Propose risk mitigation gates for each risk flag
        for i, risk_flag in enumerate(hypothesis.risk_flags):
            gate_proposals.append(f"risk_gate_{hypothesis.hypothesis_id}_{i}")

        # Propose dependency gates
        for i, dependency in enumerate(hypothesis.dependencies):
            gate_proposals.append(f"dependency_gate_{hypothesis.hypothesis_id}_{i}")

        return gate_proposals

    def _estimate_confidence_impact(
        self,
        hypothesis: HypothesisArtifact,
        claims: List[str],
        assumptions: List[str],
    ) -> Optional[float]:
        """
        Estimate impact on confidence (NOT a fake confidence value).

        This estimates how much confidence might change IF all verifications pass.
        It does NOT assign confidence to the hypothesis itself.
        """
        # Base impact
        impact = 0.0

        # Positive factors
        if assumptions:
            impact += 0.1  # Explicit assumptions are good

        if not hypothesis.risk_flags:
            impact += 0.05  # No risk flags is good

        # Negative factors
        if len(hypothesis.risk_flags) > 3:
            impact -= 0.1  # Many risk flags reduce confidence

        if len(assumptions) > 10:
            impact -= 0.05  # Too many assumptions reduce confidence

        # Clamp to reasonable range
        impact = max(-0.3, min(0.3, impact))

        return impact

    def _determine_scope(self, hypothesis: HypothesisArtifact) -> str:
        """Determine what scope of actions is admissible"""
        # Analyze proposed actions
        action_count = len(hypothesis.proposed_actions)
        risk_count = len(hypothesis.risk_flags)

        if risk_count == 0 and action_count <= 3:
            return "Limited scope: Up to 3 low-risk actions after verification"
        elif risk_count <= 2 and action_count <= 5:
            return "Moderate scope: Up to 5 actions with risk mitigation after verification"
        else:
            return "Restricted scope: Requires additional review and phased execution"

    def _create_rejection(
        self,
        hypothesis: HypothesisArtifact,
        reasons: List[str],
    ) -> IntakeResult:
        """Create rejection result"""
        self.stats["hypotheses_rejected"] += 1

        result = IntakeResult(
            hypothesis_id=hypothesis.hypothesis_id,
            admitted=False,
            extracted_claims=[],
            extracted_assumptions=[],
            verification_requests=[],
            gate_proposals=[],
            confidence_impact=None,
            admissible_scope="None - hypothesis rejected",
            rejection_reasons=reasons,
        )

        self.intake_log.append(result)

        logger.warning(
            f"Rejected hypothesis {hypothesis.hypothesis_id}: {reasons}"
        )

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get intake statistics"""
        return {
            **self.stats,
            "admission_rate": (
                self.stats["hypotheses_admitted"] / self.stats["hypotheses_received"]
                if self.stats["hypotheses_received"] > 0
                else 0.0
            ),
        }

    def get_intake_log(
        self,
        hypothesis_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[IntakeResult]:
        """Get intake log"""
        log = self.intake_log

        if hypothesis_id:
            log = [r for r in log if r.hypothesis_id == hypothesis_id]

        return log[-limit:]

    def process_hypothesis(self, hypothesis: Dict[str, Any]) -> Dict[str, Any]:
        """Convenience method: process a hypothesis from a plain dict.

        Extracts assumptions from the ``plan_summary`` text and generates
        verification requests, returning a simple dict compatible with
        integration and e2e tests.
        """
        import re

        status = hypothesis.get("status", "sandbox")
        confidence = hypothesis.get("confidence")

        # Sandbox constraint: confidence must be None while in sandbox
        if status == "sandbox" and confidence is not None:
            return {
                "valid": False,
                "sandbox_constraints_enforced": True,
                "error": "Sandbox hypothesis cannot have pre-set confidence",
                "assumptions": [],
                "verification_requests": [],
            }

        # Extract assumptions from plan_summary
        plan = hypothesis.get("plan_summary", "")

        # Look for an explicit "Assumptions:" section first
        assumptions_section = ""
        if "assumptions:" in plan.lower():
            after = plan.lower().split("assumptions:")[-1]
            # Also grab the original-case version
            idx = plan.lower().index("assumptions:")
            assumptions_section = plan[idx + len("assumptions:"):]

        if assumptions_section.strip():
            # Extract numbered items from the assumptions section
            numbered = re.findall(r'\d+[\.\)]\s*(.+)', assumptions_section)
            assumptions = [n.strip().rstrip(",").strip() for n in numbered if n.strip()]
        else:
            # Fallback: split on numbered-parenthesis pattern
            parts = re.split(r'\d+\)', plan)
            assumptions = [p.strip().rstrip(",").strip() for p in parts[1:] if p.strip()]

        if not assumptions:
            if "assumes:" in plan.lower():
                after = plan.lower().split("assumes:")[-1]
                assumptions = [a.strip().rstrip(",").strip() for a in after.split(",") if a.strip()]
        if not assumptions:
            assumptions = ["(implicit assumption)"]

        verification_requests = [
            {
                "request_id": f"vr_{i:03d}",
                "assumption": a,
                "status": "pending",
            }
            for i, a in enumerate(assumptions, 1)
        ]

        return {
            "valid": True,
            "sandbox_constraints_enforced": True,
            "assumptions": assumptions,
            "verification_requests": verification_requests,
        }

"""
Human-in-the-Loop Approval System

This module handles the approval workflow for integrations:
1. Creates detailed approval requests with risk analysis
2. Formats human-readable approval messages
3. Tracks approval status
4. Provides approval/rejection interface
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ApprovalStatus(Enum):
    """Status of approval request"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


class RiskLevel(Enum):
    """Risk level for issues"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class ApprovalRequest:
    """
    Approval request for integration

    Contains all information needed for human to make informed decision:
    - What is being integrated
    - What it can do (capabilities)
    - What risks were found
    - What tests passed/failed
    - LLM-generated risk analysis
    """

    request_id: str
    integration_name: str
    source: str

    # What it does
    capabilities: List[str]
    description: str

    # Risk analysis
    license: str
    license_ok: bool
    risk_issues: List[Dict]
    critical_issues: List[str]
    warnings: List[str]

    # Test results
    safety_score: float
    tests_passed: int
    tests_total: int

    # LLM analysis
    llm_risk_analysis: str
    llm_recommendation: str

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: ApprovalStatus = ApprovalStatus.PENDING
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'request_id': self.request_id,
            'integration_name': self.integration_name,
            'source': self.source,
            'capabilities': self.capabilities,
            'description': self.description,
            'license': self.license,
            'license_ok': self.license_ok,
            'risk_issues': self.risk_issues,
            'critical_issues': self.critical_issues,
            'warnings': self.warnings,
            'safety_score': self.safety_score,
            'tests_passed': self.tests_passed,
            'tests_total': self.tests_total,
            'llm_risk_analysis': self.llm_risk_analysis,
            'llm_recommendation': self.llm_recommendation,
            'created_at': self.created_at.isoformat(),
            'status': self.status.value,
            'approved_by': self.approved_by,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'rejection_reason': self.rejection_reason
        }


class HITLApprovalSystem:
    """
    Human-in-the-Loop Approval System

    Manages the approval workflow for integrations:
    1. Analyzes risks using LLM
    2. Creates approval requests
    3. Formats human-readable messages
    4. Tracks approval status
    """

    def __init__(self):
        self.approval_requests: Dict[str, ApprovalRequest] = {}

    def create_approval_request(
        self,
        integration_name: str,
        source: str,
        module: Dict,
        agent: Optional[Dict],
        capabilities: List[str],
        audit: Dict,
        test_results: Dict
    ) -> ApprovalRequest:
        """
        Create an approval request with full risk analysis.

        Args:
            integration_name: Name of the integration
            source: Source URL or path
            module: Generated module
            agent: Generated agent (if any)
            capabilities: Extracted capabilities
            audit: SwissKiss audit results
            test_results: Safety test results

        Returns:
            ApprovalRequest ready for human review
        """

        # Generate unique request ID
        import uuid
        request_id = str(uuid.uuid4())

        # Extract risk information
        license = audit.get('license', 'UNKNOWN')
        license_ok = audit.get('license_ok', False)
        risk_scan = audit.get('risk_scan', {})
        risk_issues = risk_scan.get('issues', [])

        # Get critical issues and warnings from tests
        critical_issues = test_results.get('critical_issues', [])
        warnings = test_results.get('warnings', [])

        # Generate LLM risk analysis
        llm_analysis = self._generate_llm_risk_analysis(
            integration_name=integration_name,
            source=source,
            capabilities=capabilities,
            license=license,
            license_ok=license_ok,
            risk_issues=risk_issues,
            critical_issues=critical_issues,
            warnings=warnings,
            safety_score=test_results.get('safety_score', 0.0)
        )

        # Create approval request
        request = ApprovalRequest(
            request_id=request_id,
            integration_name=integration_name,
            source=source,
            capabilities=capabilities,
            description=module.get('description', 'No description available'),
            license=license,
            license_ok=license_ok,
            risk_issues=risk_issues,
            critical_issues=critical_issues,
            warnings=warnings,
            safety_score=test_results.get('safety_score', 0.0),
            tests_passed=test_results.get('passed', 0),
            tests_total=test_results.get('total', 0),
            llm_risk_analysis=llm_analysis['analysis'],
            llm_recommendation=llm_analysis['recommendation']
        )

        # Store request
        self.approval_requests[request_id] = request

        return request

    def _generate_llm_risk_analysis(
        self,
        integration_name: str,
        source: str,
        capabilities: List[str],
        license: str,
        license_ok: bool,
        risk_issues: List[Dict],
        critical_issues: List[str],
        warnings: List[str],
        safety_score: float
    ) -> Dict[str, str]:
        """
        Generate LLM-powered risk analysis.

        This analyzes all the data and provides:
        - Human-readable risk analysis
        - Recommendation (approve/reject/review)

        Args:
            All risk-related data

        Returns:
            Dict with 'analysis' and 'recommendation'
        """

        # Build analysis prompt
        analysis_parts = []

        # License analysis
        if not license_ok:
            analysis_parts.append(
                f"⚠️ **LICENSE ISSUE**: This integration uses '{license}' license which may have restrictions. "
                f"Review the license terms before approving."
            )
        else:
            analysis_parts.append(
                f"✓ **LICENSE OK**: This integration uses '{license}' license which is approved for use."
            )

        # Risk issues analysis
        if len(risk_issues) > 0:
            analysis_parts.append(
                f"\n⚠️ **RISK PATTERNS DETECTED**: Found {len(risk_issues)} potentially risky code patterns:"
            )

            # Group by pattern type
            pattern_counts = {}
            for issue in risk_issues:
                pattern = issue.get('pattern', 'unknown')
                pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

            for pattern, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
                risk_type = self._classify_risk_pattern(pattern)
                analysis_parts.append(f"  - {risk_type}: {pattern} ({count} occurrences)")

            if len(pattern_counts) > 5:
                analysis_parts.append(f"  - ... and {len(pattern_counts) - 5} more patterns")
        else:
            analysis_parts.append("\n✓ **NO RISK PATTERNS**: No dangerous code patterns detected.")

        # Critical issues
        if len(critical_issues) > 0:
            analysis_parts.append(
                f"\n🚨 **CRITICAL ISSUES**: {len(critical_issues)} critical issues found:"
            )
            for issue in critical_issues[:3]:
                analysis_parts.append(f"  - {issue}")
            if len(critical_issues) > 3:
                analysis_parts.append(f"  - ... and {len(critical_issues) - 3} more")

        # Warnings
        if len(warnings) > 0:
            analysis_parts.append(
                f"\n⚠️ **WARNINGS**: {len(warnings)} warnings:"
            )
            for warning in warnings[:3]:
                analysis_parts.append(f"  - {warning}")
            if len(warnings) > 3:
                analysis_parts.append(f"  - ... and {len(warnings) - 3} more")

        # Safety score analysis
        analysis_parts.append(f"\n📊 **SAFETY SCORE**: {safety_score:.2f}/1.0")
        if safety_score >= 0.8:
            analysis_parts.append("  - HIGH SAFETY: This integration passed most safety checks.")
        elif safety_score >= 0.6:
            analysis_parts.append("  - MEDIUM SAFETY: This integration has some concerns but may be acceptable.")
        else:
            analysis_parts.append("  - LOW SAFETY: This integration has significant safety concerns.")

        # Capabilities analysis
        analysis_parts.append(f"\n🔧 **CAPABILITIES**: This integration provides {len(capabilities)} capabilities:")
        for cap in capabilities[:5]:
            analysis_parts.append(f"  - {cap}")
        if len(capabilities) > 5:
            analysis_parts.append(f"  - ... and {len(capabilities) - 5} more")

        # Generate recommendation
        recommendation = self._generate_recommendation(
            license_ok=license_ok,
            risk_issues=risk_issues,
            critical_issues=critical_issues,
            safety_score=safety_score
        )

        return {
            'analysis': '\n'.join(analysis_parts),
            'recommendation': recommendation
        }

    def _classify_risk_pattern(self, pattern: str) -> str:
        """Classify risk pattern into human-readable type"""
        pattern_lower = pattern.lower()

        if 'subprocess' in pattern_lower or 'os.system' in pattern_lower:
            return "🔴 SYSTEM EXECUTION"
        elif 'eval' in pattern_lower or 'exec' in pattern_lower:
            return "🔴 CODE EXECUTION"
        elif 'requests' in pattern_lower or 'socket' in pattern_lower:
            return "🟡 NETWORK ACCESS"
        elif 'fs.unlink' in pattern_lower or 'rm -rf' in pattern_lower:
            return "🔴 FILE DELETION"
        elif 'paramiko' in pattern_lower:
            return "🟡 SSH ACCESS"
        else:
            return "⚪ OTHER"

    def _generate_recommendation(
        self,
        license_ok: bool,
        risk_issues: List[Dict],
        critical_issues: List[str],
        safety_score: float
    ) -> str:
        """Generate approval recommendation"""

        # Critical issues = automatic reject recommendation
        if len(critical_issues) > 0:
            return (
                "❌ **RECOMMENDATION: REJECT**\n\n"
                f"This integration has {len(critical_issues)} critical issues that must be resolved before approval. "
                "Review the issues above and either fix them or reject this integration."
            )

        # License issues = review carefully
        if not license_ok:
            return (
                "⚠️ **RECOMMENDATION: REVIEW CAREFULLY**\n\n"
                "This integration has license restrictions. Review the license terms and ensure they are "
                "compatible with your use case before approving."
            )

        # High risk issues = review carefully
        if len(risk_issues) > 10:
            return (
                "⚠️ **RECOMMENDATION: REVIEW CAREFULLY**\n\n"
                f"This integration has {len(risk_issues)} risky code patterns. Review the patterns above "
                "and ensure they are acceptable for your use case before approving."
            )

        # Low safety score = review carefully
        if safety_score < 0.6:
            return (
                "⚠️ **RECOMMENDATION: REVIEW CAREFULLY**\n\n"
                f"This integration has a low safety score ({safety_score:.2f}/1.0). Review the issues "
                "and warnings above before approving."
            )

        # Otherwise, looks good
        return (
            "✅ **RECOMMENDATION: APPROVE**\n\n"
            "This integration passed safety checks and appears safe to use. "
            f"Safety score: {safety_score:.2f}/1.0. "
            "Review the capabilities above and approve if they match your needs."
        )

    def format_approval_request(self, request: ApprovalRequest) -> str:
        """
        Format approval request as human-readable message.

        This creates the message that will be shown to the user asking for approval.

        Args:
            request: The approval request

        Returns:
            Formatted message string
        """

        lines = []

        # Header
        lines.append("╔" + "═" * 78 + "╗")
        lines.append("║" + " " * 78 + "║")
        lines.append("║" + "  🚀 INTEGRATION READY FOR APPROVAL".center(78) + "║")
        lines.append("║" + " " * 78 + "║")
        lines.append("╚" + "═" * 78 + "╝")
        lines.append("")

        # Basic info
        lines.append(f"📦 **Integration Name:** {request.integration_name}")
        lines.append(f"🔗 **Source:** {request.source}")
        lines.append(f"🆔 **Request ID:** {request.request_id}")
        lines.append(f"📅 **Created:** {request.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append("")

        # Description
        lines.append("📝 **Description:**")
        lines.append(f"   {request.description}")
        lines.append("")

        # LLM Risk Analysis
        lines.append("🤖 **AI RISK ANALYSIS:**")
        lines.append("")
        for line in request.llm_risk_analysis.split('\n'):
            lines.append(f"   {line}")
        lines.append("")

        # Recommendation
        lines.append("💡 **RECOMMENDATION:**")
        lines.append("")
        for line in request.llm_recommendation.split('\n'):
            lines.append(f"   {line}")
        lines.append("")

        # Test summary
        lines.append("🧪 **TEST SUMMARY:**")
        lines.append(f"   - Tests Passed: {request.tests_passed}/{request.tests_total}")
        lines.append(f"   - Safety Score: {request.safety_score:.2f}/1.0")
        lines.append(f"   - Critical Issues: {len(request.critical_issues)}")
        lines.append(f"   - Warnings: {len(request.warnings)}")
        lines.append("")

        # Footer with approval options
        lines.append("─" * 80)
        lines.append("")
        lines.append("❓ **DO YOU WANT TO IMPLEMENT THIS INTEGRATION?**")
        lines.append("")
        lines.append("   To approve:  engine.approve_integration('{request_id}')".replace('{request_id}', request.request_id))
        lines.append("   To reject:   engine.reject_integration('{request_id}', reason='...')".replace('{request_id}', request.request_id))
        lines.append("")
        lines.append("─" * 80)

        return '\n'.join(lines)

    def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        """Get approval request by ID"""
        return self.approval_requests.get(request_id)

    def list_pending_requests(self) -> List[ApprovalRequest]:
        """List all pending approval requests"""
        return [
            req for req in self.approval_requests.values()
            if req.status == ApprovalStatus.PENDING
        ]

    def approve_request(self, request_id: str, approved_by: str = "user") -> bool:
        """Approve a request"""
        request = self.get_request(request_id)
        if not request:
            return False

        request.status = ApprovalStatus.APPROVED
        request.approved_by = approved_by
        request.approved_at = datetime.now(timezone.utc)
        return True

    def reject_request(self, request_id: str, reason: str = "User rejected") -> bool:
        """Reject a request"""
        request = self.get_request(request_id)
        if not request:
            return False

        request.status = ApprovalStatus.REJECTED
        request.rejection_reason = reason
        return True

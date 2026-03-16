"""
Unified Integration Engine - Complete system for adding integrations with HITL safety

This is the main orchestrator that:
1. Analyzes repositories using SwissKiss
2. Extracts capabilities
3. Generates modules/agents
4. Tests everything for safety
5. Asks human for approval with detailed risk analysis
6. Only commits if approved
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("integration_engine.unified_engine")

from bots.swisskiss_loader import SwissKissLoader
from src.integrations.integration_framework import IntegrationFramework
from src.module_manager import module_manager

from .agent_generator import AgentGenerator
from .capability_extractor import CapabilityExtractor
from .hitl_approval import ApprovalRequest, ApprovalStatus, HITLApprovalSystem
from .module_generator import ModuleGenerator
from .safety_tester import SafetyTester
from .sandbox_quarantine import SandboxQuarantine


class IntegrationResult:
    """Result of integration process"""

    def __init__(
        self,
        success: bool,
        integration_id: Optional[str] = None,
        module_name: Optional[str] = None,
        agent_name: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
        metadata: Optional[Dict] = None
    ):
        self.success = success
        self.integration_id = integration_id
        self.module_name = module_name
        self.agent_name = agent_name
        self.capabilities = capabilities or []
        self.errors = errors or []
        self.warnings = warnings or []
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        return {
            'success': self.success,
            'integration_id': self.integration_id,
            'module_name': self.module_name,
            'agent_name': self.agent_name,
            'capabilities': self.capabilities,
            'errors': self.errors,
            'warnings': self.warnings,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }


class UnifiedIntegrationEngine:
    """
    Unified Integration Engine - Main orchestrator for all integrations

    This engine coordinates:
    - SwissKiss Loader (repository analysis)
    - Capability Extractor (what can it do?)
    - Module Generator (create Murphy module)
    - Agent Generator (create Murphy agent)
    - Safety Tester (test before committing)
    - HITL Approval (human approval required)

    Workflow:
    1. User: "Add Stripe integration"
    2. Engine: Analyze repository
    3. Engine: Extract capabilities
    4. Engine: Generate module/agent
    5. Engine: Test for safety
    6. Engine: Ask human: "Ready to implement. Issues: [list]. Approve?"
    7. Human: "Yes" or "No"
    8. Engine: If yes, commit and load. If no, rollback.
    """

    def __init__(self):
        self.swisskiss = SwissKissLoader()
        self.capability_extractor = CapabilityExtractor()
        self.module_generator = ModuleGenerator()
        self.agent_generator = AgentGenerator()
        self.safety_tester = SafetyTester()
        self.hitl_approval = HITLApprovalSystem()
        self.sandbox_quarantine = SandboxQuarantine()
        self.integration_framework = IntegrationFramework()

        # Track pending integrations (not yet approved)
        self.pending_integrations: Dict[str, Dict] = {}

        # Track committed integrations (approved and loaded)
        self.committed_integrations: Dict[str, Dict] = {}

    def add_integration(
        self,
        source: str,
        integration_type: str = 'repository',
        category: str = 'general',
        entry_script: Optional[str] = None,
        generate_agent: bool = False,
        auto_approve: bool = False
    ) -> IntegrationResult:
        """
        Add an integration from any source with HITL approval.

        Args:
            source: GitHub URL, local path, or API endpoint
            integration_type: 'repository', 'api', 'hardware'
            category: Category for the integration
            entry_script: Optional entry script path
            generate_agent: Whether to generate an agent (in addition to module)
            auto_approve: Skip HITL approval (dangerous, only for testing)

        Returns:
            IntegrationResult with status and details

        Workflow:
        1. Analyze source (SwissKiss)
        2. Extract capabilities
        3. Generate module/agent
        4. Test for safety
        5. Create HITL approval request
        6. Wait for human approval
        7. If approved: commit and load
        8. If rejected: rollback and cleanup
        """

        logger.info(f"\n{'='*80}")
        logger.info(f"🚀 STARTING INTEGRATION: {source}")
        logger.info(f"{'='*80}\n")

        try:
            # Step 1: Analyze with SwissKiss
            logger.info("📊 Step 1: Analyzing repository with SwissKiss...")
            swisskiss_result = self.swisskiss.manual_load(
                url=source,
                category=category,
                entry_script=entry_script
            )

            module_yaml = swisskiss_result['module']
            audit = swisskiss_result['audit']
            module_name = module_yaml['module_name']

            logger.info(f"✓ Analysis complete: {module_name}")
            logger.info(f"  - License: {audit['license']} ({'✓ OK' if audit['license_ok'] else '✗ NOT OK'})")
            logger.info(f"  - Languages: {', '.join(audit['languages'].keys())}")
            logger.info(f"  - Risk issues: {audit['risk_scan']['count']}")

            # Step 2: Extract capabilities
            logger.info("\n🔍 Step 2: Extracting capabilities...")
            capabilities = self.capability_extractor.extract_from_swisskiss(
                module_yaml=module_yaml,
                audit=audit
            )

            logger.info(f"✓ Extracted {len(capabilities)} capabilities:")
            for cap in capabilities[:5]:  # Show first 5
                logger.info(f"  - {cap}")
            if len(capabilities) > 5:
                logger.info(f"  ... and {len(capabilities) - 5} more")

            # Step 3: Generate module
            logger.info("\n🏗️  Step 3: Generating Murphy module...")
            module = self.module_generator.generate_from_swisskiss(
                module_yaml=module_yaml,
                audit=audit,
                capabilities=capabilities
            )

            logger.info(f"✓ Module generated: {module['name']}")
            logger.info(f"  - Entry point: {module['entry_point']}")
            logger.info(f"  - Commands: {len(module['commands'])}")

            # Step 4: Generate agent (if requested)
            agent = None
            if generate_agent:
                logger.info("\n🤖 Step 4: Generating Murphy agent...")
                agent = self.agent_generator.generate_from_swisskiss(
                    module_yaml=module_yaml,
                    audit=audit,
                    capabilities=capabilities
                )
                logger.info(f"✓ Agent generated: {agent['name']}")
            else:
                logger.info("\n⏭️  Step 4: Skipping agent generation (not requested)")

            # Step 5: Safety testing
            logger.info("\n🛡️  Step 5: Running safety tests...")
            test_results = self.safety_tester.test_integration(
                module=module,
                agent=agent,
                audit=audit
            )

            logger.info("✓ Safety tests complete:")
            logger.info(f"  - Tests passed: {test_results['passed']}/{test_results['total']}")
            logger.info(f"  - Critical issues: {len(test_results['critical_issues'])}")
            logger.info(f"  - Warnings: {len(test_results['warnings'])}")
            logger.info(f"  - Safety score: {test_results['safety_score']:.2f}/1.0")

            # Step 5.5: Sandbox Quarantine — runs between SafetyTester and HITL Approval
            logger.info("\n🔒 Step 5.5: Running Sandbox Quarantine Protocol...")
            repo_path = swisskiss_result.get('repo_path', '')
            quarantine_report = self.sandbox_quarantine.quarantine(
                repo_path=repo_path,
                audit=audit,
                module=module,
            )

            logger.info(f"  - Quarantine score: {quarantine_report.quarantine_score:.2f}/1.0")
            logger.info(f"  - Threat findings: {len(quarantine_report.threat_findings)}")
            logger.info(f"  - Auto-remediations: {len(quarantine_report.auto_remediations)}")
            logger.info(f"  - License conflicts: {len(quarantine_report.license_conflicts)}")

            if not quarantine_report.admitted:
                logger.info(f"\n🚫 QUARANTINE REJECTED: {quarantine_report.rejection_reason}")
                return IntegrationResult(
                    success=False,
                    module_name=module_name,
                    errors=[quarantine_report.rejection_reason or "Quarantine rejected"],
                    metadata={
                        'status': 'quarantine_rejected',
                        'quarantine_score': quarantine_report.quarantine_score,
                        'rejection_reason': quarantine_report.rejection_reason,
                        'quarantine_report': quarantine_report.to_dict(),
                    }
                )

            if quarantine_report.quarantine_score < 0.7:
                logger.info("  ⚠️  Quarantine score below 0.70 — HITL will receive highlighted warnings")
            else:
                logger.info("✓ Quarantine passed — proceeding to HITL")

            # Step 6: Create HITL approval request
            logger.info("\n👤 Step 6: Creating human approval request...")

            approval_request = self.hitl_approval.create_approval_request(
                integration_name=module_name,
                source=source,
                module=module,
                agent=agent,
                capabilities=capabilities,
                audit=audit,
                test_results=test_results
            )

            # Store as pending
            self.pending_integrations[approval_request.request_id] = {
                'request': approval_request,
                'module': module,
                'agent': agent,
                'capabilities': capabilities,
                'audit': audit,
                'test_results': test_results,
                'quarantine_report': quarantine_report,
            }

            logger.info(f"✓ Approval request created: {approval_request.request_id}")

            # Auto-approve if requested (testing only)
            if auto_approve:
                logger.info("\n⚠️  AUTO-APPROVE ENABLED (testing mode)")
                approval_request.status = ApprovalStatus.APPROVED
                approval_request.approved_by = "auto_approve"
                approval_request.approved_at = datetime.now(timezone.utc)
            else:
                # Display approval request to user
                logger.info("\n" + "="*80)
                logger.info(self.hitl_approval.format_approval_request(approval_request))
                logger.info("="*80)

                # Return result with pending status
                return IntegrationResult(
                    success=False,  # Not yet successful (pending approval)
                    integration_id=approval_request.request_id,
                    module_name=module_name,
                    agent_name=agent['name'] if agent else None,
                    capabilities=capabilities,
                    warnings=test_results['warnings'],
                    metadata={
                        'status': 'pending_approval',
                        'approval_request_id': approval_request.request_id,
                        'safety_score': test_results['safety_score'],
                        'critical_issues': test_results['critical_issues'],
                        'quarantine_score': quarantine_report.quarantine_score,
                        'quarantine_warnings': quarantine_report.quarantine_score < 0.7,
                        'quarantine_report': quarantine_report.to_dict(),
                    }
                )

            # Step 7: If approved, commit and load
            if approval_request.status == ApprovalStatus.APPROVED:
                logger.info("\n✅ Step 7: APPROVED - Committing integration...")

                # Register module with Module Manager
                module_manager.register_module(
                    name=module['name'],
                    module_path=module['module_path'],
                    description=module['description'],
                    capabilities=capabilities
                )

                # Load module
                module_manager.load_module(module['name'])

                # Register agent if generated
                if agent:
                    self._register_swarm_agent(agent)
                    self._register_agent_with_swarm(agent, capabilities)
                    logger.info(f"✓ Agent registered: {agent['name']}")

                # Move to committed integrations
                self.committed_integrations[module_name] = self.pending_integrations.pop(approval_request.request_id)

                logger.info(f"\n{'='*80}")
                logger.info(f"🎉 INTEGRATION COMPLETE: {module_name}")
                logger.info(f"{'='*80}")
                logger.info("✓ Module loaded and ready to use")
                logger.info(f"✓ Available commands: {len(module['commands'])}")
                logger.info(f"✓ Capabilities: {', '.join(capabilities[:3])}...")

                return IntegrationResult(
                    success=True,
                    integration_id=approval_request.request_id,
                    module_name=module_name,
                    agent_name=agent['name'] if agent else None,
                    capabilities=capabilities,
                    warnings=test_results['warnings'],
                    metadata={
                        'status': 'committed',
                        'safety_score': test_results['safety_score'],
                        'approved_by': approval_request.approved_by
                    }
                )

        except Exception as exc:
            logger.info(f"\n❌ ERROR: {str(exc)}")
            import traceback
            traceback.print_exc()

            return IntegrationResult(
                success=False,
                errors=[str(exc)],
                metadata={'status': 'failed'}
            )

    def approve_integration(self, request_id: str, approved_by: str = "user") -> IntegrationResult:
        """
        Approve a pending integration and commit it.

        Args:
            request_id: The approval request ID
            approved_by: Who approved it

        Returns:
            IntegrationResult with final status
        """

        if request_id not in self.pending_integrations:
            return IntegrationResult(
                success=False,
                errors=[f"Integration request not found: {request_id}"]
            )

        pending = self.pending_integrations[request_id]
        approval_request = pending['request']
        module = pending['module']
        agent = pending['agent']
        capabilities = pending['capabilities']
        test_results = pending['test_results']

        logger.info(f"\n{'='*80}")
        logger.info(f"✅ APPROVING INTEGRATION: {module['name']}")
        logger.info(f"{'='*80}\n")

        # Update approval status
        approval_request.status = ApprovalStatus.APPROVED
        approval_request.approved_by = approved_by
        approval_request.approved_at = datetime.now(timezone.utc)

        # Register module with Module Manager
        logger.info("📦 Registering module with Module Manager...")
        module_manager.register_module(
            name=module['name'],
            module_path=module['module_path'],
            description=module['description'],
            capabilities=capabilities
        )

        # Load module
        logger.info("🔄 Loading module...")
        module_manager.load_module(module['name'])

        # Register agent if generated
        if agent:
            self._register_swarm_agent(agent)
            logger.info(f"🤖 Registering agent: {agent['name']}")
            self._register_agent_with_swarm(agent, capabilities)

        # Move to committed integrations
        self.committed_integrations[module['name']] = self.pending_integrations.pop(request_id)

        logger.info(f"\n{'='*80}")
        logger.info(f"🎉 INTEGRATION COMMITTED: {module['name']}")
        logger.info(f"{'='*80}")
        logger.info("✓ Module loaded and ready to use")
        logger.info(f"✓ Available commands: {len(module['commands'])}")
        logger.info(f"✓ Capabilities: {', '.join(capabilities[:3])}...")

        return IntegrationResult(
            success=True,
            integration_id=request_id,
            module_name=module['name'],
            agent_name=agent['name'] if agent else None,
            capabilities=capabilities,
            warnings=test_results['warnings'],
            metadata={
                'status': 'committed',
                'safety_score': test_results['safety_score'],
                'approved_by': approved_by
            }
        )

    def reject_integration(self, request_id: str, reason: str = "User rejected") -> IntegrationResult:
        """
        Reject a pending integration and clean up.

        Args:
            request_id: The approval request ID
            reason: Why it was rejected

        Returns:
            IntegrationResult with rejection status
        """

        if request_id not in self.pending_integrations:
            return IntegrationResult(
                success=False,
                errors=[f"Integration request not found: {request_id}"]
            )

        pending = self.pending_integrations[request_id]
        approval_request = pending['request']
        module = pending['module']

        logger.info(f"\n{'='*80}")
        logger.info(f"❌ REJECTING INTEGRATION: {module['name']}")
        logger.info(f"{'='*80}\n")
        logger.info(f"Reason: {reason}")

        # Update approval status
        approval_request.status = ApprovalStatus.REJECTED
        approval_request.rejection_reason = reason

        # Clean up (remove generated artefacts for the rejected integration)
        self._cleanup_rejected(module)
        # Clean up (remove generated files, etc.)
        self._cleanup_rejected_integration(module)

        # Remove from pending
        self.pending_integrations.pop(request_id)

        logger.info("✓ Integration rejected and cleaned up")

        return IntegrationResult(
            success=True,
            integration_id=request_id,
            module_name=module['name'],
            metadata={
                'status': 'rejected',
                'reason': reason
            }
        )

    def list_pending_integrations(self) -> List[Dict]:
        """List all pending integrations awaiting approval"""
        return [
            {
                'request_id': req_id,
                'module_name': data['module']['name'],
                'source': data['request'].source,
                'safety_score': data['test_results']['safety_score'],
                'critical_issues': len(data['test_results']['critical_issues']),
                'warnings': len(data['test_results']['warnings']),
                'created_at': data['request'].created_at.isoformat()
            }
            for req_id, data in self.pending_integrations.items()
        ]

    def list_committed_integrations(self) -> List[Dict]:
        """List all committed integrations"""
        return [
            {
                'module_name': name,
                'capabilities': len(data['capabilities']),
                'safety_score': data['test_results']['safety_score'],
                'approved_by': data['request'].approved_by,
                'approved_at': data['request'].approved_at.isoformat() if data['request'].approved_at else None
            }
            for name, data in self.committed_integrations.items()
        ]

    def get_integration_status(self, identifier: str) -> Optional[Dict]:
        """
        Get status of an integration (by request_id or module_name)

        Args:
            identifier: Request ID or module name

        Returns:
            Status dictionary or None if not found
        """

        # Check pending
        if identifier in self.pending_integrations:
            data = self.pending_integrations[identifier]
            return {
                'status': 'pending',
                'request_id': identifier,
                'module_name': data['module']['name'],
                'safety_score': data['test_results']['safety_score'],
                'critical_issues': data['test_results']['critical_issues'],
                'warnings': data['test_results']['warnings']
            }

        # Check committed
        if identifier in self.committed_integrations:
            data = self.committed_integrations[identifier]
            return {
                'status': 'committed',
                'module_name': identifier,
                'capabilities': data['capabilities'],
                'safety_score': data['test_results']['safety_score'],
                'approved_by': data['request'].approved_by
            }

        return None

    # ------------------------------------------------------------------
    # TrueSwarmSystem agent registration
    # ------------------------------------------------------------------

    def _register_swarm_agent(self, agent: Dict[str, Any]) -> None:
        """Register a generated agent with TrueSwarmSystem.

        The swarm system is lazily initialised so that the integration
        engine can operate without it (graceful degradation in
        environments where the swarm is not deployed).
        """
        try:
            from src.true_swarm_system import TrueSwarmSystem

            if getattr(self, '_swarm_system', None) is None:
                self._swarm_system = TrueSwarmSystem()

            # Store agent metadata in the workspace for later phase execution
            self._swarm_system.workspace.write_artifact(
                {
                    'artifact_type': 'agent_registration',
                    'content': agent,
                    'phase': None,
                }
            )
            logger.info(f"✓ Agent '{agent['name']}' registered with TrueSwarmSystem")
        except Exception as exc:
            # Non-fatal: the integration itself still succeeds
            logger.info(f"⚠ TrueSwarmSystem registration skipped: {exc}")

    # ------------------------------------------------------------------
    # Rejected-integration clean-up
    # ------------------------------------------------------------------

    def _cleanup_rejected(self, module: Dict[str, Any]) -> None:
        """Remove artefacts generated for a rejected integration.

        Removes on-disk generated files (commands, agents) that were
        staged during the approval workflow.  The clean-up is
        best-effort; failures are logged but do not propagate.
        """
        import shutil

        generated_path = module.get('generated_path')
        if generated_path and os.path.isdir(generated_path):
            try:
                shutil.rmtree(generated_path)
                logger.info(f"✓ Cleaned up generated artefacts at {generated_path}")
            except OSError as exc:
                logger.info(f"⚠ Could not remove {generated_path}: {exc}")
        else:
            logger.info("✓ No generated artefacts to clean up")
    # TrueSwarmSystem integration helpers
    # ------------------------------------------------------------------

    def _register_agent_with_swarm(self, agent: Dict[str, Any], capabilities: List[str]) -> None:
        """Register a generated agent with the TrueSwarmSystem.

        Creates an ``AgentInstance`` in the workspace so the swarm
        orchestrator can include the new agent in future phase executions.
        Falls back gracefully when the swarm system is unavailable.
        """
        try:
            from src.true_swarm_system import (
                AgentInstance,
                ProfessionAtom,
                TrueSwarmSystem,
            )
            from src.true_swarm_system import (
                Phase as SwarmPhase,
            )

            swarm = TrueSwarmSystem()

            # Map agent capabilities to the closest ProfessionAtom.
            profession = ProfessionAtom.SOFTWARE_ENGINEER  # sensible default
            cap_lower = ' '.join(capabilities).lower()
            if 'security' in cap_lower or 'auth' in cap_lower:
                profession = ProfessionAtom.SECURITY_ANALYST
            elif 'data' in cap_lower or 'analytics' in cap_lower:
                profession = ProfessionAtom.DATA_SCIENTIST
            elif 'compliance' in cap_lower or 'regulation' in cap_lower:
                profession = ProfessionAtom.COMPLIANCE_OFFICER
            elif 'risk' in cap_lower:
                profession = ProfessionAtom.RISK_MANAGER

            instance = AgentInstance(
                profession=profession,
                specialization=agent.get('name', 'integration_agent'),
                context={
                    'source': 'unified_integration_engine',
                    'capabilities': capabilities,
                    'agent_name': agent.get('name'),
                },
            )

            # Record in workspace so future phases can discover it.
            swarm.workspace.metadata[f"integration_agent_{instance.id}"] = {
                'instance_id': instance.id,
                'profession': profession.value,
                'capabilities': capabilities,
                'registered_at': datetime.now(timezone.utc).isoformat(),
            }

            logger.info(f"   ✓ Agent registered with TrueSwarmSystem as {profession.value}")
        except Exception as exc:
            logger.info(f"   ⚠ Could not register agent with TrueSwarmSystem: {exc}")

    def _cleanup_rejected_integration(self, module: Dict[str, Any]) -> None:
        """Remove generated files for a rejected integration.

        Deletes the module file and any associated agent file that were
        generated during the integration analysis step.
        """
        import shutil

        paths_to_clean = []
        module_path = module.get('module_path', '')
        if module_path:
            paths_to_clean.append(module_path)

        agent_path = module.get('agent_path', '')
        if agent_path:
            paths_to_clean.append(agent_path)

        for p in paths_to_clean:
            target = Path(p)
            try:
                if target.is_file():
                    target.unlink()
                    logger.info(f"   ✓ Removed generated file: {target.name}")
                elif target.is_dir():
                    shutil.rmtree(target)
                    logger.info(f"   ✓ Removed generated directory: {target.name}")
            except OSError as exc:
                logger.info(f"   ⚠ Could not remove {target}: {exc}")


# Convenience function
def create_engine() -> UnifiedIntegrationEngine:
    """Create a new UnifiedIntegrationEngine instance"""
    return UnifiedIntegrationEngine()

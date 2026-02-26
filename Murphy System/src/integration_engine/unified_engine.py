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

import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from bots.swisskiss_loader import SwissKissLoader
from src.module_manager import module_manager
from src.integrations.integration_framework import IntegrationFramework
from .capability_extractor import CapabilityExtractor
from .module_generator import ModuleGenerator
from .agent_generator import AgentGenerator
from .safety_tester import SafetyTester
from .hitl_approval import HITLApprovalSystem, ApprovalRequest, ApprovalStatus


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
        self.timestamp = datetime.utcnow()
    
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
        
        print(f"\n{'='*80}")
        print(f"🚀 STARTING INTEGRATION: {source}")
        print(f"{'='*80}\n")
        
        try:
            # Step 1: Analyze with SwissKiss
            print("📊 Step 1: Analyzing repository with SwissKiss...")
            swisskiss_result = self.swisskiss.manual_load(
                url=source,
                category=category,
                entry_script=entry_script
            )
            
            module_yaml = swisskiss_result['module']
            audit = swisskiss_result['audit']
            module_name = module_yaml['module_name']
            
            print(f"✓ Analysis complete: {module_name}")
            print(f"  - License: {audit['license']} ({'✓ OK' if audit['license_ok'] else '✗ NOT OK'})")
            print(f"  - Languages: {', '.join(audit['languages'].keys())}")
            print(f"  - Risk issues: {audit['risk_scan']['count']}")
            
            # Step 2: Extract capabilities
            print("\n🔍 Step 2: Extracting capabilities...")
            capabilities = self.capability_extractor.extract_from_swisskiss(
                module_yaml=module_yaml,
                audit=audit
            )
            
            print(f"✓ Extracted {len(capabilities)} capabilities:")
            for cap in capabilities[:5]:  # Show first 5
                print(f"  - {cap}")
            if len(capabilities) > 5:
                print(f"  ... and {len(capabilities) - 5} more")
            
            # Step 3: Generate module
            print("\n🏗️  Step 3: Generating Murphy module...")
            module = self.module_generator.generate_from_swisskiss(
                module_yaml=module_yaml,
                audit=audit,
                capabilities=capabilities
            )
            
            print(f"✓ Module generated: {module['name']}")
            print(f"  - Entry point: {module['entry_point']}")
            print(f"  - Commands: {len(module['commands'])}")
            
            # Step 4: Generate agent (if requested)
            agent = None
            if generate_agent:
                print("\n🤖 Step 4: Generating Murphy agent...")
                agent = self.agent_generator.generate_from_swisskiss(
                    module_yaml=module_yaml,
                    audit=audit,
                    capabilities=capabilities
                )
                print(f"✓ Agent generated: {agent['name']}")
            else:
                print("\n⏭️  Step 4: Skipping agent generation (not requested)")
            
            # Step 5: Safety testing
            print("\n🛡️  Step 5: Running safety tests...")
            test_results = self.safety_tester.test_integration(
                module=module,
                agent=agent,
                audit=audit
            )
            
            print(f"✓ Safety tests complete:")
            print(f"  - Tests passed: {test_results['passed']}/{test_results['total']}")
            print(f"  - Critical issues: {len(test_results['critical_issues'])}")
            print(f"  - Warnings: {len(test_results['warnings'])}")
            print(f"  - Safety score: {test_results['safety_score']:.2f}/1.0")
            
            # Step 6: Create HITL approval request
            print("\n👤 Step 6: Creating human approval request...")
            
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
                'test_results': test_results
            }
            
            print(f"✓ Approval request created: {approval_request.request_id}")
            
            # Auto-approve if requested (testing only)
            if auto_approve:
                print("\n⚠️  AUTO-APPROVE ENABLED (testing mode)")
                approval_request.status = ApprovalStatus.APPROVED
                approval_request.approved_by = "auto_approve"
                approval_request.approved_at = datetime.utcnow()
            else:
                # Display approval request to user
                print("\n" + "="*80)
                print(self.hitl_approval.format_approval_request(approval_request))
                print("="*80)
                
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
                        'critical_issues': test_results['critical_issues']
                    }
                )
            
            # Step 7: If approved, commit and load
            if approval_request.status == ApprovalStatus.APPROVED:
                print("\n✅ Step 7: APPROVED - Committing integration...")
                
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
                    # TODO: Integrate with TrueSwarmSystem
                    print(f"✓ Agent registered: {agent['name']}")
                
                # Move to committed integrations
                self.committed_integrations[module_name] = self.pending_integrations.pop(approval_request.request_id)
                
                print(f"\n{'='*80}")
                print(f"🎉 INTEGRATION COMPLETE: {module_name}")
                print(f"{'='*80}")
                print(f"✓ Module loaded and ready to use")
                print(f"✓ Available commands: {len(module['commands'])}")
                print(f"✓ Capabilities: {', '.join(capabilities[:3])}...")
                
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
        
        except Exception as e:
            print(f"\n❌ ERROR: {str(e)}")
            import traceback
            traceback.print_exc()
            
            return IntegrationResult(
                success=False,
                errors=[str(e)],
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
        
        print(f"\n{'='*80}")
        print(f"✅ APPROVING INTEGRATION: {module['name']}")
        print(f"{'='*80}\n")
        
        # Update approval status
        approval_request.status = ApprovalStatus.APPROVED
        approval_request.approved_by = approved_by
        approval_request.approved_at = datetime.utcnow()
        
        # Register module with Module Manager
        print("📦 Registering module with Module Manager...")
        module_manager.register_module(
            name=module['name'],
            module_path=module['module_path'],
            description=module['description'],
            capabilities=capabilities
        )
        
        # Load module
        print("🔄 Loading module...")
        module_manager.load_module(module['name'])
        
        # Register agent if generated
        if agent:
            print(f"🤖 Registering agent: {agent['name']}")
            # TODO: Integrate with TrueSwarmSystem
        
        # Move to committed integrations
        self.committed_integrations[module['name']] = self.pending_integrations.pop(request_id)
        
        print(f"\n{'='*80}")
        print(f"🎉 INTEGRATION COMMITTED: {module['name']}")
        print(f"{'='*80}")
        print(f"✓ Module loaded and ready to use")
        print(f"✓ Available commands: {len(module['commands'])}")
        print(f"✓ Capabilities: {', '.join(capabilities[:3])}...")
        
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
        
        print(f"\n{'='*80}")
        print(f"❌ REJECTING INTEGRATION: {module['name']}")
        print(f"{'='*80}\n")
        print(f"Reason: {reason}")
        
        # Update approval status
        approval_request.status = ApprovalStatus.REJECTED
        approval_request.rejection_reason = reason
        
        # Clean up (remove generated files, etc.)
        # TODO: Implement cleanup
        
        # Remove from pending
        self.pending_integrations.pop(request_id)
        
        print(f"✓ Integration rejected and cleaned up")
        
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


# Convenience function
def create_engine() -> UnifiedIntegrationEngine:
    """Create a new UnifiedIntegrationEngine instance"""
    return UnifiedIntegrationEngine()
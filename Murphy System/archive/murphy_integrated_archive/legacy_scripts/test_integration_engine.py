"""
Test Integration Engine - Example usage

This script demonstrates how to use the Unified Integration Engine
to add integrations with human-in-the-loop approval.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.integration_engine.unified_engine import UnifiedIntegrationEngine


def test_add_integration():
    """Test adding an integration with HITL approval"""
    
    print("\n" + "="*80)
    print("TESTING UNIFIED INTEGRATION ENGINE")
    print("="*80 + "\n")
    
    # Create engine
    engine = UnifiedIntegrationEngine()
    
    # Example 1: Add a repository (will require approval)
    print("\n📦 Example 1: Adding a GitHub repository")
    print("-" * 80)
    
    # This would be a real GitHub URL in production
    # For testing, we'll use a local path or mock
    result = engine.add_integration(
        source="https://github.com/stripe/stripe-python",
        integration_type='repository',
        category='payment-processing',
        generate_agent=False,
        auto_approve=False  # Requires human approval
    )
    
    print("\n📊 Result:")
    print(f"  Success: {result.success}")
    print(f"  Status: {result.metadata.get('status')}")
    print(f"  Module: {result.module_name}")
    print(f"  Capabilities: {len(result.capabilities)}")
    
    if not result.success and result.metadata.get('status') == 'pending_approval':
        print("\n⏳ Integration is pending approval.")
        print(f"   Request ID: {result.integration_id}")
        print("\n   To approve:")
        print(f"   >>> engine.approve_integration('{result.integration_id}')")
        print("\n   To reject:")
        print(f"   >>> engine.reject_integration('{result.integration_id}', reason='...')")
    
    # Example 2: List pending integrations
    print("\n\n📋 Example 2: List pending integrations")
    print("-" * 80)
    
    pending = engine.list_pending_integrations()
    print(f"\nFound {len(pending)} pending integrations:")
    for p in pending:
        print(f"  - {p['module_name']} (Safety: {p['safety_score']:.2f}, Issues: {p['critical_issues']})")
    
    # Example 3: Approve integration (if any pending)
    if pending:
        print("\n\n✅ Example 3: Approving first pending integration")
        print("-" * 80)
        
        request_id = pending[0]['request_id']
        approval_result = engine.approve_integration(request_id, approved_by="test_user")
        
        print(f"\n✓ Approval result:")
        print(f"  Success: {approval_result.success}")
        print(f"  Module: {approval_result.module_name}")
        print(f"  Status: {approval_result.metadata.get('status')}")
    
    # Example 4: List committed integrations
    print("\n\n📦 Example 4: List committed integrations")
    print("-" * 80)
    
    committed = engine.list_committed_integrations()
    print(f"\nFound {len(committed)} committed integrations:")
    for c in committed:
        print(f"  - {c['module_name']} (Capabilities: {c['capabilities']}, Safety: {c['safety_score']:.2f})")
    
    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80 + "\n")


def test_auto_approve():
    """Test with auto-approve (for testing only)"""
    
    print("\n" + "="*80)
    print("TESTING AUTO-APPROVE MODE (Testing Only)")
    print("="*80 + "\n")
    
    engine = UnifiedIntegrationEngine()
    
    # Add with auto-approve
    result = engine.add_integration(
        source="https://github.com/example/test-repo",
        integration_type='repository',
        category='testing',
        generate_agent=False,
        auto_approve=True  # Skip HITL approval
    )
    
    print("\n📊 Result:")
    print(f"  Success: {result.success}")
    print(f"  Module: {result.module_name}")
    print(f"  Status: {result.metadata.get('status')}")
    
    if result.success:
        print("\n✓ Integration committed automatically (testing mode)")
    
    print("\n" + "="*80)
    print("AUTO-APPROVE TEST COMPLETE")
    print("="*80 + "\n")


if __name__ == "__main__":
    print("\n🚀 UNIFIED INTEGRATION ENGINE - TEST SUITE\n")
    
    # Test 1: Normal flow with HITL approval
    test_add_integration()
    
    # Test 2: Auto-approve mode (testing)
    # Uncomment to test:
    # test_auto_approve()
    
    print("\n✅ All tests complete!\n")
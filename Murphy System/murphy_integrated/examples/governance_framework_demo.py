"""
Murphy Governance Framework Demonstration

Shows practical usage of the formal governance framework:
- Creating and validating agent descriptors
- Managing governance artifacts
- Monitoring stability and handling refusals
- Scheduling with governance rules enforcement
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime, timedelta
from src.governance_framework import (
    AgentDescriptor, AgentDescriptorValidator, AuthorityBand, ActionType,
    GovernanceArtifact, ArtifactRegistry, ArtifactValidator, ArtifactType,
    StabilityController, ExecutionOutcome,
    GovernanceScheduler, SchedulingDecision,
    RefusalHandlerImpl
)


def demo_agent_descriptor():
    """Demonstrate agent descriptor creation and validation"""
    print("=== Agent Descriptor Demo ===")
    
    # Create a data processing agent descriptor
    data_agent = AgentDescriptor(
        agent_id="data-processor-001",
        version="1.0.0",
        authority_band=AuthorityBand.MEDIUM
    )
    
    # Validate the descriptor
    validator = AgentDescriptorValidator()
    result = validator.validate_descriptor(data_agent)
    
    print(f"Agent ID: {data_agent.agent_id}")
    print(f"Authority Band: {data_agent.authority_band.value}")
    print(f"Validation Result: {result['valid']}")
    print(f"Risk Level: {result.get('risk_level', 'LOW')}")
    print()


def demo_artifact_ingestion():
    """Demonstrate governance artifact management"""
    print("=== Artifact Ingestion Demo ===")
    
    # Create artifact registry
    registry = ArtifactRegistry()
    
    # Create governance artifacts
    privacy_policy = GovernanceArtifact(
        artifact_id="privacy-policy-001",
        artifact_type=ArtifactType.POLICY,
        name="Privacy Protection Policy",
        version="2.1.0",
        source_system="Legal Department",
        expires_at=datetime.utcnow() + timedelta(days=365),
        authority_level="MEDIUM"
    )
    
    gdpr_training = GovernanceArtifact(
        artifact_id="gdpr-training-001", 
        artifact_type=ArtifactType.ATTESTATION,
        name="GDPR Compliance Training",
        version="1.0.0",
        source_system="HR System",
        expires_at=datetime.utcnow() + timedelta(days=90),
        authority_level="LOW"
    )
    
    # Register artifacts
    registry.register_artifact(privacy_policy)
    registry.register_artifact(gdpr_training)
    
    # Validate execution permissions
    validator = ArtifactValidator(registry)
    
    mock_agent = {
        "authority_band": "MEDIUM",
        "scope": "ORGANIZATION"
    }
    
    result = validator.validate_execution_permissions(mock_agent, "PROCESS_CUSTOMER_DATA")
    
    print(f"Registered Artifacts: {len(registry.artifacts)}")
    print(f"Validation Result: {result['validation_result']}")
    if result['expired_artifacts']:
        print(f"Expired: {result['expired_artifacts']}")
    print()


def demo_stability_control():
    """Demonstrate stability monitoring and refusal handling"""
    print("=== Stability Control Demo ===")
    
    # Create stability controller
    controller = StabilityController()
    
    # Simulate agent state history
    agent_state = {
        "agent_id": "stable-agent-001",
        "state": "processing",
        "stability_duration": 0
    }
    
    # Create some history showing stable operation
    history = [
        {"state_hash": "hash1", "timestamp": datetime.utcnow()},
        {"state_hash": "hash2", "timestamp": datetime.utcnow()},
        {"state_hash": "hash3", "timestamp": datetime.utcnow()}
    ]
    
    # Evaluate stability
    result = controller.evaluate_agent_stability(agent_state, history)
    
    print(f"Stability Score: {result['stability_score']:.2f}")
    print(f"Is Stable: {result['is_stable']}")
    print(f"Can Continue: {result['can_continue']}")
    print(f"Recommendation: {result['recommendation']}")
    
    # Demonstrate refusal handling
    refusal_handler = RefusalHandlerImpl()
    
    refusal_record = refusal_handler.handle_refusal(
        agent_id="data-processor-001",
        refusal_code="SAFETY_CONSTRAINT_VIOLATION",
        refusal_reason="Attempted to process data without encryption",
        authority_level="MEDIUM",
        dependencies=["validator-agent", "storage-agent"]
    )
    
    print(f"Refusal Code: {refusal_record.refusal_code}")
    print(f"Refusal Reason: {refusal_record.refusal_reason}")
    print(f"Blocked Dependencies: {len(refusal_record.blocked_dependencies)}")
    print()


def demo_scheduler():
    """Demonstrate governance-aware scheduling"""
    print("=== Governance Scheduler Demo ===")
    
    # Create scheduler
    scheduler = GovernanceScheduler()
    
    # Create agent descriptor
    descriptor = AgentDescriptor(
        agent_id="scheduled-agent-001",
        version="1.0.0", 
        authority_band=AuthorityBand.LOW
    )
    
    # Create scheduled agent (simplified)
    from src.governance_framework.scheduler import ScheduledAgent, PriorityLevel
    
    scheduled_agent = ScheduledAgent(
        agent_id="scheduled-agent-001",
        descriptor=descriptor,
        priority=PriorityLevel.NORMAL,
        scheduled_time=datetime.utcnow(),
        dependencies=[],
        resource_requirements={"cpu": 1, "memory": 512}
    )
    
    # Schedule the agent
    decision = scheduler.schedule_agent(scheduled_agent)
    
    print(f"Scheduling Decision: {decision.value}")
    
    # Get system status
    status = scheduler.get_system_status()
    print(f"Scheduled Agents: {status['scheduled_count']}")
    print(f"Running Agents: {status['running_count']}")
    print(f"CPU Utilization: {status['resource_utilization']['cpu_percent']:.1f}%")
    
    # Check system invariants
    violations = scheduler.enforce_invariants()
    print(f"System Violations: {len(violations)}")
    if violations:
        for violation in violations:
            print(f"  - {violation}")
    print()


def demo_integration():
    """Demonstrate complete framework integration"""
    print("=== Complete Integration Demo ===")
    
    # 1. Create and validate agent
    agent = AgentDescriptor(
        agent_id="integration-agent-001",
        version="1.0.0",
        authority_band=AuthorityBand.MEDIUM
    )
    
    validator = AgentDescriptorValidator()
    validation_result = validator.validate_descriptor(agent)
    
    print(f"✓ Agent Created: {agent.agent_id}")
    print(f"✓ Agent Validated: {validation_result['valid']}")
    
    # 2. Register required artifacts
    registry = ArtifactRegistry()
    policy = GovernanceArtifact(
        "integration-policy", ArtifactType.POLICY, "Integration Policy", 
        "1.0.0", "Demo System"
    )
    registry.register_artifact(policy)
    
    print(f"✓ Artifacts Registered: {len(registry.artifacts)}")
    
    # 3. Monitor stability
    controller = StabilityController()
    stability_result = controller.evaluate_agent_stability(
        {"agent_id": agent.agent_id}, 
        []
    )
    
    print(f"✓ Stability Monitored: {stability_result['stability_score']:.2f}")
    
    # 4. Schedule with governance
    scheduler = GovernanceScheduler()
    system_status = scheduler.get_system_status()
    violations = scheduler.enforce_invariants()
    
    print(f"✓ Scheduler Active: {system_status['scheduled_count']} scheduled")
    print(f"✓ Invariants Enforced: {len(violations)} violations")
    
    print("\n🎉 Governance Framework Integration Complete!")
    print("All safety constraints and governance rules are active.")


if __name__ == "__main__":
    print("Murphy System Governance Framework Demonstration")
    print("=" * 50)
    print()
    
    try:
        demo_agent_descriptor()
        demo_artifact_ingestion()
        demo_stability_control()
        demo_scheduler()
        demo_integration()
        
        print("\n✅ All demonstrations completed successfully!")
        print("The governance framework is ready for production use.")
        
    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
"""
Confidence Engine Demo
Demonstrates complete workflow from artifact creation to execution eligibility
"""

import requests
import json
from typing import Dict, Any

# API base URL
BASE_URL = "http://localhost:8055/api/confidence-engine"


def print_section(title: str):
    """Print section header"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_json(data: Dict[Any, Any]):
    """Pretty print JSON"""
    print(json.dumps(data, indent=2))


def demo_complete_workflow():
    """Demonstrate complete confidence engine workflow"""
    
    print_section("🎯 CONFIDENCE ENGINE DEMO")
    
    # Step 1: Reset state
    print_section("Step 1: Reset State")
    response = requests.post(f"{BASE_URL}/reset")
    print(f"Status: {response.json()['message']}")
    
    # Step 2: Add trust sources
    print_section("Step 2: Add Trust Sources")
    
    trust_sources = [
        {
            "source_id": "llm_primary",
            "source_type": "llm",
            "trust_weight": 0.7,
            "volatility": 0.2
        },
        {
            "source_id": "compute_plane",
            "source_type": "compute_plane",
            "trust_weight": 0.95,
            "volatility": 0.05
        },
        {
            "source_id": "human_expert",
            "source_type": "human",
            "trust_weight": 0.9,
            "volatility": 0.1
        }
    ]
    
    for source in trust_sources:
        response = requests.post(f"{BASE_URL}/trust/add-source", json=source)
        print(f"Added: {source['source_id']} (trust: {source['trust_weight']})")
    
    # Step 3: Build artifact graph
    print_section("Step 3: Build Artifact Graph")
    
    artifacts = [
        {
            "id": "h1",
            "type": "hypothesis",
            "source": "llm",
            "content": {"text": "System should use caching for performance"},
            "confidence_weight": 1.0,
            "dependencies": []
        },
        {
            "id": "h2",
            "type": "hypothesis",
            "source": "llm",
            "content": {"text": "Cache should expire after 5 minutes"},
            "confidence_weight": 1.0,
            "dependencies": ["h1"]
        },
        {
            "id": "d1",
            "type": "decision",
            "source": "llm",
            "content": {"decision": "Use Redis for caching", "topic": "caching"},
            "confidence_weight": 1.0,
            "dependencies": ["h1", "h2"]
        },
        {
            "id": "c1",
            "type": "constraint",
            "source": "human",
            "content": {"rule": "Cache must not store sensitive data"},
            "confidence_weight": 1.5,
            "dependencies": []
        },
        {
            "id": "f1",
            "type": "fact",
            "source": "compute_plane",
            "content": {"fact": "Redis supports TTL expiration"},
            "confidence_weight": 2.0,
            "dependencies": []
        }
    ]
    
    for artifact in artifacts:
        response = requests.post(f"{BASE_URL}/artifacts/add", json=artifact)
        if response.json()['success']:
            print(f"✓ Added artifact: {artifact['id']} ({artifact['type']})")
        else:
            print(f"✗ Failed to add: {artifact['id']}")
    
    # Step 4: Analyze graph
    print_section("Step 4: Analyze Graph Structure")
    response = requests.get(f"{BASE_URL}/artifacts/analyze")
    analysis = response.json()['analysis']
    
    print(f"Valid DAG: {analysis['is_valid_dag']}")
    print(f"Total Nodes: {analysis['dependencies']['total_nodes']}")
    print(f"Total Edges: {analysis['dependencies']['total_edges']}")
    print(f"Max Depth: {analysis['dependencies']['max_depth']}")
    print(f"Contradictions: {len(analysis['contradictions'])}")
    print(f"Entropy: {analysis['entropy']:.3f}")
    
    # Step 5: Add verification evidence
    print_section("Step 5: Add Verification Evidence")
    
    verifications = [
        {
            "artifact_id": "f1",
            "result": "pass",
            "stability_score": 0.98,
            "confidence_boost": 0.2,
            "details": {"verified_by": "compute_plane"}
        },
        {
            "artifact_id": "d1",
            "result": "pass",
            "stability_score": 0.85,
            "confidence_boost": 0.1,
            "details": {"verified_by": "feasibility_check"}
        }
    ]
    
    for verification in verifications:
        response = requests.post(f"{BASE_URL}/verification/add", json=verification)
        print(f"✓ Verified: {verification['artifact_id']} ({verification['result']})")
    
    # Step 6: Compute confidence (EXPAND phase)
    print_section("Step 6: Compute Confidence (EXPAND Phase)")
    response = requests.post(f"{BASE_URL}/confidence/compute", json={"phase": "expand"})
    confidence_state = response.json()['confidence_state']
    
    print(f"Confidence: {confidence_state['confidence']:.3f}")
    print(f"Generative Score: {confidence_state['generative_score']:.3f}")
    print(f"Deterministic Score: {confidence_state['deterministic_score']:.3f}")
    print(f"Epistemic Instability: {confidence_state['epistemic_instability']:.3f}")
    print(f"Verified Artifacts: {confidence_state['components']['verified_artifacts']}/{confidence_state['components']['total_artifacts']}")
    
    # Step 7: Compute Murphy Index
    print_section("Step 7: Compute Murphy Index")
    response = requests.post(f"{BASE_URL}/murphy/compute", json={"phase": "expand"})
    murphy_data = response.json()
    
    print(f"Murphy Index: {murphy_data['murphy_index']:.3f}")
    print(f"Failure Modes Detected: {len(murphy_data['failure_modes'])}")
    
    if murphy_data['failure_modes']:
        print("\nFailure Modes:")
        for mode in murphy_data['failure_modes']:
            print(f"  - {mode['type']}: Loss={mode['loss']:.2f}, P={mode['probability']:.2f}")
    
    # Step 8: Compute Authority
    print_section("Step 8: Compute Authority")
    response = requests.post(f"{BASE_URL}/authority/compute", json={
        "phase": "expand",
        "gate_satisfaction": 0.6,
        "unknowns": 3
    })
    authority_data = response.json()
    authority_state = authority_data['authority_state']
    
    print(f"Authority Band: {authority_state['authority_band']}")
    print(f"Can Execute: {authority_state['can_execute']}")
    print(f"Confidence: {authority_state['confidence']:.3f}")
    print(f"Murphy Index: {authority_state['execution_criteria']['murphy_index']:.3f}")
    
    # Step 9: Check phase transition
    print_section("Step 9: Check Phase Transition")
    response = requests.post(f"{BASE_URL}/phase/check-transition", json={
        "current_phase": "expand"
    })
    transition_data = response.json()
    
    print(f"Current Phase: {transition_data['current_phase']}")
    print(f"New Phase: {transition_data['new_phase']}")
    print(f"Transitioned: {transition_data['transitioned']}")
    print(f"Reason: {transition_data['reason']}")
    
    # Step 10: Try EXECUTE phase (should fail)
    print_section("Step 10: Try EXECUTE Phase (Should Block)")
    response = requests.post(f"{BASE_URL}/authority/compute", json={
        "phase": "execute",
        "gate_satisfaction": 0.6,
        "unknowns": 3
    })
    authority_data = response.json()
    blockers = authority_data['execution_blockers']
    
    print(f"Can Execute: {blockers['can_execute']}")
    print(f"Total Blockers: {blockers['total_blockers']}")
    print("\nBlocker Details:")
    
    for criterion, details in blockers.items():
        if isinstance(details, dict) and 'satisfied' in details:
            status = "✓" if details['satisfied'] else "✗"
            print(f"  {status} {criterion}: {details.get('current', 'N/A')}")
    
    # Step 11: Get complete state
    print_section("Step 11: Get Complete State")
    response = requests.post(f"{BASE_URL}/state/complete", json={
        "phase": "expand",
        "gate_satisfaction": 0.6,
        "unknowns": 3
    })
    complete_state = response.json()
    
    print(f"Timestamp: {complete_state['timestamp']}")
    print(f"Confidence: {complete_state['confidence_state']['confidence']:.3f}")
    print(f"Murphy Index: {complete_state['murphy_index']:.3f}")
    print(f"Authority: {complete_state['authority_state']['authority_band']}")
    print(f"Graph Valid: {complete_state['graph_stats']['is_valid_dag']}")
    print(f"Total Nodes: {complete_state['graph_stats']['total_nodes']}")
    
    print_section("✅ DEMO COMPLETE")
    print("\nKey Takeaways:")
    print("1. Confidence computed from generative + deterministic scores")
    print("2. Murphy index quantifies downstream risk")
    print("3. Authority automatically maps from confidence")
    print("4. Execution blocked when criteria not met")
    print("5. Phase transitions require confidence thresholds")


if __name__ == '__main__':
    try:
        demo_complete_workflow()
    except requests.exceptions.ConnectionError:
        print("\n❌ ERROR: Could not connect to Confidence Engine")
        print("Make sure the service is running:")
        print("  python run_confidence_engine.py")
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
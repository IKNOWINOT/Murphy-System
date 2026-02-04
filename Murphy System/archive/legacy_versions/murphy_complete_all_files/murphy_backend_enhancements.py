"""
Murphy System Backend Enhancements
Adds WebSocket infrastructure, agent tracking, state management, and interactive components
"""

import random
import uuid
from datetime import datetime
from typing import Dict, List, Optional

# Global state storage
agents = {}  # Dictionary of Agent objects
states = {}  # Dictionary of State objects
components = {}  # Dictionary of Component objects
gates = {}  # Dictionary of Gate objects
artifacts = {}  # Dictionary of Artifact objects
connections = []  # List of agent connections

# ============================================
# AGENT CLASS
# ============================================

class Agent:
    """Autonomous entity that executes tasks within a domain"""
    
    def __init__(self, id: str, name: str, type: str, domain: str):
        self.id = id
        self.name = name
        self.type = type
        self.domain = domain
        self.status = "idle"  # idle, active, error, paused
        self.current_task = None
        self.progress = 0  # 0-100
        self.confidence = 0.0  # 0.00-1.00
        self.recent_ops = []  # List of recent operations
        self.config = {}
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'domain': self.domain,
            'status': self.status,
            'current_task': self.current_task,
            'progress': self.progress,
            'confidence': self.confidence,
            'recent_ops': self.recent_ops,
            'config': self.config
        }
    
    def execute_task(self, task: str) -> dict:
        """Execute a task and return results"""
        self.current_task = task
        self.status = "active"
        self.progress = 0
        self.confidence = 0.0
        
        # Simulate task execution
        self.progress = 100
        self.confidence = 0.7 + (random.random() * 0.2)  # 0.7-0.9
        
        result = {
            'task': task,
            'confidence': self.confidence,
            'completed': True
        }
        
        self.recent_ops.append(f"Executed: {task}")
        self.status = "idle"
        
        return result
    
    def override_task(self, new_task: str) -> None:
        """Manually override current task"""
        self.current_task = new_task
        self.recent_ops.append(f"Manual override: {new_task}")
    
    def update_progress(self, progress: int) -> None:
        """Update task progress"""
        self.progress = max(0, min(100, progress))
    
    def set_status(self, status: str) -> None:
        """Set agent status"""
        self.status = status


# ============================================
# STATE CLASS
# ============================================

class State:
    """Snapshot condition of system components"""
    
    def __init__(self, id: str, type: str, label: str):
        self.id = id
        self.parent_id = None
        self.type = type  # document, gate, artifact, swarm, system
        self.label = label
        self.description = ""
        self.confidence = 0.0  # 0.00-1.00
        self.timestamp = datetime.now()
        self.children = []  # List of child state IDs
        self.metadata = {}  # Additional state information
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'parent_id': self.parent_id,
            'type': self.type,
            'label': self.label,
            'description': self.description,
            'confidence': self.confidence,
            'timestamp': self.timestamp.isoformat(),
            'children': self.children,
            'metadata': self.metadata
        }
    
    def evolve(self) -> List['State']:
        """Evolve this state into child states"""
        child_states = []
        
        # Generate child states based on state type
        if self.type == "document":
            child_states = self._evolve_document()
        elif self.type == "gate":
            child_states = self._evolve_gate()
        elif self.type == "artifact":
            child_states = self._evolve_artifact()
        elif self.type == "swarm":
            child_states = self._evolve_swarm()
        elif self.type == "system":
            child_states = self._evolve_system()
        else:
            child_states = self._evolve_generic()
        
        # Set parent references
        for child in child_states:
            child.parent_id = self.id
        
        self.children = [child.id for child in child_states]
        
        return child_states
    
    def _evolve_document(self) -> List['State']:
        """Evolve document state into child states"""
        children = [
            State(f"{self.id}-content", "document", "Content Structure"),
            State(f"{self.id}-style", "document", "Style Guidelines"),
            State(f"{self.id}-compliance", "gate", "Compliance Check")
        ]
        
        for child in children:
            child.description = f"Evolved from {self.label}"
            child.confidence = 0.7 + (random.random() * 0.2)  # 0.7-0.9
        
        return children
    
    def _evolve_gate(self) -> List['State']:
        """Evolve gate state into child states"""
        children = [
            State(f"{self.id}-validation", "artifact", "Validation Report"),
            State(f"{self.id}-correction", "document", "Corrections Needed")
        ]
        
        for child in children:
            child.description = f"Gate validation from {self.label}"
            child.confidence = 0.8 + (random.random() * 0.1)  # 0.8-0.9
        
        return children
    
    def _evolve_artifact(self) -> List['State']:
        """Evolve artifact state into child states"""
        children = [
            State(f"{self.id}-review", "gate", "Quality Review"),
            State(f"{self.id}-approval", "gate", "Approval Gate")
        ]
        
        for child in children:
            child.description = f"Review of {self.label}"
            child.confidence = 0.85 + (random.random() * 0.1)  # 0.85-0.95
        
        return children
    
    def _evolve_swarm(self) -> List['State']:
        """Evolve swarm state into child states"""
        children = [
            State(f"{self.id}-result", "artifact", "Swarm Results"),
            State(f"{self.id}-synthesis", "artifact", "Synthesized Output")
        ]
        
        for child in children:
            child.description = f"Swarm output from {self.label}"
            child.confidence = 0.75 + (random.random() * 0.15)  # 0.75-0.9
        
        return children
    
    def _evolve_system(self) -> List['State']:
        """Evolve system state into child states"""
        children = [
            State(f"{self.id}-stage1", "system", "Stage 1"),
            State(f"{self.id}-stage2", "system", "Stage 2"),
            State(f"{self.id}-validation", "gate", "System Validation")
        ]
        
        for child in children:
            child.description = f"System stage from {self.label}"
            child.confidence = 0.7 + (random.random() * 0.2)  # 0.7-0.9
        
        return children
    
    def _evolve_generic(self) -> List['State']:
        """Evolve generic state into child states"""
        children = [
            State(f"{self.id}-child1", self.type, f"{self.label} - Child 1"),
            State(f"{self.id}-child2", self.type, f"{self.label} - Child 2")
        ]
        
        for child in children:
            child.description = f"Evolved from {self.label}"
            child.confidence = 0.7 + (random.random() * 0.2)  # 0.7-0.9
        
        return children
    
    def regenerate(self) -> 'State':
        """Regenerate state with new confidence"""
        new_state = State(self.id, self.type, self.label)
        new_state.description = f"Regenerated {self.description}"
        new_state.confidence = 0.7 + (random.random() * 0.2)  # 0.7-0.9
        new_state.metadata = self.metadata.copy()
        new_state.parent_id = self.parent_id
        new_state.children = self.children.copy()
        
        return new_state


# ============================================
# COMPONENT CLASS
# ============================================

class SystemComponent:
    """Modular building block of the system"""
    
    def __init__(self, id: str, name: str, type: str):
        self.id = id
        self.name = name
        self.type = type  # router, engine, builder, generator
        self.status = "inactive"  # inactive, active, error
        self.health = 100  # 0-100
        self.recent_ops = []
        self.config = {}
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'status': self.status,
            'health': self.health,
            'recent_ops': self.recent_ops,
            'config': self.config
        }
    
    def update_health(self, new_health: int) -> None:
        """Update component health"""
        self.health = max(0, min(100, new_health))
        self.recent_ops.append(f"Health updated to {self.health}")
    
    def set_status(self, status: str) -> None:
        """Set component status"""
        self.status = status


# ============================================
# GATE CLASS
# ============================================

class Gate:
    """Validation checkpoint for outputs"""
    
    def __init__(self, id: str, name: str, type: str, criteria: dict):
        self.id = id
        self.name = name
        self.type = type  # regulatory, security, business, quality
        self.criteria = criteria
        self.status = "pending"  # pending, pass, fail
        self.results = {}
        self.history = []
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type,
            'criteria': self.criteria,
            'status': self.status,
            'results': self.results,
            'history': self.history
        }
    
    def validate(self, data: dict) -> dict:
        """Validate data against gate criteria"""
        # Simulate validation
        passed = random.random() > 0.1  # 90% pass rate
        score = 0.8 + (random.random() * 0.15) if passed else random.random() * 0.5
        
        result = {
            'passed': passed,
            'score': score,
            'criteria_checked': list(self.criteria.keys()),
            'details': 'Validation completed successfully' if passed else 'Validation failed - criteria not met'
        }
        
        self.results = result
        self.status = 'pass' if passed else 'fail'
        self.history.append({
            'timestamp': datetime.now().isoformat(),
            'result': result
        })
        
        return result


# ============================================
# HELPER FUNCTIONS
# ============================================

def create_agent(name: str, type: str, domain: str) -> Agent:
    """Create a new agent"""
    agent_id = f"agent-{uuid.uuid4().hex[:8]}"
    agent = Agent(agent_id, name, type, domain)
    agents[agent_id] = agent
    return agent

def create_state(type: str, label: str, parent_id: Optional[str] = None) -> State:
    """Create a new state"""
    state_id = f"state-{uuid.uuid4().hex[:8]}"
    state = State(state_id, type, label)
    state.parent_id = parent_id
    states[state_id] = state
    return state

def create_component(name: str, type: str) -> SystemComponent:
    """Create a new component"""
    component_id = f"component-{uuid.uuid4().hex[:8]}"
    component = SystemComponent(component_id, name, type)
    components[component_id] = component
    return component

def create_gate(name: str, type: str, criteria: dict) -> Gate:
    """Create a new gate"""
    gate_id = f"gate-{uuid.uuid4().hex[:8]}"
    gate = Gate(gate_id, name, type, criteria)
    gates[gate_id] = gate
    return gate

def get_active_agents() -> List[dict]:
    """Get list of active agents"""
    return [agent.to_dict() for agent in agents.values() if agent.status == "active"]

def get_all_agents() -> List[dict]:
    """Get all agents"""
    return [agent.to_dict() for agent in agents.values()]

def get_all_states() -> List[dict]:
    """Get all states"""
    return [state.to_dict() for state in states.values()]

def get_all_components() -> List[dict]:
    """Get all components"""
    return [component.to_dict() for component in components.values()]

def get_all_gates() -> List[dict]:
    """Get all gates"""
    return [gate.to_dict() for gate in gates.values()]

def get_agent(agent_id: str) -> Optional[Agent]:
    """Get agent by ID"""
    return agents.get(agent_id)

def get_state(state_id: str) -> Optional[State]:
    """Get state by ID"""
    return states.get(state_id)

def get_component(component_id: str) -> Optional[SystemComponent]:
    """Get component by ID"""
    return components.get(component_id)

def get_gate(gate_id: str) -> Optional[Gate]:
    """Get gate by ID"""
    return gates.get(gate_id)

def create_child_states(state: State) -> List[State]:
    """Create child states from parent state"""
    children = state.evolve()
    
    for child in children:
        states[child.id] = child
    
    return children

def regenerate_with_llm(state: State) -> State:
    """Regenerate state using LLM (simulated)"""
    return state.regenerate()

def create_connection(agent1_id: str, agent2_id: str) -> None:
    """Create a connection between two agents"""
    connection = {
        'source': agent1_id,
        'target': agent2_id
    }
    
    # Check if connection already exists
    if not any(
        c['source'] == agent1_id and c['target'] == agent2_id
        for c in connections
    ):
        connections.append(connection)


# ============================================
# INITIALIZATION HELPERS
# ============================================

def initialize_demo_system():
    """Initialize demo system with sample agents, states, components"""
    
    # Create sample agents
    create_agent("Sales Agent", "Sales", "Business")
    create_agent("Engineering Agent", "Engineering", "Engineering")
    create_agent("Financial Agent", "Financial", "Financial")
    create_agent("Legal Agent", "Legal", "Legal")
    create_agent("Operations Agent", "Operations", "Operations")
    
    # Create sample components
    create_component("LLM Router", "router")
    create_component("Domain Engine", "engine")
    create_component("Gate Builder", "builder")
    create_component("Swarm Generator", "generator")
    
    # Create root state
    root_state = create_state("document", "Root System State")
    
    # Create sample gates
    create_gate("Regulatory Gate", "regulatory", {"gdpr": True, "privacy": True})
    create_gate("Security Gate", "security", {"encryption": True, "auth": True})
    
    # Create agent connections
    agent_list = list(agents.keys())
    for i in range(len(agent_list)):
        for j in range(i + 1, min(i + 3, len(agent_list))):
            create_connection(agent_list[i], agent_list[j])
    
    return {
        'agents': len(agents),
        'components': len(components),
        'states': len(states),
        'gates': len(gates),
        'connections': len(connections),
        'root_state_id': root_state.id
    }
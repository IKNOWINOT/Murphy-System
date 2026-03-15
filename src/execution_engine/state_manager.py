"""
State Manager - Track and manage system state
"""

import hashlib
import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StateType(Enum):
    """Types of system state"""
    SYSTEM = "system"
    WORKFLOW = "workflow"
    TASK = "task"
    USER = "user"
    SESSION = "session"
    CONFIGURATION = "configuration"


class StateTransition:
    """State transition record"""

    def __init__(
        self,
        from_state: str,
        to_state: str,
        transition_id: Optional[str] = None,
        reason: str = "",
        metadata: Optional[Dict] = None
    ):
        self.transition_id = transition_id or str(uuid.uuid4())
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict:
        """Convert transition to dictionary"""
        return {
            'transition_id': self.transition_id,
            'from_state': self.from_state,
            'to_state': self.to_state,
            'reason': self.reason,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat()
        }


class SystemState:
    """System state"""

    def __init__(
        self,
        state_id: Optional[str] = None,
        state_type: StateType = StateType.SYSTEM,
        state_name: str = "default",
        variables: Optional[Dict] = None,
        version: int = 1
    ):
        self.state_id = state_id or str(uuid.uuid4())
        self.state_type = state_type
        self.state_name = state_name
        self.variables = variables or {}
        self.version = version
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.transitions: List[StateTransition] = []
        self._lock = threading.Lock()

    def get_variable(self, name: str, default: Any = None) -> Any:
        """Get a variable value"""
        with self._lock:
            return self.variables.get(name, default)

    def set_variable(self, name: str, value: Any) -> None:
        """Set a variable value"""
        with self._lock:
            self.variables[name] = value
            self.updated_at = datetime.now(timezone.utc)

    def get_variables(self) -> Dict:
        """Get all variables"""
        with self._lock:
            return self.variables.copy()

    def set_variables(self, variables: Dict) -> None:
        """Set multiple variables"""
        with self._lock:
            self.variables.update(variables)
            self.updated_at = datetime.now(timezone.utc)

    def add_transition(self, transition: StateTransition) -> None:
        """Add a state transition"""
        with self._lock:
            self.transitions.append(transition)
            self.version += 1
            self.updated_at = datetime.now(timezone.utc)

    def get_transitions(self, limit: int = 100) -> List[Dict]:
        """Get state transitions"""
        with self._lock:
            recent_transitions = self.transitions[-limit:]
            return [t.to_dict() for t in recent_transitions]

    def to_dict(self) -> Dict:
        """Convert state to dictionary"""
        return {
            'state_id': self.state_id,
            'state_type': self.state_type.value,
            'state_name': self.state_name,
            'variables': self.variables,
            'version': self.version,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'transition_count': len(self.transitions)
        }

    def to_json(self) -> str:
        """Convert state to JSON"""
        return json.dumps(self.to_dict())

    def get_hash(self) -> str:
        """Get state hash for integrity checking"""
        state_str = self.to_json()
        return hashlib.sha256(state_str.encode()).hexdigest()


class StateManager:
    """Manage system state and transitions"""

    def __init__(self):
        self.states: Dict[str, SystemState] = {}
        self._lock = threading.Lock()

    def create_state(
        self,
        state_type: StateType = StateType.SYSTEM,
        state_name: str = "default",
        variables: Optional[Dict] = None
    ) -> SystemState:
        """Create a new state"""
        state = SystemState(
            state_type=state_type,
            state_name=state_name,
            variables=variables
        )

        with self._lock:
            self.states[state.state_id] = state

        logger.info(f"State created: {state.state_id} ({state_type.value})")
        return state

    def get_state(self, state_id: str) -> Optional[SystemState]:
        """Get a state by ID"""
        return self.states.get(state_id)

    def get_state_by_name(self, state_name: str) -> Optional[SystemState]:
        """Get a state by name"""
        with self._lock:
            for state in self.states.values():
                if state.state_name == state_name:
                    return state
            return None

    def get_states_by_type(self, state_type: StateType) -> List[SystemState]:
        """Get all states of a type"""
        with self._lock:
            return [s for s in self.states.values() if s.state_type == state_type]

    def get_all_states(self) -> List[Dict]:
        """Get all states"""
        with self._lock:
            return [state.to_dict() for state in self.states.values()]

    def update_state(self, state_id: str, variables: Dict) -> bool:
        """Update state variables"""
        state = self.get_state(state_id)
        if state:
            state.set_variables(variables)
            return True
        return False

    def transition_state(
        self,
        state_id: str,
        to_state_name: str,
        reason: str = "",
        metadata: Optional[Dict] = None
    ) -> bool:
        """Transition a state to a new state"""
        state = self.get_state(state_id)
        if not state:
            return False

        # Create transition record
        transition = StateTransition(
            from_state=state.state_name,
            to_state=to_state_name,
            reason=reason,
            metadata=metadata
        )

        # Update state name and add transition
        state.state_name = to_state_name
        state.add_transition(transition)

        logger.info(f"State transitioned: {state_id} from {transition.from_state} to {transition.to_state}")

        return True

    def delete_state(self, state_id: str) -> bool:
        """Delete a state"""
        with self._lock:
            if state_id in self.states:
                del self.states[state_id]
                logger.info(f"State deleted: {state_id}")
                return True
            return False

    def persist_state(self, state_id: str, file_path: str) -> bool:
        """Persist state to file"""
        state = self.get_state(state_id)
        if not state:
            return False

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(state.to_dict(), f, indent=2)
            logger.info(f"State persisted: {state_id} to {file_path}")
            return True
        except Exception as exc:
            logger.error(f"Error persisting state: {exc}")
            return False

    def restore_state(self, state_id: str, file_path: str) -> bool:
        """Restore state from file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                state_data = json.load(f)

            state = SystemState(
                state_id=state_id,
                state_type=StateType(state_data['state_type']),
                state_name=state_data['state_name'],
                variables=state_data['variables']
            )

            with self._lock:
                self.states[state_id] = state

            logger.info(f"State restored: {state_id} from {file_path}")
            return True
        except Exception as exc:
            logger.error(f"Error restoring state: {exc}")
            return False

    def verify_state(self, state_id: str, expected_hash: str) -> bool:
        """Verify state integrity"""
        state = self.get_state(state_id)
        if not state:
            return False

        actual_hash = state.get_hash()
        return actual_hash == expected_hash

    def get_statistics(self) -> Dict:
        """Get state manager statistics"""
        with self._lock:
            states_by_type = {}
            for state in self.states.values():
                state_type = state.state_type.value
                states_by_type[state_type] = states_by_type.get(state_type, 0) + 1

            total_transitions = sum(len(s.transitions) for s in self.states.values())

            return {
                'total_states': len(self.states),
                'states_by_type': states_by_type,
                'total_transitions': total_transitions,
                'average_transitions_per_state': total_transitions / (len(self.states) or 1) if self.states else 0
            }

    def cleanup_old_states(self, days: int = 7) -> int:
        """Clean up old states"""
        from datetime import timedelta

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        removed_count = 0

        with self._lock:
            to_remove = []
            for state_id, state in self.states.items():
                if state.updated_at < cutoff_date:
                    to_remove.append(state_id)

            for state_id in to_remove:
                del self.states[state_id]
                removed_count += 1

        logger.info(f"Cleaned up {removed_count} old states")
        return removed_count


# Convenience functions

def create_system_state(variables: Optional[Dict] = None) -> SystemState:
    """Create a system state"""
    return SystemState(
        state_type=StateType.SYSTEM,
        state_name="system",
        variables=variables
    )


def create_workflow_state(workflow_id: str, variables: Optional[Dict] = None) -> SystemState:
    """Create a workflow state"""
    return SystemState(
        state_type=StateType.WORKFLOW,
        state_name=f"workflow_{workflow_id}",
        variables=variables
    )


def get_current_state(manager: StateManager, state_id: str) -> Dict:
    """Get current state as dictionary"""
    state = manager.get_state(state_id)
    if state:
        return state.to_dict()
    return {}

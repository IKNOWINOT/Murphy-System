"""
Librarian Integration for State Management and Setup Modification

This module integrates the Librarian system for:
- State management and persistence
- Setup configuration management
- Knowledge-based state queries
- Dynamic setup modification
"""

import hashlib
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StateEntry:
    """Represents a state entry"""
    state_id: str
    state_key: str
    state_value: Any
    state_type: str  # string, number, boolean, dict, list
    timestamp: datetime
    checksum: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SetupConfiguration:
    """Represents a setup configuration"""
    config_id: str
    config_name: str
    config_category: str
    configuration: Dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    version: int


class LibrarianStateManager:
    """
    Manages system state using Librarian integration

    Features:
    - State persistence
    - State versioning
    - State rollback
    - State queries and filtering
    """

    def __init__(self):
        self.states: Dict[str, StateEntry] = {}
        self.state_history: List[StateEntry] = []
        self.state_index: Dict[str, List[str]] = {}  # state_key -> state_ids
        self.lock = threading.Lock()
        self.auto_save = True
        self.max_history = 1000

    def set_state(self, state_key: str, state_value: Any,
                 state_type: str = "string", metadata: Dict[str, Any] = None) -> str:
        """Set a state value"""
        with self.lock:
            # Create checksum
            checksum = self._create_checksum(state_value)

            # Create state entry
            state_entry = StateEntry(
                state_id=f"state_{len(self.states)}_{int(datetime.now(timezone.utc).timestamp())}",
                state_key=state_key,
                state_value=state_value,
                state_type=state_type,
                timestamp=datetime.now(timezone.utc),
                checksum=checksum,
                metadata=metadata or {}
            )

            # Store state
            self.states[state_entry.state_id] = state_entry

            # Add to index
            if state_key not in self.state_index:
                self.state_index[state_key] = []
            self.state_index[state_key].append(state_entry.state_id)

            # Add to history
            self.state_history.append(state_entry)

            # Trim history if needed
            if len(self.state_history) > self.max_history:
                removed = self.state_history.pop(0)
                if removed.state_id in self.states:
                    del self.states[removed.state_id]
                if removed.state_key in self.state_index and removed.state_id in self.state_index[removed.state_key]:
                    self.state_index[removed.state_key].remove(removed.state_id)

            return state_entry.state_id

    def get_state(self, state_key: str) -> Optional[Any]:
        """Get the current state value for a key"""
        with self.lock:
            if state_key in self.state_index and self.state_index[state_key]:
                # Get the most recent state
                state_id = self.state_index[state_key][-1]
                state_entry = self.states.get(state_id)
                if state_entry:
                    return state_entry.state_value
        return None

    def get_state_history(self, state_key: str, limit: int = 10) -> List[StateEntry]:
        """Get state history for a key"""
        with self.lock:
            if state_key not in self.state_index:
                return []

            state_ids = self.state_index[state_key][-limit:]
            return [self.states[sid] for sid in state_ids if sid in self.states]

    def delete_state(self, state_key: str) -> bool:
        """Delete a state"""
        with self.lock:
            if state_key in self.state_index:
                # Remove all states for this key
                for state_id in self.state_index[state_key]:
                    if state_id in self.states:
                        del self.states[state_id]

                # Remove from index
                del self.state_index[state_key]
                return True
        return False

    def query_states(self, query: Dict[str, Any]) -> List[StateEntry]:
        """Query states by metadata or values"""
        with self.lock:
            results = []

            for state_entry in self.state_history:
                match = True

                # Check metadata
                for key, value in query.items():
                    if key == 'state_key':
                        if state_entry.state_key != value:
                            match = False
                            break
                    elif key in state_entry.metadata:
                        if state_entry.metadata[key] != value:
                            match = False
                            break
                    else:
                        match = False
                        break

                if match:
                    results.append(state_entry)

            return results

    def get_all_state_keys(self) -> List[str]:
        """Get all state keys"""
        with self.lock:
            return list(self.state_index.keys())

    def export_states(self) -> Dict[str, Any]:
        """Export all states to dictionary"""
        with self.lock:
            export = {}

            for state_key, state_ids in self.state_index.items():
                if state_ids:
                    state_entry = self.states.get(state_ids[-1])
                    if state_entry is not None:
                        export[state_key] = state_entry.state_value

            return export

    def import_states(self, states: Dict[str, Any]) -> int:
        """Import states from dictionary"""
        count = 0

        for state_key, state_value in states.items():
            state_type = self._determine_type(state_value)
            self.set_state(state_key, state_value, state_type)
            count += 1

        return count

    def clear_all_states(self) -> None:
        """Clear all states"""
        with self.lock:
            self.states.clear()
            self.state_history.clear()
            self.state_index.clear()

    def _create_checksum(self, value: Any) -> str:
        """Create a checksum for a value"""
        value_str = json.dumps(value, sort_keys=True)
        return hashlib.md5(value_str.encode(), usedforsecurity=False).hexdigest()  # value checksum only, not used for security

    def _determine_type(self, value: Any) -> str:
        """Determine the type of a value"""
        if isinstance(value, str):
            return "string"
        elif isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int) or isinstance(value, float):
            return "number"
        elif isinstance(value, dict):
            return "dict"
        elif isinstance(value, list):
            return "list"
        else:
            return "string"


class LibrarianSetupManager:
    """
    Manages setup configurations using Librarian integration

    Features:
    - Setup configuration management
    - Configuration versioning
    - Configuration activation/deactivation
    - Setup queries and filtering
    """

    def __init__(self):
        self.configurations: Dict[str, SetupConfiguration] = {}
        self.config_index: Dict[str, List[str]] = {}  # category -> config_ids
        self.active_configs: Dict[str, str] = {}  # category -> active_config_id
        self.lock = threading.Lock()

    def create_configuration(self, config_name: str, config_category: str,
                          configuration: Dict[str, Any]) -> str:
        """Create a new setup configuration"""
        with self.lock:
            config_id = f"config_{len(self.configurations)}_{int(datetime.now(timezone.utc).timestamp())}"

            setup_config = SetupConfiguration(
                config_id=config_id,
                config_name=config_name,
                config_category=config_category,
                configuration=configuration,
                is_active=False,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                version=1
            )

            self.configurations[config_id] = setup_config

            # Add to index
            if config_category not in self.config_index:
                self.config_index[config_category] = []
            self.config_index[config_category].append(config_id)

            return config_id

    def get_configuration(self, config_id: str) -> Optional[SetupConfiguration]:
        """Get a configuration by ID"""
        with self.lock:
            return self.configurations.get(config_id)

    def get_configurations_by_category(self, category: str) -> List[SetupConfiguration]:
        """Get all configurations in a category"""
        with self.lock:
            config_ids = self.config_index.get(category, [])
            return [self.configurations[cid] for cid in config_ids if cid in self.configurations]

    def update_configuration(self, config_id: str, configuration: Dict[str, Any]) -> bool:
        """Update a configuration"""
        with self.lock:
            if config_id in self.configurations:
                config = self.configurations[config_id]
                config.configuration = configuration
                config.updated_at = datetime.now(timezone.utc)
                config.version += 1
                return True
        return False

    def activate_configuration(self, config_id: str) -> bool:
        """Activate a configuration"""
        with self.lock:
            if config_id not in self.configurations:
                return False

            config = self.configurations[config_id]

            # Deactivate other configs in same category
            category = config.config_category
            for other_config_id in self.config_index.get(category, []):
                if other_config_id in self.configurations:
                    self.configurations[other_config_id].is_active = False

            # Activate this config
            config.is_active = True
            self.active_configs[category] = config_id

            return True

    def deactivate_configuration(self, config_id: str) -> bool:
        """Deactivate a configuration"""
        with self.lock:
            if config_id in self.configurations:
                config = self.configurations[config_id]
                config.is_active = False

                # Remove from active configs
                category = config.config_category
                if category in self.active_configs and self.active_configs[category] == config_id:
                    del self.active_configs[category]

                return True
        return False

    def get_active_configuration(self, category: str) -> Optional[SetupConfiguration]:
        """Get the active configuration for a category"""
        with self.lock:
            active_id = self.active_configs.get(category)
            if active_id:
                return self.configurations.get(active_id)
        return None

    def delete_configuration(self, config_id: str) -> bool:
        """Delete a configuration"""
        with self.lock:
            if config_id in self.configurations:
                config = self.configurations[config_id]

                # Remove from index
                category = config.config_category
                if category in self.config_index and config_id in self.config_index[category]:
                    self.config_index[category].remove(config_id)

                # Remove from active configs
                if category in self.active_configs and self.active_configs[category] == config_id:
                    del self.active_configs[category]

                # Delete configuration
                del self.configurations[config_id]

                return True
        return False

    def export_configuration(self, config_id: str) -> Optional[Dict[str, Any]]:
        """Export a configuration to dictionary"""
        config = self.get_configuration(config_id)
        if config:
            return {
                'config_id': config.config_id,
                'config_name': config.config_name,
                'config_category': config.config_category,
                'configuration': config.configuration,
                'is_active': config.is_active,
                'version': config.version,
                'created_at': config.created_at.isoformat(),
                'updated_at': config.updated_at.isoformat()
            }
        return None

    def import_configuration(self, config_data: Dict[str, Any]) -> str:
        """Import a configuration from dictionary"""
        config_id = self.create_configuration(
            config_data['config_name'],
            config_data['config_category'],
            config_data['configuration']
        )

        # Set version if provided
        if 'version' in config_data:
            config = self.configurations[config_id]
            config.version = config_data['version']

        # Activate if it was active
        if config_data.get('is_active', False):
            self.activate_configuration(config_id)

        return config_id


class LibrarianIntegration:
    """
    Main integration point for Librarian state and setup management

    This class provides a unified interface for:
    - State management
    - Setup configuration
    - Knowledge-based queries
    - System-wide operations
    """

    # Persistence document ID  [ARCH-003]
    _PERSIST_DOC_ID = "librarian_integration_state"

    def __init__(self, persistence_manager=None):
        self.state_manager = LibrarianStateManager()
        self.setup_manager = LibrarianSetupManager()
        self.initialized = False
        self._persistence = persistence_manager

    def initialize(self) -> None:
        """Initialize the librarian integration"""
        # Try to restore previously persisted state first
        if not self.load_state():
            # No persisted state found; create defaults
            self._create_default_configurations()
        self.initialized = True

    def _create_default_configurations(self) -> None:
        """Create default setup configurations"""
        # System configuration
        self.setup_manager.create_configuration(
            "Default System",
            "system",
            {
                "log_level": "info",
                "enable_auto_save": True,
                "max_history": 1000
            }
        )

        # Performance configuration
        self.setup_manager.create_configuration(
            "Default Performance",
            "performance",
            {
                "enable_caching": True,
                "cache_size": 1000,
                "enable_parallel_processing": True
            }
        )

        # Security configuration
        self.setup_manager.create_configuration(
            "Default Security",
            "security",
            {
                "enable_authentication": False,
                "enable_authorization": False,
                "log_security_events": True
            }
        )

    def get_state(self, key: str) -> Optional[Any]:
        """Get a state value"""
        return self.state_manager.get_state(key)

    def set_state(self, key: str, value: Any, **kwargs) -> str:
        """Set a state value"""
        state_id = self.state_manager.set_state(key, value, **kwargs)
        if self.state_manager.auto_save and self._persistence is not None:
            try:
                self.save_state()
            except Exception as exc:
                logger.debug("Suppressed auto-save exception in set_state: %s", exc)
        return state_id

    def get_setup(self, category: str) -> Optional[Dict[str, Any]]:
        """Get active setup configuration for a category"""
        config = self.setup_manager.get_active_configuration(category)
        return config.configuration if config else None

    def update_setup(self, category: str, configuration: Dict[str, Any]) -> bool:
        """Update setup configuration for a category"""
        config = self.setup_manager.get_active_configuration(category)
        if config:
            result = self.setup_manager.update_configuration(config.config_id, configuration)
            if result and self.state_manager.auto_save and self._persistence is not None:
                try:
                    self.save_state()
                except Exception as exc:
                    logger.debug("Suppressed auto-save exception in update_setup: %s", exc)
            return result
        return False

    def query_states(self, query: Dict[str, Any]) -> List[StateEntry]:
        """Query states"""
        return self.state_manager.query_states(query)

    def get_all_states(self) -> Dict[str, Any]:
        """Get all states"""
        return self.state_manager.export_states()

    def get_all_configurations(self) -> List[SetupConfiguration]:
        """Get all configurations"""
        return list(self.setup_manager.configurations.values())

    def export_all(self) -> Dict[str, Any]:
        """Export all states and configurations"""
        return {
            'states': self.get_all_states(),
            'configurations': [
                self.setup_manager.export_configuration(c.config_id)
                for c in self.get_all_configurations()
            ]
        }

    def import_all(self, data: Dict[str, Any]) -> None:
        """Import all states and configurations"""
        # Import states
        if 'states' in data:
            self.state_manager.import_states(data['states'])

        # Import configurations
        if 'configurations' in data:
            for config_data in data['configurations']:
                self.setup_manager.import_configuration(config_data)

    # ---- Persistence Integration  [ARCH-003] ----

    def save_state(self) -> bool:
        """Persist librarian state via PersistenceManager.

        Returns True on success, False if persistence is unavailable.
        """
        if self._persistence is None:
            return False
        data = self.export_all()
        try:
            self._persistence.save_document(self._PERSIST_DOC_ID, data)
            return True
        except Exception as exc:
            logger.debug("Suppressed exception in save_state: %s", exc)
            return False

    def load_state(self) -> bool:
        """Restore librarian state from PersistenceManager.

        Returns True on success, False if persistence is unavailable or
        no prior state exists.
        """
        if self._persistence is None:
            return False
        try:
            data = self._persistence.load_document(self._PERSIST_DOC_ID)
        except Exception as exc:
            logger.debug("Suppressed exception in load_state: %s", exc)
            return False
        if data is None:
            return False
        self.import_all(data)
        return True

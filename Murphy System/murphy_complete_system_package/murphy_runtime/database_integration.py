# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Database Integration Module
Migrates in-memory data to database and provides unified interface
"""

import uuid
from datetime import datetime
from typing import List, Dict, Optional
from database import Database, get_database
from repositories import (
    get_repository,
    AgentRepository,
    StateRepository,
    ComponentRepository,
    GateRepository,
    UserRepository
)
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database operations and data persistence"""
    
    def __init__(self, db_path: str = 'murphy_system.db'):
        """
        Initialize database manager
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db = get_database()
        self.agent_repo = get_repository(AgentRepository)
        self.state_repo = get_repository(StateRepository)
        self.component_repo = get_repository(ComponentRepository)
        self.gate_repo = get_repository(GateRepository)
        self.user_repo = get_repository(UserRepository)
    
    def initialize_default_users(self):
        """Create default users in database"""
        try:
            # Check if admin user exists
            existing_admin = self.user_repo.get_user_by_username('admin')
            
            if not existing_admin:
                # Create admin user (password will be hashed by auth system)
                admin_id = str(uuid.uuid4())
                self.user_repo.create_user(
                    user_id=admin_id,
                    username='admin',
                    password_hash='admin_hash',  # Will be updated by auth system
                    role='admin'
                )
                logger.info("✓ Default admin user created")
            
            # Check if demo user exists
            existing_demo = self.user_repo.get_user_by_username('demo')
            
            if not existing_demo:
                demo_id = str(uuid.uuid4())
                self.user_repo.create_user(
                    user_id=demo_id,
                    username='demo',
                    password_hash='demo_hash',  # Will be updated by auth system
                    role='user'
                )
                logger.info("✓ Default demo user created")
        
        except Exception as e:
            logger.error(f"✗ Failed to create default users: {e}")
    
    def initialize_system_data(self):
        """Initialize system with default data"""
        try:
            # Check if already initialized
            agent_count = self.agent_repo.count_agents()
            
            if agent_count > 0:
                logger.info("✓ System data already initialized")
                return {
                    'success': True,
                    'message': 'System data already initialized',
                    'agents_count': agent_count,
                    'states_count': self.state_repo.count_states()
                }
            
            # Create demo agents
            agents_data = [
                {
                    'id': 'agent-1',
                    'name': 'Executive Agent',
                    'role': 'planning',
                    'status': 'active',
                    'domain': 'business',
                    'confidence': 0.85,
                    'tasks_completed': 0,
                    'metadata': {'type': 'demo'}
                },
                {
                    'id': 'agent-2',
                    'name': 'Engineering Agent',
                    'role': 'technical',
                    'status': 'active',
                    'domain': 'engineering',
                    'confidence': 0.90,
                    'tasks_completed': 0,
                    'metadata': {'type': 'demo'}
                },
                {
                    'id': 'agent-3',
                    'name': 'Financial Agent',
                    'role': 'finance',
                    'status': 'active',
                    'domain': 'financial',
                    'confidence': 0.88,
                    'tasks_completed': 0,
                    'metadata': {'type': 'demo'}
                },
                {
                    'id': 'agent-4',
                    'name': 'Legal Agent',
                    'role': 'legal',
                    'status': 'active',
                    'domain': 'legal',
                    'confidence': 0.87,
                    'tasks_completed': 0,
                    'metadata': {'type': 'demo'}
                },
                {
                    'id': 'agent-5',
                    'name': 'Operations Agent',
                    'role': 'operations',
                    'status': 'active',
                    'domain': 'operations',
                    'confidence': 0.89,
                    'tasks_completed': 0,
                    'metadata': {'type': 'demo'}
                }
            ]
            
            for agent_data in agents_data:
                self.agent_repo.create_agent(agent_data)
            
            logger.info(f"✓ Created {len(agents_data)} demo agents")
            
            # Create initial state
            state_data = {
                'id': 'state-1',
                'name': 'Initial State',
                'description': 'System initialization state',
                'status': 'active',
                'confidence': 0.85,
                'parent_id': None,
                'metadata': {
                    'type': 'initial',
                    'children': []
                }
            }
            
            self.state_repo.create_state(state_data)
            logger.info("✓ Created initial state")
            
            # Create components
            components_data = [
                {
                    'id': 'comp-1',
                    'name': 'LLM Router',
                    'type': 'router',
                    'status': 'active',
                    'configuration': {'version': '1.0'}
                },
                {
                    'id': 'comp-2',
                    'name': 'State Machine',
                    'type': 'state_manager',
                    'status': 'active',
                    'configuration': {'version': '1.0'}
                },
                {
                    'id': 'comp-3',
                    'name': 'Agent Manager',
                    'type': 'agent_manager',
                    'status': 'active',
                    'configuration': {'version': '1.0'}
                }
            ]
            
            for component_data in components_data:
                self.component_repo.create_component(component_data)
            
            logger.info(f"✓ Created {len(components_data)} components")
            
            # Create gates
            gates_data = [
                {
                    'id': 'gate-1',
                    'name': 'Safety Gate 1',
                    'type': 'safety',
                    'description': 'First safety gate for validation',
                    'status': 'active',
                    'configuration': {'threshold': 0.85}
                },
                {
                    'id': 'gate-2',
                    'name': 'Quality Gate 1',
                    'type': 'quality',
                    'description': 'First quality gate for validation',
                    'status': 'active',
                    'configuration': {'threshold': 0.90}
                }
            ]
            
            for gate_data in gates_data:
                self.gate_repo.create_gate(gate_data)
            
            logger.info(f"✓ Created {len(gates_data)} gates")
            
            return {
                'success': True,
                'message': 'System data initialized successfully',
                'agents_count': len(agents_data),
                'states_count': 1,
                'components_count': len(components_data),
                'gates_count': len(gates_data)
            }
        
        except Exception as e:
            logger.error(f"✗ Failed to initialize system data: {e}")
            raise
    
    def get_agents(self) -> List[Dict]:
        """Get all agents from database"""
        return self.agent_repo.get_all_agents()
    
    def get_states(self) -> List[Dict]:
        """Get all states from database"""
        return self.state_repo.get_all_states()
    
    def get_components(self) -> List[Dict]:
        """Get all components from database"""
        return self.component_repo.get_all_components()
    
    def get_gates(self) -> List[Dict]:
        """Get all gates from database"""
        return self.gate_repo.get_all_gates()
    
    def get_state_by_id(self, state_id: str) -> Optional[Dict]:
        """Get state by ID"""
        return self.state_repo.get_state_by_id(state_id)
    
    def update_state(self, state_id: str, updates: Dict) -> bool:
        """Update state"""
        return self.state_repo.update_state(state_id, updates)
    
    def get_statistics(self) -> Dict:
        """Get system statistics"""
        return {
            'agents_count': self.agent_repo.count_agents(),
            'states_count': self.state_repo.count_states(),
            'components_count': self.component_repo.count_components(),
            'gates_count': self.gate_repo.count_gates()
        }
    
    def reset_database(self):
        """Reset database by deleting all data (for testing)"""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            tables = [
                'attention_history',
                'workflows',
                'messages',
                'tasks',
                'proposals',
                'patterns',
                'observations',
                'shadow_agents',
                'artifacts',
                'gates',
                'components',
                'states',
                'agents',
                'users'
            ]
            
            for table in tables:
                cursor.execute(f"DELETE FROM {table}")
            
            conn.commit()
            logger.info("✓ Database reset successfully")
            
        except Exception as e:
            logger.error(f"✗ Failed to reset database: {e}")
            raise
    
    def evolve_state(self, state_id: str) -> List[Dict]:
        """
        Evolve state into child states
        
        Args:
            state_id: ID of state to evolve
            
        Returns:
            List of child states
        """
        parent_state = self.get_state_by_id(state_id)
        if not parent_state:
            return []
        
        # Create 3 child states
        children = []
        for i in range(3):
            child_id = str(uuid.uuid4())
            child_data = {
                'id': child_id,
                'parent_id': state_id,
                'name': f"Child State {i+1}",
                'description': f"Evolved from {parent_state['name']}",
                'status': 'active',
                'confidence': round(parent_state.get('confidence', 0.85) + (0.01 * (i + 1)), 2),
                'metadata': {
                    'type': 'evolved',
                    'generation': parent_state.get('metadata', {}).get('generation', 0) + 1
                }
            }
            self.state_repo.create_state(child_data)
            children.append(child_data)
        
        logger.info(f"✓ Evolved state {state_id} into {len(children)} children")
        return children
    
    def regenerate_state(self, state_id: str) -> Optional[Dict]:
        """
        Regenerate state with new confidence
        
        Args:
            state_id: ID of state to regenerate
            
        Returns:
            Updated state or None
        """
        state = self.get_state_by_id(state_id)
        if not state:
            return None
        
        # Update confidence and metadata
        updates = {
            'confidence': min(1.0, state.get('confidence', 0.85) + 0.1),
            'metadata': {
                **state.get('metadata', {}),
                'regenerated': True,
                'regeneration_count': state.get('metadata', {}).get('regeneration_count', 0) + 1
            }
        }
        
        self.state_repo.update_state(state_id, updates)
        
        # Get updated state
        updated_state = self.get_state_by_id(state_id)
        logger.info(f"✓ Regenerated state {state_id}")
        return updated_state
    
    def rollback_state(self, state_id: str) -> Optional[Dict]:
        """
        Rollback state to parent
        
        Args:
            state_id: ID of state to rollback
            
        Returns:
            Parent state or None
        """
        state = self.get_state_by_id(state_id)
        if not state or not state.get('parent_id'):
            return None
        
        parent_id = state['parent_id']
        parent_state = self.get_state_by_id(parent_id)
        
        if parent_state:
            logger.info(f"✓ Rolled back state {state_id} to parent {parent_id}")
        
        return parent_state


# Global database manager instance
_db_manager = None


def get_database_manager() -> DatabaseManager:
    """Get or create global database manager instance"""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager
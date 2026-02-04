# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Data Access Layer
Repository pattern for database operations
"""

import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from database import Database, get_database
import logging

logger = logging.getLogger(__name__)


class UserRepository:
    """Repository for user operations"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create_user(self, user_id: str, username: str, password_hash: str, 
                    role: str = 'user') -> Dict:
        """Create a new user"""
        query = """
            INSERT INTO users (id, username, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?)
        """
        now = datetime.now().isoformat()
        self.db.execute_insert(query, (user_id, username, password_hash, role, now))
        
        return {
            'id': user_id,
            'username': username,
            'role': role,
            'created_at': now
        }
    
    def get_user_by_username(self, username: str) -> Optional[Dict]:
        """Get user by username"""
        query = "SELECT * FROM users WHERE username = ?"
        results = self.db.execute_query(query, (username,))
        return results[0] if results else None


class AgentRepository:
    """Repository for agent operations"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create_agent(self, agent_data: Dict) -> Dict:
        """Create a new agent"""
        query = """
            INSERT INTO agents (id, name, role, status, domain, confidence, 
                             tasks_completed, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        now = datetime.now().isoformat()
        params = (
            agent_data['id'],
            agent_data['name'],
            agent_data['role'],
            agent_data.get('status', 'active'),
            agent_data.get('domain'),
            agent_data.get('confidence'),
            agent_data.get('tasks_completed', 0),
            json.dumps(agent_data.get('metadata', {})),
            now,
            now
        )
        self.db.execute_insert(query, params)
        return agent_data
    
    def get_all_agents(self) -> List[Dict]:
        """Get all agents"""
        query = "SELECT * FROM agents ORDER BY created_at"
        results = self.db.execute_query(query)
        
        for agent in results:
            if agent.get('metadata'):
                agent['metadata'] = json.loads(agent['metadata'])
        
        return results
    
    def count_agents(self) -> int:
        """Count all agents"""
        query = "SELECT COUNT(*) as count FROM agents"
        results = self.db.execute_query(query)
        return results[0]['count'] if results else 0


class StateRepository:
    """Repository for state operations"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create_state(self, state_data: Dict) -> Dict:
        """Create a new state"""
        query = """
            INSERT INTO states (id, parent_id, name, description, status, 
                             confidence, metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        now = datetime.now().isoformat()
        params = (
            state_data['id'],
            state_data.get('parent_id'),
            state_data['name'],
            state_data.get('description'),
            state_data.get('status', 'active'),
            state_data.get('confidence'),
            json.dumps(state_data.get('metadata', {})),
            now,
            now
        )
        self.db.execute_insert(query, params)
        return state_data
    
    def get_all_states(self) -> List[Dict]:
        """Get all states"""
        query = "SELECT * FROM states ORDER BY created_at"
        results = self.db.execute_query(query)
        
        for state in results:
            if state.get('metadata'):
                state['metadata'] = json.loads(state['metadata'])
        
        return results
    
    def get_state_by_id(self, state_id: str) -> Optional[Dict]:
        """Get state by ID"""
        query = "SELECT * FROM states WHERE id = ?"
        results = self.db.execute_query(query, (state_id,))
        
        if results:
            state = results[0]
            if state.get('metadata'):
                state['metadata'] = json.loads(state['metadata'])
            return state
        return None
    
    def update_state(self, state_id: str, updates: Dict) -> bool:
        """Update state"""
        set_clauses = []
        params = []
        
        for key, value in updates.items():
            if key in ['name', 'description', 'status', 'confidence', 'parent_id']:
                set_clauses.append(f"{key} = ?")
                params.append(value)
            elif key == 'metadata':
                set_clauses.append("metadata = ?")
                params.append(json.dumps(value))
        
        if not set_clauses:
            return False
        
        set_clauses.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(state_id)
        
        query = f"UPDATE states SET {', '.join(set_clauses)} WHERE id = ?"
        self.db.execute_update(query, tuple(params))
        return True
    
    def count_states(self) -> int:
        """Count all states"""
        query = "SELECT COUNT(*) as count FROM states"
        results = self.db.execute_query(query)
        return results[0]['count'] if results else 0


class ComponentRepository:
    """Repository for component operations"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create_component(self, component_data: Dict) -> Dict:
        """Create a new component"""
        query = """
            INSERT INTO components (id, name, type, status, configuration, 
                                 created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        now = datetime.now().isoformat()
        params = (
            component_data['id'],
            component_data['name'],
            component_data['type'],
            component_data.get('status', 'active'),
            json.dumps(component_data.get('configuration', {})),
            now,
            now
        )
        self.db.execute_insert(query, params)
        return component_data
    
    def get_all_components(self) -> List[Dict]:
        """Get all components"""
        query = "SELECT * FROM components ORDER BY created_at"
        results = self.db.execute_query(query)
        
        for component in results:
            if component.get('configuration'):
                component['configuration'] = json.loads(component['configuration'])
        
        return results
    
    def count_components(self) -> int:
        """Count all components"""
        query = "SELECT COUNT(*) as count FROM components"
        results = self.db.execute_query(query)
        return results[0]['count'] if results else 0


class GateRepository:
    """Repository for gate operations"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create_gate(self, gate_data: Dict) -> Dict:
        """Create a new gate"""
        query = """
            INSERT INTO gates (id, name, type, description, status, 
                            configuration, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        now = datetime.now().isoformat()
        params = (
            gate_data['id'],
            gate_data['name'],
            gate_data['type'],
            gate_data.get('description'),
            gate_data.get('status', 'active'),
            json.dumps(gate_data.get('configuration', {})),
            now,
            now
        )
        self.db.execute_insert(query, params)
        return gate_data
    
    def get_all_gates(self) -> List[Dict]:
        """Get all gates"""
        query = "SELECT * FROM gates ORDER BY created_at"
        results = self.db.execute_query(query)
        
        for gate in results:
            if gate.get('configuration'):
                gate['configuration'] = json.loads(gate['configuration'])
        
        return results
    
    def count_gates(self) -> int:
        """Count all gates"""
        query = "SELECT COUNT(*) as count FROM gates"
        results = self.db.execute_query(query)
        return results[0]['count'] if results else 0


# Global repository instances
_repositories = {}


def get_repository(repo_class: type) -> Any:
    """Get or create repository instance"""
    db = get_database()
    class_name = repo_class.__name__
    
    if class_name not in _repositories:
        _repositories[class_name] = repo_class(db)
    
    return _repositories[class_name]
# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Database Layer
SQLite database integration for persistent storage
"""

import sqlite3
import json
import uuid
from datetime import datetime
from typing import List, Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class Database:
    """Database connection and operations manager"""
    
    def __init__(self, db_path: str = 'murphy_system.db'):
        """
        Initialize database connection
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn = None
        self._initialize_database()
    
    def get_connection(self) -> sqlite3.Connection:
        """
        Get database connection
        
        Returns:
            SQLite connection object
        """
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row  # Enable dict-like access
        return self.conn
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def _initialize_database(self):
        """Create all database tables"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Create tables
        self._create_users_table(cursor)
        self._create_agents_table(cursor)
        self._create_states_table(cursor)
        self._create_components_table(cursor)
        self._create_gates_table(cursor)
        self._create_artifacts_table(cursor)
        self._create_shadow_agents_table(cursor)
        self._create_observations_table(cursor)
        self._create_patterns_table(cursor)
        self._create_proposals_table(cursor)
        self._create_tasks_table(cursor)
        self._create_messages_table(cursor)
        self._create_workflows_table(cursor)
        self._create_attention_history_table(cursor)
        
        conn.commit()
        logger.info("✓ Database initialized successfully")
    
    def _create_users_table(self, cursor: sqlite3.Cursor):
        """Create users table"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_login TEXT
            )
        """)
    
    def _create_agents_table(self, cursor: sqlite3.Cursor):
        """Create agents table"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                status TEXT NOT NULL,
                domain TEXT,
                confidence REAL,
                tasks_completed INTEGER DEFAULT 0,
                metadata TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
    
    def _create_states_table(self, cursor: sqlite3.Cursor):
        """Create states table"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS states (
                id TEXT PRIMARY KEY,
                parent_id TEXT,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                confidence REAL,
                metadata TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (parent_id) REFERENCES states(id) ON DELETE CASCADE
            )
        """)
    
    def _create_components_table(self, cursor: sqlite3.Cursor):
        """Create components table"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS components (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                configuration TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
    
    def _create_gates_table(self, cursor: sqlite3.Cursor):
        """Create gates table"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gates (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                configuration TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
    
    def _create_artifacts_table(self, cursor: sqlite3.Cursor):
        """Create artifacts table"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS artifacts (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                content TEXT,
                file_path TEXT,
                quality_score REAL,
                status TEXT NOT NULL,
                validation_results TEXT,
                version INTEGER DEFAULT 1,
                metadata TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
    
    def _create_shadow_agents_table(self, cursor: sqlite3.Cursor):
        """Create shadow agents table"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shadow_agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                status TEXT NOT NULL,
                observations_count INTEGER DEFAULT 0,
                patterns_found INTEGER DEFAULT 0,
                automations_created INTEGER DEFAULT 0,
                configuration TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
    
    def _create_observations_table(self, cursor: sqlite3.Cursor):
        """Create observations table"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                action_type TEXT NOT NULL,
                context TEXT,
                timestamp TEXT NOT NULL,
                metadata TEXT,
                FOREIGN KEY (agent_id) REFERENCES shadow_agents(id) ON DELETE CASCADE
            )
        """)
    
    def _create_patterns_table(self, cursor: sqlite3.Cursor):
        """Create patterns table"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS patterns (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                pattern_type TEXT NOT NULL,
                description TEXT,
                confidence REAL,
                frequency INTEGER DEFAULT 1,
                metadata TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (agent_id) REFERENCES shadow_agents(id) ON DELETE CASCADE
            )
        """)
    
    def _create_proposals_table(self, cursor: sqlite3.Cursor):
        """Create automation proposals table"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS proposals (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                pattern_id TEXT,
                title TEXT NOT NULL,
                description TEXT,
                code_snippet TEXT,
                status TEXT NOT NULL,
                approval_date TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (agent_id) REFERENCES shadow_agents(id) ON DELETE CASCADE,
                FOREIGN KEY (pattern_id) REFERENCES patterns(id) ON DELETE CASCADE
            )
        """)
    
    def _create_tasks_table(self, cursor: sqlite3.Cursor):
        """Create swarm tasks table"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                workflow_id TEXT,
                type TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                assigned_to TEXT,
                result TEXT,
                metadata TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (workflow_id) REFERENCES workflows(id) ON DELETE CASCADE
            )
        """)
    
    def _create_messages_table(self, cursor: sqlite3.Cursor):
        """Create agent messages table"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                from_agent TEXT NOT NULL,
                to_agent TEXT NOT NULL,
                message_type TEXT NOT NULL,
                content TEXT,
                timestamp TEXT NOT NULL,
                FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
            )
        """)
    
    def _create_workflows_table(self, cursor: sqlite3.Cursor):
        """Create workflows table"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                execution_mode TEXT NOT NULL,
                configuration TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
    
    def _create_attention_history_table(self, cursor: sqlite3.Cursor):
        """Create attention history table"""
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attention_history (
                id TEXT PRIMARY KEY,
                representation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                decision_reason TEXT,
                success BOOLEAN,
                timestamp TEXT NOT NULL,
                metadata TEXT
            )
        """)
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict]:
        """
        Execute SELECT query and return results
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            List of dictionaries representing rows
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    
    def execute_update(self, query: str, params: tuple = ()) -> int:
        """
        Execute INSERT, UPDATE, or DELETE query
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            Number of affected rows
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        return cursor.rowcount
    
    def execute_insert(self, query: str, params: tuple = ()) -> str:
        """
        Execute INSERT query and return last row ID
        
        Args:
            query: SQL query
            params: Query parameters
            
        Returns:
            ID of inserted row (or the ID field if provided)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        
        # If params contains an id, return it
        if params and len(params) > 0:
            return params[0]
        
        return cursor.lastrowid


# Global database instance
_db_instance = None


def get_database() -> Database:
    """
    Get or create global database instance
    
    Returns:
        Database instance
    """
    global _db_instance
    if _db_instance is None:
        _db_instance = Database()
    return _db_instance
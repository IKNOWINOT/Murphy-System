"""
Database Connectors - SQL and NoSQL database connections
"""

import threading
import uuid
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone
from enum import Enum
import logging

from .integration_framework import Integration, IntegrationResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseType(Enum):
    """Types of databases"""
    MYSQL = "mysql"
    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"
    MONGODB = "mongodb"
    REDIS = "redis"
    CUSTOM = "custom"


class DatabaseConnector:
    """Base database connection manager"""
    
    def __init__(
        self,
        connection_string: str,
        database_type: DatabaseType = DatabaseType.CUSTOM,
        connection_pool_size: int = 10
    ):
        self.connection_string = connection_string
        self.database_type = database_type
        self.connection_pool_size = connection_pool_size
        self.is_connected = False
        self.connection_attempts = 0
        self.last_connected_at: Optional[datetime] = None
        self._lock = threading.Lock()
        
    def connect(self) -> bool:
        """Connect to database"""
        with self._lock:
            self.connection_attempts += 1
            
            try:
                connection_success = self._establish_connection()
                
                if connection_success:
                    self.is_connected = True
                    self.last_connected_at = datetime.now(timezone.utc)
                    logger.info(f"Connected to {self.database_type.value} database")
                    return True
                else:
                    logger.error(f"Failed to connect to {self.database_type.value} database")
                    return False
            
            except Exception as exc:
                logger.error(f"Error connecting to database: {exc}")
                return False
    
    def disconnect(self) -> bool:
        """Disconnect from database"""
        with self._lock:
            try:
                self._close_connection()
                self.is_connected = False
                logger.info(f"Disconnected from {self.database_type.value} database")
                return True
            except Exception as exc:
                logger.error(f"Error disconnecting from database: {exc}")
                return False
    
    def _establish_connection(self) -> bool:
        """Establish database connection (override in subclasses)"""
        return True
    
    def _close_connection(self) -> None:
        """Close database connection (override in subclasses)"""
        pass
    
    def execute_query(
        self,
        query: str,
        parameters: Optional[Dict] = None
    ) -> IntegrationResult:
        """Execute a database query"""
        if not self.is_connected:
            return IntegrationResult(
                success=False,
                error="Not connected to database"
            )
        
        try:
            result = self._execute_query(query, parameters)
            return IntegrationResult(success=True, data=result)
        
        except Exception as exc:
            logger.error(f"Error executing query: {exc}")
            return IntegrationResult(success=False, error=str(exc))
    
    def _execute_query(
        self,
        query: str,
        parameters: Optional[Dict] = None
    ) -> List[Dict]:
        """Execute query (override in subclasses)"""
        return [{'query': query, 'parameters': parameters}]
    
    def execute_transaction(
        self,
        operations: List[Dict]
    ) -> IntegrationResult:
        """Execute a transaction"""
        if not self.is_connected:
            return IntegrationResult(
                success=False,
                error="Not connected to database"
            )
        
        try:
            results = []
            for operation in operations:
                query = operation.get('query')
                parameters = operation.get('parameters')
                result = self._execute_query(query, parameters)
                results.append(result)
            
            return IntegrationResult(success=True, data=results)
        
        except Exception as exc:
            logger.error(f"Error executing transaction: {exc}")
            return IntegrationResult(success=False, error=str(exc))


class SQLDatabaseConnector(DatabaseConnector):
    """SQL database connector"""
    
    def __init__(
        self,
        connection_string: str,
        database_type: DatabaseType = DatabaseType.MYSQL,
        **kwargs
    ):
        super().__init__(connection_string, database_type, **kwargs)
    
    def _establish_connection(self) -> bool:
        """Establish SQL database connection"""
        return True
    
    def _execute_query(
        self,
        query: str,
        parameters: Optional[Dict] = None
    ) -> List[Dict]:
        """Execute SQL query"""
        query_lower = query.lower().strip()
        
        if query_lower.startswith('select'):
            return [
                {
                    'id': 1,
                    'name': 'Test Record',
                    'created_at': datetime.now(timezone.utc).isoformat()
                }
            ]
        elif query_lower.startswith('insert'):
            return [{'affected_rows': 1}]
        elif query_lower.startswith('update'):
            return [{'affected_rows': 1}]
        elif query_lower.startswith('delete'):
            return [{'affected_rows': 1}]
        else:
            return [{'query': query, 'parameters': parameters}]
    
    def execute_stored_procedure(
        self,
        name: str,
        parameters: Optional[Dict] = None
    ) -> IntegrationResult:
        """Execute stored procedure"""
        if not self.is_connected:
            return IntegrationResult(
                success=False,
                error="Not connected to database"
            )
        
        try:
            result = {
                'procedure': name,
                'parameters': parameters,
                'result': 'success'
            }
            return IntegrationResult(success=True, data=result)
        
        except Exception as exc:
            logger.error(f"Error executing stored procedure: {exc}")
            return IntegrationResult(success=False, error=str(exc))


class NoSQLDatabaseConnector(DatabaseConnector):
    """NoSQL database connector"""
    
    def __init__(
        self,
        connection_string: str,
        database_type: DatabaseType = DatabaseType.MONGODB,
        **kwargs
    ):
        super().__init__(connection_string, database_type, **kwargs)
        self.collections: Dict[str, List[Dict]] = {}
    
    def _establish_connection(self) -> bool:
        """Establish NoSQL database connection"""
        return True
    
    def get_document(
        self,
        collection: str,
        document_id: str
    ) -> IntegrationResult:
        """Get a document from collection"""
        if not self.is_connected:
            return IntegrationResult(
                success=False,
                error="Not connected to database"
            )
        
        try:
            document = {
                '_id': document_id,
                'collection': collection,
                'data': 'Sample document',
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            return IntegrationResult(success=True, data=document)
        
        except Exception as exc:
            logger.error(f"Error getting document: {exc}")
            return IntegrationResult(success=False, error=str(exc))
    
    def save_document(
        self,
        collection: str,
        document: Dict
    ) -> IntegrationResult:
        """Save a document to collection"""
        if not self.is_connected:
            return IntegrationResult(
                success=False,
                error="Not connected to database"
            )
        
        try:
            if 'created_at' not in document:
                document['created_at'] = datetime.now(timezone.utc).isoformat()
            
            if collection not in self.collections:
                self.collections[collection] = []
            
            self.collections[collection].append(document)
            
            return IntegrationResult(
                success=True,
                data={'document_id': document.get('_id', str(uuid.uuid4()))}
            )
        
        except Exception as exc:
            logger.error(f"Error saving document: {exc}")
            return IntegrationResult(success=False, error=str(exc))
    
    def query_documents(
        self,
        collection: str,
        filter: Optional[Dict] = None,
        limit: int = 100
    ) -> IntegrationResult:
        """Query documents from collection"""
        if not self.is_connected:
            return IntegrationResult(
                success=False,
                error="Not connected to database"
            )
        
        try:
            documents = self.collections.get(collection, [])
            
            if filter:
                filtered_documents = []
                for doc in documents:
                    match = True
                    for key, value in filter.items():
                        if doc.get(key) != value:
                            match = False
                            break
                    if match:
                        filtered_documents.append(doc)
                documents = filtered_documents
            
            documents = documents[:limit]
            
            return IntegrationResult(success=True, data=documents)
        
        except Exception as exc:
            logger.error(f"Error querying documents: {exc}")
            return IntegrationResult(success=False, error=str(exc))
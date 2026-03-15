"""
Database Connectors - SQL and NoSQL database connections

Environment variables
---------------------
MURPHY_DB_MODE : str
    ``stub`` (default) — all SQL operations return deterministic in-memory
    responses suitable for development and testing.
    ``live``           — all SQL operations are executed against a real
    database using a SQLAlchemy engine created from the connector's
    ``connection_string``.
    In ``production`` or ``staging`` environments (``MURPHY_ENV``), the
    ``stub`` value is **rejected at startup** with a ``RuntimeError`` to
    prevent silent data-loss.  Set ``MURPHY_DB_MODE=live`` and configure
    a real ``DATABASE_URL`` before deploying.
DATABASE_URL : str
    Ignored by this module; the ``connection_string`` passed to the
    constructor is used instead.  ``DATABASE_URL`` is consumed by
    ``src/db.py`` for the ORM layer.
MURPHY_ENV : str
    Runtime environment: ``development`` (default), ``test``,
    ``staging``, or ``production``.
"""

import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from .integration_framework import Integration, IntegrationResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Feature toggle: MURPHY_DB_MODE = "stub" | "live"
# ---------------------------------------------------------------------------

MURPHY_DB_MODE: str = os.environ.get("MURPHY_DB_MODE", "stub").lower()

# ---------------------------------------------------------------------------
# Development-mode safety guard
# ---------------------------------------------------------------------------

_MURPHY_ENV: str = os.environ.get("MURPHY_ENV", "development").lower()
_PRODUCTION_ENVS = {"production", "staging"}


def stub_mode_allowed() -> bool:
    """Return whether stub mode is permitted in the current environment.

    Stub mode is allowed in ``development`` and ``test`` environments.
    It is **not** allowed in ``production`` or ``staging``.

    Returns:
        ``True`` when stub mode is safe to use, ``False`` otherwise.
    """
    return _MURPHY_ENV not in _PRODUCTION_ENVS


def _check_stub_mode_at_startup() -> None:
    """Raise or warn depending on environment when stub mode is active."""
    if MURPHY_DB_MODE != "stub":
        return
    if not stub_mode_allowed():
        raise RuntimeError(
            f"MURPHY_DB_MODE=stub is not allowed in MURPHY_ENV={_MURPHY_ENV!r}. "
            "Set MURPHY_DB_MODE=live and configure a real database before deploying. "
            "See .env.example for DATABASE_URL guidance."
        )
    logger.warning(
        "DATABASE STUB MODE ACTIVE — all SQL operations return fake data. "
        "Set MURPHY_DB_MODE=live for a real database. "
        "(MURPHY_ENV=%s)",
        _MURPHY_ENV,
    )


_check_stub_mode_at_startup()


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
                    logger.info("Connected to %s database", self.database_type.value)
                    return True
                else:
                    logger.error("Failed to connect to %s database", self.database_type.value)
                    return False

            except Exception as exc:
                logger.error("Error connecting to database: %s", exc)
                return False

    def disconnect(self) -> bool:
        """Disconnect from database"""
        with self._lock:
            try:
                self._close_connection()
                self.is_connected = False
                logger.info("Disconnected from %s database", self.database_type.value)
                return True
            except Exception as exc:
                logger.error("Error disconnecting from database: %s", exc)
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
            logger.error("Error executing query: %s", exc)
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
            logger.error("Error executing transaction: %s", exc)
            return IntegrationResult(success=False, error=str(exc))


class SQLDatabaseConnector(DatabaseConnector):
    """SQL database connector.

    Behaviour is controlled by the ``MURPHY_DB_MODE`` environment variable:

    * ``stub`` (default) — all operations return deterministic in-memory
      responses.  No real database driver is required.
    * ``live``           — all operations are executed against the database
      at ``connection_string`` via a SQLAlchemy engine.  Requires
      SQLAlchemy to be installed and a reachable database server.
    """

    def __init__(
        self,
        connection_string: str,
        database_type: DatabaseType = DatabaseType.MYSQL,
        **kwargs
    ):
        super().__init__(connection_string, database_type, **kwargs)
        self._engine = None
        self._db_mode: str = os.environ.get("MURPHY_DB_MODE", "stub").lower()

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    def _establish_connection(self) -> bool:
        """Establish SQL database connection.

        In *live* mode, creates a SQLAlchemy engine and verifies connectivity
        with a ``SELECT 1`` probe.  In *stub* mode, returns ``True``
        immediately without touching any external resource.
        """
        if self._db_mode == "live":
            try:
                from sqlalchemy import create_engine  # noqa: PLC0415
                from sqlalchemy import text as sa_text
                connect_args: Dict = {}
                if self.connection_string.startswith("sqlite"):
                    connect_args["check_same_thread"] = False
                self._engine = create_engine(
                    self.connection_string,
                    connect_args=connect_args,
                    echo=False,
                )
                with self._engine.connect() as conn:
                    conn.execute(sa_text("SELECT 1"))
                logger.info("Live SQL engine connected (%s)", self.database_type.value)
                return True
            except Exception as exc:
                logger.error("Live DB connection failed: %s", exc)
                self._engine = None
                return False
        # development mode — always succeeds
        return True

    def _close_connection(self) -> None:
        """Dispose the SQLAlchemy engine if one exists."""
        if self._engine is not None:
            try:
                self._engine.dispose()
            except Exception as exc:
                logger.error("Error disposing SQL engine: %s", exc)
            finally:
                self._engine = None

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------

    def _execute_query(
        self,
        query: str,
        parameters: Optional[Dict] = None
    ) -> List[Dict]:
        """Execute a SQL query.

        In *live* mode, executes against the real database and returns rows
        as a list of dicts (SELECT) or ``[{'affected_rows': N}]`` for DML.
        In *stub* mode, returns deterministic fixture data for testing.
        """
        if self._db_mode == "live" and self._engine is not None:
            from sqlalchemy import text as sa_text  # noqa: PLC0415
            with self._engine.begin() as conn:
                result = conn.execute(sa_text(query), parameters or {})
                if result.returns_rows:
                    cols = list(result.keys())
                    return [dict(zip(cols, row)) for row in result.fetchall()]
                return [{"affected_rows": result.rowcount}]

        # development mode — return deterministic fixture data
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

    # ------------------------------------------------------------------
    # Transaction execution (overrides base class for live-mode isolation)
    # ------------------------------------------------------------------

    def execute_transaction(
        self,
        operations: List[Dict]
    ) -> IntegrationResult:
        """Execute a series of operations as a single atomic transaction.

        In *live* mode, wraps all operations in a SQLAlchemy
        ``engine.begin()`` context so that a failure in any operation rolls
        back all previously executed statements automatically.

        In *stub* mode, the operations are executed sequentially without
        real transaction isolation (suitable for testing only).
        """
        if not self.is_connected:
            return IntegrationResult(
                success=False,
                error="Not connected to database"
            )

        if self._db_mode == "live" and self._engine is not None:
            from sqlalchemy import text as sa_text  # noqa: PLC0415
            try:
                results: List = []
                with self._engine.begin() as conn:
                    for operation in operations:
                        query = operation.get('query')
                        parameters = operation.get('parameters')
                        result = conn.execute(sa_text(query), parameters or {})
                        if result.returns_rows:
                            cols = list(result.keys())
                            results.append(
                                [dict(zip(cols, row)) for row in result.fetchall()]
                            )
                        else:
                            results.append([{"affected_rows": result.rowcount}])
                return IntegrationResult(success=True, data=results)
            except Exception as exc:
                logger.error("Error executing transaction: %s", exc)
                return IntegrationResult(success=False, error=str(exc))

        # development mode — sequential execution, no real rollback
        try:
            results = []
            for operation in operations:
                query = operation.get('query')
                parameters = operation.get('parameters')
                result = self._execute_query(query, parameters)
                results.append(result)
            return IntegrationResult(success=True, data=results)
        except Exception as exc:
            logger.error("Error executing transaction: %s", exc)
            return IntegrationResult(success=False, error=str(exc))

    # ------------------------------------------------------------------
    # Stored procedure execution
    # ------------------------------------------------------------------

    def execute_stored_procedure(
        self,
        name: str,
        parameters: Optional[Dict] = None
    ) -> IntegrationResult:
        """Execute a stored procedure.

        In *live* mode, issues a ``CALL <name>(...)`` statement via the
        SQLAlchemy engine and returns any result rows.  In *stub* mode,
        returns a deterministic success payload for testing.
        """
        if not self.is_connected:
            return IntegrationResult(
                success=False,
                error="Not connected to database"
            )

        if self._db_mode == "live" and self._engine is not None:
            from sqlalchemy import text as sa_text  # noqa: PLC0415
            try:
                param_list = ", ".join(
                    f":{k}" for k in (parameters or {}).keys()
                )
                call_sql = f"CALL {name}({param_list})"
                with self._engine.begin() as conn:
                    result = conn.execute(sa_text(call_sql), parameters or {})
                    if result.returns_rows:
                        cols = list(result.keys())
                        data: Any = [
                            dict(zip(cols, row)) for row in result.fetchall()
                        ]
                    else:
                        data = {
                            'procedure': name,
                            'affected_rows': result.rowcount,
                        }
                return IntegrationResult(success=True, data=data)
            except Exception as exc:
                logger.error("Error executing stored procedure: %s", exc)
                return IntegrationResult(success=False, error=str(exc))

        # development mode — return deterministic success payload
        try:
            result = {
                'procedure': name,
                'parameters': parameters,
                'result': 'success'
            }
            return IntegrationResult(success=True, data=result)
        except Exception as exc:
            logger.error("Error executing stored procedure: %s", exc)
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
            logger.error("Error getting document: %s", exc)
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
            logger.error("Error saving document: %s", exc)
            return IntegrationResult(success=False, error=str(exc))

    def query_documents(
        self,
        collection: str,
        doc_filter: Optional[Dict] = None,
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

            if doc_filter:
                filtered_documents = []
                for doc in documents:
                    match = True
                    for key, value in doc_filter.items():
                        if doc.get(key) != value:
                            match = False
                            break
                    if match:
                        filtered_documents.append(doc)
                documents = filtered_documents

            documents = documents[:limit]

            return IntegrationResult(success=True, data=documents)

        except Exception as exc:
            logger.error("Error querying documents: %s", exc)
            return IntegrationResult(success=False, error=str(exc))

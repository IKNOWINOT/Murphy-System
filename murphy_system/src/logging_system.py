"""
COMPREHENSIVE LOGGING SYSTEM FOR MURPHY SYSTEM
Implements session, thread, runtime gate, and employee atom logging

Owner: INONI LLC / Corey Post
Contact: corey.gfc@gmail.com
Repository: https://github.com/IKNOWINOT/Murphy-System
"""

import json
import logging
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ThreadStatus(Enum):
    """Thread execution status"""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class AtomType(Enum):
    """Employee atom types"""
    CONSTRAINT = "constraint"
    REQUIREMENT = "requirement"
    CAPABILITY = "capability"
    RESOURCE = "resource"
    KNOWLEDGE = "knowledge"


class AtomSource(Enum):
    """Source of employee atom"""
    USER_INPUT = "user_input"
    DERIVED = "derived"
    LEARNED = "learned"
    DOMAIN_KNOWLEDGE = "domain_knowledge"


@dataclass
class Session:
    """User session tracking"""
    session_id: str
    user_id: Optional[str] = None
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    total_messages: int = 0
    total_commands: int = 0
    domains_accessed: List[str] = field(default_factory=list)
    confidence_history: List[float] = field(default_factory=list)
    murphy_index_history: List[float] = field(default_factory=list)
    packets_compiled: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'session_id': self.session_id,
            'user_id': self.user_id,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'total_messages': self.total_messages,
            'total_commands': self.total_commands,
            'domains_accessed': json.dumps(self.domains_accessed),
            'metadata': json.dumps({
                'confidence_history': self.confidence_history,
                'murphy_index_history': self.murphy_index_history,
                'packets_compiled': self.packets_compiled,
                **self.metadata
            })
        }


@dataclass
class Thread:
    """Conversation/process thread tracking"""
    thread_id: str
    session_id: str
    parent_thread_id: Optional[str] = None
    project_name: str = "Untitled Project"
    domain: str = "general"
    industry: str = "general"
    start_time: float = field(default_factory=time.time)
    status: ThreadStatus = ThreadStatus.ACTIVE
    messages: List[Dict[str, Any]] = field(default_factory=list)
    gates_active: List[str] = field(default_factory=list)
    employee_atoms: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'thread_id': self.thread_id,
            'session_id': self.session_id,
            'parent_thread_id': self.parent_thread_id,
            'project_name': self.project_name,
            'domain': self.domain,
            'industry': self.industry,
            'start_time': self.start_time,
            'status': self.status.value,
            'metadata': json.dumps({
                'messages': self.messages,
                'gates_active': self.gates_active,
                'employee_atoms': self.employee_atoms,
                'artifacts': self.artifacts,
                **self.metadata
            })
        }


@dataclass
class RuntimeLoopGate:
    """Runtime gate for continuous monitoring"""
    gate_id: str
    thread_id: str
    gate_type: str
    trigger_condition: str
    current_state: Dict[str, Any] = field(default_factory=dict)
    satisfaction_level: float = 0.0
    last_check: float = field(default_factory=time.time)
    check_frequency: float = 60.0  # seconds
    is_active: bool = True
    actions_triggered: List[Dict[str, Any]] = field(default_factory=list)
    employee_atoms_generated: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'gate_id': self.gate_id,
            'thread_id': self.thread_id,
            'gate_type': self.gate_type,
            'trigger_condition': self.trigger_condition,
            'current_state': json.dumps(self.current_state),
            'satisfaction_level': self.satisfaction_level,
            'last_check': self.last_check,
            'check_frequency': self.check_frequency,
            'is_active': 1 if self.is_active else 0
        }


@dataclass
class EmployeeAtom:
    """Domain/industry-specific data atom"""
    atom_id: str
    thread_id: str
    domain: str
    industry: str
    atom_type: AtomType
    content: Dict[str, Any]
    confidence: float
    source: AtomSource
    timestamp: float = field(default_factory=time.time)
    dependencies: List[str] = field(default_factory=list)
    used_by_gates: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'atom_id': self.atom_id,
            'thread_id': self.thread_id,
            'domain': self.domain,
            'industry': self.industry,
            'atom_type': self.atom_type.value,
            'content': json.dumps(self.content),
            'confidence': self.confidence,
            'source': self.source.value,
            'timestamp': self.timestamp,
            'dependencies': json.dumps(self.dependencies)
        }


class LoggingDatabase:
    """SQLite database for persistent logging"""

    def __init__(self, db_path: str = "murphy_logs.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._initialize_database()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections with automatic cleanup"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize_database(self):
        """Create database schema"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Sessions table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    start_time REAL NOT NULL,
                    end_time REAL,
                    total_messages INTEGER DEFAULT 0,
                    total_commands INTEGER DEFAULT 0,
                    domains_accessed TEXT,
                    metadata TEXT
                )
                """)

                # Threads table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS threads (
                    thread_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    parent_thread_id TEXT,
                    project_name TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    industry TEXT NOT NULL,
                    start_time REAL NOT NULL,
                    status TEXT NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
                """)

                # Runtime gates table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS runtime_gates (
                    gate_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    gate_type TEXT NOT NULL,
                    trigger_condition TEXT NOT NULL,
                    current_state TEXT,
                    satisfaction_level REAL,
                    last_check REAL,
                    check_frequency REAL,
                    is_active INTEGER DEFAULT 1,
                    FOREIGN KEY (thread_id) REFERENCES threads(thread_id)
                )
                """)

                # Employee atoms table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS employee_atoms (
                    atom_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    industry TEXT NOT NULL,
                    atom_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    confidence REAL,
                    source TEXT,
                    timestamp REAL NOT NULL,
                    dependencies TEXT,
                    FOREIGN KEY (thread_id) REFERENCES threads(thread_id)
                )
                """)

                # Events table (enhanced)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    thread_id TEXT,
                    timestamp REAL NOT NULL,
                    event_type TEXT NOT NULL,
                    phase TEXT,
                    confidence REAL,
                    murphy_index REAL,
                    data TEXT,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
                    FOREIGN KEY (thread_id) REFERENCES threads(thread_id)
                )
                """)

                # Create indexes
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_start ON sessions(start_time)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_threads_session ON threads(session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_threads_status ON threads(status)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_gates_thread ON runtime_gates(thread_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_gates_active ON runtime_gates(is_active)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_atoms_thread ON employee_atoms(thread_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_atoms_domain ON employee_atoms(domain)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_thread ON events(thread_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)")

    def insert_session(self, session: Session):
        """Insert or update session"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                data = session.to_dict()
                cursor.execute("""
                    INSERT OR REPLACE INTO sessions
                    (session_id, user_id, start_time, end_time, total_messages,
                     total_commands, domains_accessed, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data['session_id'], data['user_id'], data['start_time'],
                    data['end_time'], data['total_messages'], data['total_commands'],
                    data['domains_accessed'], data['metadata']
                ))

    def insert_thread(self, thread: Thread):
        """Insert or update thread"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
            data = thread.to_dict()
            cursor.execute("""
                INSERT OR REPLACE INTO threads
                (thread_id, session_id, parent_thread_id, project_name,
                 domain, industry, start_time, status, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['thread_id'], data['session_id'], data['parent_thread_id'],
                data['project_name'], data['domain'], data['industry'],
                data['start_time'], data['status'], data['metadata']
            ))
    def insert_runtime_gate(self, gate: RuntimeLoopGate):
        """Insert or update runtime gate"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
            data = gate.to_dict()
            cursor.execute("""
                INSERT OR REPLACE INTO runtime_gates
                (gate_id, thread_id, gate_type, trigger_condition,
                 current_state, satisfaction_level, last_check,
                 check_frequency, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['gate_id'], data['thread_id'], data['gate_type'],
                data['trigger_condition'], data['current_state'],
                data['satisfaction_level'], data['last_check'],
                data['check_frequency'], data['is_active']
            ))
    def insert_employee_atom(self, atom: EmployeeAtom):
        """Insert employee atom"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
            data = atom.to_dict()
            cursor.execute("""
                INSERT OR REPLACE INTO employee_atoms
                (atom_id, thread_id, domain, industry, atom_type,
                 content, confidence, source, timestamp, dependencies)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data['atom_id'], data['thread_id'], data['domain'],
                data['industry'], data['atom_type'], data['content'],
                data['confidence'], data['source'], data['timestamp'],
                data['dependencies']
            ))
    def insert_event(self, event: Dict[str, Any]):
        """Insert event"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO events
                (event_id, session_id, thread_id, timestamp, event_type,
                 phase, confidence, murphy_index, data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.get('event_id', str(uuid.uuid4())),
                event.get('session_id'),
                event.get('thread_id'),
                event.get('timestamp', time.time()),
                event['event_type'],
                event.get('phase'),
                event.get('confidence'),
                event.get('murphy_index'),
                json.dumps(event.get('data', {}))
            ))
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Get all active sessions"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM sessions
                WHERE end_time IS NULL
                ORDER BY start_time DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_thread(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get thread by ID"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
            cursor.execute("SELECT * FROM threads WHERE thread_id = ?", (thread_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_threads_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all threads for a session"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM threads
                WHERE session_id = ?
                ORDER BY start_time DESC
            """, (session_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_active_threads(self) -> List[Dict[str, Any]]:
        """Get all active threads"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM threads
                WHERE status = 'active'
                ORDER BY start_time DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_runtime_gates_by_thread(self, thread_id: str) -> List[Dict[str, Any]]:
        """Get all runtime gates for a thread"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM runtime_gates
                WHERE thread_id = ? AND is_active = 1
                ORDER BY last_check DESC
            """, (thread_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_active_runtime_gates(self) -> List[Dict[str, Any]]:
        """Get all active runtime gates"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM runtime_gates
                WHERE is_active = 1
                ORDER BY last_check DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_employee_atoms_by_thread(self, thread_id: str) -> List[Dict[str, Any]]:
        """Get all employee atoms for a thread"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM employee_atoms
                WHERE thread_id = ?
                ORDER BY timestamp DESC
            """, (thread_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_employee_atoms_by_domain(self, domain: str) -> List[Dict[str, Any]]:
        """Get all employee atoms for a domain"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM employee_atoms
                WHERE domain = ?
                ORDER BY confidence DESC, timestamp DESC
            """, (domain,))
            return [dict(row) for row in cursor.fetchall()]

    def get_events(self, session_id: Optional[str] = None,
                   thread_id: Optional[str] = None,
                   limit: int = 100) -> List[Dict[str, Any]]:
        """Get events with optional filtering"""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()

            if session_id:
                cursor.execute("""
                    SELECT * FROM events
                    WHERE session_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (session_id, limit))
            elif thread_id:
                cursor.execute("""
                    SELECT * FROM events
                    WHERE thread_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (thread_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM events
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    def close(self):
        """Close database connection (no-op with connection pooling)"""
        # With connection pooling, connections are closed automatically
        # This method is kept for backward compatibility
        pass


class LoggingSystem:
    """Main logging system coordinator"""

    def __init__(self, db_path: str = "murphy_logs.db"):
        self.db = LoggingDatabase(db_path)
        self.current_session: Optional[Session] = None
        self.current_thread: Optional[Thread] = None
        self.active_gates: Dict[str, RuntimeLoopGate] = {}

    def create_session(self, user_id: Optional[str] = None) -> Session:
        """Create new session"""
        session = Session(
            session_id=str(uuid.uuid4()),
            user_id=user_id
        )
        self.db.insert_session(session)
        self.current_session = session
        return session

    def end_session(self, session_id: str):
        """End a session"""
        session = self.db.get_session(session_id)
        if session:
            session['end_time'] = time.time()
            # Reconstruct Session object
            sess_obj = Session(
                session_id=session['session_id'],
                user_id=session['user_id'],
                start_time=session['start_time'],
                end_time=session['end_time'],
                total_messages=session['total_messages'],
                total_commands=session['total_commands']
            )
            self.db.insert_session(sess_obj)

    def create_thread(self, session_id: str, project_name: str,
                     domain: str = "general", industry: str = "general",
                     parent_thread_id: Optional[str] = None) -> Thread:
        """Create new thread"""
        thread = Thread(
            thread_id=str(uuid.uuid4()),
            session_id=session_id,
            parent_thread_id=parent_thread_id,
            project_name=project_name,
            domain=domain,
            industry=industry
        )
        self.db.insert_thread(thread)
        self.current_thread = thread
        return thread

    def update_thread_status(self, thread_id: str, status: ThreadStatus):
        """Update thread status"""
        thread = self.db.get_thread(thread_id)
        if thread:
            thread['status'] = status.value
            # Reconstruct Thread object
            thread_obj = Thread(
                thread_id=thread['thread_id'],
                session_id=thread['session_id'],
                parent_thread_id=thread['parent_thread_id'],
                project_name=thread['project_name'],
                domain=thread['domain'],
                industry=thread['industry'],
                start_time=thread['start_time'],
                status=ThreadStatus(thread['status'])
            )
            self.db.insert_thread(thread_obj)

    def create_runtime_gate(self, thread_id: str, gate_type: str,
                           trigger_condition: str,
                           check_frequency: float = 60.0) -> RuntimeLoopGate:
        """Create new runtime gate"""
        gate = RuntimeLoopGate(
            gate_id=str(uuid.uuid4()),
            thread_id=thread_id,
            gate_type=gate_type,
            trigger_condition=trigger_condition,
            check_frequency=check_frequency
        )
        self.db.insert_runtime_gate(gate)
        self.active_gates[gate.gate_id] = gate
        return gate

    def update_gate_satisfaction(self, gate_id: str, satisfaction: float,
                                state: Dict[str, Any]):
        """Update gate satisfaction level"""
        if gate_id in self.active_gates:
            gate = self.active_gates[gate_id]
            gate.satisfaction_level = satisfaction
            gate.current_state = state
            gate.last_check = time.time()
            self.db.insert_runtime_gate(gate)

    def create_employee_atom(self, thread_id: str, domain: str, industry: str,
                            atom_type: AtomType, content: Dict[str, Any],
                            confidence: float, source: AtomSource) -> EmployeeAtom:
        """Create new employee atom"""
        atom = EmployeeAtom(
            atom_id=str(uuid.uuid4()),
            thread_id=thread_id,
            domain=domain,
            industry=industry,
            atom_type=atom_type,
            content=content,
            confidence=confidence,
            source=source
        )
        self.db.insert_employee_atom(atom)
        return atom

    def log_event(self, event_type: str, data: Dict[str, Any],
                 session_id: Optional[str] = None,
                 thread_id: Optional[str] = None):
        """Log an event"""
        event = {
            'event_id': str(uuid.uuid4()),
            'session_id': session_id or (self.current_session.session_id if self.current_session else None),
            'thread_id': thread_id or (self.current_thread.thread_id if self.current_thread else None),
            'timestamp': time.time(),
            'event_type': event_type,
            'data': data
        }
        self.db.insert_event(event)

    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get comprehensive session summary"""
        session = self.db.get_session(session_id)
        if not session:
            return {}

        threads = self.db.get_threads_by_session(session_id)
        events = self.db.get_events(session_id=session_id)

        return {
            'session': session,
            'threads': threads,
            'events': events,
            'thread_count': len(threads),
            'event_count': len(events)
        }

    def get_thread_summary(self, thread_id: str) -> Dict[str, Any]:
        """Get comprehensive thread summary"""
        thread = self.db.get_thread(thread_id)
        if not thread:
            return {}

        gates = self.db.get_runtime_gates_by_thread(thread_id)
        atoms = self.db.get_employee_atoms_by_thread(thread_id)
        events = self.db.get_events(thread_id=thread_id)

        return {
            'thread': thread,
            'gates': gates,
            'atoms': atoms,
            'events': events,
            'gate_count': len(gates),
            'atom_count': len(atoms)
        }

    def close(self):
        """Close logging system"""
        self.db.close()


# Global logging system instance
_logging_system = None

def get_logging_system() -> LoggingSystem:
    """Get global logging system instance"""
    global _logging_system
    if _logging_system is None:
        _logging_system = LoggingSystem()
    return _logging_system

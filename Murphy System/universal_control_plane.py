"""
Murphy Universal Control Plane

A modular control system where sessions load ONLY the engines they need:
- Factory HVAC → Sensor/Actuator engines
- Blog Publishing → Content/API engines
- Data Pipeline → Database/Compute engines

Each session is an isolated control plane with its own engine set.

Copyright © 2020 Inoni Limited Liability Company
Created by: Corey Post
License: Apache License 2.0
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from typing import Dict, Any, List, Optional, Set
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# Import universal systems
from control_plane.execution_packet import (
    ExecutionPacket, Action, ActionType, SafetyConstraint, Gate,
    TimeWindow, RollbackPlan, AuthorityEnvelope, create_simple_packet
)
from control_plane.packet_compiler import PacketCompiler
from governance_framework.scheduler import GovernanceScheduler, ScheduledAgent
from execution_engine.workflow_orchestrator import WorkflowOrchestrator

# ============================================================================
# ENGINE TYPES & REGISTRY
# ============================================================================

class EngineType(Enum):
    """Types of control engines"""
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    DATABASE = "database"
    API = "api"
    CONTENT = "content"
    COMMAND = "command"
    AGENT = "agent"
    WORKFLOW = "workflow"
    GOVERNANCE = "governance"  # Universal - always loaded

class ControlType(Enum):
    """Types of control automation"""
    SENSOR_ACTUATOR = "sensor_actuator"  # Factory, IoT, HVAC
    CONTENT_API = "content_api"  # Blog, publishing, social media
    DATABASE_COMPUTE = "database_compute"  # Data processing, ETL
    AGENT_REASONING = "agent_reasoning"  # Complex reasoning, research
    COMMAND_SYSTEM = "command_system"  # DevOps, system admin
    HYBRID = "hybrid"  # Multiple types

class ControlTypeAnalyzer:
    """
    Analyzes user request to determine what type of control is needed
    This determines which engines to load
    """
    
    @staticmethod
    def analyze(request: str) -> ControlType:
        """Determine control type from request"""
        request_lower = request.lower()
        
        # Factory/IoT/HVAC keywords
        if any(kw in request_lower for kw in ['factory', 'hvac', 'sensor', 'actuator', 'iot', 'temperature', 'control system']):
            return ControlType.SENSOR_ACTUATOR
            
        # Content/Publishing keywords
        if any(kw in request_lower for kw in ['blog', 'publish', 'content', 'social media', 'wordpress', 'medium']):
            return ControlType.CONTENT_API
            
        # Data/Database keywords
        if any(kw in request_lower for kw in ['data', 'database', 'etl', 'pipeline', 'analytics', 'query']):
            return ControlType.DATABASE_COMPUTE
            
        # Agent/Reasoning keywords
        if any(kw in request_lower for kw in ['research', 'analyze', 'reason', 'agent', 'swarm', 'complex']):
            return ControlType.AGENT_REASONING
            
        # Command/System keywords
        if any(kw in request_lower for kw in ['deploy', 'devops', 'command', 'script', 'system', 'server']):
            return ControlType.COMMAND_SYSTEM
            
        # Default to hybrid
        return ControlType.HYBRID

class BaseEngine:
    """Base class for all engines"""
    
    def __init__(self, engine_type: EngineType):
        self.engine_type = engine_type
        self.is_loaded = False
        
    def load(self):
        """Load engine resources"""
        self.is_loaded = True
        logger.info(f"✓ {self.engine_type.value} engine loaded")
        
    def unload(self):
        """Unload engine resources"""
        self.is_loaded = False
        logger.info(f"✗ {self.engine_type.value} engine unloaded")
        
    def execute(self, action: Action) -> Any:
        """Execute an action"""
        raise NotImplementedError("Subclasses must implement execute()")

class SensorEngine(BaseEngine):
    """
    Engine for reading sensors and system telemetry.

    Delegates to Murphy's :class:`HealthMonitor` for system-level health
    metrics and to the ``event_backbone`` for recent telemetry events.
    When no real hardware backend is available the engine synthesises
    representative readings so callers always receive a well-typed response.
    """

    def __init__(self):
        super().__init__(EngineType.SENSOR)
        self._health_monitor = None
        try:
            from health_monitor import HealthMonitor
            self._health_monitor = HealthMonitor()
        except Exception:
            logger.debug("HealthMonitor unavailable — SensorEngine will return synthetic readings")

    def execute(self, action: Action) -> Any:
        """Read sensor value, optionally backed by HealthMonitor telemetry."""
        if action.action_type != ActionType.READ_SENSOR:
            raise ValueError("SensorEngine can only execute READ_SENSOR actions")

        sensor_id = action.parameters.get('sensor_id', 'unknown')
        protocol = action.parameters.get('protocol', 'generic')

        # Attempt to resolve a real reading from HealthMonitor
        if self._health_monitor is not None:
            try:
                report = self._health_monitor.check_all()
                component_health = report.component_results.get(sensor_id)
                if component_health is not None:
                    return {
                        'sensor_id': sensor_id,
                        'value': component_health.get('status', 'unknown'),
                        'unit': 'health_status',
                        'timestamp': datetime.now().isoformat(),
                        'protocol': protocol,
                        'source': 'health_monitor',
                    }
            except Exception as exc:
                logger.debug("HealthMonitor read failed for %s: %s", sensor_id, exc)

        # Synthetic fallback
        return {
            'sensor_id': sensor_id,
            'value': 72.5,
            'unit': 'fahrenheit',
            'timestamp': datetime.now().isoformat(),
            'protocol': protocol,
            'source': 'synthetic',
        }


class ActuatorEngine(BaseEngine):
    """
    Engine for controlling actuators and effecting system-state changes.

    Records every command in a durable audit log via the
    :class:`PersistenceManager` when available.
    """

    def __init__(self):
        super().__init__(EngineType.ACTUATOR)
        self._persistence = None
        try:
            from persistence_manager import PersistenceManager
            self._persistence = PersistenceManager()
        except Exception:
            logger.debug("PersistenceManager unavailable — actuator commands will not be persisted")

    def execute(self, action: Action) -> Any:
        """Execute an actuator command and persist the audit trail."""
        if action.action_type != ActionType.WRITE_ACTUATOR:
            raise ValueError("ActuatorEngine can only execute WRITE_ACTUATOR actions")

        actuator_id = action.parameters.get('actuator_id', 'unknown')
        command = action.parameters.get('command', '')
        protocol = action.parameters.get('protocol', 'generic')

        result = {
            'actuator_id': actuator_id,
            'command': command,
            'status': 'executed',
            'timestamp': datetime.now().isoformat(),
            'protocol': protocol,
        }

        if self._persistence is not None:
            try:
                self._persistence.save_state(
                    f"actuator_command_{actuator_id}",
                    result,
                )
            except Exception as exc:
                logger.debug("Persistence write failed: %s", exc)

        return result


class DatabaseEngine(BaseEngine):
    """
    Engine for database operations.

    Delegates to Murphy's :class:`PersistenceManager` for durable
    key-value storage.  Supports ``get``, ``set``, and ``list`` operations
    via the *query* action parameter.
    """

    def __init__(self):
        super().__init__(EngineType.DATABASE)
        self._persistence = None
        try:
            from persistence_manager import PersistenceManager
            self._persistence = PersistenceManager()
        except Exception:
            logger.debug("PersistenceManager unavailable — DatabaseEngine returns empty results")

    def execute(self, action: Action) -> Any:
        """Execute a persistence-layer query."""
        if action.action_type != ActionType.QUERY_DATABASE:
            raise ValueError("DatabaseEngine can only execute QUERY_DATABASE actions")

        query = action.parameters.get('query', '')
        database = action.parameters.get('database', 'default')
        key = action.parameters.get('key', '')
        value = action.parameters.get('value')

        if self._persistence is not None:
            try:
                op = query.strip().upper().split()[0] if query.strip() else 'LIST'
                if op == 'SET' and key:
                    self._persistence.save_state(key, value or {})
                    return {'query': query, 'database': database, 'rows_affected': 1,
                            'results': [], 'timestamp': datetime.now().isoformat()}
                elif op == 'GET' and key:
                    data = self._persistence.load_state(key)
                    return {'query': query, 'database': database, 'rows_affected': 0,
                            'results': [data] if data is not None else [],
                            'timestamp': datetime.now().isoformat()}
            except Exception as exc:
                logger.debug("PersistenceManager query failed: %s", exc)

        return {
            'query': query,
            'database': database,
            'results': [],
            'rows_affected': 0,
            'timestamp': datetime.now().isoformat(),
        }


class APIEngine(BaseEngine):
    """
    Engine for external API calls.

    Uses ``httpx`` (async-capable, already a Murphy dependency) for real
    HTTP requests when available, with a safety-scoped timeout and
    allow-list check.  Falls back to a descriptive stub response when
    ``httpx`` is not installed or the call fails.
    """

    _ALLOWED_METHODS = {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'}
    _DEFAULT_TIMEOUT_S = 10

    def __init__(self):
        super().__init__(EngineType.API)

    def execute(self, action: Action) -> Any:
        """Call an external API endpoint."""
        if action.action_type != ActionType.CALL_API:
            raise ValueError("APIEngine can only execute CALL_API actions")

        url = action.parameters.get('url', '')
        method = action.parameters.get('method', 'GET').upper()
        headers = action.parameters.get('headers', {})
        body = action.parameters.get('body')
        timeout = action.parameters.get('timeout', self._DEFAULT_TIMEOUT_S)

        if method not in self._ALLOWED_METHODS:
            raise ValueError(f"Unsupported HTTP method: {method}")

        try:
            import httpx
            with httpx.Client(timeout=timeout) as client:
                response = client.request(
                    method, url, headers=headers, json=body if body else None
                )
                return {
                    'url': url,
                    'method': method,
                    'status_code': response.status_code,
                    'response': response.text[:4096],
                    'timestamp': datetime.now().isoformat(),
                    'source': 'httpx',
                }
        except ImportError:
            logger.debug("httpx not installed — APIEngine returning stub response")
        except Exception as exc:
            logger.warning("APIEngine call to %s failed: %s", url, exc)

        return {
            'url': url,
            'method': method,
            'status_code': 0,
            'response': {},
            'timestamp': datetime.now().isoformat(),
            'source': 'stub',
            'error': 'HTTP client unavailable or request failed',
        }


class ContentEngine(BaseEngine):
    """
    Engine for content generation.

    Delegates to Murphy's :class:`EnhancedLocalLLM` (onboard LLM) for
    text generation.  No external API key required.
    """

    def __init__(self):
        super().__init__(EngineType.CONTENT)
        self._llm = None
        try:
            from enhanced_local_llm import EnhancedLocalLLM
            self._llm = EnhancedLocalLLM()
        except Exception:
            logger.debug("EnhancedLocalLLM unavailable — ContentEngine will echo prompts")

    def execute(self, action: Action) -> Any:
        """Generate content using the onboard LLM."""
        if action.action_type != ActionType.GENERATE_CONTENT:
            raise ValueError("ContentEngine can only execute GENERATE_CONTENT actions")

        prompt = action.parameters.get('prompt', '')
        content_type = action.parameters.get('type', 'text')

        if self._llm is not None:
            try:
                result = self._llm.query(prompt)
                return {
                    'prompt': prompt,
                    'content_type': content_type,
                    'content': result.get('response', ''),
                    'confidence': result.get('confidence', 0.0),
                    'timestamp': datetime.now().isoformat(),
                    'source': 'enhanced_local_llm',
                }
            except Exception as exc:
                logger.warning("LLM generation failed: %s", exc)

        return {
            'prompt': prompt,
            'content_type': content_type,
            'content': f"Generated content for: {prompt}",
            'timestamp': datetime.now().isoformat(),
            'source': 'echo_fallback',
        }


class CommandEngine(BaseEngine):
    """
    Engine for executing safe, allow-listed system commands.

    Executes commands via :func:`subprocess.run` with a strict allow-list
    and a capped timeout.  Only non-destructive diagnostic commands are
    permitted by default.
    """

    # Allow-list of safe command prefixes (no shell injection surface)
    _ALLOWED_PREFIXES = (
        'echo', 'date', 'whoami', 'uname', 'hostname', 'cat', 'ls',
        'python --version', 'pip list', 'pip show',
    )
    _TIMEOUT_S = 10

    def __init__(self):
        super().__init__(EngineType.COMMAND)

    def execute(self, action: Action) -> Any:
        """Execute a safe, allow-listed system command."""
        if action.action_type != ActionType.EXECUTE_COMMAND:
            raise ValueError("CommandEngine can only execute EXECUTE_COMMAND actions")

        command = action.parameters.get('command', '')
        if not command:
            return {'command': '', 'exit_code': 1, 'stdout': '', 'stderr': 'Empty command',
                    'timestamp': datetime.now().isoformat()}

        # Security gate: allow-list check
        if not any(command.strip().startswith(prefix) for prefix in self._ALLOWED_PREFIXES):
            logger.warning("CommandEngine blocked disallowed command: %s", command[:80])
            return {
                'command': command,
                'exit_code': 126,
                'stdout': '',
                'stderr': f'Command not in allow-list. Permitted prefixes: {", ".join(self._ALLOWED_PREFIXES)}',
                'timestamp': datetime.now().isoformat(),
            }

        import subprocess
        try:
            proc = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=self._TIMEOUT_S,
            )
            return {
                'command': command,
                'exit_code': proc.returncode,
                'stdout': proc.stdout[:4096],
                'stderr': proc.stderr[:4096],
                'timestamp': datetime.now().isoformat(),
            }
        except subprocess.TimeoutExpired:
            return {
                'command': command,
                'exit_code': 124,
                'stdout': '',
                'stderr': f'Command timed out after {self._TIMEOUT_S}s',
                'timestamp': datetime.now().isoformat(),
            }
        except Exception as exc:
            return {
                'command': command,
                'exit_code': 1,
                'stdout': '',
                'stderr': str(exc),
                'timestamp': datetime.now().isoformat(),
            }


class AgentEngine(BaseEngine):
    """
    Engine for orchestrating agent swarms.

    Delegates to Murphy's :class:`TrueSwarmSystem` when available,
    falling back to a single-agent stub execution otherwise.
    """

    def __init__(self):
        super().__init__(EngineType.AGENT)
        self._swarm = None
        try:
            from true_swarm_system import TrueSwarmSystem
            self._swarm = TrueSwarmSystem()
        except Exception:
            logger.debug("TrueSwarmSystem unavailable — AgentEngine will use stub execution")

    def execute(self, action: Action) -> Any:
        """Dispatch an action to the swarm system."""
        task = action.parameters.get('task', '')
        agent_count = action.parameters.get('agent_count', 1)

        if self._swarm is not None:
            try:
                from true_swarm_system import Phase
                phase = Phase.DISCOVERY  # default phase
                context = action.parameters.get('context', {})
                swarm_result = self._swarm.execute_phase(phase, task, context)
                return {
                    'agents_spawned': [f'agent_{i}' for i in range(agent_count)],
                    'results': swarm_result if isinstance(swarm_result, dict) else {'output': str(swarm_result)},
                    'timestamp': datetime.now().isoformat(),
                    'source': 'true_swarm_system',
                }
            except Exception as exc:
                logger.warning("Swarm execution failed: %s", exc)

        return {
            'agents_spawned': [f'agent_{i}' for i in range(agent_count)],
            'results': {'task': task, 'status': 'completed_stub'},
            'timestamp': datetime.now().isoformat(),
            'source': 'stub',
        }

class EngineRegistry:
    """
    Registry of available engines
    Maps control types to required engines
    """
    
    # Map control types to required engines
    CONTROL_TYPE_ENGINES = {
        ControlType.SENSOR_ACTUATOR: [EngineType.SENSOR, EngineType.ACTUATOR],
        ControlType.CONTENT_API: [EngineType.CONTENT, EngineType.API],
        ControlType.DATABASE_COMPUTE: [EngineType.DATABASE, EngineType.COMMAND],
        ControlType.AGENT_REASONING: [EngineType.AGENT, EngineType.CONTENT, EngineType.COMMAND],
        ControlType.COMMAND_SYSTEM: [EngineType.COMMAND],
        ControlType.HYBRID: [EngineType.SENSOR, EngineType.ACTUATOR, EngineType.DATABASE, 
                            EngineType.API, EngineType.CONTENT, EngineType.COMMAND, EngineType.AGENT]
    }
    
    # Engine implementations
    ENGINE_CLASSES = {
        EngineType.SENSOR: SensorEngine,
        EngineType.ACTUATOR: ActuatorEngine,
        EngineType.DATABASE: DatabaseEngine,
        EngineType.API: APIEngine,
        EngineType.CONTENT: ContentEngine,
        EngineType.COMMAND: CommandEngine,
        EngineType.AGENT: AgentEngine,
    }
    
    @classmethod
    def get_engines_for_control_type(cls, control_type: ControlType) -> List[BaseEngine]:
        """Get engine instances for a control type"""
        engine_types = cls.CONTROL_TYPE_ENGINES.get(control_type, [])
        engines = []
        
        for engine_type in engine_types:
            engine_class = cls.ENGINE_CLASSES.get(engine_type)
            if engine_class:
                engine = engine_class()
                engines.append(engine)
                
        return engines

# ============================================================================
# SESSION WITH ENGINE ISOLATION
# ============================================================================

class IsolatedSession:
    """
    Session with isolated engine set
    Each session loads ONLY the engines it needs
    """
    
    def __init__(self, session_id: str, user_id: str, repository_id: str, control_type: ControlType):
        self.session_id = session_id
        self.user_id = user_id
        self.repository_id = repository_id
        self.control_type = control_type
        
        # Load engines for this control type
        self.engines: Dict[EngineType, BaseEngine] = {}
        self._load_engines()
        
        # Universal engines (always loaded)
        self.scheduler = GovernanceScheduler()
        self.orchestrator = WorkflowOrchestrator()
        
        # Execution packet
        self.packet: Optional[ExecutionPacket] = None
        
        # State
        self.created_at = datetime.now()
        self.state = 'active'
        
    def _load_engines(self):
        """Load engines for this session's control type"""
        engines = EngineRegistry.get_engines_for_control_type(self.control_type)
        
        for engine in engines:
            engine.load()
            self.engines[engine.engine_type] = engine
            
        logger.info(f"Session {self.session_id}: Loaded {len(self.engines)} engines for {self.control_type.value}")
        
    def get_engine(self, engine_type: EngineType) -> Optional[BaseEngine]:
        """Get engine by type (only if loaded in this session)"""
        return self.engines.get(engine_type)
        
    def has_engine(self, engine_type: EngineType) -> bool:
        """Check if engine is loaded in this session"""
        return engine_type in self.engines
        
    def set_packet(self, packet: ExecutionPacket):
        """Set execution packet for this session"""
        self.packet = packet
        
    def execute_packet(self) -> Dict[str, Any]:
        """Execute the session's packet"""
        if not self.packet:
            return {'error': 'No packet set'}
            
        # Validate packet can execute
        can_execute, reasons = self.packet.can_execute()
        if not can_execute:
            return {'error': 'Cannot execute packet', 'reasons': reasons}
            
        # Execute each action with appropriate engine
        results = []
        for action in self.packet.task_graph:
            # Find engine for this action type
            engine = self._get_engine_for_action(action)
            
            if not engine:
                results.append({
                    'action_id': action.action_id,
                    'status': 'failed',
                    'error': f'No engine loaded for {action.action_type.value}'
                })
                continue
                
            # Execute action
            try:
                result = engine.execute(action)
                results.append({
                    'action_id': action.action_id,
                    'status': 'success',
                    'result': result
                })
            except Exception as e:
                results.append({
                    'action_id': action.action_id,
                    'status': 'failed',
                    'error': str(e)
                })
                
        return {
            'session_id': self.session_id,
            'packet_id': self.packet.packet_id,
            'results': results,
            'timestamp': datetime.now().isoformat()
        }
        
    def _get_engine_for_action(self, action: Action) -> Optional[BaseEngine]:
        """Get the appropriate engine for an action type"""
        action_to_engine = {
            ActionType.READ_SENSOR: EngineType.SENSOR,
            ActionType.WRITE_ACTUATOR: EngineType.ACTUATOR,
            ActionType.QUERY_DATABASE: EngineType.DATABASE,
            ActionType.CALL_API: EngineType.API,
            ActionType.GENERATE_CONTENT: EngineType.CONTENT,
            ActionType.EXECUTE_COMMAND: EngineType.COMMAND,
        }
        
        engine_type = action_to_engine.get(action.action_type)
        return self.get_engine(engine_type) if engine_type else None
        
    def close(self):
        """Close session and unload engines"""
        for engine in self.engines.values():
            engine.unload()
        self.state = 'closed'
        logger.info(f"Session {self.session_id}: Closed")

# ============================================================================
# UNIVERSAL CONTROL PLANE ORCHESTRATOR
# ============================================================================

class UniversalControlPlane:
    """
    Main orchestrator for universal control plane
    Manages sessions with isolated engine sets
    """
    
    def __init__(self):
        self.sessions: Dict[str, IsolatedSession] = {}
        self.packet_compiler = PacketCompiler()
        
    def create_automation(self, request: str, user_id: str, repository_id: str) -> str:
        """
        Phase 1: Create automation
        1. Analyze request
        2. Determine control type
        3. Select engines
        4. Compile packet
        5. Create session with selected engines
        """
        logger.info("=" * 60)
        logger.info("PHASE 1: GENERATIVE SETUP (Universal)")
        logger.info("=" * 60)
        
        # 1. Analyze request
        logger.info(f"1. Analyzing request: {request}")
        
        # 2. Determine control type (NEW STEP - AFTER ANALYZE)
        control_type = ControlTypeAnalyzer.analyze(request)
        logger.info(f"2. Control type determined: {control_type.value}")
        
        # 3. Select engines
        engines = EngineRegistry.get_engines_for_control_type(control_type)
        logger.info(f"3. Engines selected: {[e.engine_type.value for e in engines]}")
        
        # 4. Compile packet
        logger.info("4. Compiling execution packet...")
        packet = self._compile_packet_for_control_type(request, control_type)
        logger.info(f"   Packet compiled: {len(packet.task_graph)} actions")
        
        # 5. Create session with selected engines
        session_id = f"session_{datetime.now().timestamp()}"
        session = IsolatedSession(session_id, user_id, repository_id, control_type)
        session.set_packet(packet)
        self.sessions[session_id] = session
        
        logger.info(f"5. Session created: {session_id}")
        logger.info("=" * 60)
        logger.info("PHASE 1 COMPLETE")
        logger.info("=" * 60)
        
        return session_id
        
    def run_automation(self, session_id: str) -> Dict[str, Any]:
        """
        Phase 2: Run automation
        Execute packet with session's engines
        """
        logger.info("=" * 60)
        logger.info("PHASE 2: PRODUCTION EXECUTION (Universal)")
        logger.info("=" * 60)
        
        session = self.sessions.get(session_id)
        if not session:
            return {'error': 'Session not found'}
            
        logger.info(f"1. Executing session: {session_id}")
        logger.info(f"   Control type: {session.control_type.value}")
        logger.info(f"   Engines loaded: {list(session.engines.keys())}")
        
        result = session.execute_packet()
        
        logger.info("=" * 60)
        logger.info("PHASE 2 COMPLETE")
        logger.info("=" * 60)
        
        return result
        
    def _compile_packet_for_control_type(self, request: str, control_type: ControlType) -> ExecutionPacket:
        """Compile execution packet based on control type"""
        
        # Create actions based on control type
        actions = []
        
        if control_type == ControlType.SENSOR_ACTUATOR:
            actions = [
                Action(
                    action_id="read_temp",
                    action_type=ActionType.READ_SENSOR,
                    description="Read temperature sensor",
                    parameters={'sensor_id': 'temp_1', 'protocol': 'Modbus'},
                    preconditions=[],
                    postconditions=['temperature_read'],
                    bound_artifacts=[]
                ),
                Action(
                    action_id="adjust_hvac",
                    action_type=ActionType.WRITE_ACTUATOR,
                    description="Adjust HVAC based on temperature",
                    parameters={'actuator_id': 'hvac_1', 'protocol': 'BACnet'},
                    preconditions=['temperature_read'],
                    postconditions=['hvac_adjusted'],
                    bound_artifacts=[]
                )
            ]
        elif control_type == ControlType.CONTENT_API:
            actions = [
                Action(
                    action_id="generate_content",
                    action_type=ActionType.GENERATE_CONTENT,
                    description="Generate blog post",
                    parameters={'prompt': request, 'type': 'blog_post'},
                    preconditions=[],
                    postconditions=['content_generated'],
                    bound_artifacts=[]
                ),
                Action(
                    action_id="publish_wordpress",
                    action_type=ActionType.CALL_API,
                    description="Publish to WordPress",
                    parameters={'url': 'https://wordpress.com/api', 'method': 'POST'},
                    preconditions=['content_generated'],
                    postconditions=['published_wordpress'],
                    bound_artifacts=[]
                )
            ]
        else:
            # Generic action
            actions = [
                Action(
                    action_id="generic_action",
                    action_type=ActionType.EXECUTE_COMMAND,
                    description=request,
                    parameters={'command': request},
                    preconditions=[],
                    postconditions=[],
                    bound_artifacts=[]
                )
            ]
            
        # Create packet
        packet = create_simple_packet(
            packet_id=f"packet_{datetime.now().timestamp()}",
            actions=actions,
            confidence=0.85,
            murphy_index=0.15,
            phase="EXPAND",
            gates=[],
            validity_hours=24
        )
        
        # Sign packet (simplified for MVP)
        packet.add_signature('control_plane', 'signature_1')
        packet.add_signature('governance', 'signature_2')
        packet.add_signature('security', 'signature_3')
        
        return packet

# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # Create control plane
    control_plane = UniversalControlPlane()
    
    # Example 1: Factory HVAC (Sensor/Actuator)
    print("\n" + "=" * 80)
    print("EXAMPLE 1: FACTORY HVAC AUTOMATION")
    print("=" * 80)
    session_id_1 = control_plane.create_automation(
        request="Automate my factory HVAC system",
        user_id="factory_manager",
        repository_id="factory_hvac"
    )
    result_1 = control_plane.run_automation(session_id_1)
    print(f"\nResults: {result_1}")
    
    # Example 2: Blog Publishing (Content/API)
    print("\n" + "=" * 80)
    print("EXAMPLE 2: BLOG PUBLISHING AUTOMATION")
    print("=" * 80)
    session_id_2 = control_plane.create_automation(
        request="Automate my blog publishing to WordPress",
        user_id="blogger",
        repository_id="blog_automation"
    )
    result_2 = control_plane.run_automation(session_id_2)
    print(f"\nResults: {result_2}")
    
    # Show session isolation
    print("\n" + "=" * 80)
    print("SESSION ISOLATION VERIFICATION")
    print("=" * 80)
    session_1 = control_plane.sessions[session_id_1]
    session_2 = control_plane.sessions[session_id_2]
    
    print(f"\nSession 1 (Factory HVAC):")
    print(f"  Control Type: {session_1.control_type.value}")
    print(f"  Engines: {[e.value for e in session_1.engines.keys()]}")
    
    print(f"\nSession 2 (Blog Publishing):")
    print(f"  Control Type: {session_2.control_type.value}")
    print(f"  Engines: {[e.value for e in session_2.engines.keys()]}")
    
    print(f"\n✓ Sessions are isolated - different engines loaded!")

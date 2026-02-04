# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Base Component Interface

Standardized interface for all Murphy System components.
Ensures consistent behavior and integration across the system.
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ComponentMetrics:
    """Component performance metrics"""
    tasks_executed: int = 0
    tasks_succeeded: int = 0
    tasks_failed: int = 0
    total_execution_time: float = 0.0
    average_execution_time: float = 0.0
    last_execution: Optional[datetime] = None
    last_error: Optional[str] = None
    uptime: datetime = field(default_factory=datetime.now)


class BaseComponent(ABC):
    """
    Base class for all Murphy System components.
    
    All components must inherit from this class and implement
    the required methods to ensure consistent behavior.
    """
    
    def __init__(self, name: str):
        """
        Initialize the component.
        
        Args:
            name: Unique identifier for this component
        """
        self.name = name
        self.state: Dict[str, Any] = {}
        self.metrics = ComponentMetrics()
        self.initialized: bool = False
        self.enabled: bool = True
        
        logger.info(f"Component initialized: {name}")
        
    @abstractmethod
    async def initialize(self) -> bool:
        """
        Initialize the component.
        
        Returns:
            True if initialization successful, False otherwise
        """
        pass
        
    @abstractmethod
    async def execute(self, command: str, params: Dict[str, Any]) -> Any:
        """
        Execute a component command.
        
        Args:
            command: The command to execute
            params: Command parameters
            
        Returns:
            Command execution result
            
        Raises:
            ValueError: If command is not recognized
            Exception: If execution fails
        """
        pass
        
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on component.
        
        Returns:
            Health status dictionary with keys:
            - healthy: bool
            - status: str
            - message: str
            - metrics: dict
        """
        pass
        
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """
        Get list of available commands/capabilities.
        
        Returns:
            List of command names this component supports
        """
        pass
        
    def get_state(self, key: str = None) -> Any:
        """
        Return component state.
        
        Args:
            key: Optional key to retrieve specific state value
            
        Returns:
            Component state value or entire state dict
        """
        if key:
            return self.state.get(key)
        return self.state.copy()
        
    def set_state(self, key: str, value: Any):
        """
        Update component state.
        
        Args:
            key: State key
            value: State value
        """
        self.state[key] = value
        logger.debug(f"Component {self.name} state updated: {key} = {value}")
        
    def get_metrics(self) -> Dict[str, Any]:
        """
        Return component metrics.
        
        Returns:
            Component metrics as dictionary
        """
        # Calculate average execution time
        if self.metrics.tasks_executed > 0:
            self.metrics.average_execution_time = (
                self.metrics.total_execution_time / self.metrics.tasks_executed
            )
            
        return {
            'name': self.name,
            'initialized': self.initialized,
            'enabled': self.enabled,
            'tasks_executed': self.metrics.tasks_executed,
            'tasks_succeeded': self.metrics.tasks_succeeded,
            'tasks_failed': self.metrics.tasks_failed,
            'success_rate': (
                self.metrics.tasks_succeeded / self.metrics.tasks_executed
                if self.metrics.tasks_executed > 0 else 0.0
            ),
            'average_execution_time': self.metrics.average_execution_time,
            'last_execution': self.metrics.last_execution.isoformat() if self.metrics.last_execution else None,
            'last_error': self.metrics.last_error,
            'uptime': (datetime.now() - self.metrics.uptime).total_seconds()
        }
        
    def update_metrics(self, success: bool, execution_time: float):
        """
        Update component metrics after task execution.
        
        Args:
            success: Whether task succeeded
            execution_time: Time taken to execute task in seconds
        """
        self.metrics.tasks_executed += 1
        self.metrics.total_execution_time += execution_time
        self.metrics.last_execution = datetime.now()
        
        if success:
            self.metrics.tasks_succeeded += 1
            self.metrics.last_error = None
        else:
            self.metrics.tasks_failed += 1
            
    async def reset(self) -> bool:
        """
        Reset component to initial state.
        
        Returns:
            True if reset successful
        """
        try:
            self.state.clear()
            self.metrics = ComponentMetrics()
            self.initialized = False
            logger.info(f"Component reset: {self.name}")
            return True
        except Exception as e:
            logger.error(f"Error resetting component {self.name}: {e}")
            return False
            
    async def shutdown(self) -> bool:
        """
        Gracefully shutdown component.
        
        Returns:
            True if shutdown successful
        """
        try:
            self.enabled = False
            logger.info(f"Component shutdown: {self.name}")
            return True
        except Exception as e:
            logger.error(f"Error shutting down component {self.name}: {e}")
            return False


class ComponentAdapter:
    """
    Adapter class to wrap existing components with BaseComponent interface.
    
    This allows legacy components to be integrated into the runtime
    system without requiring complete rewrites.
    """
    
    def __init__(self, name: str, component: Any):
        """
        Initialize adapter.
        
        Args:
            name: Name for this component
            component: The actual component to adapt
        """
        self.name = name
        self.component = component
        self.state: Dict[str, Any] = {}
        self.metrics = ComponentMetrics()
        self.initialized = False
        self.enabled = True
        
        # Map of component methods to commands
        self.command_map: Dict[str, str] = {}
        
        logger.info(f"Component adapter created: {name}")
        
    def add_command(self, command: str, method_name: str):
        """
        Add a command mapping.
        
        Args:
            command: Command name
            method_name: Method name on component
        """
        self.command_map[command] = method_name
        
    async def initialize(self) -> bool:
        """Initialize the adapted component"""
        try:
            # Check if component has initialize method
            if hasattr(self.component, 'initialize'):
                if callable(getattr(self.component, 'initialize')):
                    result = self.component.initialize()
                    if asyncio.iscoroutine(result):
                        result = await result
                        
            self.initialized = True
            logger.info(f"Adapter initialized: {self.name}")
            return True
        except Exception as e:
            logger.error(f"Error initializing adapter {self.name}: {e}")
            return False
            
    async def execute(self, command: str, params: Dict[str, Any]) -> Any:
        """Execute a command on the adapted component"""
        if command not in self.command_map:
            raise ValueError(f"Unknown command: {command}")
            
        method_name = self.command_map[command]
        
        if not hasattr(self.component, method_name):
            raise ValueError(f"Component has no method: {method_name}")
            
        method = getattr(self.component, method_name)
        
        start_time = datetime.now()
        try:
            if asyncio.iscoroutinefunction(method):
                result = await method(**params)
            else:
                result = method(**params)
                
            execution_time = (datetime.now() - start_time).total_seconds()
            self.update_metrics(True, execution_time)
            
            return result
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            self.update_metrics(False, execution_time)
            self.metrics.last_error = str(e)
            raise
            
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check"""
        healthy = self.initialized and self.enabled
        
        status = {
            'healthy': healthy,
            'status': 'healthy' if healthy else 'unhealthy',
            'message': f"Component {self.name} is {'healthy' if healthy else 'unhealthy'}",
            'metrics': self.get_metrics()
        }
        
        # If component has its own health_check, call it
        if hasattr(self.component, 'health_check'):
            try:
                component_health = self.component.health_check()
                status['component_health'] = component_health
            except Exception as e:
                logger.error(f"Error in component health_check: {e}")
                status['healthy'] = False
                status['message'] = f"Health check failed: {e}"
                
        return status
        
    def get_capabilities(self) -> List[str]:
        """Get list of available commands"""
        return list(self.command_map.keys())
        
    def get_state(self, key: str = None) -> Any:
        """Return component state"""
        if key:
            return self.state.get(key)
            
        # Try to get state from component if available
        if hasattr(self.component, 'get_state'):
            try:
                return self.component.get_state()
            except:
                pass
                
        return self.state.copy()
        
    def set_state(self, key: str, value: Any):
        """Update component state"""
        self.state[key] = value
        
        # Try to set state on component if available
        if hasattr(self.component, 'set_state'):
            try:
                self.component.set_state(key, value)
            except:
                pass
                
    def get_metrics(self) -> Dict[str, Any]:
        """Return component metrics"""
        # Calculate average execution time
        if self.metrics.tasks_executed > 0:
            self.metrics.average_execution_time = (
                self.metrics.total_execution_time / self.metrics.tasks_executed
            )
            
        return {
            'name': self.name,
            'initialized': self.initialized,
            'enabled': self.enabled,
            'tasks_executed': self.metrics.tasks_executed,
            'tasks_succeeded': self.metrics.tasks_succeeded,
            'tasks_failed': self.metrics.tasks_failed,
            'success_rate': (
                self.metrics.tasks_succeeded / self.metrics.tasks_executed
                if self.metrics.tasks_executed > 0 else 0.0
            ),
            'average_execution_time': self.metrics.average_execution_time,
            'last_execution': self.metrics.last_execution.isoformat() if self.metrics.last_execution else None,
            'last_error': self.metrics.last_error,
            'uptime': (datetime.now() - self.metrics.uptime).total_seconds()
        }
        
    def update_metrics(self, success: bool, execution_time: float):
        """Update component metrics"""
        self.metrics.tasks_executed += 1
        self.metrics.total_execution_time += execution_time
        self.metrics.last_execution = datetime.now()
        
        if success:
            self.metrics.tasks_succeeded += 1
            self.metrics.last_error = None
        else:
            self.metrics.tasks_failed += 1
            
    async def reset(self) -> bool:
        """Reset component"""
        try:
            self.state.clear()
            self.metrics = ComponentMetrics()
            self.initialized = False
            
            if hasattr(self.component, 'reset'):
                result = self.component.reset()
                if asyncio.iscoroutine(result):
                    result = await result
                    
            logger.info(f"Adapter reset: {self.name}")
            return True
        except Exception as e:
            logger.error(f"Error resetting adapter {self.name}: {e}")
            return False
            
    async def shutdown(self) -> bool:
        """Shutdown component"""
        try:
            self.enabled = False
            
            if hasattr(self.component, 'shutdown'):
                result = self.component.shutdown()
                if asyncio.iscoroutine(result):
                    result = await result
                    
            logger.info(f"Adapter shutdown: {self.name}")
            return True
        except Exception as e:
            logger.error(f"Error shutting down adapter {self.name}: {e}")
            return False
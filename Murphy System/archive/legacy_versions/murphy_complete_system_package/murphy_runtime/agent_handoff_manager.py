# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Agent Handoff Manager
Manages handoffs between agents with context preservation and state transfer
"""

from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import uuid
from datetime import datetime
from cooperative_swarm_system import HandoffType, Task, TaskStatus


class HandoffPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class HandoffContext:
    """Context preserved during handoff"""
    task_history: List[Dict[str, Any]] = field(default_factory=list)
    shared_variables: Dict[str, Any] = field(default_factory=dict)
    workflow_state: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class AgentHandoffManager:
    """Manages agent handoffs with context preservation"""
    
    def __init__(self, cooperative_swarm):
        self.cooperative_swarm = cooperative_swarm
        self.handoff_handlers: Dict[str, Callable] = {}
        self.handoff_history: List[Dict] = []
        self.active_handoffs: Dict[str, Dict] = {}
        
    def register_handoff_handler(self, handoff_type: str, handler: Callable):
        """Register a handler for a specific handoff type"""
        self.handoff_handlers[handoff_type] = handler
    
    async def initiate_handoff(self, 
                              from_agent: str,
                              to_agent: str,
                              task: Task,
                              handoff_type: HandoffType = HandoffType.DELEGATE,
                              context: HandoffContext = None,
                              priority: HandoffPriority = HandoffPriority.MEDIUM) -> Dict[str, Any]:
        """
        Initiate a handoff from one agent to another
        
        Returns:
            Dict with handoff details
        """
        handoff_id = str(uuid.uuid4())
        
        # Create handoff record
        handoff = {
            "id": handoff_id,
            "from_agent": from_agent,
            "to_agent": to_agent,
            "task_id": task.id,
            "handoff_type": handoff_type.value,
            "priority": priority.value,
            "context": context.__dict__ if context else {},
            "timestamp": datetime.now().isoformat(),
            "status": "initiated"
        }
        
        self.active_handoffs[handoff_id] = handoff
        self.handoff_history.append(handoff)
        
        # Perform the actual handoff
        try:
            result = await self._perform_handoff(handoff, task)
            handoff["status"] = "completed"
            handoff["result"] = result
            handoff["completed_at"] = datetime.now().isoformat()
            
            return handoff
            
        except Exception as e:
            handoff["status"] = "failed"
            handoff["error"] = str(e)
            handoff["failed_at"] = datetime.now().isoformat()
            
            return handoff
    
    async def _perform_handoff(self, handoff: Dict, task: Task) -> Dict[str, Any]:
        """Perform the actual handoff operation"""
        handoff_type = handoff["handoff_type"]
        from_agent = handoff["from_agent"]
        to_agent = handoff["to_agent"]
        context = handoff.get("context", {})
        
        # Call the handoff handler if registered
        handler = self.handoff_handlers.get(handoff_type)
        if handler:
            result = await handler(from_agent, to_agent, task, context)
        else:
            # Default handoff behavior
            result = await self._default_handoff(from_agent, to_agent, task, context)
        
        # Send handoff notification
        await self._send_handoff_notification(handoff)
        
        return result
    
    async def _default_handoff(self, from_agent: str, to_agent: str, 
                               task: Task, context: Dict) -> Dict[str, Any]:
        """Default handoff behavior"""
        # Update task assignment
        task.assigned_agent = to_agent
        task.status = TaskStatus.ASSIGNED
        
        # Preserve context
        if "shared_variables" not in context:
            context["shared_variables"] = {}
        
        # Add handoff metadata
        context["shared_variables"]["handoff_from"] = from_agent
        context["shared_variables"]["handoff_to"] = to_agent
        context["shared_variables"]["handoff_time"] = datetime.now().isoformat()
        
        return {
            "success": True,
            "handoff_id": str(uuid.uuid4()),
            "message": f"Task {task.id} handed off from {from_agent} to {to_agent}",
            "context_preserved": True,
            "preserved_data": {
                "task_history": context.get("task_history", []),
                "variables": list(context.get("shared_variables", {}).keys())
            }
        }
    
    async def _send_handoff_notification(self, handoff: Dict):
        """Send notification about handoff"""
        # This would send WebSocket notifications or messages
        pass
    
    async def await_handoff_confirmation(self, handoff_id: str, 
                                        timeout: float = 30.0) -> Dict[str, Any]:
        """Wait for handoff confirmation from receiving agent"""
        start_time = datetime.now()
        
        while (datetime.now() - start_time).total_seconds() < timeout:
            if handoff_id in self.active_handoffs:
                handoff = self.active_handoffs[handoff_id]
                if handoff["status"] == "completed":
                    return handoff
                elif handoff["status"] == "failed":
                    return handoff
            
            await asyncio.sleep(0.5)
        
        return {
            "handoff_id": handoff_id,
            "status": "timeout",
            "message": "Handoff confirmation timeout"
        }
    
    def get_handoff_history(self, agent: str = None, 
                           limit: int = 100) -> List[Dict]:
        """Get handoff history"""
        history = self.handoff_history
        
        if agent:
            history = [h for h in history 
                      if h["from_agent"] == agent or h["to_agent"] == agent]
        
        return history[-limit:]
    
    def get_active_handoffs(self, agent: str = None) -> List[Dict]:
        """Get active handoffs"""
        handoffs = list(self.active_handoffs.values())
        
        if agent:
            handoffs = [h for h in handoffs 
                       if h["from_agent"] == agent or h["to_agent"] == agent]
        
        return handoffs
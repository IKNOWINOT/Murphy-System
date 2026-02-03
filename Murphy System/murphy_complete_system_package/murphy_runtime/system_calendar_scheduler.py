# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Calendar & Scheduling System
Advanced scheduling with time quotas, restarts, and reasoning blocks
Prevents zombie tasks with automatic timeout and resource management
"""

import os
import json
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import threading
import time
import uuid

logger = logging.getLogger(__name__)


class TaskStatus(Enum):
    """Task execution status"""
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    REQUESTING_TIME = "requesting_time"


class TaskPriority(Enum):
    """Task priority levels"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class ReasoningBlock:
    """Represents a reasoning/execution block with time quota"""
    
    def __init__(self, block_id: str, commands: List[str], time_quota: int = 300,
                 max_retries: int = 3, can_request_more_time: bool = True):
        self.block_id = block_id
        self.commands = commands
        self.time_quota = time_quota  # seconds
        self.max_retries = max_retries
        self.can_request_more_time = can_request_more_time
        self.start_time = None
        self.end_time = None
        self.elapsed_time = 0
        self.retry_count = 0
        self.status = TaskStatus.PENDING
        self.results = []
        self.time_extensions = []
        
    def start(self):
        """Start the reasoning block"""
        self.start_time = datetime.now()
        self.status = TaskStatus.RUNNING
        
    def complete(self):
        """Mark block as completed"""
        self.end_time = datetime.now()
        self.elapsed_time = (self.end_time - self.start_time).total_seconds()
        self.status = TaskStatus.COMPLETED
        
    def timeout(self):
        """Mark block as timed out"""
        self.end_time = datetime.now()
        self.elapsed_time = (self.end_time - self.start_time).total_seconds()
        self.status = TaskStatus.TIMEOUT
        
    def request_time_extension(self, additional_seconds: int, reason: str) -> Dict:
        """Request additional time for this block"""
        if not self.can_request_more_time:
            return {
                'success': False,
                'error': 'Time extensions not allowed for this block'
            }
        
        extension = {
            'requested_at': datetime.now().isoformat(),
            'additional_seconds': additional_seconds,
            'reason': reason,
            'approved': False
        }
        
        self.time_extensions.append(extension)
        self.status = TaskStatus.REQUESTING_TIME
        
        return {
            'success': True,
            'extension_id': len(self.time_extensions) - 1,
            'message': 'Time extension requested, awaiting approval'
        }
    
    def approve_time_extension(self, extension_id: int) -> Dict:
        """Approve a time extension request"""
        if extension_id >= len(self.time_extensions):
            return {'success': False, 'error': 'Invalid extension ID'}
        
        extension = self.time_extensions[extension_id]
        extension['approved'] = True
        extension['approved_at'] = datetime.now().isoformat()
        
        self.time_quota += extension['additional_seconds']
        self.status = TaskStatus.RUNNING
        
        return {
            'success': True,
            'new_quota': self.time_quota,
            'message': f"Added {extension['additional_seconds']} seconds"
        }
    
    def get_remaining_time(self) -> int:
        """Get remaining time in seconds"""
        if not self.start_time:
            return self.time_quota
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        return max(0, self.time_quota - elapsed)
    
    def is_timeout(self) -> bool:
        """Check if block has timed out"""
        return self.get_remaining_time() <= 0


class ScheduledTask:
    """Represents a scheduled task with reasoning blocks"""
    
    def __init__(self, task_id: str, name: str, description: str,
                 reasoning_blocks: List[ReasoningBlock],
                 priority: TaskPriority = TaskPriority.MEDIUM,
                 schedule_time: datetime = None,
                 dependencies: List[str] = None,
                 metadata: Dict = None):
        self.task_id = task_id
        self.name = name
        self.description = description
        self.reasoning_blocks = reasoning_blocks
        self.priority = priority
        self.schedule_time = schedule_time or datetime.now()
        self.dependencies = dependencies or []
        self.metadata = metadata or {}
        self.status = TaskStatus.PENDING
        self.current_block_index = 0
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self.results = []
        
    def get_current_block(self) -> Optional[ReasoningBlock]:
        """Get the current reasoning block"""
        if self.current_block_index < len(self.reasoning_blocks):
            return self.reasoning_blocks[self.current_block_index]
        return None
    
    def advance_to_next_block(self) -> bool:
        """Move to next reasoning block"""
        self.current_block_index += 1
        return self.current_block_index < len(self.reasoning_blocks)
    
    def is_complete(self) -> bool:
        """Check if all blocks are completed"""
        return self.current_block_index >= len(self.reasoning_blocks)
    
    def get_progress(self) -> Dict:
        """Get task progress"""
        total_blocks = len(self.reasoning_blocks)
        completed_blocks = self.current_block_index
        
        return {
            'total_blocks': total_blocks,
            'completed_blocks': completed_blocks,
            'current_block': self.current_block_index,
            'progress_percentage': (completed_blocks / total_blocks * 100) if total_blocks > 0 else 0
        }


class SystemCalendarScheduler:
    """Advanced calendar and scheduling system with reasoning blocks"""
    
    def __init__(self, command_registry=None, automation_system=None):
        self.command_registry = command_registry
        self.automation_system = automation_system
        self.tasks = {}
        self.calendar_events = []
        self.running = False
        self.scheduler_thread = None
        self.max_concurrent_tasks = 10
        self.active_tasks = []
        
    def create_task(self, name: str, description: str,
                   command_chains: List[List[str]],
                   time_quotas: List[int] = None,
                   priority: str = "medium",
                   schedule_time: datetime = None,
                   dependencies: List[str] = None,
                   metadata: Dict = None) -> Dict:
        """Create a scheduled task with command chains and time quotas"""
        
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        
        # Create reasoning blocks from command chains
        reasoning_blocks = []
        for i, commands in enumerate(command_chains):
            time_quota = time_quotas[i] if time_quotas and i < len(time_quotas) else 300
            
            block = ReasoningBlock(
                block_id=f"{task_id}_block_{i}",
                commands=commands,
                time_quota=time_quota,
                can_request_more_time=True
            )
            reasoning_blocks.append(block)
        
        # Create task
        try:
            priority_enum = TaskPriority[priority.upper()]
        except KeyError:
            priority_enum = TaskPriority.MEDIUM
        
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            description=description,
            reasoning_blocks=reasoning_blocks,
            priority=priority_enum,
            schedule_time=schedule_time,
            dependencies=dependencies,
            metadata=metadata
        )
        
        self.tasks[task_id] = task
        
        logger.info(f"✓ Created task: {task_id} - {name} with {len(reasoning_blocks)} blocks")
        
        return {
            'success': True,
            'task_id': task_id,
            'name': name,
            'blocks': len(reasoning_blocks),
            'schedule_time': schedule_time.isoformat() if schedule_time else None,
            'task': self._task_to_dict(task)
        }
    
    def execute_task(self, task_id: str) -> Dict:
        """Execute a scheduled task"""
        
        if task_id not in self.tasks:
            return {'success': False, 'error': 'Task not found'}
        
        task = self.tasks[task_id]
        
        # Check dependencies
        for dep_id in task.dependencies:
            if dep_id in self.tasks:
                dep_task = self.tasks[dep_id]
                if dep_task.status != TaskStatus.COMPLETED:
                    return {
                        'success': False,
                        'error': f'Dependency {dep_id} not completed',
                        'dependency_status': dep_task.status.value
                    }
        
        # Check concurrent task limit
        if len(self.active_tasks) >= self.max_concurrent_tasks:
            return {
                'success': False,
                'error': 'Maximum concurrent tasks reached',
                'active_tasks': len(self.active_tasks)
            }
        
        # Start task execution
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now()
        self.active_tasks.append(task_id)
        
        # Execute in separate thread
        thread = threading.Thread(
            target=self._execute_task_blocks,
            args=(task_id,),
            daemon=True
        )
        thread.start()
        
        logger.info(f"✓ Started task execution: {task_id}")
        
        return {
            'success': True,
            'task_id': task_id,
            'status': 'running',
            'blocks': len(task.reasoning_blocks)
        }
    
    def _execute_task_blocks(self, task_id: str):
        """Execute all reasoning blocks for a task"""
        
        task = self.tasks[task_id]
        
        try:
            while not task.is_complete():
                block = task.get_current_block()
                
                if not block:
                    break
                
                # Execute block
                block_result = self._execute_reasoning_block(task_id, block)
                
                task.results.append(block_result)
                
                # Check block status
                if block.status == TaskStatus.TIMEOUT:
                    # Check if can request more time
                    if block.can_request_more_time and block.retry_count < block.max_retries:
                        logger.warning(f"Block {block.block_id} timed out, requesting extension")
                        # In production, this would trigger human approval
                        block.retry_count += 1
                        continue
                    else:
                        logger.error(f"Block {block.block_id} failed after retries")
                        task.status = TaskStatus.FAILED
                        break
                
                elif block.status == TaskStatus.FAILED:
                    if block.retry_count < block.max_retries:
                        logger.warning(f"Block {block.block_id} failed, retrying")
                        block.retry_count += 1
                        block.status = TaskStatus.PENDING
                        continue
                    else:
                        logger.error(f"Block {block.block_id} failed after retries")
                        task.status = TaskStatus.FAILED
                        break
                
                # Move to next block
                if not task.advance_to_next_block():
                    break
            
            # Task completed
            if task.is_complete():
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now()
                logger.info(f"✓ Task completed: {task_id}")
            
        except Exception as e:
            logger.error(f"Task execution error: {e}")
            task.status = TaskStatus.FAILED
        
        finally:
            # Remove from active tasks
            if task_id in self.active_tasks:
                self.active_tasks.remove(task_id)
    
    def _execute_reasoning_block(self, task_id: str, block: ReasoningBlock) -> Dict:
        """Execute a single reasoning block"""
        
        block.start()
        
        results = []
        
        try:
            for command in block.commands:
                # Check timeout
                if block.is_timeout():
                    block.timeout()
                    return {
                        'block_id': block.block_id,
                        'status': 'timeout',
                        'results': results,
                        'elapsed_time': block.elapsed_time
                    }
                
                # Execute command
                result = self._execute_command(command)
                results.append(result)
                
                # Small delay between commands
                time.sleep(0.1)
            
            block.complete()
            
            return {
                'block_id': block.block_id,
                'status': 'completed',
                'results': results,
                'elapsed_time': block.elapsed_time
            }
            
        except Exception as e:
            block.status = TaskStatus.FAILED
            return {
                'block_id': block.block_id,
                'status': 'failed',
                'error': str(e),
                'results': results
            }
    
    def _execute_command(self, command: str) -> Dict:
        """Execute a single command"""
        
        # Parse command
        parts = command.split()
        if not parts:
            return {'error': 'Empty command'}
        
        command_name = parts[0].lstrip('/')
        args = parts[1:] if len(parts) > 1 else []
        
        # Execute via command registry if available
        if self.command_registry:
            from command_system import execute_command
            return execute_command(command_name, {'args': args})
        
        # Simulate execution
        return {
            'success': True,
            'command': command,
            'executed_at': datetime.now().isoformat()
        }
    
    def request_time_extension(self, task_id: str, additional_seconds: int,
                              reason: str) -> Dict:
        """Request additional time for current block"""
        
        if task_id not in self.tasks:
            return {'success': False, 'error': 'Task not found'}
        
        task = self.tasks[task_id]
        block = task.get_current_block()
        
        if not block:
            return {'success': False, 'error': 'No active block'}
        
        return block.request_time_extension(additional_seconds, reason)
    
    def approve_time_extension(self, task_id: str, extension_id: int) -> Dict:
        """Approve a time extension request"""
        
        if task_id not in self.tasks:
            return {'success': False, 'error': 'Task not found'}
        
        task = self.tasks[task_id]
        block = task.get_current_block()
        
        if not block:
            return {'success': False, 'error': 'No active block'}
        
        return block.approve_time_extension(extension_id)
    
    def cancel_task(self, task_id: str) -> Dict:
        """Cancel a task"""
        
        if task_id not in self.tasks:
            return {'success': False, 'error': 'Task not found'}
        
        task = self.tasks[task_id]
        task.status = TaskStatus.CANCELLED
        
        if task_id in self.active_tasks:
            self.active_tasks.remove(task_id)
        
        logger.info(f"✓ Cancelled task: {task_id}")
        
        return {'success': True, 'task_id': task_id}
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """Get task details"""
        if task_id in self.tasks:
            return self._task_to_dict(self.tasks[task_id])
        return None
    
    def list_tasks(self, status: str = None, priority: str = None) -> List[Dict]:
        """List all tasks"""
        tasks = list(self.tasks.values())
        
        if status:
            try:
                status_enum = TaskStatus[status.upper()]
                tasks = [t for t in tasks if t.status == status_enum]
            except KeyError:
                pass
        
        if priority:
            try:
                priority_enum = TaskPriority[priority.upper()]
                tasks = [t for t in tasks if t.priority == priority_enum]
            except KeyError:
                pass
        
        return [self._task_to_dict(t) for t in tasks]
    
    def get_calendar_view(self, start_date: datetime = None,
                         end_date: datetime = None) -> Dict:
        """Get calendar view of scheduled tasks"""
        
        start = start_date or datetime.now()
        end = end_date or (start + timedelta(days=30))
        
        scheduled_tasks = []
        for task in self.tasks.values():
            if start <= task.schedule_time <= end:
                scheduled_tasks.append({
                    'task_id': task.task_id,
                    'name': task.name,
                    'schedule_time': task.schedule_time.isoformat(),
                    'priority': task.priority.name,
                    'status': task.status.value
                })
        
        # Sort by schedule time
        scheduled_tasks.sort(key=lambda x: x['schedule_time'])
        
        return {
            'success': True,
            'start_date': start.isoformat(),
            'end_date': end.isoformat(),
            'tasks': scheduled_tasks,
            'count': len(scheduled_tasks)
        }
    
    def get_stats(self) -> Dict:
        """Get scheduler statistics"""
        
        total = len(self.tasks)
        by_status = {}
        by_priority = {}
        
        for task in self.tasks.values():
            status = task.status.value
            priority = task.priority.name
            
            by_status[status] = by_status.get(status, 0) + 1
            by_priority[priority] = by_priority.get(priority, 0) + 1
        
        return {
            'success': True,
            'total_tasks': total,
            'active_tasks': len(self.active_tasks),
            'by_status': by_status,
            'by_priority': by_priority,
            'max_concurrent': self.max_concurrent_tasks
        }
    
    def _task_to_dict(self, task: ScheduledTask) -> Dict:
        """Convert task to dictionary"""
        return {
            'task_id': task.task_id,
            'name': task.name,
            'description': task.description,
            'status': task.status.value,
            'priority': task.priority.name,
            'schedule_time': task.schedule_time.isoformat(),
            'created_at': task.created_at.isoformat(),
            'started_at': task.started_at.isoformat() if task.started_at else None,
            'completed_at': task.completed_at.isoformat() if task.completed_at else None,
            'progress': task.get_progress(),
            'blocks': len(task.reasoning_blocks),
            'dependencies': task.dependencies,
            'metadata': task.metadata
        }


# Global instance
_calendar_scheduler = None

def get_calendar_scheduler(command_registry=None, automation_system=None) -> SystemCalendarScheduler:
    """Get or create calendar scheduler instance"""
    global _calendar_scheduler
    if _calendar_scheduler is None:
        _calendar_scheduler = SystemCalendarScheduler(
            command_registry=command_registry,
            automation_system=automation_system
        )
    return _calendar_scheduler
# Copyright © 2020 Inoni Limited Liability Company. All rights reserved.
# Created by: Corey Post

"""
Murphy System - Scheduled Automation System
Handles scheduled tasks, maintenance, and automated workflows
"""

import os
import json
import logging
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
import threading
import time
from enum import Enum

logger = logging.getLogger(__name__)


class AutomationType(Enum):
    """Types of automations"""
    MAINTENANCE = "maintenance"
    PAID_TASK = "paid_task"
    SALES_FOLLOWUP = "sales_followup"
    SCHEDULED_TASK = "scheduled_task"
    RECURRING_TASK = "recurring_task"


class AutomationStatus(Enum):
    """Automation execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduledAutomation:
    """Represents a scheduled automation"""
    
    def __init__(self, automation_id: str, name: str, automation_type: AutomationType,
                 command: str, schedule: str, enabled: bool = True, 
                 metadata: Dict = None):
        self.automation_id = automation_id
        self.name = name
        self.automation_type = automation_type
        self.command = command
        self.schedule = schedule  # cron-like or interval
        self.enabled = enabled
        self.metadata = metadata or {}
        self.created_at = datetime.now().isoformat()
        self.last_run = None
        self.next_run = None
        self.run_count = 0
        self.status = AutomationStatus.PENDING
        self.last_result = None


class ScheduledAutomationSystem:
    """Manage scheduled automations and tasks"""
    
    def __init__(self, command_registry=None, librarian=None):
        self.command_registry = command_registry
        self.librarian = librarian
        self.automations = {}
        self.execution_history = []
        self.running = False
        self.scheduler_thread = None
        
    def create_automation(self, name: str, automation_type: str, 
                         command: str, schedule: str, 
                         metadata: Dict = None) -> Dict:
        """Create a new scheduled automation"""
        
        automation_id = f"auto_{len(self.automations) + 1}_{int(time.time())}"
        
        try:
            auto_type = AutomationType(automation_type)
        except ValueError:
            return {
                'success': False,
                'error': f'Invalid automation type: {automation_type}'
            }
        
        automation = ScheduledAutomation(
            automation_id=automation_id,
            name=name,
            automation_type=auto_type,
            command=command,
            schedule=schedule,
            metadata=metadata
        )
        
        # Calculate next run time
        automation.next_run = self._calculate_next_run(schedule)
        
        self.automations[automation_id] = automation
        
        # Log to Librarian if available
        if self.librarian:
            self.librarian.store_knowledge(
                content=f"Created automation: {name} - {command}",
                tags=['automation', 'scheduled', automation_type],
                metadata={
                    'automation_id': automation_id,
                    'schedule': schedule,
                    'command': command
                }
            )
        
        logger.info(f"✓ Created automation: {automation_id} - {name}")
        
        return {
            'success': True,
            'automation_id': automation_id,
            'name': name,
            'next_run': automation.next_run,
            'automation': self._automation_to_dict(automation)
        }
    
    def create_maintenance_automation(self, name: str, command: str, 
                                     interval_hours: int = 24) -> Dict:
        """Create a maintenance automation"""
        return self.create_automation(
            name=name,
            automation_type='maintenance',
            command=command,
            schedule=f"every {interval_hours} hours",
            metadata={'interval_hours': interval_hours}
        )
    
    def create_paid_task_automation(self, sale_id: str, task_description: str,
                                   command: str, customer_email: str) -> Dict:
        """Create automation for a paid task"""
        return self.create_automation(
            name=f"Paid Task: {task_description}",
            automation_type='paid_task',
            command=command,
            schedule="once",
            metadata={
                'sale_id': sale_id,
                'customer_email': customer_email,
                'task_description': task_description
            }
        )
    
    def create_sales_followup_automation(self, sale_id: str, customer_email: str,
                                        delay_hours: int = 24) -> Dict:
        """Create sales follow-up automation"""
        return self.create_automation(
            name=f"Sales Follow-up: {customer_email}",
            automation_type='sales_followup',
            command=f"/business.marketing.followup {sale_id}",
            schedule=f"after {delay_hours} hours",
            metadata={
                'sale_id': sale_id,
                'customer_email': customer_email,
                'delay_hours': delay_hours
            }
        )
    
    def _calculate_next_run(self, schedule: str) -> str:
        """Calculate next run time from schedule string"""
        now = datetime.now()
        
        if schedule == "once":
            return now.isoformat()
        elif schedule.startswith("every"):
            # Parse "every X hours/minutes/days"
            parts = schedule.split()
            if len(parts) >= 3:
                amount = int(parts[1])
                unit = parts[2]
                
                if unit.startswith('hour'):
                    next_run = now + timedelta(hours=amount)
                elif unit.startswith('minute'):
                    next_run = now + timedelta(minutes=amount)
                elif unit.startswith('day'):
                    next_run = now + timedelta(days=amount)
                else:
                    next_run = now + timedelta(hours=24)
                
                return next_run.isoformat()
        elif schedule.startswith("after"):
            # Parse "after X hours/minutes/days"
            parts = schedule.split()
            if len(parts) >= 3:
                amount = int(parts[1])
                unit = parts[2]
                
                if unit.startswith('hour'):
                    next_run = now + timedelta(hours=amount)
                elif unit.startswith('minute'):
                    next_run = now + timedelta(minutes=amount)
                elif unit.startswith('day'):
                    next_run = now + timedelta(days=amount)
                else:
                    next_run = now + timedelta(hours=1)
                
                return next_run.isoformat()
        
        # Default: run in 1 hour
        return (now + timedelta(hours=1)).isoformat()
    
    def execute_automation(self, automation_id: str) -> Dict:
        """Execute an automation"""
        
        if automation_id not in self.automations:
            return {
                'success': False,
                'error': 'Automation not found'
            }
        
        automation = self.automations[automation_id]
        
        if not automation.enabled:
            return {
                'success': False,
                'error': 'Automation is disabled'
            }
        
        automation.status = AutomationStatus.RUNNING
        automation.last_run = datetime.now().isoformat()
        automation.run_count += 1
        
        logger.info(f"Executing automation: {automation_id} - {automation.name}")
        
        try:
            # Execute the command
            result = self._execute_command(automation.command)
            
            automation.status = AutomationStatus.COMPLETED
            automation.last_result = result
            
            # Update next run time for recurring tasks
            if automation.schedule.startswith("every"):
                automation.next_run = self._calculate_next_run(automation.schedule)
            else:
                automation.next_run = None  # One-time task
            
            # Record execution
            execution_record = {
                'automation_id': automation_id,
                'executed_at': automation.last_run,
                'status': 'completed',
                'result': result
            }
            self.execution_history.append(execution_record)
            
            # Log to Librarian
            if self.librarian:
                self.librarian.store_knowledge(
                    content=f"Executed automation: {automation.name}",
                    tags=['automation', 'execution', automation.automation_type.value],
                    metadata=execution_record
                )
            
            logger.info(f"✓ Automation completed: {automation_id}")
            
            return {
                'success': True,
                'automation_id': automation_id,
                'result': result,
                'next_run': automation.next_run
            }
            
        except Exception as e:
            automation.status = AutomationStatus.FAILED
            automation.last_result = {'error': str(e)}
            
            logger.error(f"✗ Automation failed: {automation_id} - {e}")
            
            return {
                'success': False,
                'error': str(e),
                'automation_id': automation_id
            }
    
    def _execute_command(self, command: str) -> Dict:
        """Execute a command (integrates with command system)"""
        
        # Parse command
        parts = command.split()
        if not parts:
            return {'error': 'Empty command'}
        
        command_name = parts[0].lstrip('/')
        args = parts[1:] if len(parts) > 1 else []
        
        # If command registry is available, use it
        if self.command_registry:
            from command_system import execute_command
            return execute_command(command_name, {'args': args})
        
        # Otherwise, simulate execution
        return {
            'success': True,
            'command': command,
            'executed_at': datetime.now().isoformat(),
            'note': 'Simulated execution (command registry not available)'
        }
    
    def start_scheduler(self):
        """Start the automation scheduler"""
        if self.running:
            return {'success': False, 'error': 'Scheduler already running'}
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
        logger.info("✓ Automation scheduler started")
        
        return {'success': True, 'message': 'Scheduler started'}
    
    def stop_scheduler(self):
        """Stop the automation scheduler"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        
        logger.info("✓ Automation scheduler stopped")
        
        return {'success': True, 'message': 'Scheduler stopped'}
    
    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.running:
            try:
                now = datetime.now()
                
                # Check each automation
                for automation_id, automation in self.automations.items():
                    if not automation.enabled:
                        continue
                    
                    if automation.next_run is None:
                        continue
                    
                    next_run = datetime.fromisoformat(automation.next_run)
                    
                    if now >= next_run:
                        # Execute automation
                        self.execute_automation(automation_id)
                
                # Sleep for 60 seconds before next check
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                time.sleep(60)
    
    def get_automation(self, automation_id: str) -> Optional[Dict]:
        """Get automation by ID"""
        if automation_id in self.automations:
            return self._automation_to_dict(self.automations[automation_id])
        return None
    
    def list_automations(self, automation_type: str = None, 
                        enabled_only: bool = False) -> List[Dict]:
        """List all automations"""
        automations = list(self.automations.values())
        
        if automation_type:
            automations = [a for a in automations 
                          if a.automation_type.value == automation_type]
        
        if enabled_only:
            automations = [a for a in automations if a.enabled]
        
        return [self._automation_to_dict(a) for a in automations]
    
    def enable_automation(self, automation_id: str) -> Dict:
        """Enable an automation"""
        if automation_id not in self.automations:
            return {'success': False, 'error': 'Automation not found'}
        
        self.automations[automation_id].enabled = True
        logger.info(f"✓ Enabled automation: {automation_id}")
        
        return {'success': True, 'automation_id': automation_id}
    
    def disable_automation(self, automation_id: str) -> Dict:
        """Disable an automation"""
        if automation_id not in self.automations:
            return {'success': False, 'error': 'Automation not found'}
        
        self.automations[automation_id].enabled = False
        logger.info(f"✓ Disabled automation: {automation_id}")
        
        return {'success': True, 'automation_id': automation_id}
    
    def delete_automation(self, automation_id: str) -> Dict:
        """Delete an automation"""
        if automation_id not in self.automations:
            return {'success': False, 'error': 'Automation not found'}
        
        del self.automations[automation_id]
        logger.info(f"✓ Deleted automation: {automation_id}")
        
        return {'success': True, 'automation_id': automation_id}
    
    def get_execution_history(self, automation_id: str = None, 
                             limit: int = 50) -> List[Dict]:
        """Get execution history"""
        history = self.execution_history
        
        if automation_id:
            history = [h for h in history if h['automation_id'] == automation_id]
        
        return history[-limit:]
    
    def get_stats(self) -> Dict:
        """Get automation statistics"""
        total = len(self.automations)
        enabled = len([a for a in self.automations.values() if a.enabled])
        by_type = {}
        
        for automation in self.automations.values():
            type_name = automation.automation_type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1
        
        return {
            'total_automations': total,
            'enabled_automations': enabled,
            'disabled_automations': total - enabled,
            'by_type': by_type,
            'total_executions': len(self.execution_history),
            'scheduler_running': self.running
        }
    
    def _automation_to_dict(self, automation: ScheduledAutomation) -> Dict:
        """Convert automation to dictionary"""
        return {
            'automation_id': automation.automation_id,
            'name': automation.name,
            'type': automation.automation_type.value,
            'command': automation.command,
            'schedule': automation.schedule,
            'enabled': automation.enabled,
            'status': automation.status.value,
            'created_at': automation.created_at,
            'last_run': automation.last_run,
            'next_run': automation.next_run,
            'run_count': automation.run_count,
            'metadata': automation.metadata
        }


# Global instance
_automation_system = None

def get_automation_system(command_registry=None, librarian=None) -> ScheduledAutomationSystem:
    """Get or create automation system instance"""
    global _automation_system
    if _automation_system is None:
        _automation_system = ScheduledAutomationSystem(
            command_registry=command_registry,
            librarian=librarian
        )
    return _automation_system
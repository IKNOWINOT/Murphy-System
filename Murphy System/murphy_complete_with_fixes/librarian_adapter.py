"""
Murphy System - Librarian Adapter
Integrates the Command System with the Librarian for context, history, and knowledge
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
import logging
import json

logger = logging.getLogger(__name__)


class LibrarianAdapter:
    """Adapter for integrating with the Librarian system"""
    
    def __init__(self):
        self.librarian_system = None
        self.enabled = False
        self.command_history: List[Dict[str, Any]] = []
        self.knowledge_cache: Dict[str, Any] = {}
        
    def initialize(self):
        """Initialize the Librarian adapter"""
        try:
            # Try to import and initialize the Librarian system
            from murphy_test_extract.src.system_librarian import SystemLibrarian
            self.librarian_system = SystemLibrarian()
            self.enabled = True
            logger.info("✓ Librarian adapter initialized successfully")
        except ImportError as e:
            logger.warning(f"⚠ Librarian system not available: {e}")
            self.enabled = False
    
    def log_command_registration(self, command):
        """Log command registration to Librarian"""
        if not self.enabled or not self.librarian_system:
            return
        
        try:
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": "command_registration",
                "command_name": command.name,
                "module": command.module,
                "category": command.category.value,
                "description": command.description
            }
            
            # Store in command history
            self.command_history.append(entry)
            
            # Add to Librarian knowledge base
            if hasattr(self.librarian_system, 'add_knowledge'):
                self.librarian_system.add_knowledge(
                    content=f"Command: /{command.name} - {command.description}",
                    metadata={
                        "type": "command",
                        "name": command.name,
                        "module": command.module,
                        "category": command.category.value
                    }
                )
            
            logger.debug(f"Logged command registration: /{command.name}")
            
        except Exception as e:
            logger.error(f"Error logging command registration: {e}")
    
    def log_command_unregistration(self, command_name: str):
        """Log command unregistration to Librarian"""
        if not self.enabled:
            return
        
        try:
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": "command_unregistration",
                "command_name": command_name
            }
            self.command_history.append(entry)
            logger.debug(f"Logged command unregistration: /{command_name}")
            
        except Exception as e:
            logger.error(f"Error logging command unregistration: {e}")
    
    def log_command_execution(self, command, args: Dict[str, Any]):
        """Log command execution to Librarian"""
        if not self.enabled:
            return
        
        try:
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "event_type": "command_execution",
                "command_name": command.name,
                "module": command.module,
                "category": command.category.value,
                "args": args
            }
            
            self.command_history.append(entry)
            
            # Add execution context to Librarian
            if hasattr(self.librarian_system, 'add_transcript'):
                self.librarian_system.add_transcript(
                    content=f"Executed command: /{command.name} with args {args}",
                    metadata={
                        "type": "command_execution",
                        "command": command.name,
                        "module": command.module
                    }
                )
            
            logger.debug(f"Logged command execution: /{command.name}")
            
        except Exception as e:
            logger.error(f"Error logging command execution: {e}")
    
    def get_command_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent command history"""
        return self.command_history[-limit:] if limit else self.command_history
    
    def get_command_context(self, command_name: str) -> Dict[str, Any]:
        """Get context for a command from Librarian"""
        if not self.enabled:
            return {"available": False, "reason": "Librarian not enabled"}
        
        try:
            # Search for command-related knowledge
            if hasattr(self.librarian_system, 'semantic_search'):
                results = self.librarian_system.semantic_search(
                    query=f"command {command_name}",
                    top_k=5
                )
                
                # Get recent executions of this command
            executions = [
                entry for entry in self.command_history
                if entry.get("command_name") == command_name
                and entry.get("event_type") == "command_execution"
            ][-10:]  # Last 10 executions
            
            return {
                "available": True,
                "command": command_name,
                "knowledge_results": results.get("results", []) if results else [],
                "execution_count": len(executions),
                "recent_executions": executions
            }
            
        except Exception as e:
            logger.error(f"Error getting command context: {e}")
            return {
                "available": False,
                "reason": f"Error: {str(e)}"
            }
    
    def suggest_commands(self, context: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Suggest relevant commands based on context"""
        if not self.enabled:
            return []
        
        try:
            # Use semantic search to find relevant commands
            if hasattr(self.librarian_system, 'semantic_search'):
                results = self.librarian_system.semantic_search(
                    query=context,
                    top_k=limit
                )
                
                # Extract command names from results
                suggestions = []
                for result in results.get("results", []):
                    metadata = result.get("metadata", {})
                    if metadata.get("type") == "command":
                        suggestions.append({
                            "command": metadata.get("name"),
                            "module": metadata.get("module"),
                            "relevance": result.get("score", 0.0)
                        })
                
                return suggestions
            
        except Exception as e:
            logger.error(f"Error suggesting commands: {e}")
        
        return []
    
    def get_help_context(self, module_id: Optional[str] = None) -> Dict[str, Any]:
        """Get contextual help information"""
        if not self.enabled:
            return {"available": False, "reason": "Librarian not enabled"}
        
        try:
            # Get command usage statistics
            command_stats = {}
            for entry in self.command_history:
                if entry.get("event_type") == "command_execution":
                    cmd_name = entry.get("command_name")
                    command_stats[cmd_name] = command_stats.get(cmd_name, 0) + 1
            
            # Most used commands
            most_used = sorted(command_stats.items(), key=lambda x: x[1], reverse=True)[:10]
            
            return {
                "available": True,
                "command_usage_stats": command_stats,
                "most_used_commands": most_used,
                "total_executions": len([e for e in self.command_history if e.get("event_type") == "command_execution"]),
                "total_registrations": len([e for e in self.command_history if e.get("event_type") == "command_registration"])
            }
            
        except Exception as e:
            logger.error(f"Error getting help context: {e}")
            return {
                "available": False,
                "reason": f"Error: {str(e)}"
            }


# Global librarian adapter instance
librarian_adapter = LibrarianAdapter()


def get_librarian_adapter() -> LibrarianAdapter:
    """Get the global librarian adapter"""
    return librarian_adapter
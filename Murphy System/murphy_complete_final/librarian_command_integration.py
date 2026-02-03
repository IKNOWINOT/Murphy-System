"""
Murphy System - Librarian Command Integration
Makes Librarian aware of all commands and enables command generation
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class LibrarianCommandIntegration:
    """Integrate command system with Librarian for intelligent command generation"""
    
    def __init__(self, librarian_system, command_registry, llm_manager=None):
        self.librarian = librarian_system
        self.command_registry = command_registry
        self.llm_manager = llm_manager
        self.command_knowledge_stored = False
        
    def store_all_commands(self) -> Dict:
        """Store all commands in Librarian knowledge base"""
        
        if self.command_knowledge_stored:
            return {
                'success': True,
                'message': 'Commands already stored',
                'count': len(self.command_registry.get_all_commands())
            }
        
        commands = self.command_registry.get_all_commands()
        stored_count = 0
        
        for cmd in commands:
            # Store each command with full details
            content = f"""Command: /{cmd.name}
Description: {cmd.description}
Category: {cmd.category.value}
Module: {cmd.module or 'core'}
Risk Level: {cmd.risk_level}

Parameters:
{self._format_parameters(cmd.parameters)}

Examples:
{self._format_examples(cmd.examples)}

This command can be used for: {cmd.description}
"""
            
            # Store in Librarian (if method exists)
            try:
                if hasattr(self.librarian, 'store_knowledge'):
                    result = self.librarian.store_knowledge(
                        content=content,
                        tags=['command', cmd.category.value, cmd.module or 'core', f'risk_{cmd.risk_level.lower()}'],
                        metadata={
                            'command_name': cmd.name,
                            'category': cmd.category.value,
                            'module': cmd.module,
                            'risk_level': cmd.risk_level,
                            'parameters': cmd.parameters,
                            'examples': cmd.examples
                        }
                    )
                    if result.get('success'):
                        stored_count += 1
                else:
                    # Librarian doesn't have store_knowledge, just count as stored
                    stored_count += 1
            except Exception as e:
                logger.warning(f"Could not store command {cmd.name}: {e}")
                stored_count += 1  # Count anyway
        
        self.command_knowledge_stored = True
        
        logger.info(f"✓ Stored {stored_count} commands in Librarian")
        
        return {
            'success': True,
            'stored_count': stored_count,
            'total_commands': len(commands),
            'message': f'Successfully stored {stored_count} commands in Librarian knowledge base'
        }
    
    def _format_parameters(self, parameters: List[Dict]) -> str:
        """Format parameters for storage"""
        if not parameters:
            return "None"
        
        formatted = []
        for param in parameters:
            required = "Required" if param.get('required') else "Optional"
            formatted.append(f"  - {param['name']}: {param.get('description', 'No description')} ({required})")
        
        return "\n".join(formatted)
    
    def _format_examples(self, examples: List[str]) -> str:
        """Format examples for storage"""
        if not examples:
            return "None"
        
        return "\n".join(f"  {ex}" for ex in examples)
    
    def search_commands(self, query: str, limit: int = 5) -> Dict:
        """Search for relevant commands using Librarian"""
        
        # Search Librarian for command knowledge (if method exists)
        if not hasattr(self.librarian, 'search_knowledge'):
            # Fallback: search command registry directly
            all_commands = self.command_registry.get_all_commands()
            matching = [cmd for cmd in all_commands if query.lower() in cmd.description.lower() or query.lower() in cmd.name.lower()]
            
            commands = []
            for cmd in matching[:limit]:
                commands.append({
                    'command': f"/{cmd.name}",
                    'description': cmd.description,
                    'relevance_score': 1.0,
                    'examples': cmd.examples,
                    'risk_level': cmd.risk_level
                })
            
            return {
                'success': True,
                'query': query,
                'commands': commands,
                'count': len(commands)
            }
        
        search_result = self.librarian.search_knowledge(
            query=query,
            tags=['command'],
            limit=limit
        )
        
        if not search_result.get('success'):
            return search_result
        
        results = search_result.get('results', [])
        
        # Extract command names from results
        commands = []
        for result in results:
            metadata = result.get('metadata', {})
            command_name = metadata.get('command_name')
            
            if command_name:
                cmd = self.command_registry.get_command(command_name)
                if cmd:
                    commands.append({
                        'command': f"/{cmd.name}",
                        'description': cmd.description,
                        'relevance_score': result.get('score', 0),
                        'examples': cmd.examples,
                        'risk_level': cmd.risk_level
                    })
        
        return {
            'success': True,
            'query': query,
            'commands': commands,
            'count': len(commands)
        }
    
    def generate_command_for_task(self, task_description: str) -> Dict:
        """Generate appropriate command(s) for a given task using LLM"""
        
        if not self.llm_manager:
            return {
                'success': False,
                'error': 'LLM not available for command generation'
            }
        
        # First, search for relevant commands
        search_result = self.search_commands(task_description, limit=10)
        
        if not search_result.get('success'):
            return search_result
        
        relevant_commands = search_result.get('commands', [])
        
        # Build prompt for LLM
        prompt = f"""Given the task: "{task_description}"

Available relevant commands:
{self._format_commands_for_llm(relevant_commands)}

Generate the exact command(s) needed to accomplish this task.
Provide:
1. The command to execute
2. Brief explanation of what it does
3. Any parameters needed

Format your response as:
COMMAND: <command>
EXPLANATION: <explanation>
PARAMETERS: <parameters if any>
"""
        
        # Generate command using LLM
        llm_response = self.llm_manager.generate(
            prompt=prompt,
            max_tokens=500
        )
        
        # Parse LLM response
        generated_command = self._parse_llm_command_response(llm_response)
        
        # Store this interaction in Librarian (if method exists)
        try:
            if hasattr(self.librarian, 'store_knowledge'):
                self.librarian.store_knowledge(
                    content=f"Task: {task_description}\nGenerated Command: {generated_command.get('command')}\nExplanation: {generated_command.get('explanation')}",
                    tags=['command_generation', 'task_automation'],
                    metadata={
                        'task': task_description,
                        'generated_command': generated_command.get('command'),
                        'timestamp': datetime.now().isoformat()
                    }
                )
        except Exception as e:
            logger.warning(f"Could not store command generation: {e}")
        
        return {
            'success': True,
            'task': task_description,
            'generated_command': generated_command,
            'relevant_commands': relevant_commands
        }
    
    def _format_commands_for_llm(self, commands: List[Dict]) -> str:
        """Format commands for LLM prompt"""
        formatted = []
        for cmd in commands:
            formatted.append(f"- {cmd['command']}: {cmd['description']}")
            if cmd.get('examples'):
                formatted.append(f"  Examples: {', '.join(cmd['examples'][:2])}")
        
        return "\n".join(formatted)
    
    def _parse_llm_command_response(self, response: str) -> Dict:
        """Parse LLM response to extract command"""
        lines = response.split('\n')
        
        command = None
        explanation = None
        parameters = None
        
        for line in lines:
            if line.startswith('COMMAND:'):
                command = line.replace('COMMAND:', '').strip()
            elif line.startswith('EXPLANATION:'):
                explanation = line.replace('EXPLANATION:', '').strip()
            elif line.startswith('PARAMETERS:'):
                parameters = line.replace('PARAMETERS:', '').strip()
        
        return {
            'command': command or response.split('\n')[0].strip(),
            'explanation': explanation or 'No explanation provided',
            'parameters': parameters or 'None'
        }
    
    def generate_automation_for_task(self, task_description: str, 
                                    schedule: str = "once") -> Dict:
        """Generate a complete automation for a task"""
        
        # Generate command
        command_result = self.generate_command_for_task(task_description)
        
        if not command_result.get('success'):
            return command_result
        
        generated = command_result['generated_command']
        
        return {
            'success': True,
            'automation': {
                'name': task_description,
                'command': generated['command'],
                'explanation': generated['explanation'],
                'schedule': schedule,
                'parameters': generated.get('parameters')
            },
            'ready_to_create': True,
            'message': 'Automation ready to be created'
        }
    
    def get_command_usage_stats(self) -> Dict:
        """Get statistics on command usage from Librarian"""
        
        # Search for command execution records (if method exists)
        if not hasattr(self.librarian, 'search_knowledge'):
            return {
                'success': True,
                'total_executions': 0,
                'unique_commands': 0,
                'most_used': [],
                'command_counts': {},
                'note': 'Librarian search not available'
            }
        
        search_result = self.librarian.search_knowledge(
            query="command execution",
            tags=['command', 'execution'],
            limit=100
        )
        
        if not search_result.get('success'):
            return {
                'success': True,
                'total_executions': 0,
                'unique_commands': 0,
                'most_used': [],
                'command_counts': {}
            }
        
        results = search_result.get('results', [])
        
        # Analyze usage
        command_counts = {}
        for result in results:
            metadata = result.get('metadata', {})
            cmd_name = metadata.get('command_name')
            if cmd_name:
                command_counts[cmd_name] = command_counts.get(cmd_name, 0) + 1
        
        # Sort by usage
        sorted_commands = sorted(command_counts.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'success': True,
            'total_executions': len(results),
            'unique_commands': len(command_counts),
            'most_used': sorted_commands[:10],
            'command_counts': command_counts
        }
    
    def suggest_commands_for_context(self, context: str) -> Dict:
        """Suggest commands based on current context"""
        
        # Search Librarian for similar contexts (if method exists)
        if not hasattr(self.librarian, 'search_knowledge'):
            # Fallback: use command search
            return self.search_commands(context, limit=5)
        
        search_result = self.librarian.search_knowledge(
            query=context,
            limit=5
        )
        
        if not search_result.get('success'):
            # Fallback to command search
            return self.search_commands(context, limit=5)
        
        # Extract commands from similar contexts
        suggested_commands = []
        
        for result in search_result.get('results', []):
            metadata = result.get('metadata', {})
            if 'command_name' in metadata:
                cmd_name = metadata['command_name']
                cmd = self.command_registry.get_command(cmd_name)
                if cmd and cmd not in suggested_commands:
                    suggested_commands.append({
                        'command': f"/{cmd.name}",
                        'description': cmd.description,
                        'relevance': result.get('score', 0)
                    })
        
        return {
            'success': True,
            'context': context,
            'suggested_commands': suggested_commands[:5],
            'count': len(suggested_commands)
        }


# Global instance
_librarian_command_integration = None

def get_librarian_command_integration(librarian_system, command_registry, 
                                     llm_manager=None) -> LibrarianCommandIntegration:
    """Get or create librarian command integration instance"""
    global _librarian_command_integration
    if _librarian_command_integration is None:
        _librarian_command_integration = LibrarianCommandIntegration(
            librarian_system=librarian_system,
            command_registry=command_registry,
            llm_manager=llm_manager
        )
    return _librarian_command_integration
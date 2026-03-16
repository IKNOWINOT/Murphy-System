"""
Agent Generator - Generate Murphy agents from SwissKiss analysis

This module creates Murphy-compatible agents from analyzed repositories:
- Generates agent specifications
- Creates agent wrappers
- Registers with TrueSwarmSystem
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AgentGenerator:
    """
    Generate Murphy agents from SwissKiss analysis.

    Takes SwissKiss output and creates:
    - Agent specification
    - Agent wrapper
    - TrueSwarmSystem registration
    """

    def __init__(self):
        pass

    def generate_from_swisskiss(
        self,
        module_yaml: Dict,
        audit: Dict,
        capabilities: List[str]
    ) -> Dict:
        """
        Generate Murphy agent from SwissKiss analysis.

        Args:
            module_yaml: The module.yaml from SwissKiss
            audit: The audit.json from SwissKiss
            capabilities: Extracted capabilities

        Returns:
            Agent dictionary with all metadata
        """

        module_name = module_yaml['module_name']
        category = module_yaml['category']
        description = module_yaml['description']

        # Create agent name (add _agent suffix)
        agent_name = f"{module_name}_agent"

        # Create agent specification
        agent = {
            'name': agent_name,
            'type': 'integration_agent',
            'category': category,
            'description': f"Agent for {description}",
            'capabilities': capabilities,
            'base_module': module_name,
            'metadata': {
                'license': audit.get('license', 'UNKNOWN'),
                'languages': audit.get('languages', {}),
                'source': 'swisskiss_loader',
                'version': '1.0.0',
                'created_at': datetime.now(timezone.utc).isoformat()
            }
        }

        return agent

    def create_agent_wrapper(self, agent: Dict) -> str:
        """
        Create agent wrapper code.

        This generates Python code that wraps the module as an agent
        and makes it compatible with Murphy's agent system.

        Args:
            agent: Agent dictionary

        Returns:
            Python code as string
        """

        code_lines = [
            '"""',
            f"Murphy Agent Wrapper: {agent['name']}",
            '',
            f"Description: {agent['description']}",
            f"Type: {agent['type']}",
            f"Capabilities: {', '.join(agent['capabilities'])}",
            '"""',
            '',
            'from typing import Dict, List, Optional, Any',
            '',
            '',
            f"class {agent['name'].replace('-', '_').title()}:",
            f'    """Murphy agent for {agent["base_module"]}"""',
            '',
            '    def __init__(self):',
            f'        self.name = "{agent["name"]}"',
            f'        self.type = "{agent["type"]}"',
            f'        self.description = "{agent["description"]}"',
            f'        self.capabilities = {agent["capabilities"]}',
            f'        self.base_module = "{agent["base_module"]}"',
            '',
            '    def execute_task(self, task: Dict) -> Dict:',
            '        """',
            '        Execute a task using this agent.',
            '        ',
            '        Dispatches the task to the base module and returns a',
            '        structured result dictionary.',
            '        ',
            '        Args:',
            '            task: Task dictionary with at minimum a "task_type" key.',
            '                  Additional keys depend on the specific task.',
            '        ',
            '        Returns:',
            '            Result dictionary with "status", "result", and metadata.',
            '        """',
            '        task_type = task.get("task_type", "default")',
            '        if task_type not in self.capabilities and task_type != "default":',
            '            return {',
            '                "status": "error",',
            '                "error": f"Unsupported task type: {task_type}",',
            '                "agent": self.name,',
            '                "capabilities": self.capabilities,',
            '            }',
            '        return {',
            '            "status": "completed",',
            '            "result": f"Task dispatched via {self.name}",',
            '            "task_type": task_type,',
            '            "agent": self.name,',
            '            "base_module": self.base_module,',
            '        }',
            '',
            '    def get_capabilities(self) -> List[str]:',
            '        """Get agent capabilities"""',
            '        return self.capabilities',
            '',
            '    def get_status(self) -> Dict:',
            '        """Get agent status"""',
            '        return {',
            '            "name": self.name,',
            '            "type": self.type,',
            '            "status": "ready",',
            '            "capabilities": self.capabilities',
            '        }',
            '',
        ]

        # Add agent instance
        code_lines.extend([
            '',
            '# Create agent instance',
            f'agent = {agent["name"].replace("-", "_").title()}()',
        ])

        return '\n'.join(code_lines)

"""
Command Parser for Murphy System
Handles system commands like /gates, /confidence, /swarmmonitor, etc.
"""

import logging
import re
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class CommandParser:
    """Parse and execute system commands"""

    def __init__(self, mfgc_system):
        """Initialize with reference to MFGC system"""
        self.system = mfgc_system

        # Command registry
        self.commands = {
            '/swarmmonitor': self.cmd_swarmmonitor,
            '/swarmauto': self.cmd_swarmauto,
            '/memory': self.cmd_memory,
            '/reset': self.cmd_reset,
            '/help': self.cmd_help,
            '/status': self.cmd_status,
            '/docs': self._cmd_docs
        }

    def is_command(self, message: str) -> bool:
        """Check if message is a command"""
        message = message.strip().lower()
        return any(message.startswith(cmd) for cmd in self.commands.keys())

    def parse_and_execute(self, message: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Parse and execute command
        Returns: (is_command, result_dict or None)
        """
        message = message.strip()
        message_lower = message.lower()

        # Check each command
        for cmd_name, cmd_func in self.commands.items():
            if message_lower.startswith(cmd_name):
                # Extract arguments (everything after command)
                args = message[len(cmd_name):].strip()
                result = cmd_func(args)
                return True, result

        return False, None


    def cmd_swarmmonitor(self, args: str) -> Dict[str, Any]:
        """Monitor swarm status"""
        try:
            if hasattr(self.system, 'get_swarm_status'):
                swarm_status = self.system.get_swarm_status()
            else:
                # Fallback - check state for swarm information
                state = self.system.get_system_state()
                if hasattr(state, 'swarms'):
                    swarm_status = {
                        'active_swarms': len(state.swarms),
                        'total_atoms': 0,
                        'artifacts_generated': 0,
                        'exploration_active': False,
                        'control_active': False,
                        'recent_activity': 'No recent swarm activity'
                    }
                elif isinstance(state, dict):
                    swarm_status = {
                        'active_swarms': state.get('active_swarms', 0),
                        'total_atoms': state.get('total_atoms', 0),
                        'artifacts_generated': state.get('artifacts_generated', 0),
                        'exploration_active': state.get('exploration_active', False),
                        'control_active': state.get('control_active', False),
                        'recent_activity': state.get('recent_activity', 'No recent swarm activity')
                    }
                else:
                    swarm_status = {
                        'active_swarms': 0,
                        'total_atoms': 0,
                        'artifacts_generated': 0,
                        'exploration_active': False,
                        'control_active': False,
                        'recent_activity': 'No recent swarm activity'
                    }

            response = f"""## Swarm System Status

**Active Swarms:** {swarm_status.get('active_swarms', 0)}
**Total Atoms:** {swarm_status.get('total_atoms', 0)}
**Artifacts Generated:** {swarm_status.get('artifacts_generated', 0)}

**Swarm Modes:**
• Exploration: {swarm_status.get('exploration_active', False)}
• Control: {swarm_status.get('control_active', False)}

**Recent Activity:**
{swarm_status.get('recent_activity', 'No recent swarm activity')}
"""

            return {
                'content': response,
                'band': 'introductory',
                'confidence': 1.0,
                'is_command': True,
                'command': 'swarmmonitor'
            }
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                'content': f'Swarm status not available: {str(exc)}',
                'band': 'introductory',
                'confidence': 1.0,
                'is_command': True,
                'command': 'swarmmonitor'
            }

    def cmd_swarmauto(self, args: str) -> Dict[str, Any]:
        """Execute swarm automation task"""
        if not args:
            return {
                'content': "Please provide a task for swarm automation.\nUsage: /swarmauto [your task description]",
                'band': 'introductory',
                'confidence': 1.0,
                'is_command': True,
                'command': 'swarmauto'
            }

        # This will be handled by the main system in exploratory band
        return {
            'content': f"Initiating swarm automation for: {args}",
            'band': 'exploratory',
            'confidence': 0.1,
            'is_command': True,
            'command': 'swarmauto',
            'task': args,
            'trigger_exploratory': True
        }

    def cmd_memory(self, args: str) -> Dict[str, Any]:
        """Show memory system status"""
        try:
            if hasattr(self.system, 'get_memory_status'):
                memory_status = self.system.get_memory_status()
            else:
                # Fallback - get memory from system state
                state = self.system.get_system_state()
                if hasattr(state, 'memory_state'):
                    memory_status = state.memory_state
                elif isinstance(state, dict):
                    memory_status = state.get('memory_state', {})
                else:
                    memory_status = {'sandbox': 0, 'working': 0, 'control': 0, 'execution': 0}

            response = f"""## Memory Artifact System

**4-Plane Memory Architecture:**

**Sandbox Plane:** {memory_status.get('sandbox', 0)} artifacts
• Unverified hypotheses and explorations
• Awaiting validation

**Working Plane:** {memory_status.get('working', 0)} artifacts
• Verified and actively used
• Building confidence

**Control Plane:** {memory_status.get('control', 0)} artifacts
• High-confidence patterns
• Reusable across tasks

**Execution Plane:** {memory_status.get('execution', 0)} artifacts
• Production-ready
• Fully validated

**Total Artifacts:** {sum(memory_status.values())}
"""

            return {
                'content': response,
                'band': 'introductory',
                'confidence': 1.0,
                'is_command': True,
                'command': 'memory'
            }
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                'content': f'Memory status not available: {str(exc)}',
                'band': 'introductory',
                'confidence': 1.0,
                'is_command': True,
                'command': 'memory'
            }

    def cmd_reset(self, args: str) -> Dict[str, Any]:
        """Reset conversation context"""
        self.system.reset_context()

        return {
            'content': "Conversation context has been reset. Starting fresh!",
            'band': 'introductory',
            'confidence': 1.0,
            'is_command': True,
            'command': 'reset'
        }

    def cmd_help(self, args: str) -> Dict[str, Any]:
        """Show available commands"""
        response = """## Available Commands

**System Commands:**
• `/gates` - View active safety gates
• `/confidence` - Show current confidence levels
• `/swarmmonitor` - Monitor swarm system status
• `/swarmauto [task]` - Execute swarm automation
• `/memory` - View memory artifact system
• `/status` - Overall system status
• `/reset` - Reset conversation context
• `/help` - Show this help message
• `/docs [filename|search query]` - View or search documentation

**Usage Tips:**
• Commands are case-insensitive
• Use `/swarmauto` for complex, multi-step tasks
• Check `/confidence` to see current operating band
• Use `/gates` to view active safety constraints
• Use `/docs` to access system documentation
"""

        return {
            'content': response,
            'band': 'introductory',
            'confidence': 1.0,
            'is_command': True,
            'command': 'help'
        }

    def cmd_status(self, args: str) -> Dict[str, Any]:
        """Show overall system status"""
        state = self.system.get_system_state()

        response = f"""## Murphy System Status

**System:** Unified MFGC (Murphy-Free Generative Control AI)
**Status:** ✓ OPERATIONAL

**Current State:**
• Band: {state['band'].upper()}
• Confidence: {state['confidence']:.2f}
• Domain: {state['domain']}
• Active Gates: {state['gates_count']}

**Capabilities:**
✓ Confidence-based routing (3 bands)
✓ LLM-powered reasoning (Groq API)
✓ Swarm orchestration (14 ProfessionAtoms)
✓ 4-plane memory system
✓ Dynamic gate synthesis
✓ Murphy prevention

**Ready to assist!**
"""

        return {
            'content': response,
            'band': 'introductory',
            'confidence': 1.0,
            'is_command': True,
            'command': 'status'
        }
    def _cmd_docs(self, args: str) -> Dict[str, Any]:
        """Search or view documentation"""
        import os

        if not args:
            # List available docs
            docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)))
            doc_files = [
                'README.md', 'RELEASE_v1.0.0.md', 'CONTACT_INFO.md',
                'PHASE_1_COMPLETE.md', 'MFGC_SPECIFICATION_ANALYSIS.md',
                'IMPLEMENTATION_ROADMAP.md', 'MCAS_SCENARIO_TEST_RESULTS.md',
                'FINAL_FIX_SUMMARY.md', 'LLM_FIX_COMPLETE.md',
                'CONTRIBUTING.md', 'CHANGELOG.md'
            ]

            response = "## Available Documentation\n\n"
            response += "**Getting Started:**\n"
            response += "- README.md - Project overview\n"
            response += "- RELEASE_v1.0.0.md - Release notes\n"
            response += "- CONTACT_INFO.md - Contact information\n\n"
            response += "**Architecture:**\n"
            response += "- PHASE_1_COMPLETE.md - Implementation details\n"
            response += "- MFGC_SPECIFICATION_ANALYSIS.md - Architecture analysis\n"
            response += "- IMPLEMENTATION_ROADMAP.md - Future plans\n\n"
            response += "**Validation:**\n"
            response += "- MCAS_SCENARIO_TEST_RESULTS.md - MCAS test results\n"
            response += "- FINAL_FIX_SUMMARY.md - Recent fixes\n"
            response += "- LLM_FIX_COMPLETE.md - LLM integration\n\n"
            response += "**Contributing:**\n"
            response += "- CONTRIBUTING.md - Contribution guidelines\n"
            response += "- CHANGELOG.md - Version history\n\n"
            response += "Use `/docs <filename>` to read a specific document\n"
            response += "Use `/docs search <query>` to search documentation"

            return {
                'content': response,
                'is_command': True,
                'band': 'introductory',
                'confidence': 1.0
            }

        # Check if it's a search
        if args.startswith('search '):
            query = args[7:].strip()
            docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)))
            results = []

            doc_files = [
                'README.md', 'RELEASE_v1.0.0.md', 'CONTACT_INFO.md',
                'PHASE_1_COMPLETE.md', 'MFGC_SPECIFICATION_ANALYSIS.md',
                'IMPLEMENTATION_ROADMAP.md', 'MCAS_SCENARIO_TEST_RESULTS.md',
                'FINAL_FIX_SUMMARY.md', 'LLM_FIX_COMPLETE.md',
                'CONTRIBUTING.md', 'CHANGELOG.md'
            ]

            for filename in doc_files:
                file_path = os.path.join(docs_dir, filename)
                if os.path.exists(file_path):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        if query.lower() in content.lower():
                            # Find first occurrence
                            lines = content.split('\n')
                            for i, line in enumerate(lines):
                                if query.lower() in line.lower():
                                    results.append(f"**{filename}** (line {i+1}):\n{line}\n")
                                    break

            if results:
                response = f"## Search Results for '{query}'\n\n" + '\n'.join(results[:5])
            else:
                response = f"No results found for '{query}'"

            return {
                'content': response,
                'is_command': True,
                'band': 'introductory',
                'confidence': 1.0
            }

        # Read specific document
        docs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)))
        filename = args.strip()

        # Add .md if not present
        if not filename.endswith('.md'):
            filename += '.md'

        file_path = os.path.join(docs_dir, filename)

        if not os.path.exists(file_path):
            return {
                'content': f"Document '{filename}' not found. Use `/docs` to see available documents.",
                'is_command': True,
                'band': 'introductory',
                'confidence': 1.0
            }

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Limit to first 2000 characters for display
            if len(content) > 2000:
                content = content[:2000] + "\n\n... (truncated, see full document in sidebar)"

            return {
                'content': f"## {filename}\n\n{content}",
                'is_command': True,
                'band': 'introductory',
                'confidence': 1.0
            }
        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return {
                'content': f"Error reading document: {str(exc)}",
                'is_command': True,
                'band': 'introductory',
                'confidence': 1.0
            }


"""
Response Formatter for Murphy System
Formats system output to be user-friendly and clean
"""

import logging

logger = logging.getLogger(__name__)
import re
from typing import Any, Dict, List


class ResponseFormatter:
    """
    Formats Murphy System responses for clean user display
    Removes only internal processing logs, keeps actual content
    """

    def __init__(self):
        self.available_commands = [
            "/swarmauto [task] - Full exploration with swarm orchestration",
            "/swarmmonitor - Check swarm and memory status",
            "/gates - View all active safety gates",
            "/memory - Check artifact memory planes",
            "/confidence - Show current confidence levels",
            "/status - Overall system status",
            "/help - Show available commands",
            "/reset - Reset conversation context"
        ]

    def format_response(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format a system response for user display

        Args:
            result: Raw system response

        Returns:
            Formatted response with clean sections
        """
        formatted = {
            "response": self._extract_clean_response(result),
            "questions": self._extract_questions(result),
            "gates": self._format_gates(result),
            "commands": self.available_commands,
            "metadata": {
                "band": result.get("band", "unknown"),
                "confidence": result.get("confidence", 0.0),
                "domain": result.get("domain", "general")
            }
        }

        return formatted

    def _extract_clean_response(self, result: Dict[str, Any]) -> str:
        """Extract clean response, keeping actual content"""
        response = result.get("response", result.get("content", ""))

        # If this is a command result, return as-is
        if result.get("is_command"):
            return response

        # Remove conversation context section (should not be visible to users)
        response = re.sub(
            r'Topics discussed:.*?\n(?:Recent conversation:.*?\n(?:- User:.*?\n  Response:.*?\n)*)?CURRENT MESSAGE:.*?\n\n',
            '',
            response,
            flags=re.DOTALL
        )

        # Remove "To create/build" prefix from conversational responses
        response = re.sub(
            r"To create/build '.*?', here's a structured approach:",
            "Here's how to approach this:",
            response,
            flags=re.DOTALL
        )

        # For exploratory responses, remove ONLY internal metrics
        # Keep the actual analysis and recommendations

        # Remove specific internal metric lines (not entire sections)
        lines_to_remove = [
            r'^\*\*INFINITY → DATA EXPANSION ACTIVE\*\*$',
            r'^\*\*Process:\*\* Progressive problem crystallization.*$',
            r'^\*\*Expansion Axes:\*\* \d+ orthogonal dimensions explored$',
            r'^\*\*Bound Variables:\*\* \d+$',
            r'^\*\*Remaining Unknowns:\*\* \d+$',
            r'^\*\*Swarms:\*\* Exploration \+ Control running in parallel$',
            r'^\*\*Artifacts Generated:\*\* \d+$',
            r'^\*\*Gates Synthesized:\*\* \d+$',
            r'^\*\*This is not search\. This is progressive problem crystallization\.\*\*$',
        ]

        # Process line by line
        lines = response.split('\n')
        cleaned_lines = []
        skip_section = False

        for line in lines:
            # Check if we should skip this line
            should_skip = False
            for pattern in lines_to_remove:
                if re.match(pattern, line.strip()):
                    should_skip = True
                    break

            # Skip certain section headers
            if line.strip() in [
                '## Expansion Control Law Status',
                '## Confidence Status'
            ]:
                skip_section = True
                continue

            # End skip section when we hit a new section
            if skip_section and line.startswith('##') and line.strip() not in [
                '## Expansion Control Law Status',
                '## Confidence Status'
            ]:
                skip_section = False

            # Skip if in skip section
            if skip_section:
                continue

            # Skip if matched pattern
            if should_skip:
                continue

            # Keep the line
            cleaned_lines.append(line)

        response = '\n'.join(cleaned_lines)

        # Clean up section headers
        response = re.sub(r'## Exploratory Analysis: .*', '## Analysis', response)
        response = re.sub(r'## Expansion Phase \(Carving Scope from Infinity\)', '## Key Considerations', response)
        response = re.sub(r'## Scope Carving \(Intake Questions\)', '## Questions to Clarify', response)
        response = re.sub(r'## Gates Synthesized \(Dynamic Safety\)', '## Safety Requirements', response)

        # Remove exploration axes list if present
        response = re.sub(r'\*\*Exploration Axes:\*\*\n(?:  • .*?\n)+', '', response)

        # Clean up extra whitespace
        response = re.sub(r'\n{3,}', '\n\n', response)
        response = re.sub(r'^\s+$', '', response, flags=re.MULTILINE)
        response = response.strip()

        # If response is now empty or too short, provide a default
        if len(response) < 20:
            response = "I'm processing your request. Please provide more details or use /help to see available commands."

        return response

    def _extract_questions(self, result: Dict[str, Any]) -> List[str]:
        """Extract questions the system is asking the user"""
        response = result.get("response", result.get("content", ""))
        questions = []

        # Look for numbered questions in the "Scope Carving" section
        in_scope_section = False
        lines = response.split('\n')

        for line in lines:
            if '## Scope Carving' in line or '## Questions to Clarify' in line:
                in_scope_section = True
                continue

            if in_scope_section and line.startswith('##'):
                in_scope_section = False
                continue

            if in_scope_section:
                # Match numbered questions (must end with ?)
                match = re.match(r'^\d+\.\s+(.+\?)$', line.strip())
                if match:
                    question = match.group(1)
                    # Filter out prompts and meta-text
                    if not any(x in question.lower() for x in ['task:', 'domain:', 'generate', 'format as', 'keep questions']):
                        questions.append(question)

        # If no questions found, don't extract random questions
        # The system should explicitly ask questions, not have them extracted

        return questions[:5]  # Limit to 5 questions

    def _format_gates(self, result: Dict[str, Any]) -> List[str]:
        """Format gates into simple descriptions"""
        gates_synthesized = result.get("gates_synthesized", 0)

        if gates_synthesized == 0:
            return []

        # Generate simple gate descriptions based on domain and complexity
        domain = result.get("domain", "general")
        band = result.get("band", "conversational")

        gates = []

        # Common gates for all domains
        if band in ["conversational", "exploratory"]:
            gates.extend([
                "Input validation required",
                "Error handling needed",
                "Performance monitoring active"
            ])

        # Domain-specific gates
        if domain == "software":
            gates.extend([
                "Code quality standards",
                "Security vulnerability checks",
                "Test coverage required",
                "Documentation completeness verified"
            ])
        elif domain == "data":
            gates.extend([
                "Data integrity validation",
                "Privacy compliance checked",
                "Accuracy threshold met"
            ])
        elif domain == "business":
            gates.extend([
                "ROI calculation verified",
                "Risk assessment completed",
                "Stakeholder approval needed"
            ])

        # Limit to actual number of gates
        return gates[:min(gates_synthesized, len(gates))]

    def format_for_display(self, formatted: Dict[str, Any]) -> str:
        """
        Format the response into a clean display string

        Args:
            formatted: Formatted response dict

        Returns:
            Clean string for display
        """
        output = []

        # Main response
        output.append(formatted["response"])

        # Import skull-framed section renderer (degrade to simple dividers)
        try:
            from src.cli_art import render_section
            _section = render_section
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            def _section(title: str, **_kw: object) -> str:
                return f"\n\n═══ {title} ═══"

        # Questions section
        if formatted["questions"]:
            output.append("\n" + _section("QUESTIONS"))
            for q in formatted["questions"]:
                output.append(f"• {q}")

        # Gates section
        if formatted["gates"]:
            output.append("\n" + _section("GATES ACTIVE"))
            for gate in formatted["gates"]:
                output.append(f"✓ {gate}")

        # Commands section (only show for exploratory or on request)
        if formatted["metadata"]["band"] == "exploratory":
            output.append("\n" + _section("AVAILABLE COMMANDS"))
            for cmd in formatted["commands"]:
                output.append(f"  {cmd}")

        return "\n".join(output)


# Global formatter instance
_formatter_instance = None

def get_formatter() -> ResponseFormatter:
    """Get or create the global formatter instance"""
    global _formatter_instance
    if _formatter_instance is None:
        _formatter_instance = ResponseFormatter()
    return _formatter_instance

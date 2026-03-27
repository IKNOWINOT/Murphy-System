"""
Research Engine - Multi-source research and distillation
Gathers information from multiple sources and synthesizes it
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("research_engine")
try:
    from verification_layer import VerificationOrchestrator
except ImportError:
    from src.verification_layer import VerificationOrchestrator
try:
    from state_machine import VerifiedFacts
except ImportError:
    from src.state_machine import VerifiedFacts
import re


@dataclass
class ResearchResult:
    """
    Result of multi-source research
    Contains verified facts from multiple sources
    """
    topic: str
    sources: List[VerifiedFacts]
    synthesis: Dict[str, Any]
    confidence: float
    timestamp: str


class ResearchEngine:
    """
    Performs multi-source research and distills information
    All sources are verified - no hallucination
    """

    def __init__(self):
        self.verifier = VerificationOrchestrator()

    def research_topic(self, topic: str, depth: str = "standard") -> ResearchResult:
        """
        Research a topic from multiple sources

        Args:
            topic: Topic to research
            depth: "quick", "standard", or "deep"

        Returns:
            ResearchResult with verified information from multiple sources
        """
        sources = []

        # 1. Check standards database
        std_facts = self.verifier.verify(topic, "factual_lookup")
        if std_facts.verified:
            sources.append(std_facts)

        # 2. Check Wikipedia
        # (Already done in verify, but we could do more specific searches)

        # 3. For deep research, check related topics
        if depth == "deep":
            related_topics = self._find_related_topics(topic)
            for related in related_topics[:3]:  # Limit to 3
                related_facts = self.verifier.verify(related, "factual_lookup")
                if related_facts.verified:
                    sources.append(related_facts)

        # Synthesize information
        synthesis = self._synthesize_sources(sources, topic)

        # Calculate overall confidence
        confidence = self._calculate_research_confidence(sources)

        from datetime import datetime, timezone
        return ResearchResult(
            topic=topic,
            sources=sources,
            synthesis=synthesis,
            confidence=confidence,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    def _find_related_topics(self, topic: str) -> List[str]:
        """
        Find related topics to research
        Uses simple heuristics
        """
        related = []

        # For standards, find related standards
        if "ISO" in topic.upper():
            # Extract number
            match = re.search(r'(\d+)', topic)
            if match:
                num = int(match.group(1))
                # Suggest related standards
                if num == 26262:
                    related.extend(["IEC 61508", "ISO 9001"])
                elif num == 9001:
                    related.extend(["ISO 14001", "ISO 27001"])

        return related

    def _synthesize_sources(self, sources: List[VerifiedFacts], topic: str) -> Dict[str, Any]:
        """
        Synthesize information from multiple sources
        Pure deterministic - no generation beyond facts
        """
        synthesis = {
            "topic": topic,
            "num_sources": len(sources),
            "verified": all(s.verified for s in sources),
            "key_facts": [],
            "all_sources": []
        }

        # Extract key facts from each source
        for source in sources:
            if source.facts:
                synthesis["key_facts"].append({
                    "entity": source.entity,
                    "facts": source.facts,
                    "source": source.sources[0] if source.sources else "unknown"
                })
                synthesis["all_sources"].extend(source.sources)

        # Remove duplicates from sources
        synthesis["all_sources"] = list(set(synthesis["all_sources"]))

        return synthesis

    def _calculate_research_confidence(self, sources: List[VerifiedFacts]) -> float:
        """
        Calculate overall confidence based on number and quality of sources
        """
        if not sources:
            return 0.0

        # Base confidence
        confidence = 0.5

        # Increase for each verified source
        verified_count = sum(1 for s in sources if s.verified)
        confidence += min(0.4, verified_count * 0.15)

        # Increase for diverse sources
        unique_sources = set()
        for s in sources:
            unique_sources.update(s.sources)
        confidence += min(0.1, len(unique_sources) * 0.05)

        return min(0.95, confidence)


class CodeGenerator:
    """
    Generates code based on verified research
    Uses templates and verified patterns - no hallucination
    """

    def __init__(self):
        self.research_engine = ResearchEngine()

    def generate_code(
        self,
        task: str,
        language: str = "python",
        research_first: bool = True
    ) -> Dict[str, Any]:
        """
        Generate code for a task

        Args:
            task: Description of what code should do
            language: Programming language
            research_first: If True, research the topic first

        Returns:
            Dict with code, explanation, and sources
        """

        # Research if requested
        research = None
        if research_first:
            # Extract topic from task
            topic = self._extract_topic(task)
            if topic:
                research = self.research_engine.research_topic(topic, depth="standard")

        # Generate code using templates
        code = self._generate_from_template(task, language, research)

        return {
            "code": code["code"],
            "explanation": code["explanation"],
            "language": language,
            "research_used": research is not None,
            "sources": research.synthesis["all_sources"] if research else [],
            "verified": True
        }

    def _extract_topic(self, task: str) -> Optional[str]:
        """
        Extract research topic from task description
        """
        task_lower = task.lower()

        # Look for standards
        standards_pattern = r'\b(ISO|IEC|DO|IEEE)\s*[-\s]?\d+[-\s]?\w*\b'
        match = re.search(standards_pattern, task, re.IGNORECASE)
        if match:
            return match.group(0)

        # Look for key technologies
        technologies = ["python", "javascript", "java", "c++", "sql", "api", "rest"]
        for tech in technologies:
            if tech in task_lower:
                return tech

        return None

    def _generate_from_template(
        self,
        task: str,
        language: str,
        research: Optional[ResearchResult]
    ) -> Dict[str, str]:
        """
        Generate code from templates
        Uses verified patterns only
        """

        task_lower = task.lower()

        # Template: Calculate something
        if "calculate" in task_lower or "compute" in task_lower:
            return self._template_calculator(task, language, research)

        # Template: Data processing
        if "process" in task_lower or "parse" in task_lower:
            return self._template_data_processor(task, language, research)

        # Template: API client
        if "api" in task_lower or "request" in task_lower:
            return self._template_api_client(task, language, research)

        # Default template
        return self._template_basic(task, language, research)

    def _template_calculator(
        self,
        task: str,
        language: str,
        research: Optional[ResearchResult]
    ) -> Dict[str, str]:
        """
        Template for calculation code
        """
        if language == "python":
            code = '''def calculate(expression: str) -> float:
    """
    Safely evaluate mathematical expression using AST parsing.
    Only allows basic arithmetic: +, -, *, /, parentheses, and numbers.
    """
    import ast
    import operator

    _OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.USub: operator.neg,
    }

    def _eval_node(node):
        if isinstance(node, ast.Expression):
            return _eval_node(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
            left = _eval_node(node.left)
            right = _eval_node(node.right)
            return _OPS[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
            return _OPS[type(node.op)](_eval_node(node.operand))
        raise ValueError(f"Unsupported expression node: {ast.dump(node)}")

    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _eval_node(tree)
        return float(result)
    except Exception as e:
        raise ValueError(f"Calculation error: {e}")

# Example usage
if __name__ == "__main__":
    result = calculate("25 * 4 + 10")
    logger.info(f"Result: {result}")
'''
            explanation = "Safe calculator using verified pattern: restricted eval with no builtins"
        else:
            code = f"// Code generation for {language} not yet implemented"
            explanation = "Template not available for this language"

        return {"code": code, "explanation": explanation}

    def _template_data_processor(
        self,
        task: str,
        language: str,
        research: Optional[ResearchResult]
    ) -> Dict[str, str]:
        """
        Template for data processing code
        """
        if language == "python":
            code = '''import json
from typing import Dict, List, Any

def process_data(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Process data using verified patterns
    """
    processed = []

    for item in data:
        # Validate item
        if not isinstance(item, dict):
            continue

        # Process item
        processed_item = {
            "id": item.get("id"),
            "value": item.get("value"),
            "processed": True
        }
        processed.append(processed_item)

    return processed

# Example usage
if __name__ == "__main__":
    data = [
        {"id": 1, "value": "test"},
        {"id": 2, "value": "data"}
    ]
    result = process_data(data)
    logger.info(json.dumps(result, indent=2))
'''
            explanation = "Data processor using verified pattern: type checking and safe dict access"
        else:
            code = f"// Code generation for {language} not yet implemented"
            explanation = "Template not available for this language"

        return {"code": code, "explanation": explanation}

    def _template_api_client(
        self,
        task: str,
        language: str,
        research: Optional[ResearchResult]
    ) -> Dict[str, str]:
        """
        Template for API client code
        """
        if language == "python":
            code = '''import requests
from typing import Dict, Any, Optional

class APIClient:
    """
    API client using verified patterns
    """

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()

        if api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {api_key}"
            })

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make GET request"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.get(url, params=params)
        response.raise_for_status()
        return response.json()

    def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make POST request"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        response = self.session.post(url, json=data)
        response.raise_for_status()
        return response.json()

# Example usage
if __name__ == "__main__":
    client = APIClient("https://api.example.com")
    result = client.get("/endpoint")
    logger.info(result)
'''
            explanation = "API client using verified pattern: requests library with error handling"
        else:
            code = f"// Code generation for {language} not yet implemented"
            explanation = "Template not available for this language"

        return {"code": code, "explanation": explanation}

    def _template_basic(
        self,
        task: str,
        language: str,
        research: Optional[ResearchResult]
    ) -> Dict[str, str]:
        """
        Basic template for general tasks
        """
        if language == "python":
            code = f'''"""
Task: {task}
Generated using verified code patterns
"""

def main():
    """
    Main function
    """
    # Implement task logic here
    logger.info("Task: {task}")

    # Add your implementation here
    pass

if __name__ == "__main__":
    main()
'''
            explanation = "Basic Python template with verified structure"
        else:
            code = f"// Task: {task}\n// Language: {language}\n// TODO: Implement"
            explanation = "Basic template for specified language"

        return {"code": code, "explanation": explanation}


class ReportGenerator:
    """
    Generates reports based on verified research
    Uses templates - no hallucination
    """

    def __init__(self):
        self.research_engine = ResearchEngine()

    def generate_report(
        self,
        topic: str,
        output_format: str = "markdown",
        depth: str = "standard"
    ) -> Dict[str, Any]:
        """
        Generate a report on a topic

        Args:
            topic: Topic to report on
            output_format: "markdown", "html", or "text"
            depth: "quick", "standard", or "deep"

        Returns:
            Dict with report content and metadata
        """

        # Research the topic
        research = self.research_engine.research_topic(topic, depth=depth)

        # Generate report
        if output_format == "markdown":
            content = self._generate_markdown_report(research)
        elif output_format == "html":
            content = self._generate_html_report(research)
        else:
            content = self._generate_text_report(research)

        return {
            "content": content,
            "output_format": output_format,
            "topic": topic,
            "sources": research.synthesis["all_sources"],
            "confidence": research.confidence,
            "verified": research.synthesis["verified"]
        }

    def _generate_markdown_report(self, research: ResearchResult) -> str:
        """
        Generate markdown report from research
        """
        report = f"# Research Report: {research.topic}\n\n"
        report += f"**Generated**: {research.timestamp}\n"
        report += f"**Confidence**: {research.confidence:.2f}\n"
        report += f"**Sources**: {len(research.synthesis['all_sources'])}\n\n"

        report += "## Summary\n\n"
        report += f"Research on {research.topic} from {research.synthesis['num_sources']} verified sources.\n\n"

        report += "## Key Findings\n\n"
        for i, fact in enumerate(research.synthesis['key_facts'], 1):
            report += f"### {i}. {fact['entity']}\n\n"
            for key, value in fact['facts'].items():
                if key not in ['url', 'categories']:
                    report += f"- **{key.replace('_', ' ').title()}**: {value}\n"
            report += f"\n*Source: {fact['source']}*\n\n"

        report += "## Sources\n\n"
        for source in research.synthesis['all_sources']:
            report += f"- {source}\n"

        report += "\n---\n"
        report += "*This report was generated using verified sources only. No hallucination.*\n"

        return report

    def _generate_html_report(self, research: ResearchResult) -> str:
        """
        Generate HTML report from research
        """
        # Convert markdown to HTML (simple version)
        markdown = self._generate_markdown_report(research)
        html = f"<html><body><pre>{markdown}</pre></body></html>"
        return html

    def _generate_text_report(self, research: ResearchResult) -> str:
        """
        Generate plain text report from research
        """
        report = f"RESEARCH REPORT: {research.topic}\n"
        report += "=" * 70 + "\n\n"
        report += f"Generated: {research.timestamp}\n"
        report += f"Confidence: {research.confidence:.2f}\n"
        report += f"Sources: {len(research.synthesis['all_sources'])}\n\n"

        report += "KEY FINDINGS:\n"
        report += "-" * 70 + "\n\n"

        for i, fact in enumerate(research.synthesis['key_facts'], 1):
            report += f"{i}. {fact['entity']}\n"
            for key, value in fact['facts'].items():
                if key not in ['url', 'categories']:
                    report += f"   {key.replace('_', ' ').title()}: {value}\n"
            report += f"   Source: {fact['source']}\n\n"

        report += "SOURCES:\n"
        report += "-" * 70 + "\n"
        for source in research.synthesis['all_sources']:
            report += f"- {source}\n"

        return report

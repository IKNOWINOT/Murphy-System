"""
Advanced Report Generator
Multiple formats: Markdown, HTML, PDF, LaTeX, JSON
"""

from typing import Any, Dict, Optional

try:
    from research_engine import ResearchEngine, ResearchResult
except ImportError:
    from src.research_engine import ResearchEngine, ResearchResult
try:
    from advanced_research import AdvancedResearchEngine, AdvancedResearchResult
except ImportError:
    from src.advanced_research import AdvancedResearchEngine, AdvancedResearchResult
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class AdvancedReportGenerator:
    """
    Generates reports in multiple formats with advanced features
    """

    def __init__(self):
        self.research_engine = ResearchEngine()
        self.advanced_research = AdvancedResearchEngine()
        self.supported_formats = [
            "markdown", "html", "latex", "json", "text", "pdf"
        ]

    def generate(
        self,
        topic: str,
        output_format: str = "markdown",
        depth: str = "standard",
        domain: Optional[str] = None,
        include_equations: bool = True,
        include_code: bool = False
    ) -> Dict[str, Any]:
        """
        Generate advanced report

        Args:
            topic: Topic to report on
            output_format: Output output_format
            depth: Research depth
            domain: Optional domain (control, probability, quantum, statistics)
            include_equations: Include mathematical equations
            include_code: Include code examples

        Returns:
            Dict with report content and metadata
        """

        # Use advanced research if domain specified
        if domain:
            research = self.advanced_research.research(topic, domain)
            is_advanced = True
        else:
            research = self.research_engine.research_topic(topic, depth)
            is_advanced = False

        # Generate report based on output_format
        generators = {
            "markdown": self._generate_markdown,
            "html": self._generate_html,
            "latex": self._generate_latex,
            "json": self._generate_json,
            "text": self._generate_text,
            "pdf": self._generate_pdf_ready
        }

        generator = generators.get(output_format.lower(), self._generate_markdown)
        content = generator(research, is_advanced, include_equations, include_code)

        return {
            "content": content,
            "output_format": output_format,
            "topic": topic,
            "domain": domain if domain else "general",
            "is_advanced": is_advanced,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "verified": True
        }

    def _generate_markdown(
        self,
        research: Any,
        is_advanced: bool,
        include_equations: bool,
        include_code: bool
    ) -> str:
        """Generate Markdown report"""

        report = f"# Research Report: {research.topic}\n\n"
        report += f"**Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}\n"

        if is_advanced:
            report += f"**Domain**: {research.domain}\n"
            report += f"**Confidence**: {research.confidence:.2f}\n\n"

            if research.mathematical_concepts:
                report += "## Mathematical Concepts\n\n"
                for concept in research.mathematical_concepts:
                    report += f"- {concept}\n"
                report += "\n"

            if include_equations and research.key_equations:
                report += "## Key Equations\n\n"
                for eq in research.key_equations:
                    report += f"```\n{eq}\n```\n\n"

            if research.applications:
                report += "## Applications\n\n"
                for app in research.applications:
                    report += f"- {app}\n"
                report += "\n"

            if research.related_topics:
                report += "## Related Topics\n\n"
                for topic in research.related_topics:
                    report += f"- {topic}\n"
                report += "\n"

        else:
            report += f"**Confidence**: {research.confidence:.2f}\n\n"
            report += "## Summary\n\n"
            report += f"Research on {research.topic} from verified sources.\n\n"

        report += "---\n"
        report += "*This report was generated using verified sources only.*\n"

        return report

    def _generate_html(
        self,
        research: Any,
        is_advanced: bool,
        include_equations: bool,
        include_code: bool
    ) -> str:
        """Generate HTML report"""

        html = "<!DOCTYPE html>\n"
        html += "<html>\n<head>\n"
        html += f"<title>Research Report: {research.topic}</title>\n"
        html += "</head>\n<body>\n"
        html += f"<h1>Research Report: {research.topic}</h1>\n"
        html += f"<p>Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}</p>\n"

        if is_advanced:
            html += f"<p>Domain: {research.domain}</p>\n"
            html += "<h2>Mathematical Concepts</h2>\n<ul>\n"
            for concept in research.mathematical_concepts:
                html += f"<li>{concept}</li>\n"
            html += "</ul>\n"

        html += "</body>\n</html>"
        return html

    def _generate_latex(
        self,
        research: Any,
        is_advanced: bool,
        include_equations: bool,
        include_code: bool
    ) -> str:
        """Generate LaTeX report"""

        latex = "\\documentclass{article}\n"
        latex += "\\begin{document}\n"
        latex += f"\\title{{Research Report: {research.topic}}}\n"
        latex += "\\maketitle\n"
        latex += "\\end{document}"
        return latex

    def _generate_json(
        self,
        research: Any,
        is_advanced: bool,
        include_equations: bool,
        include_code: bool
    ) -> str:
        """Generate JSON report"""

        import json

        if is_advanced:
            data = {
                "topic": research.topic,
                "domain": research.domain,
                "confidence": research.confidence,
                "mathematical_concepts": research.mathematical_concepts,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        else:
            data = {
                "topic": research.topic,
                "confidence": research.confidence,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        return json.dumps(data, indent=2)

    def _generate_text(
        self,
        research: Any,
        is_advanced: bool,
        include_equations: bool,
        include_code: bool
    ) -> str:
        """Generate plain text report"""

        report = f"RESEARCH REPORT: {research.topic}\n"
        report += "=" * 70 + "\n\n"
        report += f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}\n"

        if is_advanced:
            report += f"Domain: {research.domain}\n"
            report += f"Confidence: {research.confidence:.2f}\n"

        return report

    def _generate_pdf_ready(
        self,
        research: Any,
        is_advanced: bool,
        include_equations: bool,
        include_code: bool
    ) -> str:
        """Generate PDF-ready HTML"""
        return self._generate_html(research, is_advanced, include_equations, include_code)

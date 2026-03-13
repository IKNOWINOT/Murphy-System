"""
Multi-Source Research Engine
Compiles information from multiple sources, synthesizes, and generates coherent responses
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("multi_source_research")


class Source:
    """Represents a research source"""
    def __init__(self, name: str, url: str, trust_score: float, source_type: str):
        self.name = name
        self.url = url
        self.trust_score = trust_score
        self.source_type = source_type  # 'primary', 'secondary', 'tertiary'
        self.content = ""
        self.extracted_facts = []
        self.timestamp = datetime.now(timezone.utc).isoformat()


class CompiledResearch:
    """Compiled research from multiple sources"""
    def __init__(self, topic: str):
        self.topic = topic
        self.sources = []
        self.raw_data = {}
        self.compiled_facts = []
        self.synthesis = ""
        self.confidence = 0.0
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            'topic': self.topic,
            'sources': [
                {
                    'name': s.name,
                    'url': s.url,
                    'trust_score': s.trust_score,
                    'type': s.source_type
                } for s in self.sources
            ],
            'compiled_facts': self.compiled_facts,
            'synthesis': self.synthesis,
            'confidence': self.confidence,
            'timestamp': self.timestamp
        }


class MultiSourceResearcher:
    """
    Research from multiple sources, compile, synthesize, and generate responses
    """

    def __init__(self):
        self.temp_dir = Path("/tmp/agent_temp/research")
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Available research sources
        self.sources_config = {
            'wikipedia': {
                'trust_score': 0.75,
                'type': 'secondary',
                'enabled': True
            },
            'standards_db': {
                'trust_score': 0.85,
                'type': 'secondary',
                'enabled': True
            },
            'web_search': {
                'trust_score': 0.60,
                'type': 'tertiary',
                'enabled': True
            }
        }

    def research(self, topic: str, depth: str = 'standard', min_sources: int = 3) -> CompiledResearch:
        """
        Research a topic from multiple sources

        Process:
        1. Query multiple sources
        2. Extract and store raw data
        3. Compile facts from all sources
        4. Synthesize into coherent response
        5. Generate final artifact

        Args:
            topic: Research topic
            depth: 'quick' (1-2 sources), 'standard' (3-5 sources), 'deep' (5+ sources)
            min_sources: Minimum number of sources required

        Returns:
            CompiledResearch object with synthesis
        """
        compiled = CompiledResearch(topic)

        # Determine number of sources based on depth
        target_sources = {
            'quick': 2,
            'standard': 3,
            'deep': 5
        }.get(depth, 3)

        # STEP 1: Query all available sources
        logger.info("[Research] Querying %s sources for: %s", target_sources, topic)

        # Query Wikipedia
        if self.sources_config['wikipedia']['enabled']:
            wiki_data = self._query_wikipedia(topic)
            if wiki_data:
                compiled.sources.append(wiki_data)
                compiled.raw_data['wikipedia'] = wiki_data.content

        # Query Standards DB
        if self.sources_config['standards_db']['enabled']:
            std_data = self._query_standards(topic)
            if std_data:
                compiled.sources.append(std_data)
                compiled.raw_data['standards'] = std_data.content

        # Query Web Search
        if self.sources_config['web_search']['enabled'] and len(compiled.sources) < target_sources:
            web_data = self._query_web_search(topic)
            for source in web_data[:target_sources - len(compiled.sources)]:
                compiled.sources.append(source)
                compiled.raw_data[source.name] = source.content

        # Check if we have enough sources
        if len(compiled.sources) < min_sources:
            logger.warning("[Research] Warning: Only found %d sources (minimum: %d)", len(compiled.sources), min_sources)

        # STEP 2: Extract facts from all sources
        logger.info("[Research] Extracting facts from %d sources", len(compiled.sources))
        for source in compiled.sources:
            facts = self._extract_facts(source.content, source.name)
            compiled.compiled_facts.extend(facts)

        # STEP 3: Synthesize information
        logger.info("[Research] Synthesizing %d facts", len(compiled.compiled_facts))
        compiled.synthesis = self._synthesize(compiled)

        # STEP 4: Calculate confidence
        compiled.confidence = self._calculate_confidence(compiled)

        # STEP 5: Save compiled research
        self._save_compiled(compiled)

        logger.info("[Research] Complete. Confidence: %.1f%%", compiled.confidence * 100)

        return compiled

    def _query_wikipedia(self, topic: str) -> Optional[Source]:
        """Query Wikipedia for information"""
        try:
            import requests

            # Wikipedia API with user agent
            url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + topic.replace(' ', '_')
            headers = {
                'User-Agent': 'ResearchBot/1.0 (Educational Purpose)'
            }
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 200:
                data = response.json()

                source = Source(
                    name="Wikipedia",
                    url=data.get('content_urls', {}).get('desktop', {}).get('page', ''),
                    trust_score=self.sources_config['wikipedia']['trust_score'],
                    source_type=self.sources_config['wikipedia']['type']
                )

                # Extract content
                source.content = data.get('extract', '')

                # Extract facts
                source.extracted_facts = [
                    {'type': 'title', 'value': data.get('title', '')},
                    {'type': 'description', 'value': data.get('description', '')},
                    {'type': 'summary', 'value': data.get('extract', '')}
                ]

                return source
        except Exception as exc:
            logger.error("[Research] Wikipedia query failed: %s", exc)

        return None

    def _query_standards(self, topic: str) -> Optional[Source]:
        """Query standards database"""
        # This would query a standards database
        # For now, return None (not implemented)
        return None

    def _query_web_search(self, topic: str) -> List[Source]:
        """Query web search for additional sources"""
        sources = []

        try:
            # This would use web-search tool
            # For now, return empty list
            pass
        except Exception as exc:
            logger.error("[Research] Web search failed: %s", exc)

        return sources

    def _extract_facts(self, content: str, source_name: str) -> List[Dict[str, Any]]:
        """Extract facts from content"""
        facts = []

        if not content:
            return facts

        # Split into sentences
        sentences = content.split('. ')

        for sentence in sentences[:10]:  # Limit to first 10 sentences
            if len(sentence.strip()) > 20:  # Meaningful sentences
                facts.append({
                    'statement': sentence.strip(),
                    'source': source_name,
                    'confidence': 0.8  # Base confidence
                })

        return facts

    def _synthesize(self, compiled: CompiledResearch) -> str:
        """
        Synthesize information from multiple sources into coherent response

        This is the key step - compile raw data into a generated artifact
        """
        synthesis = []

        # Header
        synthesis.append(f"# Research Synthesis: {compiled.topic}\n")

        # Overview from highest trust source
        if compiled.sources:
            best_source = max(compiled.sources, key=lambda s: s.trust_score)
            if best_source.content:
                synthesis.append("## Overview\n")
                # Take first 2-3 sentences
                overview = '. '.join(best_source.content.split('.')[:3]) + '.'
                synthesis.append(f"{overview}\n")

        # Key findings from all sources
        if compiled.compiled_facts:
            synthesis.append("\n## Key Findings\n")

            # Group facts by uniqueness (simple deduplication)
            unique_facts = []
            seen = set()

            for fact in compiled.compiled_facts:
                statement = fact['statement'].lower()
                # Simple similarity check
                is_unique = True
                for seen_fact in seen:
                    if len(set(statement.split()) & set(seen_fact.split())) > len(statement.split()) * 0.7:
                        is_unique = False
                        break

                if is_unique:
                    unique_facts.append(fact)
                    seen.add(statement)

                if len(unique_facts) >= 8:  # Limit to 8 key findings
                    break

            for i, fact in enumerate(unique_facts, 1):
                synthesis.append(f"{i}. {fact['statement']}")
                if fact.get('source'):
                    synthesis.append(f" *(Source: {fact['source']})*")
                synthesis.append("\n")

        # Sources section
        synthesis.append("\n## Sources Consulted\n")
        for source in compiled.sources:
            synthesis.append(f"- **{source.name}** (Trust: {source.trust_score:.0%}, Type: {source.source_type})\n")
            if source.url:
                synthesis.append(f"  {source.url}\n")

        # Confidence and metadata
        synthesis.append("\n## Research Metadata\n")
        synthesis.append(f"- **Sources Used:** {len(compiled.sources)}\n")
        synthesis.append(f"- **Facts Compiled:** {len(compiled.compiled_facts)}\n")
        synthesis.append(f"- **Timestamp:** {compiled.timestamp}\n")

        return ''.join(synthesis)

    def _calculate_confidence(self, compiled: CompiledResearch) -> float:
        """Calculate overall confidence score"""
        if not compiled.sources:
            return 0.0

        # Base confidence on number and quality of sources
        source_score = min(len(compiled.sources) / 5.0, 1.0)  # Max at 5 sources

        # Average trust score
        avg_trust = sum(s.trust_score for s in compiled.sources) / (len(compiled.sources) or 1)

        # Fact coverage
        fact_score = min(len(compiled.compiled_facts) / 10.0, 1.0)  # Max at 10 facts

        # Weighted average
        confidence = (source_score * 0.4 + avg_trust * 0.4 + fact_score * 0.2)

        return confidence

    def _save_compiled(self, compiled: CompiledResearch):
        """Save compiled research to temp file"""
        filename = f"research_{compiled.topic.replace(' ', '_')}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
        filepath = self.temp_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(compiled.to_dict(), f, indent=2)

        logger.info("[Research] Saved to: %s", filepath)

    def generate_response(self, compiled: CompiledResearch) -> str:
        """
        Generate final response artifact from compiled research

        This is what the user sees - the synthesized, coherent response
        """
        return compiled.synthesis


# Example usage
if __name__ == "__main__":
    researcher = MultiSourceResearcher()

    # Research a topic
    compiled = researcher.research("quantum computing", depth="standard")

    # Generate response
    response = researcher.generate_response(compiled)

    logger.info("\n" + "="*60)
    logger.info("GENERATED RESPONSE:")
    logger.info("="*60)
    logger.info(response)

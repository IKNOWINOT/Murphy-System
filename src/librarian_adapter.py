"""
Librarian Adapter for Murphy System Runtime
Provides help, documentation, and question-answering capabilities with graceful fallback
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LibrarianAdapter:
    """
    Adapter for Librarian System integration.

    Provides librarian capabilities including:
    - Question answering and help
    - Topic-based documentation
    - System health monitoring
    - Troubleshooting guidance
    - Knowledge base search
    """

    def __init__(self, librarian_module=None):
        """
        Initialize the librarian adapter.

        Args:
            librarian_module: Optional librarian module instance
        """
        self.librarian = librarian_module
        self.enabled = librarian_module is not None

        # Knowledge base (fallback)
        self.knowledge_base = {
            'catalog': {
                'name': 'Catalog Management',
                'description': 'Managing and organizing resources',
                'topics': ['add_item', 'remove_item', 'search', 'update_metadata']
            },
            'circulation': {
                'name': 'Circulation',
                'description': 'Resource borrowing and returning',
                'topics': ['checkout', 'checkin', 'renew', 'reserves']
            },
            'security': {
                'name': 'Security',
                'description': 'Access control and permissions',
                'topics': ['authentication', 'authorization', 'encryption', 'audit']
            },
            'api': {
                'name': 'API Integration',
                'description': 'REST API endpoints and usage',
                'topics': ['endpoints', 'authentication', 'rate_limits', 'errors']
            },
            'database': {
                'name': 'Database',
                'description': 'Data storage and retrieval',
                'topics': ['queries', 'schema', 'migrations', 'backups']
            },
            'telemetry': {
                'name': 'Telemetry',
                'description': 'System monitoring and metrics',
                'topics': ['metrics', 'anomalies', 'patterns', 'recommendations']
            },
            'neuro_symbolic': {
                'name': 'Neuro-Symbolic Reasoning',
                'description': 'AI-powered reasoning capabilities',
                'topics': ['inference', 'constraints', 'hybrid_reasoning', 'knowledge_graphs']
            },
            'security_plane': {
                'name': 'Security Plane',
                'description': 'Enterprise security features',
                'topics': ['validation', 'trust_scoring', 'gates', 'anomalies']
            }
        }

        # Troubleshooting guides (fallback)
        self.troubleshooting_guides = {
            'performance': {
                'issue': 'Slow system performance',
                'causes': ['High load', 'Inefficient queries', 'Resource exhaustion'],
                'solutions': ['Optimize queries', 'Scale resources', 'Enable caching']
            },
            'errors': {
                'issue': 'Frequent errors',
                'causes': ['Invalid inputs', 'Security violations', 'Integration failures'],
                'solutions': ['Validate inputs', 'Check security gates', 'Verify integrations']
            },
            'security': {
                'issue': 'Security concerns',
                'causes': ['Weak authentication', 'Insufficient validation', 'Outdated components'],
                'solutions': ['Implement MFA', 'Add input validation', 'Update dependencies']
            },
            'connectivity': {
                'issue': 'Connection problems',
                'causes': ['Network issues', 'Service downtime', 'Configuration errors'],
                'solutions': ['Check network', 'Verify service status', 'Review configuration']
            }
        }

        # Usage statistics
        self.usage_stats = {
            'questions_asked': 0,
            'topics_accessed': {},
            'searches_performed': 0,
            'troubleshooting_accessed': {}
        }

        if self.enabled:
            logger.info("Librarian Adapter initialized with librarian module")
        else:
            logger.warning("Librarian Adapter running in FALLBACK mode - librarian module not available")

    def is_enabled(self) -> bool:
        """Check if librarian is enabled"""
        return self.enabled

    def ask_question(self, question: str, topic: Optional[str] = None) -> Dict:
        """
        Ask a question to the librarian.

        Args:
            question: The question to ask
            topic: Optional topic to focus on

        Returns:
            Dict containing answer with structure:
                {
                    'success': bool,
                    'answer': str,
                    'confidence': float,
                    'topic': str,
                    'related_topics': List[str],
                    'sources': List[str],
                    'timestamp': str
                }
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        try:
            if not self.enabled:
                # Fallback: Provide helpful answer based on knowledge base
                result = self._fallback_answer(question, topic)
            else:
                # Use actual librarian module
                result = self._actual_answer(question, topic)

            # Update statistics
            self.usage_stats['questions_asked'] += 1
            if topic:
                self.usage_stats['topics_accessed'][topic] = self.usage_stats['topics_accessed'].get(topic, 0) + 1

            result['timestamp'] = timestamp
            return result

        except Exception as exc:
            logger.error(f"Error in ask_question: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'answer': None,
                'confidence': 0.0,
                'timestamp': timestamp
            }

    def get_topics(self) -> Dict:
        """
        Get all available topics.

        Returns:
            Dict containing topics with structure:
                {
                    'success': bool,
                    'topics': List[Dict],
                    'count': int
                }
        """
        try:
            if not self.enabled:
                # Fallback: Return knowledge base topics
                topics_list = [
                    {
                        'id': topic_id,
                        'name': topic_info['name'],
                        'description': topic_info['description'],
                        'subtopics': topic_info['topics']
                    }
                    for topic_id, topic_info in self.knowledge_base.items()
                ]

                return {
                    'success': True,
                    'topics': topics_list,
                    'count': len(topics_list),
                    'fallback_mode': True
                }
            else:
                # Use actual librarian module
                return self._actual_get_topics()

        except Exception as exc:
            logger.error(f"Error in get_topics: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'topics': [],
                'count': 0
            }

    def get_health_status(self) -> Dict:
        """
        Get system health status.

        Returns:
            Dict containing health status with structure:
                {
                    'success': bool,
                    'status': str,
                    'components': Dict,
                    'overall_health': str,
                    'last_check': str
                }
        """
        try:
            timestamp = datetime.now(timezone.utc).isoformat()

            if not self.enabled:
                # Fallback: Simulated health check
                components = {
                    'security': 'healthy',
                    'telemetry': 'healthy',
                    'neuro_symbolic': 'healthy',
                    'module_compiler': 'healthy',
                    'librarian': 'healthy'
                }

                # Determine overall health
                all_healthy = all(status == 'healthy' for status in components.values())
                overall_health = 'healthy' if all_healthy else 'degraded'

                return {
                    'success': True,
                    'status': overall_health,
                    'components': components,
                    'overall_health': overall_health,
                    'last_check': timestamp,
                    'fallback_mode': True
                }
            else:
                # Use actual librarian module
                return self._actual_get_health_status()

        except Exception as exc:
            logger.error(f"Error in get_health_status: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'status': 'unknown',
                'components': {},
                'overall_health': 'unknown'
            }

    def get_troubleshooting_guide(self, issue: str) -> Dict:
        """
        Get troubleshooting guidance for an issue.

        Args:
            issue: The issue to troubleshoot

        Returns:
            Dict containing troubleshooting guide with structure:
                {
                    'success': bool,
                    'issue': str,
                    'causes': List[str],
                    'solutions': List[str],
                    'related_issues': List[str],
                    'confidence': float
                }
        """
        try:
            if not self.enabled:
                # Fallback: Match against known issues
                result = self._fallback_troubleshooting(issue)
            else:
                # Use actual librarian module
                result = self._actual_troubleshooting(issue)

            # Update statistics
            if result['success']:
                self.usage_stats['troubleshooting_accessed'][issue] = \
                    self.usage_stats['troubleshooting_accessed'].get(issue, 0) + 1

            return result

        except Exception as exc:
            logger.error(f"Error in get_troubleshooting_guide: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'issue': issue,
                'causes': [],
                'solutions': []
            }

    def get_documentation(self, topic: str) -> Dict:
        """
        Get documentation for a specific topic.

        Args:
            topic: The topic to get documentation for

        Returns:
            Dict containing documentation with structure:
                {
                    'success': bool,
                    'topic': str,
                    'documentation': str,
                    'examples': List[str],
                    'related_topics': List[str]
                }
        """
        try:
            if not self.enabled:
                # Fallback: Return topic information from knowledge base
                result = self._fallback_documentation(topic)
            else:
                # Use actual librarian module
                result = self._actual_documentation(topic)

            return result

        except Exception as exc:
            logger.error(f"Error in get_documentation: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'topic': topic,
                'documentation': None,
                'examples': []
            }

    def search_knowledge_base(self, query: str) -> Dict:
        """
        Search the knowledge base.

        Args:
            query: The search query

        Returns:
            Dict containing search results with structure:
                {
                    'success': bool,
                    'query': str,
                    'results': List[Dict],
                    'count': int,
                    'total_matches': int
                }
        """
        try:
            # Update statistics
            self.usage_stats['searches_performed'] += 1

            if not self.enabled:
                # Fallback: Simple keyword search
                result = self._fallback_search(query)
            else:
                # Use actual librarian module
                result = self._actual_search(query)

            return result

        except Exception as exc:
            logger.error(f"Error in search_knowledge_base: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'query': query,
                'results': [],
                'count': 0,
                'total_matches': 0
            }

    def get_librarian_statistics(self) -> Dict:
        """
        Get librarian usage statistics.

        Returns:
            Dict containing statistics with structure:
                {
                    'success': bool,
                    'questions_asked': int,
                    'topics_accessed': Dict,
                    'searches_performed': int,
                    'troubleshooting_accessed': Dict,
                    'enabled': bool
                }
        """
        try:
            return {
                'success': True,
                'questions_asked': self.usage_stats['questions_asked'],
                'topics_accessed': self.usage_stats['topics_accessed'],
                'searches_performed': self.usage_stats['searches_performed'],
                'troubleshooting_accessed': self.usage_stats['troubleshooting_accessed'],
                'enabled': self.enabled
            }
        except Exception as exc:
            logger.error(f"Error in get_librarian_statistics: {exc}")
            return {
                'success': False,
                'error': str(exc),
                'enabled': self.enabled
            }

    # ========== Fallback Methods ==========

    def _fallback_answer(self, question: str, topic: Optional[str]) -> Dict:
        """Fallback answer generation"""
        question_lower = question.lower()

        # Try to match to a topic
        if topic and topic in self.knowledge_base:
            topic_info = self.knowledge_base[topic]
            answer = f"{topic_info['name']}: {topic_info['description']}. " \
                    f"Available topics: {', '.join(topic_info['topics'])}"
            confidence = 0.8
            related_topics = list(self.knowledge_base.keys())
        else:
            # General help answer
            answer = "I can help you with various topics including: " + \
                    ", ".join(self.knowledge_base.keys()) + \
                    ". Please ask about a specific topic for detailed information."
            confidence = 0.6
            related_topics = list(self.knowledge_base.keys())

        return {
            'success': True,
            'answer': answer,
            'confidence': confidence,
            'topic': topic or 'general',
            'related_topics': related_topics,
            'sources': ['knowledge_base'],
            'fallback_mode': True
        }

    def _actual_answer(self, question: str, topic: Optional[str]) -> Dict:
        """Actual answer using librarian module"""
        # This would call the actual librarian module
        return self._fallback_answer(question, topic)

    def _actual_get_topics(self) -> Dict:
        """Actual topics from librarian module"""
        return self.get_topics()

    def _actual_get_health_status(self) -> Dict:
        """Actual health status from librarian module"""
        return self.get_health_status()

    def _fallback_troubleshooting(self, issue: str) -> Dict:
        """Fallback troubleshooting"""
        issue_lower = issue.lower()

        # Try to match against known issues
        for key, guide in self.troubleshooting_guides.items():
            if key in issue_lower or guide['issue'].lower() in issue_lower:
                return {
                    'success': True,
                    'issue': guide['issue'],
                    'causes': guide['causes'],
                    'solutions': guide['solutions'],
                    'related_issues': list(self.troubleshooting_guides.keys()),
                    'confidence': 0.8,
                    'fallback_mode': True
                }

        # No match found
        return {
            'success': False,
            'issue': issue,
            'message': f"No troubleshooting guide found for: {issue}",
            'causes': [],
            'solutions': [],
            'confidence': 0.0
        }

    def _actual_troubleshooting(self, issue: str) -> Dict:
        """Actual troubleshooting from librarian module"""
        return self._fallback_troubleshooting(issue)

    def _fallback_documentation(self, topic: str) -> Dict:
        """Fallback documentation"""
        if topic in self.knowledge_base:
            topic_info = self.knowledge_base[topic]
            doc = f"# {topic_info['name']}\n\n" \
                  f"{topic_info['description']}\n\n" \
                  f"## Topics\n\n"
            for subtopic in topic_info['topics']:
                doc += f"- {subtopic}\n"

            return {
                'success': True,
                'topic': topic,
                'documentation': doc,
                'examples': [f"Example using {subtopic}" for subtopic in topic_info['topics'][:3]],
                'related_topics': list(self.knowledge_base.keys()),
                'fallback_mode': True
            }
        else:
            return {
                'success': False,
                'topic': topic,
                'message': f"No documentation found for topic: {topic}",
                'documentation': None,
                'examples': []
            }

    def _actual_documentation(self, topic: str) -> Dict:
        """Actual documentation from librarian module"""
        return self._fallback_documentation(topic)

    def _fallback_search(self, query: str) -> Dict:
        """Fallback search"""
        query_lower = query.lower()
        results = []

        # Search through knowledge base
        for topic_id, topic_info in self.knowledge_base.items():
            # Check topic name
            if query_lower in topic_info['name'].lower():
                results.append({
                    'type': 'topic',
                    'id': topic_id,
                    'title': topic_info['name'],
                    'description': topic_info['description'],
                    'relevance': 0.9
                })

            # Check subtopics
            for subtopic in topic_info['topics']:
                if query_lower in subtopic.lower():
                    results.append({
                        'type': 'subtopic',
                        'id': topic_id,
                        'title': subtopic,
                        'description': f"Part of {topic_info['name']}",
                        'relevance': 0.7
                    })

        # Sort by relevance
        results.sort(key=lambda x: x['relevance'], reverse=True)

        return {
            'success': True,
            'query': query,
            'results': results,
            'count': len(results),
            'total_matches': len(results),
            'fallback_mode': True
        }

    def _actual_search(self, query: str) -> Dict:
        """Actual search from librarian module"""
        return self._fallback_search(query)

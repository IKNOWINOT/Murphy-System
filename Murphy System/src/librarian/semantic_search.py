"""
Semantic Search Engine for Librarian Module
Provides intelligent search and retrieval capabilities
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SemanticSearchEngine:
    """
    Advanced semantic search engine with natural language understanding.

    Provides:
    - Semantic query processing
    - Relevance ranking
    - Concept extraction
    - Context-aware search
    """

    def __init__(self, knowledge_base):
        """
        Initialize the semantic search engine.

        Args:
            knowledge_base: Reference to the knowledge base
        """
        self.knowledge_base = knowledge_base
        self.query_history: List[Dict] = []
        self.concept_index: Dict[str, List[str]] = {}

        # Search configuration
        self.config = {
            'relevance_threshold': 0.3,
            'max_results': 20,
            'enable_fuzzy_matching': True,
            'boost_recent': True
        }

        logger.info("Semantic Search Engine initialized")

    def search(self,
               query: str,
               filters: Optional[Dict] = None,
               limit: int = 10) -> List[Dict]:
        """
        Perform semantic search on the knowledge base.

        Args:
            query: Natural language query
            filters: Optional metadata filters
            limit: Maximum number of results

        Returns:
            List of ranked search results with relevance scores
        """
        try:
            # Process the query
            processed_query = self._process_query(query)

            # Search for matching entries
            candidates = self.knowledge_base.query(processed_query['text'], filters, limit * 2)

            # Calculate relevance scores
            scored_results = self._calculate_relevance(candidates, processed_query)

            # Sort by relevance and apply threshold
            ranked_results = sorted(
                scored_results,
                key=lambda x: x['relevance_score'],
                reverse=True
            )

            # Apply threshold and limit
            final_results = [
                result for result in ranked_results
                if result['relevance_score'] >= self.config['relevance_threshold']
            ][:limit]

            # Log query for learning
            self._log_query(query, processed_query, len(final_results))

            logger.info(f"Semantic search returned {len(final_results)} results")
            return final_results

        except Exception as exc:
            logger.error(f"Error in semantic search: {exc}")
            return []

    def _process_query(self, query: str) -> Dict:
        """
        Process and analyze the search query.

        Args:
            query: Raw query string

        Returns:
            Processed query with extracted features
        """
        # Convert to lowercase and clean
        cleaned_query = query.lower().strip()

        # Extract key terms
        terms = self._extract_terms(cleaned_query)

        # Identify query type
        query_type = self._classify_query_type(cleaned_query)

        # Extract concepts
        concepts = self._extract_concepts(cleaned_query)

        return {
            'original': query,
            'text': cleaned_query,
            'terms': terms,
            'query_type': query_type,
            'concepts': concepts,
            'processed_at': datetime.now(timezone.utc).isoformat()
        }

    def _extract_terms(self, query: str) -> List[str]:
        """
        Extract meaningful terms from the query.

        Args:
            query: Cleaned query string

        Returns:
            List of extracted terms
        """
        # Remove stopwords and extract meaningful terms
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'with', 'by'}

        # Split into words
        words = re.findall(r'\b\w+\b', query)

        # Filter stopwords and short words
        terms = [word for word in words if word not in stopwords and len(word) > 2]

        return terms

    def _classify_query_type(self, query: str) -> str:
        """
        Classify the type of query.

        Args:
            query: Cleaned query string

        Returns:
            Query type classification
        """
        question_words = {'what', 'how', 'why', 'when', 'where', 'who', 'which', 'can', 'could', 'should', 'would'}

        if any(word in query.split() for word in question_words):
            return 'question'
        elif any(operator in query for operator in ['=', '>', '<', '!=', '>=', '<=']):
            return 'comparison'
        elif 'list' in query or 'show' in query or 'get' in query:
            return 'retrieval'
        else:
            return 'search'

    def _extract_concepts(self, query: str) -> List[str]:
        """
        Extract key concepts from the query.

        Args:
            query: Cleaned query string

        Returns:
            List of extracted concepts
        """
        # Simple concept extraction based on capitalized terms and phrases
        concepts = []

        # Look for technical terms or proper nouns
        technical_pattern = r'\b[A-Z][a-zA-Z]+\b'
        concepts.extend(re.findall(technical_pattern, query))

        # Look for compound terms
        compound_pattern = r'\b\w+[_-]\w+\b'
        concepts.extend(re.findall(compound_pattern, query))

        return list(set(concepts))

    def _calculate_relevance(self, candidates: List[Dict], processed_query: Dict) -> List[Dict]:
        """
        Calculate relevance scores for candidate entries.

        Args:
            candidates: List of candidate entries
            processed_query: Processed query information

        Returns:
            List of entries with relevance scores
        """
        scored_results = []

        for candidate in candidates:
            score = 0.0

            # Term matching score
            content_str = json.dumps(candidate['content']).lower()
            metadata_str = json.dumps(candidate.get('metadata', {})).lower()
            combined_text = content_str + ' ' + metadata_str

            for term in processed_query['terms']:
                if term in combined_text:
                    score += 0.3
                # Bonus for exact phrase matches
                if processed_query['text'] in combined_text:
                    score += 0.5

            # Concept matching bonus
            for concept in processed_query['concepts']:
                if concept.lower() in combined_text:
                    score += 0.4

            # Recent content bonus (if enabled)
            if self.config['boost_recent']:
                created_at = candidate.get('created_at', '')
                if created_at:
                    try:
                        created_time = datetime.fromisoformat(created_at)
                        days_old = (datetime.now(timezone.utc) - created_time).days
                        if days_old < 7:
                            score += 0.2
                        elif days_old < 30:
                            score += 0.1
                    except Exception as exc:
                        logger.debug("Suppressed exception: %s", exc)
                        pass

            # Access popularity bonus
            access_count = candidate.get('access_count', 0)
            score += min(0.3, access_count * 0.05)

            # Normalize score to 0-1 range
            normalized_score = min(1.0, score / 2.0)

            candidate_with_score = candidate.copy()
            candidate_with_score['relevance_score'] = round(normalized_score, 4)
            scored_results.append(candidate_with_score)

        return scored_results

    def suggest_queries(self, partial_query: str, limit: int = 5) -> List[str]:
        """
        Suggest query completions based on history and knowledge base.

        Args:
            partial_query: Partial query string
            limit: Maximum number of suggestions

        Returns:
            List of suggested query completions
        """
        try:
            suggestions = []

            # Extract terms from partial query
            terms = self._extract_terms(partial_query.lower())

            # Find related concepts from knowledge base
            for entry in self.knowledge_base.knowledge_store.values():
                content_str = json.dumps(entry['content']).lower()

                for term in terms:
                    if term in content_str:
                        # Extract context around the term
                        context = self._extract_context(content_str, term)
                        if context and context not in suggestions:
                            suggestions.append(context)
                        if len(suggestions) >= limit:
                            break

                if len(suggestions) >= limit:
                    break

            return suggestions[:limit]

        except Exception as exc:
            logger.error(f"Error generating query suggestions: {exc}")
            return []

    def _extract_context(self, text: str, term: str, window: int = 20) -> str:
        """
        Extract context around a term in text.

        Args:
            text: Full text
            term: Term to find context for
            window: Number of words around the term

        Returns:
            Context string
        """
        try:
            words = text.split()

            for i, word in enumerate(words):
                if term in word.lower():
                    start = max(0, i - window)
                    end = min(len(words), i + window + 1)
                    context = ' '.join(words[start:end])
                    return context

            return ""

        except Exception as exc:
            logger.error(f"Error extracting context: {exc}")
            return ""

    def _log_query(self, query: str, processed_query: Dict, result_count: int):
        """
        Log query for learning and analytics.

        Args:
            query: Original query
            processed_query: Processed query information
            result_count: Number of results returned
        """
        log_entry = {
            'query': query,
            'terms': processed_query['terms'],
            'query_type': processed_query['query_type'],
            'result_count': result_count,
            'timestamp': datetime.now(timezone.utc).isoformat()
        }

        self.query_history.append(log_entry)

        # Keep only recent history
        if len(self.query_history) > 1000:
            self.query_history = self.query_history[-1000:]

    def get_search_statistics(self) -> Dict:
        """
        Get search engine statistics.

        Returns:
            Dictionary with statistics
        """
        query_types = {}
        for log in self.query_history:
            qtype = log['query_type']
            query_types[qtype] = query_types.get(qtype, 0) + 1

        return {
            'total_queries': len(self.query_history),
            'query_types': query_types,
            'avg_results_per_query': sum(log['result_count'] for log in self.query_history) / (len(self.query_history) or 1) if self.query_history else 0,
            'config': self.config.copy()
        }

"""
Deterministic Verification Layer
External truth sources - NO generation, only lookup
"""

import logging

logger = logging.getLogger(__name__)
import re

try:
    import requests
except ImportError:
    requests = None
try:
    import wikipedia
except ImportError:
    wikipedia = None
from datetime import datetime, timezone
from typing import Any, Dict, Optional

try:
    from SPARQLWrapper import JSON, SPARQLWrapper
except ImportError:
    SPARQLWrapper = None
    JSON = None
try:
    from state_machine import VerifiedFacts
except ImportError:
    from src.state_machine import VerifiedFacts


class StandardsDatabase:
    """
    Deterministic lookup for standards and specifications
    Uses curated database - no generation
    """

    def __init__(self):
        self.database = {
            "ISO 26262": {
                "title": "Road vehicles – Functional safety",
                "latest_revision": "2018",
                "parts": 12,
                "domain": "automotive",
                "organization": "ISO"
            },
            "ISO 9001": {
                "title": "Quality management systems",
                "latest_revision": "2015",
                "parts": 10,
                "domain": "quality",
                "organization": "ISO"
            },
            "IEC 61508": {
                "title": "Functional Safety of Electrical/Electronic/Programmable Electronic Safety-related Systems",
                "latest_revision": "2010",
                "parts": 7,
                "domain": "functional_safety",
                "organization": "IEC"
            },
            "DO-178C": {
                "title": "Software Considerations in Airborne Systems and Equipment Certification",
                "latest_revision": "2011",
                "parts": 1,
                "domain": "aviation",
                "organization": "RTCA"
            }
        }

    def lookup(self, entity: str) -> Optional[Dict[str, Any]]:
        """
        Deterministic lookup - returns None if not found
        """
        # Normalize entity name
        entity_normalized = entity.upper().strip()

        for key, value in self.database.items():
            if key.upper() == entity_normalized:
                return value

        return None


class WikipediaVerifier:
    """
    Uses Wikipedia as deterministic truth source
    """

    def __init__(self):
        wikipedia.set_lang("en")

    def lookup(self, entity: str) -> Optional[Dict[str, Any]]:
        """
        Look up entity on Wikipedia
        Returns structured data, not generated text
        """
        try:
            # Search for the page
            search_results = wikipedia.search(entity, results=1)

            if not search_results:
                return None

            # Get page
            page = wikipedia.page(search_results[0], auto_suggest=False)

            # Extract structured information
            return {
                "title": page.title,
                "summary": page.summary[:500],  # First 500 chars
                "url": page.url,
                "categories": page.categories[:10] if hasattr(page, 'categories') else []
            }

        except wikipedia.exceptions.DisambiguationError as exc:
            # Return disambiguation options
            return {
                "title": entity,
                "disambiguation": True,
                "options": exc.options[:5]
            }
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            return None


class WikidataVerifier:
    """
    Uses Wikidata SPARQL endpoint for structured data
    """

    def __init__(self):
        self.endpoint = "https://query.wikidata.org/sparql"
        self.sparql = SPARQLWrapper(self.endpoint)
        self.sparql.setReturnFormat(JSON)

    def lookup_by_label(self, label: str) -> Optional[Dict[str, Any]]:
        """
        Look up entity by label in Wikidata
        """
        query = f"""
        SELECT ?item ?itemLabel ?description WHERE {{
          ?item rdfs:label "{label}"@en.
          ?item schema:description ?description.
          FILTER(LANG(?description) = "en")
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT 1
        """

        try:
            self.sparql.setQuery(query)
            results = self.sparql.query().convert()

            if results["results"]["bindings"]:
                binding = results["results"]["bindings"][0]
                return {
                    "id": binding["item"]["value"],
                    "label": binding["itemLabel"]["value"],
                    "description": binding.get("description", {}).get("value", "")
                }

            return None

        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            return None


class CalculationEngine:
    """
    Deterministic calculations - no approximation
    """

    @staticmethod
    def evaluate(expression: str) -> Optional[float]:
        """
        Safely evaluate mathematical expressions
        Only allows basic arithmetic
        """
        # Remove whitespace
        expression = expression.replace(" ", "")

        # Only allow numbers, operators, parentheses, and decimal points
        if not re.match(r'^[\d+\-*/().]+$', expression):
            return None

        try:
            # Use ast.literal_eval for safer evaluation of literals only
            # For arithmetic expressions, we need a custom parser
            import ast
            import operator

            # Define safe operators
            operators = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.USub: operator.neg,
            }

            # Parse the expression
            node = ast.parse(expression, mode='eval')

            # Evaluate safely
            def eval_node(node):
                if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                    return node.value
                elif isinstance(node, ast.BinOp):
                    left = eval_node(node.left)
                    right = eval_node(node.right)
                    op_type = type(node.op)
                    if op_type in operators:
                        return operators[op_type](left, right)
                    else:
                        raise ValueError(f"Unsupported operator: {op_type}")
                elif isinstance(node, ast.UnaryOp):
                    operand = eval_node(node.operand)
                    op_type = type(node.op)
                    if op_type in operators:
                        return operators[op_type](operand)
                    else:
                        raise ValueError(f"Unsupported unary operator: {op_type}")
                else:
                    raise ValueError(f"Unsupported expression: {type(node)}")

            result = eval_node(node.body)
            return float(result)
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            return None

    @staticmethod
    def calculate_percentage(part: float, whole: float) -> Optional[float]:
        """Calculate percentage"""
        if whole == 0:
            return None
        return (part / whole) * 100

    @staticmethod
    def calculate_compound_interest(
        principal: float,
        rate: float,
        time: float,
        n: int = 1
    ) -> Optional[float]:
        """Calculate compound interest"""
        try:
            amount = principal * (1 + rate / n) ** (n * time)
            return round(amount, 2)
        except Exception as exc:
            logger.debug("Suppressed exception: %s", exc)
            return None


class VerificationOrchestrator:
    """
    Coordinates all verification sources
    """

    def __init__(self):
        self.standards_db = StandardsDatabase()
        self.wikipedia = WikipediaVerifier()
        self.wikidata = WikidataVerifier()
        self.calculator = CalculationEngine()

    def verify(self, entity: str, question_type: str) -> VerifiedFacts:
        """
        Attempt verification from multiple sources
        Returns VerifiedFacts with source attribution
        """
        sources = []
        facts = {}
        verified = False
        method = "none"

        # Try standards database first
        std_result = self.standards_db.lookup(entity)
        if std_result:
            facts.update(std_result)
            sources.append("standards_database")
            verified = True
            method = "standards_lookup"

        # Try Wikipedia
        if not verified or question_type == "definition":
            wiki_result = self.wikipedia.lookup(entity)
            if wiki_result and not wiki_result.get("disambiguation"):
                facts.update(wiki_result)
                sources.append("wikipedia")
                verified = True
                method = "wikipedia_lookup"

        # Try Wikidata for structured data
        if not verified:
            wikidata_result = self.wikidata.lookup_by_label(entity)
            if wikidata_result:
                facts.update(wikidata_result)
                sources.append("wikidata")
                verified = True
                method = "wikidata_sparql"

        return VerifiedFacts(
            entity=entity,
            facts=facts,
            sources=sources,
            verified=verified,
            verification_method=method,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

    def verify_calculation(self, expression: str) -> VerifiedFacts:
        """
        Verify a calculation
        """
        result = self.calculator.evaluate(expression)

        if result is not None:
            return VerifiedFacts(
                entity=expression,
                facts={"result": result, "expression": expression},
                sources=["calculation_engine"],
                verified=True,
                verification_method="deterministic_calculation",
                timestamp=datetime.now(timezone.utc).isoformat()
            )

        return VerifiedFacts(
            entity=expression,
            facts={},
            sources=[],
            verified=False,
            verification_method="calculation_failed",
            timestamp=datetime.now(timezone.utc).isoformat()
        )

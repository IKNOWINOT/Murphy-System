"""
External Validation Service Interface
Provides integration with external systems for validation and verification.
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ValidationType(str, Enum):
    """Types of external validation."""
    CREDENTIAL = "credential"
    DATA_SOURCE = "data_source"
    API_ENDPOINT = "api_endpoint"
    DOMAIN_EXPERT = "domain_expert"
    HISTORICAL_DATA = "historical_data"
    RESOURCE_AVAILABILITY = "resource_availability"


class ValidationStatus(str, Enum):
    """Status of validation check."""
    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"
    UNAVAILABLE = "unavailable"
    PENDING = "pending"
    ERROR = "error"


class ValidationResult(BaseModel):
    """Result of an external validation check."""
    validation_type: ValidationType
    status: ValidationStatus
    confidence: float = Field(ge=0.0, le=1.0)
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ExternalValidator(ABC):
    """Abstract base class for external validators."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.validation_cache: Dict[str, ValidationResult] = {}

    @abstractmethod
    async def validate(self, target: str, context: Dict[str, Any]) -> ValidationResult:
        """
        Validate a target using external service.

        Args:
            target: The item to validate (credential, endpoint, etc.)
            context: Additional context for validation

        Returns:
            ValidationResult with status and confidence
        """
        pass

    def get_cached_result(self, cache_key: str) -> Optional[ValidationResult]:
        """Get cached validation result if available."""
        return self.validation_cache.get(cache_key)

    def cache_result(self, cache_key: str, result: ValidationResult):
        """Cache validation result."""
        self.validation_cache[cache_key] = result


class CredentialValidator(ExternalValidator):
    """Validates credentials (API keys, tokens, etc.)."""

    async def validate(self, target: str, context: Dict[str, Any]) -> ValidationResult:
        """
        Validate a credential.

        Args:
            target: Credential string (API key, token, etc.)
            context: Contains credential_type, service_name, etc.

        Returns:
            ValidationResult indicating if credential is valid
        """
        credential_type = context.get("credential_type", "api_key")
        service_name = context.get("service_name", "unknown")

        # Check cache first
        cache_key = f"{service_name}:{credential_type}:{target[:10]}"
        cached = self.get_cached_result(cache_key)
        if cached:
            return cached

        try:
            # Simulate credential validation
            # In production, this would call actual service APIs
            is_valid = await self._check_credential(target, credential_type, service_name)

            result = ValidationResult(
                validation_type=ValidationType.CREDENTIAL,
                status=ValidationStatus.VALID if is_valid else ValidationStatus.INVALID,
                confidence=1.0 if is_valid else 0.0,
                details={
                    "credential_type": credential_type,
                    "service_name": service_name,
                    "checked_at": datetime.now(timezone.utc).isoformat()
                }
            )

            self.cache_result(cache_key, result)
            return result

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return ValidationResult(
                validation_type=ValidationType.CREDENTIAL,
                status=ValidationStatus.ERROR,
                confidence=0.0,
                error_message=str(exc)
            )

    async def _check_credential(self, credential: str, cred_type: str, service: str) -> bool:
        """
        Check if credential is valid.
        Validates minimum length, non-whitespace, alphanumeric content, and
        rejects obvious test/placeholder patterns.
        """
        try:
            if len(credential) <= 10:
                return False
            if credential.strip() == "":
                return False
            # Must contain at least one alphanumeric character
            if not any(c.isalnum() for c in credential):
                return False
            # Reject obvious test/placeholder patterns (case-insensitive)
            lower = credential.lower()
            for pattern in ("test", "xxx", "placeholder", "dummy", "example", "changeme"):
                if pattern in lower:
                    return False
            return True
        except Exception as exc:
            logger.debug("Credential check failed: %s", exc)
            return False


class DataSourceValidator(ExternalValidator):
    """Validates data sources (databases, APIs, files)."""

    async def validate(self, target: str, context: Dict[str, Any]) -> ValidationResult:
        """
        Validate a data source.

        Args:
            target: Data source identifier (URL, connection string, etc.)
            context: Contains source_type, required_fields, etc.

        Returns:
            ValidationResult indicating if data source is accessible
        """
        source_type = context.get("source_type", "api")

        try:
            is_available = await self._check_data_source(target, source_type)

            return ValidationResult(
                validation_type=ValidationType.DATA_SOURCE,
                status=ValidationStatus.VALID if is_available else ValidationStatus.UNAVAILABLE,
                confidence=1.0 if is_available else 0.0,
                details={
                    "source_type": source_type,
                    "target": target,
                    "checked_at": datetime.now(timezone.utc).isoformat()
                }
            )

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return ValidationResult(
                validation_type=ValidationType.DATA_SOURCE,
                status=ValidationStatus.ERROR,
                confidence=0.0,
                error_message=str(exc)
            )

    async def _check_data_source(self, source: str, source_type: str) -> bool:
        """
        Check if data source is available.
        Dispatches by source_type: api/url, database, file.
        Returns False for unknown types or on any exception.
        """
        try:
            if source_type in ("api", "url"):
                # Attempt async HEAD request with a 3-second timeout
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.head(source, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                            return resp.status < 500
                except ImportError:
                    # Fallback to urllib — run in executor to avoid blocking the event loop
                    import asyncio
                    import urllib.request

                    def _head_request():
                        req = urllib.request.Request(source, method="HEAD")
                        with urllib.request.urlopen(req, timeout=3) as resp:
                            return resp.status < 500

                    return await asyncio.to_thread(_head_request)

            elif source_type == "database":
                # Basic connection string format validation
                if not source:
                    return False
                # Must contain common delimiters used in connection strings
                has_delimiters = any(d in source for d in ("://", "@", ";", "="))
                return has_delimiters

            elif source_type == "file":
                import os
                return os.path.exists(source)

            else:
                # Unknown source type — do not trust
                return False

        except Exception as exc:
            logger.debug("Data source check failed: %s", exc)
            return False


class DomainExpertValidator(ExternalValidator):
    """Validates using domain expert knowledge bases."""

    async def validate(self, target: str, context: Dict[str, Any]) -> ValidationResult:
        """
        Validate using domain expertise.

        Args:
            target: Query or statement to validate
            context: Contains domain, expertise_level, etc.

        Returns:
            ValidationResult with expert confidence score
        """
        domain = context.get("domain", "general")

        try:
            expertise_score = await self._query_expert_system(target, domain)

            return ValidationResult(
                validation_type=ValidationType.DOMAIN_EXPERT,
                status=ValidationStatus.VALID if expertise_score > 0.7 else ValidationStatus.INVALID,
                confidence=expertise_score,
                details={
                    "domain": domain,
                    "query": target,
                    "expertise_score": expertise_score
                }
            )

        except Exception as exc:
            logger.debug("Caught exception: %s", exc)
            return ValidationResult(
                validation_type=ValidationType.DOMAIN_EXPERT,
                status=ValidationStatus.ERROR,
                confidence=0.0,
                error_message=str(exc)
            )

    async def _query_expert_system(self, query: str, domain: str) -> float:
        """
        Query domain expert system using keyword-based confidence lookup.
        Known domains receive a base score; unknown domains get 0.5.
        Domain-specific keyword matches adjust the score up or down.
        """
        try:
            domain_keywords: Dict[str, List[str]] = {
                "general": ["information", "data", "analysis", "result", "overview"],
                "software": ["code", "software", "program", "function", "algorithm",
                             "api", "library", "framework", "debug", "deploy"],
                "data": ["dataset", "database", "query", "schema", "table",
                         "pipeline", "etl", "analytics", "statistics", "model"],
                "security": ["vulnerability", "exploit", "authentication", "encryption",
                              "token", "firewall", "threat", "audit", "compliance", "access"],
            }
            base_scores: Dict[str, float] = {
                "general": 0.65,
                "software": 0.70,
                "data": 0.70,
                "security": 0.72,
            }

            domain_norm = domain.lower().strip()
            base = base_scores.get(domain_norm, 0.5)

            keywords = domain_keywords.get(domain_norm, [])
            if keywords:
                import re as _re
                query_lower = query.lower()
                # Use word-boundary matching to avoid false positives (e.g. 'code' in 'decode')
                matches = sum(1 for kw in keywords if _re.search(r'\b' + _re.escape(kw) + r'\b', query_lower))
                # Each keyword match adjusts score by +0.03, up to +0.15
                adjustment = min(matches * 0.03, 0.15)
                # If none of the domain keywords appear, penalise slightly
                if matches == 0:
                    adjustment = -0.1
                base = max(0.0, min(1.0, base + adjustment))

            return round(base, 4)

        except Exception as exc:
            logger.debug("Expert system query failed: %s", exc)
            return 0.5


class ExternalValidationService:
    """
    Orchestrates multiple external validators.
    Provides unified interface for all validation types.
    """

    def __init__(self):
        self.validators: Dict[ValidationType, ExternalValidator] = {
            ValidationType.CREDENTIAL: CredentialValidator(),
            ValidationType.DATA_SOURCE: DataSourceValidator(),
            ValidationType.DOMAIN_EXPERT: DomainExpertValidator()
        }

    def register_validator(self, validation_type: ValidationType, validator: ExternalValidator):
        """Register a custom validator."""
        self.validators[validation_type] = validator

    async def validate(
        self,
        validation_type: ValidationType,
        target: str,
        context: Dict[str, Any]
    ) -> ValidationResult:
        """
        Perform validation using appropriate validator.

        Args:
            validation_type: Type of validation to perform
            target: Item to validate
            context: Additional context

        Returns:
            ValidationResult
        """
        validator = self.validators.get(validation_type)
        if not validator:
            return ValidationResult(
                validation_type=validation_type,
                status=ValidationStatus.ERROR,
                confidence=0.0,
                error_message=f"No validator registered for {validation_type}"
            )

        return await validator.validate(target, context)

    async def validate_multiple(
        self,
        validations: List[tuple[ValidationType, str, Dict[str, Any]]]
    ) -> List[ValidationResult]:
        """
        Perform multiple validations in parallel.

        Args:
            validations: List of (validation_type, target, context) tuples

        Returns:
            List of ValidationResults
        """
        import asyncio

        tasks = [
            self.validate(val_type, target, context)
            for val_type, target, context in validations
        ]

        return await asyncio.gather(*tasks)

    def get_overall_confidence(self, results: List[ValidationResult]) -> float:
        """
        Calculate overall confidence from multiple validation results.

        Args:
            results: List of validation results

        Returns:
            Overall confidence score (0.0 to 1.0)
        """
        if not results:
            return 0.0

        valid_results = [r for r in results if r.status == ValidationStatus.VALID]
        if not valid_results:
            return 0.0

        # Weighted average of confidence scores
        total_confidence = sum(r.confidence for r in valid_results)
        return total_confidence / (len(results) or 1)

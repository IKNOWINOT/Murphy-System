"""
Comprehensive Unit Tests for Phase 2 Components
Tests for validation, risk management, and performance systems.
"""

import pytest
import asyncio
from datetime import datetime, timedelta

# Import Phase 2 components
from murphy_implementation.validation.external_validator import (
    ExternalValidationService, ValidationType, ValidationStatus
)
from murphy_implementation.validation.credential_verifier import (
    CredentialStore, CredentialVerifier, Credential, CredentialType
)
from murphy_implementation.validation.historical_analyzer import (
    HistoricalDataAnalysisSystem, DataSourceType, DataQualityMetric
)
from murphy_implementation.validation.domain_expertise import (
    DomainExpertiseSystem, ExpertiseLevel, DomainCategory, AssumptionType
)
from murphy_implementation.validation.information_quality import (
    InformationQualitySystem, InformationSource
)
from murphy_implementation.validation.resource_checker import (
    ResourceAvailabilitySystem, ResourceType, ResourceUnit
)
from murphy_implementation.risk.risk_database import (
    RiskDatabase, RiskPattern, RiskCategory, RiskSeverity, RiskLikelihood
)
from murphy_implementation.risk.risk_storage import (
    RiskPatternStorageSystem, RiskPatternQuery
)
from murphy_implementation.risk.risk_scoring import (
    RiskScoringSystem, ScoringMethod
)
from murphy_implementation.performance.optimization import (
    PerformanceOptimizationSystem
)


# ============================================================================
# EXTERNAL VALIDATION TESTS
# ============================================================================

class TestExternalValidation:
    """Tests for external validation service."""
    
    def test_credential_validation(self):
        """Test credential validation."""
        service = ExternalValidationService()
        
        result = asyncio.run(service.validate(
            ValidationType.CREDENTIAL,
            "test_api_key_12345",
            {"credential_type": "api_key", "service_name": "test_service"}
        ))
        
        assert result.validation_type == ValidationType.CREDENTIAL
        assert result.status in [ValidationStatus.VALID, ValidationStatus.INVALID]
    
    def test_data_source_validation(self):
        """Test data source validation."""
        service = ExternalValidationService()
        
        result = asyncio.run(service.validate(
            ValidationType.DATA_SOURCE,
            "https://api.example.com",
            {"source_type": "api"}
        ))
        
        assert result.validation_type == ValidationType.DATA_SOURCE
        assert result.confidence >= 0.0 and result.confidence <= 1.0


# ============================================================================
# CREDENTIAL VERIFICATION TESTS
# ============================================================================

class TestCredentialVerification:
    """Tests for credential verification system."""
    
    def test_credential_store(self):
        """Test credential storage."""
        store = CredentialStore()
        
        credential = Credential(
            id="test_1",
            credential_type=CredentialType.API_KEY,
            service_name="test_service",
            credential_value="test_key_123"
        )
        
        cred_id = store.add_credential(credential)
        assert cred_id == "test_1"
        
        retrieved = store.get_credential(cred_id)
        assert retrieved is not None
        assert retrieved.service_name == "test_service"
    
    def test_credential_expiry(self):
        """Test credential expiry detection."""
        credential = Credential(
            id="test_2",
            credential_type=CredentialType.API_KEY,
            service_name="test_service",
            credential_value="test_key_456",
            expires_at=datetime.utcnow() - timedelta(days=1)
        )
        
        assert credential.is_expired() == True
    
    def test_credential_verification(self):
        """Test credential verification."""
        store = CredentialStore()
        verifier = CredentialVerifier(store)
        
        credential = Credential(
            id="test_3",
            credential_type=CredentialType.API_KEY,
            service_name="test_service",
            credential_value="test_key_789"
        )
        
        store.add_credential(credential)
        
        result = asyncio.run(verifier.verify_credential("test_3"))
        assert result.credential_id == "test_3"


# ============================================================================
# HISTORICAL DATA ANALYSIS TESTS
# ============================================================================

class TestHistoricalAnalysis:
    """Tests for historical data analysis."""
    
    def test_data_point_recording(self):
        """Test recording data points."""
        system = HistoricalDataAnalysisSystem()
        
        system.record_data_point(
            source_name="test_source",
            source_type=DataSourceType.API,
            quality_metrics={
                DataQualityMetric.ACCURACY: 0.9,
                DataQualityMetric.COMPLETENESS: 0.85
            },
            success_count=10,
            error_count=1
        )
        
        analysis = system.analyze_source("test_source")
        assert analysis.data_points_analyzed > 0
    
    def test_ud_calculation(self):
        """Test UD calculation."""
        system = HistoricalDataAnalysisSystem()
        
        system.record_data_point(
            source_name="test_source",
            source_type=DataSourceType.API,
            quality_metrics={DataQualityMetric.ACCURACY: 0.8},
            success_count=8,
            error_count=2
        )
        
        ud_score = system.calculate_ud("test_source")
        assert ud_score >= 0.0 and ud_score <= 1.0


# ============================================================================
# DOMAIN EXPERTISE TESTS
# ============================================================================

class TestDomainExpertise:
    """Tests for domain expertise system."""
    
    def test_expert_registration(self):
        """Test expert registration."""
        system = DomainExpertiseSystem()
        
        expert_id = system.register_expert(
            name="Test Expert",
            expertise_level=ExpertiseLevel.EXPERT,
            domains=["software_development"],
            domain_categories=[DomainCategory.TECHNOLOGY],
            years_experience=10
        )
        
        assert expert_id is not None
    
    def test_ua_calculation(self):
        """Test UA calculation."""
        system = DomainExpertiseSystem()
        
        system.register_expert(
            name="Test Expert",
            expertise_level=ExpertiseLevel.EXPERT,
            domains=["software_development"],
            domain_categories=[DomainCategory.TECHNOLOGY],
            years_experience=10
        )
        
        ua_score = system.calculate_ua(
            assumption="The API will always return valid JSON",
            domain="software_development",
            assumption_type=AssumptionType.TECHNICAL
        )
        
        assert ua_score >= 0.0 and ua_score <= 1.0


# ============================================================================
# INFORMATION QUALITY TESTS
# ============================================================================

class TestInformationQuality:
    """Tests for information quality system."""
    
    def test_information_assessment(self):
        """Test information quality assessment."""
        system = InformationQualitySystem()
        
        info_id = system.add_information(
            content="This is a test article about software development.",
            source=InformationSource.OFFICIAL_DOCUMENTATION,
            published_date=datetime.utcnow()
        )
        
        assessment = system.assess_information(info_id)
        assert assessment.quality_score >= 0.0 and assessment.quality_score <= 1.0
    
    def test_ui_calculation(self):
        """Test UI calculation."""
        system = InformationQualitySystem()
        
        info_id = system.add_information(
            content="Test content",
            source=InformationSource.PEER_REVIEWED
        )
        
        ui_score = system.calculate_ui(info_id)
        assert ui_score >= 0.0 and ui_score <= 1.0


# ============================================================================
# RESOURCE AVAILABILITY TESTS
# ============================================================================

class TestResourceAvailability:
    """Tests for resource availability system."""
    
    def test_resource_registration(self):
        """Test resource registration."""
        system = ResourceAvailabilitySystem()
        
        resource_id = system.register_resource(
            name="Test CPU",
            resource_type=ResourceType.COMPUTE,
            total_capacity=100.0,
            available_capacity=75.0,
            unit=ResourceUnit.CORES
        )
        
        assert resource_id is not None
    
    def test_availability_check(self):
        """Test availability checking."""
        system = ResourceAvailabilitySystem()
        
        resource_id = system.register_resource(
            name="Test Memory",
            resource_type=ResourceType.MEMORY,
            total_capacity=16.0,
            available_capacity=8.0,
            unit=ResourceUnit.GIGABYTES
        )
        
        result = asyncio.run(system.check_availability(resource_id, 4.0))
        assert result.is_available == True


# ============================================================================
# RISK DATABASE TESTS
# ============================================================================

class TestRiskDatabase:
    """Tests for risk database."""
    
    def test_risk_pattern_storage(self):
        """Test storing risk patterns."""
        db = RiskDatabase()
        
        pattern = RiskPattern(
            id="test_risk_1",
            name="Test Risk",
            description="A test risk pattern",
            category=RiskCategory.TECHNICAL,
            severity=RiskSeverity.HIGH,
            likelihood=RiskLikelihood.MEDIUM,
            impact_score=7.0,
            probability_score=0.5,
            risk_score=3.5,
            keywords={"test", "risk"}
        )
        
        pattern_id = db.add_risk_pattern(pattern)
        assert pattern_id == "test_risk_1"
        
        retrieved = db.get_risk_pattern(pattern_id)
        assert retrieved is not None
        assert retrieved.name == "Test Risk"
    
    def test_risk_search(self):
        """Test risk pattern search."""
        db = RiskDatabase()
        
        results = db.search_risk_patterns(
            category=RiskCategory.SECURITY,
            min_risk_score=3.0
        )
        
        assert isinstance(results, list)


# ============================================================================
# RISK SCORING TESTS
# ============================================================================

class TestRiskScoring:
    """Tests for risk scoring system."""
    
    def test_basic_scoring(self):
        """Test basic risk scoring."""
        system = RiskScoringSystem()
        
        pattern = RiskPattern(
            id="test_risk_2",
            name="Test Risk",
            description="Test",
            category=RiskCategory.TECHNICAL,
            severity=RiskSeverity.HIGH,
            likelihood=RiskLikelihood.MEDIUM,
            impact_score=8.0,
            probability_score=0.6,
            risk_score=4.8,
            keywords=set()
        )
        
        breakdown = system.calculate_score(pattern, ScoringMethod.BASIC)
        assert breakdown.total_score >= 0.0 and breakdown.total_score <= 10.0
    
    def test_composite_scoring(self):
        """Test composite risk scoring."""
        system = RiskScoringSystem()
        
        pattern = RiskPattern(
            id="test_risk_3",
            name="Test Risk",
            description="Test",
            category=RiskCategory.SECURITY,
            severity=RiskSeverity.CRITICAL,
            likelihood=RiskLikelihood.HIGH,
            impact_score=9.0,
            probability_score=0.7,
            risk_score=6.3,
            keywords=set()
        )
        
        breakdown = system.calculate_score(pattern, ScoringMethod.COMPOSITE)
        assert breakdown.method_used == ScoringMethod.COMPOSITE


# ============================================================================
# PERFORMANCE OPTIMIZATION TESTS
# ============================================================================

class TestPerformanceOptimization:
    """Tests for performance optimization."""
    
    def test_cache_operations(self):
        """Test cache operations."""
        system = PerformanceOptimizationSystem()
        
        system.set_cached("test_key", "test_value")
        value = system.get_cached("test_key")
        
        assert value == "test_value"
    
    def test_cache_stats(self):
        """Test cache statistics."""
        system = PerformanceOptimizationSystem()
        
        system.set_cached("key1", "value1")
        system.get_cached("key1")
        system.get_cached("key2")  # Miss
        
        stats = system.get_cache_stats()
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
    
    def test_performance_monitoring(self):
        """Test performance monitoring."""
        system = PerformanceOptimizationSystem()
        
        system.record_performance("test_metric", 100.0, "ms")
        
        stats = system.get_performance_stats()
        assert "metrics" in stats


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """Integration tests for Phase 2 components."""
    
    def test_end_to_end_uncertainty_calculation(self):
        """Test complete uncertainty calculation flow."""
        # Initialize systems
        historical_system = HistoricalDataAnalysisSystem()
        domain_system = DomainExpertiseSystem()
        info_system = InformationQualitySystem()
        resource_system = ResourceAvailabilitySystem()
        
        # Record data
        historical_system.record_data_point(
            source_name="test_source",
            source_type=DataSourceType.API,
            quality_metrics={DataQualityMetric.ACCURACY: 0.9},
            success_count=9,
            error_count=1
        )
        
        # Calculate uncertainties
        ud = historical_system.calculate_ud("test_source")
        
        domain_system.register_expert(
            name="Expert",
            expertise_level=ExpertiseLevel.EXPERT,
            domains=["test"],
            domain_categories=[DomainCategory.TECHNOLOGY],
            years_experience=10
        )
        
        ua = domain_system.calculate_ua(
            "Test assumption",
            "test",
            AssumptionType.TECHNICAL
        )
        
        info_id = info_system.add_information(
            "Test content",
            InformationSource.OFFICIAL_DOCUMENTATION
        )
        ui = info_system.calculate_ui(info_id)
        
        # All uncertainties should be valid
        assert 0.0 <= ud <= 1.0
        assert 0.0 <= ua <= 1.0
        assert 0.0 <= ui <= 1.0
    
    def test_risk_management_flow(self):
        """Test complete risk management flow."""
        # Initialize systems
        storage_system = RiskPatternStorageSystem()
        scoring_system = RiskScoringSystem()
        
        # Store pattern
        pattern_id = storage_system.store_pattern(
            name="Test Risk",
            description="Integration test risk",
            category=RiskCategory.TECHNICAL,
            severity=RiskSeverity.HIGH,
            likelihood=RiskLikelihood.MEDIUM,
            impact_score=7.0,
            keywords=["test", "integration"]
        )
        
        # Retrieve and score
        pattern = storage_system.get_pattern(pattern_id)
        assert pattern is not None
        
        breakdown = scoring_system.calculate_score(pattern, ScoringMethod.COMPOSITE)
        assert breakdown.total_score > 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
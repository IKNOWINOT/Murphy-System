"""
Unit tests for verification layer
"""

import pytest
from src.verification_layer import (
    StandardsDatabase,
    CalculationEngine,
    VerificationOrchestrator
)


def test_standards_database_lookup():
    """Test standards database lookup"""
    db = StandardsDatabase()

    # Test successful lookup
    result = db.lookup("ISO 26262")
    assert result is not None
    assert result["title"] == "Road vehicles – Functional safety"
    assert result["latest_revision"] == "2018"

    # Test case insensitivity
    result_lower = db.lookup("iso 26262")
    assert result_lower is not None

    # Test not found
    result_none = db.lookup("NONEXISTENT")
    assert result_none is None


def test_calculation_engine():
    """Test calculation engine"""
    calc = CalculationEngine()

    # Test basic arithmetic
    assert calc.evaluate("2 + 2") == 4.0
    assert calc.evaluate("10 * 5") == 50.0
    assert calc.evaluate("100 / 4") == 25.0
    assert calc.evaluate("(10 + 5) * 2") == 30.0

    # Test invalid expressions
    assert calc.evaluate("import os") is None
    assert calc.evaluate("print('hello')") is None

    # Test percentage calculation
    assert calc.calculate_percentage(25, 100) == 25.0
    assert calc.calculate_percentage(50, 200) == 25.0
    assert calc.calculate_percentage(10, 0) is None


def test_verification_orchestrator():
    """Test verification orchestrator"""
    try:
        orchestrator = VerificationOrchestrator()
    except AttributeError:
        pytest.skip("Wikipedia module not available (optional dependency)")

    # Test standards verification
    result = orchestrator.verify("ISO 26262", "factual_lookup")
    assert result.verified == True
    assert "standards_database" in result.sources
    assert result.facts["latest_revision"] == "2018"

    # Test calculation verification
    calc_result = orchestrator.verify_calculation("5 + 5")
    assert calc_result.verified == True
    assert calc_result.facts["result"] == 10.0

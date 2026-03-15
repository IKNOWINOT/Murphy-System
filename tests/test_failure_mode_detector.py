"""
Tests for Enhanced Failure Mode Detector

Tests capability-specific failure mode detection.
"""

import unittest
from src.module_compiler.analyzers.failure_mode_detector import (
    EnhancedFailureModeDetector,
    FailureMode
)


class TestFailureModeDetector(unittest.TestCase):
    """Test enhanced failure mode detection"""

    def setUp(self):
        self.detector = EnhancedFailureModeDetector()

    def test_network_failure_detection(self):
        """Test detection of network failure modes"""
        code = '''
import requests

def fetch_data(url):
    response = requests.get(url, timeout=5)
    return response.json()
'''

        failures = self.detector.detect_failure_modes(code)

        # Should detect network-specific failures
        network_failures = [f for f in failures if f.category == "network"]
        self.assertGreater(len(network_failures), 0)

        # Check for specific network failures
        descriptions = [f.description.lower() for f in network_failures]
        self.assertTrue(any("timeout" in d for d in descriptions))
        self.assertTrue(any("connection" in d for d in descriptions))

    def test_filesystem_failure_detection(self):
        """Test detection of file system failure modes"""
        code = '''
def read_config(path):
    with open(path, 'r') as f:
        return f.read()
'''

        failures = self.detector.detect_failure_modes(code)

        # Should detect filesystem-specific failures
        fs_failures = [f for f in failures if f.category == "filesystem"]
        self.assertGreater(len(fs_failures), 0)

        # Check for specific filesystem failures
        descriptions = [f.description.lower() for f in fs_failures]
        self.assertTrue(any("not found" in d for d in descriptions))
        self.assertTrue(any("permission" in d for d in descriptions))

    def test_computation_failure_detection(self):
        """Test detection of computation failure modes"""
        code = '''
def calculate_ratio(a, b):
    return a / b
'''

        failures = self.detector.detect_failure_modes(code)

        # Should detect computation-specific failures
        comp_failures = [f for f in failures if f.category == "computation"]
        self.assertGreater(len(comp_failures), 0)

        # Check for division by zero
        descriptions = [f.description.lower() for f in comp_failures]
        self.assertTrue(any("division by zero" in d for d in descriptions))

    def test_state_failure_detection(self):
        """Test detection of state failure modes"""
        code = '''
class Counter:
    def __init__(self):
        self.count = 0

    def increment(self):
        self.count += 1
'''

        failures = self.detector.detect_failure_modes(code)

        # Should detect state-specific failures
        state_failures = [f for f in failures if f.category == "state"]
        self.assertGreater(len(state_failures), 0)

        # Check for state corruption
        descriptions = [f.description.lower() for f in state_failures]
        self.assertTrue(any("corruption" in d or "concurrent" in d for d in descriptions))

    def test_validation_failure_detection(self):
        """Test detection of validation failure modes"""
        code = '''
def process_data(value, threshold):
    if value > threshold:
        return value * 2
    return value
'''

        failures = self.detector.detect_failure_modes(code)

        # Should detect validation failures
        val_failures = [f for f in failures if f.category == "validation"]
        self.assertGreater(len(val_failures), 0)

        # Check for input validation
        descriptions = [f.description.lower() for f in val_failures]
        self.assertTrue(any("invalid" in d or "input" in d for d in descriptions))

    def test_dependency_failure_detection(self):
        """Test detection of dependency failure modes"""
        code = '''
import numpy as np
import pandas as pd

def analyze_data(data):
    return np.mean(data)
'''

        failures = self.detector.detect_failure_modes(code)

        # Should detect dependency failures
        dep_failures = [f for f in failures if f.category == "dependency"]
        self.assertGreater(len(dep_failures), 0)

        # Check for missing dependency
        descriptions = [f.description.lower() for f in dep_failures]
        self.assertTrue(any("missing" in d or "dependency" in d for d in descriptions))

    def test_generic_failures_always_present(self):
        """Test that generic failures are always detected"""
        code = '''
def simple_function():
    return "hello"
'''

        failures = self.detector.detect_failure_modes(code)

        # Should always have generic failures
        generic_failures = [f for f in failures if f.category == "generic"]
        self.assertGreater(len(generic_failures), 0)

        # Check for timeout and exception
        descriptions = [f.description.lower() for f in generic_failures]
        self.assertTrue(any("timeout" in d for d in descriptions))
        self.assertTrue(any("exception" in d for d in descriptions))

    def test_risk_score_calculation(self):
        """Test that risk scores are calculated correctly"""
        code = '''
def divide(a, b):
    return a / b
'''

        failures = self.detector.detect_failure_modes(code)

        # All failures should have valid risk scores
        for failure in failures:
            self.assertGreaterEqual(failure.risk_score, 0.0)
            self.assertLessEqual(failure.risk_score, 1.0)

            # Risk score should be likelihood × impact
            expected_risk = failure.likelihood * failure.impact
            self.assertAlmostEqual(failure.risk_score, expected_risk, places=2)

    def test_mitigation_strategies_provided(self):
        """Test that mitigation strategies are provided"""
        code = '''
import requests

def fetch(url):
    return requests.get(url).json()
'''

        failures = self.detector.detect_failure_modes(code)

        # All failures should have mitigation strategies
        for failure in failures:
            self.assertIsNotNone(failure.mitigation)
            self.assertGreater(len(failure.mitigation), 0)

    def test_code_location_tracking(self):
        """Test that code locations are tracked"""
        code = '''
def divide(a, b):
    return a / b  # line 2
'''

        failures = self.detector.detect_failure_modes(code)

        # Computation failures should have code locations
        comp_failures = [f for f in failures if f.category == "computation"]
        for failure in comp_failures:
            self.assertIsNotNone(failure.code_location)

    def test_multiple_failure_categories(self):
        """Test detection of multiple failure categories"""
        code = '''
import requests
import os

class DataFetcher:
    def __init__(self):
        self.cache = {}

    def fetch_and_save(self, url, path):
        response = requests.get(url)
        with open(path, 'w') as f:
            f.write(response.text)
        return response.text
'''

        failures = self.detector.detect_failure_modes(code)

        # Should detect multiple categories
        categories = set(f.category for f in failures)
        self.assertIn("network", categories)
        self.assertIn("filesystem", categories)
        self.assertIn("state", categories)
        self.assertIn("dependency", categories)

    def test_empty_code(self):
        """Test handling of empty code"""
        code = ""

        failures = self.detector.detect_failure_modes(code)

        # Should at least have generic failures
        self.assertGreater(len(failures), 0)

    def test_invalid_syntax(self):
        """Test handling of invalid syntax"""
        code = '''
def broken(
    # Missing closing parenthesis
'''

        failures = self.detector.detect_failure_modes(code)

        # Should return generic failures even with syntax errors
        self.assertGreater(len(failures), 0)


class TestFailureModeDataClass(unittest.TestCase):
    """Test FailureMode data class"""

    def test_valid_failure_mode(self):
        """Test creating valid failure mode"""
        failure = FailureMode(
            category="network",
            description="Connection timeout",
            likelihood=0.3,
            impact=0.7,
            risk_score=0.21,
            mitigation="Implement retry logic",
            detection_method="AST analysis",
            code_location="line 10",
            related_operations=["requests.get"]
        )

        self.assertEqual(failure.category, "network")
        self.assertEqual(failure.likelihood, 0.3)
        self.assertEqual(failure.impact, 0.7)
        self.assertEqual(failure.risk_score, 0.21)

    def test_invalid_likelihood(self):
        """Test that invalid likelihood raises error"""
        with self.assertRaises(ValueError):
            FailureMode(
                category="network",
                description="Test",
                likelihood=1.5,  # Invalid
                impact=0.5,
                risk_score=0.75,
                mitigation="Test",
                detection_method="Test"
            )

    def test_invalid_impact(self):
        """Test that invalid impact raises error"""
        with self.assertRaises(ValueError):
            FailureMode(
                category="network",
                description="Test",
                likelihood=0.5,
                impact=-0.1,  # Invalid
                risk_score=0.0,
                mitigation="Test",
                detection_method="Test"
            )


def run_tests():
    """Run all tests"""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    run_tests()

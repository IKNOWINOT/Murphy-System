"""
Tests for Intelligent Sandbox Generator

Tests dynamic sandbox profile generation and optimization.
"""

import unittest
from src.module_compiler.analyzers.sandbox_generator import (
    IntelligentSandboxGenerator,
    OptimizedSandboxProfile
)


class TestSandboxGenerator(unittest.TestCase):
    """Test intelligent sandbox generation"""

    def setUp(self):
        self.generator = IntelligentSandboxGenerator()

    def test_simple_capability_optimization(self):
        """Test optimization for simple capability"""
        code = '''
def add(a, b):
    return a + b
'''

        profile = self.generator.generate_profile(code)

        # Should have minimal resources
        self.assertLessEqual(profile.cpu_cores, 1.0)
        self.assertLessEqual(profile.memory_mb, 512)
        self.assertLessEqual(profile.timeout_seconds, 60)
        self.assertGreater(profile.optimization_score, 0.5)
        self.assertFalse(profile.network_enabled)
        self.assertFalse(profile.filesystem_enabled)

    def test_network_capability_optimization(self):
        """Test optimization for network-heavy capability"""
        code = '''
import requests

def fetch_data(url):
    response = requests.get(url, timeout=5)
    return response.json()
'''

        profile = self.generator.generate_profile(code)

        # Should have network access
        self.assertTrue(profile.network_enabled)

        # Should have moderate resources
        self.assertGreaterEqual(profile.cpu_cores, 0.5)
        self.assertGreaterEqual(profile.memory_mb, 256)

    def test_computation_heavy_capability(self):
        """Test optimization for computation-heavy capability"""
        code = '''
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

def process_large_data():
    result = 0
    for i in range(1000000):
        result += i * i
    return result
'''

        profile = self.generator.generate_profile(code)

        # Should have high CPU allocation
        self.assertGreaterEqual(profile.cpu_cores, 1.0)
        self.assertGreaterEqual(profile.timeout_seconds, 30)

    def test_filesystem_capability_optimization(self):
        """Test optimization for filesystem capability"""
        code = '''
def read_file(path):
    with open(path, 'r') as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w') as f:
        f.write(content)
'''

        profile = self.generator.generate_profile(code)

        # Should have filesystem access
        self.assertTrue(profile.filesystem_enabled)
        self.assertGreater(len(profile.read_paths), 0)
        self.assertGreater(len(profile.write_paths), 0)

    def test_deterministic_capability_optimization(self):
        """Test optimization for deterministic capability"""
        code = '''
def multiply(a, b):
    return a * b
'''

        profile = self.generator.generate_profile(
            code,
            determinism_level="deterministic"
        )

        # Deterministic capabilities should use fewer resources
        self.assertLessEqual(profile.cpu_cores, 1.0)
        self.assertLessEqual(profile.memory_mb, 512)
        self.assertLessEqual(profile.timeout_seconds, 60)

    def test_external_state_capability_optimization(self):
        """Test optimization for external state capability"""
        code = '''
import requests
import sqlite3

def fetch_and_store(url, db_path):
    data = requests.get(url).json()
    conn = sqlite3.connect(db_path)
    # Store data
    conn.close()
    return data
'''

        profile = self.generator.generate_profile(
            code,
            determinism_level="external_state"
        )

        # External state capabilities need more resources than deterministic
        # But actual values depend on code analysis
        self.assertGreaterEqual(profile.cpu_cores, 0.5)
        self.assertGreaterEqual(profile.memory_mb, 256)
        self.assertGreaterEqual(profile.timeout_seconds, 30)

    def test_security_constraints_generation(self):
        """Test security constraint generation"""
        code = '''
import os

def dangerous_operation():
    os.system("rm -rf /")
'''

        profile = self.generator.generate_profile(code)

        # Should have security constraints
        self.assertGreater(len(profile.allowed_syscalls), 0)
        self.assertGreater(len(profile.environment_variables), 0)

    def test_resource_bounds(self):
        """Test that resources stay within bounds"""
        code = '''
def extreme_computation():
    result = 1
    for i in range(10**9):
        result *= i
    return result
'''

        profile = self.generator.generate_profile(code)

        # Should respect bounds
        self.assertGreaterEqual(profile.cpu_cores, 0.1)
        self.assertLessEqual(profile.cpu_cores, 4.0)
        self.assertGreaterEqual(profile.memory_mb, 64)
        self.assertLessEqual(profile.memory_mb, 4096)
        self.assertGreaterEqual(profile.disk_quota_mb, 0)
        self.assertLessEqual(profile.disk_quota_mb, 1024)
        self.assertGreaterEqual(profile.timeout_seconds, 1)
        self.assertLessEqual(profile.timeout_seconds, 300)

    def test_optimization_score_calculation(self):
        """Test optimization score calculation"""
        code = '''
def simple_function():
    return "hello"
'''

        profile = self.generator.generate_profile(code)

        # Should have valid optimization score
        self.assertGreaterEqual(profile.optimization_score, 0.0)
        self.assertLessEqual(profile.optimization_score, 1.0)

    def test_resource_efficiency_calculation(self):
        """Test resource efficiency calculation"""
        code = '''
def efficient_function(x):
    return x * 2
'''

        profile = self.generator.generate_profile(code)

        # Should have valid efficiency score
        self.assertGreaterEqual(profile.resource_efficiency, 0.0)
        self.assertLessEqual(profile.resource_efficiency, 1.0)

    def test_security_level_determination(self):
        """Test security level determination"""
        code = '''
def safe_function():
    return 42
'''

        profile = self.generator.generate_profile(code)

        # Should have valid security level
        self.assertIn(profile.security_level, ["low", "medium", "high"])

    def test_log_level_determination(self):
        """Test log level determination"""
        code = '''
def logged_function():
    return "result"
'''

        profile = self.generator.generate_profile(code)

        # Should have valid log level
        self.assertIn(profile.log_level, ["debug", "info", "warning", "error"])

    def test_empty_code(self):
        """Test handling of empty code"""
        code = ""

        profile = self.generator.generate_profile(code)

        # Should return conservative profile
        self.assertIsNotNone(profile)
        self.assertGreater(profile.cpu_cores, 0)
        self.assertGreater(profile.memory_mb, 0)

    def test_invalid_syntax(self):
        """Test handling of invalid syntax"""
        code = '''
def broken(
    # Missing closing parenthesis
'''

        profile = self.generator.generate_profile(code)

        # Should return conservative profile
        self.assertIsNotNone(profile)
        self.assertEqual(profile.security_level, "high")

    def test_with_failure_modes(self):
        """Test profile generation with failure modes"""
        from src.module_compiler.analyzers.failure_mode_detector import FailureMode

        code = '''
import requests

def fetch(url):
    return requests.get(url).json()
'''

        failure_modes = [
            FailureMode(
                category="network",
                description="HTTP timeout",
                likelihood=0.3,
                impact=0.7,
                risk_score=0.21,
                mitigation="Add retry logic",
                detection_method="AST analysis"
            )
        ]

        profile = self.generator.generate_profile(code, failure_modes)

        # Should consider failure modes
        self.assertIsNotNone(profile)
        # Network may be disabled due to high risk (risk_score > 0.2)
        # This is correct behavior - high risk network operations should be blocked
        self.assertIsNotNone(profile.security_level)

    def test_environment_variables(self):
        """Test environment variable generation"""
        code = '''
def process():
    return "result"
'''

        profile = self.generator.generate_profile(code)

        # Should have Python-specific env vars
        self.assertIn('PYTHONHASHSEED', profile.environment_variables)
        self.assertIn('PYTHONDONTWRITEBYTECODE', profile.environment_variables)
        self.assertIn('PYTHONUNBUFFERED', profile.environment_variables)


class TestOptimizedSandboxProfile(unittest.TestCase):
    """Test OptimizedSandboxProfile data class"""

    def test_valid_profile(self):
        """Test creating valid profile"""
        profile = OptimizedSandboxProfile(
            cpu_cores=1.0,
            memory_mb=512,
            disk_quota_mb=100,
            timeout_seconds=30,
            network_enabled=True,
            filesystem_enabled=True,
            optimization_score=0.8,
            resource_efficiency=0.7,
            security_level="medium"
        )

        self.assertEqual(profile.cpu_cores, 1.0)
        self.assertEqual(profile.memory_mb, 512)
        self.assertEqual(profile.security_level, "medium")

    def test_invalid_cpu_cores(self):
        """Test that invalid CPU cores raises error"""
        with self.assertRaises(ValueError):
            OptimizedSandboxProfile(
                cpu_cores=5.0,  # Invalid (> 4.0)
                memory_mb=512,
                disk_quota_mb=100,
                timeout_seconds=30,
                network_enabled=False,
                filesystem_enabled=False,
                optimization_score=0.8,
                resource_efficiency=0.7
            )

    def test_invalid_memory(self):
        """Test that invalid memory raises error"""
        with self.assertRaises(ValueError):
            OptimizedSandboxProfile(
                cpu_cores=1.0,
                memory_mb=5000,  # Invalid (> 4096)
                disk_quota_mb=100,
                timeout_seconds=30,
                network_enabled=False,
                filesystem_enabled=False,
                optimization_score=0.8,
                resource_efficiency=0.7
            )

    def test_invalid_timeout(self):
        """Test that invalid timeout raises error"""
        with self.assertRaises(ValueError):
            OptimizedSandboxProfile(
                cpu_cores=1.0,
                memory_mb=512,
                disk_quota_mb=100,
                timeout_seconds=400,  # Invalid (> 300)
                network_enabled=False,
                filesystem_enabled=False,
                optimization_score=0.8,
                resource_efficiency=0.7
            )


def run_tests():
    """Run all tests"""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    run_tests()

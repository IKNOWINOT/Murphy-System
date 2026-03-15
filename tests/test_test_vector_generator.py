"""
Tests for Test Vector Generator

Tests automatic test case generation for capabilities.
"""

import unittest
from src.module_compiler.analyzers.test_vector_generator import (
    TestVectorGenerator,
    TestVector,
    TestResult
)


class TestTestVectorGenerator(unittest.TestCase):
    """Test test vector generation"""

    def setUp(self):
        self.generator = TestVectorGenerator()

    def test_valid_input_generation(self):
        """Test generation of valid inputs"""
        code = '''
def add(a: int, b: int) -> int:
    return a + b
'''

        vectors = self.generator.generate_test_vectors(code)

        # Should have valid tests
        valid_tests = [v for v in vectors if v.test_type == "valid"]
        self.assertGreater(len(valid_tests), 0)

        # All valid tests should have no expected exception
        for test in valid_tests:
            self.assertIsNone(test.expected_exception)

    def test_invalid_input_generation(self):
        """Test generation of invalid inputs"""
        code = '''
def divide(a: int, b: int) -> float:
    return a / b
'''

        vectors = self.generator.generate_test_vectors(code)

        # Should have invalid tests
        invalid_tests = [v for v in vectors if v.test_type == "invalid"]
        self.assertGreater(len(invalid_tests), 0)

        # Invalid tests should expect exceptions
        for test in invalid_tests:
            self.assertIsNotNone(test.expected_exception)

    def test_edge_case_generation(self):
        """Test generation of edge cases"""
        code = '''
def process_number(n: int) -> int:
    return n * 2
'''

        vectors = self.generator.generate_test_vectors(code)

        # Should have edge tests
        edge_tests = [v for v in vectors if v.test_type == "edge"]
        self.assertGreater(len(edge_tests), 0)

        # Should include boundary values
        edge_inputs = [list(t.inputs.values())[0] for t in edge_tests if t.inputs]
        self.assertIn(0, edge_inputs)

    def test_random_test_generation(self):
        """Test generation of random tests"""
        code = '''
def multiply(x: int, y: int) -> int:
    return x * y
'''

        vectors = self.generator.generate_test_vectors(code, num_random_tests=10)

        # Should have random tests
        random_tests = [v for v in vectors if v.test_type == "random"]
        self.assertEqual(len(random_tests), 10)

    def test_function_with_no_parameters(self):
        """Test generation for function with no parameters"""
        code = '''
def get_constant() -> int:
    return 42
'''

        vectors = self.generator.generate_test_vectors(code)

        # Should have at least one test
        self.assertGreater(len(vectors), 0)

        # Should have a valid test with no inputs
        valid_tests = [v for v in vectors if v.test_type == "valid"]
        self.assertGreater(len(valid_tests), 0)
        self.assertEqual(valid_tests[0].inputs, {})

    def test_function_with_multiple_parameters(self):
        """Test generation for function with multiple parameters"""
        code = '''
def calculate(a: int, b: float, c: str) -> str:
    return f"{a} {b} {c}"
'''

        vectors = self.generator.generate_test_vectors(code)

        # Should have tests for each parameter
        self.assertGreater(len(vectors), 0)

        # Should have tests with different parameter types
        param_names = set()
        for vector in vectors:
            param_names.update(vector.inputs.keys())

        self.assertIn('a', param_names)
        self.assertIn('b', param_names)
        self.assertIn('c', param_names)

    def test_string_parameter_tests(self):
        """Test generation for string parameters"""
        code = '''
def process_string(s: str) -> str:
    return s.upper()
'''

        vectors = self.generator.generate_test_vectors(code)

        # Should have string tests
        string_tests = [v for v in vectors if 's' in v.inputs]
        self.assertGreater(len(string_tests), 0)

        # Should include empty string edge case
        edge_tests = [v for v in vectors if v.test_type == "edge"]
        edge_values = [v.inputs.get('s') for v in edge_tests]
        self.assertIn("", edge_values)

    def test_list_parameter_tests(self):
        """Test generation for list parameters"""
        code = '''
def sum_list(items: list) -> int:
    return sum(items)
'''

        vectors = self.generator.generate_test_vectors(code)

        # Should have list tests
        list_tests = [v for v in vectors if 'items' in v.inputs]
        self.assertGreater(len(list_tests), 0)

        # Should include empty list edge case
        edge_tests = [v for v in vectors if v.test_type == "edge"]
        edge_values = [v.inputs.get('items') for v in edge_tests]
        self.assertIn([], edge_values)

    def test_bool_parameter_tests(self):
        """Test generation for bool parameters"""
        code = '''
def toggle(flag: bool) -> bool:
    return not flag
'''

        vectors = self.generator.generate_test_vectors(code)

        # Should have bool tests
        bool_tests = [v for v in vectors if 'flag' in v.inputs]
        self.assertGreater(len(bool_tests), 0)

        # Should include both True and False
        bool_values = [v.inputs.get('flag') for v in bool_tests]
        self.assertIn(True, bool_values)
        self.assertIn(False, bool_values)

    def test_test_id_uniqueness(self):
        """Test that test IDs are unique"""
        code = '''
def func(a: int, b: int) -> int:
    return a + b
'''

        vectors = self.generator.generate_test_vectors(code)

        # All test IDs should be unique
        test_ids = [v.test_id for v in vectors]
        self.assertEqual(len(test_ids), len(set(test_ids)))

    def test_test_priority_assignment(self):
        """Test that test priorities are assigned correctly"""
        code = '''
def process(x: int) -> int:
    return x * 2
'''

        vectors = self.generator.generate_test_vectors(code)

        # All tests should have valid priorities
        for vector in vectors:
            self.assertGreaterEqual(vector.priority, 1)
            self.assertLessEqual(vector.priority, 5)

        # Valid and edge tests should have high priority
        valid_tests = [v for v in vectors if v.test_type == "valid"]
        for test in valid_tests:
            self.assertLessEqual(test.priority, 2)

        edge_tests = [v for v in vectors if v.test_type == "edge"]
        for test in edge_tests:
            self.assertLessEqual(test.priority, 2)

    def test_coverage_summary(self):
        """Test coverage summary generation"""
        code = '''
def add(a: int, b: int) -> int:
    return a + b
'''

        vectors = self.generator.generate_test_vectors(code, num_random_tests=5)
        summary = self.generator.get_coverage_summary(vectors)

        # Should have all required fields
        self.assertIn('total_tests', summary)
        self.assertIn('valid_tests', summary)
        self.assertIn('invalid_tests', summary)
        self.assertIn('edge_tests', summary)
        self.assertIn('random_tests', summary)

        # Total should equal sum of parts
        self.assertEqual(
            summary['total_tests'],
            summary['valid_tests'] + summary['invalid_tests'] +
            summary['edge_tests'] + summary['random_tests']
        )

    def test_empty_code(self):
        """Test handling of empty code"""
        code = ""

        vectors = self.generator.generate_test_vectors(code)

        # Should return empty list
        self.assertEqual(len(vectors), 0)

    def test_invalid_syntax(self):
        """Test handling of invalid syntax"""
        code = '''
def broken(
    # Missing closing parenthesis
'''

        vectors = self.generator.generate_test_vectors(code)

        # Should return empty list
        self.assertEqual(len(vectors), 0)

    def test_multiple_functions(self):
        """Test generation for multiple functions"""
        code = '''
def add(a: int, b: int) -> int:
    return a + b

def multiply(x: int, y: int) -> int:
    return x * y
'''

        vectors = self.generator.generate_test_vectors(code)

        # Should have tests for both functions
        self.assertGreater(len(vectors), 0)

        # Should have tests with different parameter names
        param_names = set()
        for vector in vectors:
            param_names.update(vector.inputs.keys())

        # Parameters from both functions
        self.assertTrue(
            ('a' in param_names and 'b' in param_names) or
            ('x' in param_names and 'y' in param_names)
        )


class TestTestVector(unittest.TestCase):
    """Test TestVector data class"""

    def test_valid_test_vector(self):
        """Test creating valid test vector"""
        vector = TestVector(
            test_id="test_001",
            test_type="valid",
            inputs={"a": 1, "b": 2},
            expected_output=3,
            description="Test addition",
            priority=1
        )

        self.assertEqual(vector.test_id, "test_001")
        self.assertEqual(vector.test_type, "valid")
        self.assertEqual(vector.inputs, {"a": 1, "b": 2})

    def test_invalid_test_type(self):
        """Test that invalid test type raises error"""
        with self.assertRaises(ValueError):
            TestVector(
                test_id="test_001",
                test_type="invalid_type",  # Invalid
                inputs={}
            )

    def test_invalid_priority(self):
        """Test that invalid priority raises error"""
        with self.assertRaises(ValueError):
            TestVector(
                test_id="test_001",
                test_type="valid",
                inputs={},
                priority=10  # Invalid (> 5)
            )


class TestTestResult(unittest.TestCase):
    """Test TestResult data class"""

    def test_valid_test_result(self):
        """Test creating valid test result"""
        result = TestResult(
            test_id="test_001",
            passed=True,
            actual_output=3,
            expected_output=3
        )

        self.assertEqual(result.test_id, "test_001")
        self.assertTrue(result.passed)
        self.assertEqual(result.actual_output, 3)


def run_tests():
    """Run all tests"""
    unittest.main(argv=[''], verbosity=2, exit=False)


if __name__ == '__main__':
    run_tests()

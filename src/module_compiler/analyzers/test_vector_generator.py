"""
Test Vector Generator

Automatically generates test cases for capabilities including valid inputs,
invalid inputs, edge cases, and random fuzzing tests.
"""

import ast
import logging
import random
import string
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TestVector:
    """
    Test case with input and expected output.

    Attributes:
        test_id: Unique test identifier
        test_type: Type of test (valid, invalid, edge, random)
        inputs: Input parameters {param_name: value}
        expected_output: Expected output value
        expected_exception: Expected exception type (if any)
        description: Human-readable description
        priority: Test priority (1=critical, 5=nice-to-have)
    """

    test_id: str
    test_type: str
    inputs: Dict[str, Any]
    expected_output: Any = None
    expected_exception: Optional[str] = None
    description: str = ""
    priority: int = 3

    def __post_init__(self):
        """Validate test vector"""
        if self.test_type not in ["valid", "invalid", "edge", "random"]:
            raise ValueError(f"Invalid test type: {self.test_type}")
        if self.priority < 1 or self.priority > 5:
            raise ValueError("Priority must be between 1 and 5")


@dataclass
class TestResult:
    """
    Result of test execution.

    Attributes:
        test_id: Test identifier
        passed: Whether test passed
        actual_output: Actual output from execution
        expected_output: Expected output
        error: Error message (if any)
        execution_time: Time taken to execute (seconds)
    """

    test_id: str
    passed: bool
    actual_output: Any = None
    expected_output: Any = None
    error: str = ""
    execution_time: float = 0.0


class TestVectorGenerator:
    """
    Generate test vectors for capabilities.

    Generates:
    - Valid input tests (happy path)
    - Invalid input tests (error cases)
    - Edge case tests (boundaries, nulls, extremes)
    - Random fuzzing tests
    """

    def __init__(self):
        """Initialize test vector generator"""
        self.test_counter = 0

    def generate_test_vectors(
        self,
        code: str,
        num_random_tests: int = 5
    ) -> List[TestVector]:
        """
        Generate test vectors for capability.

        Args:
            code: Source code to test
            num_random_tests: Number of random tests to generate

        Returns:
            List of test vectors
        """
        vectors = []

        try:
            # Parse code
            tree = ast.parse(code)

            # Find functions
            functions = self._find_functions(tree)

            for func_info in functions:
                # 1. Generate valid input tests
                vectors.extend(self._generate_valid_tests(func_info))

                # 2. Generate invalid input tests
                vectors.extend(self._generate_invalid_tests(func_info))

                # 3. Generate edge case tests
                vectors.extend(self._generate_edge_tests(func_info))

                # 4. Generate random tests
                vectors.extend(self._generate_random_tests(func_info, num_random_tests))

        except SyntaxError as exc:
            # If code can't be parsed, return empty list
            logger.debug("Suppressed %s: %s", type(exc).__name__, exc)  # noqa: E501

        return vectors

    # ========== Function Analysis ==========

    def _find_functions(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Find all functions in code"""
        functions = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_info = {
                    'name': node.name,
                    'parameters': self._extract_parameters(node),
                    'return_type': self._extract_return_type(node)
                }
                functions.append(func_info)

        return functions

    def _extract_parameters(self, func_node: ast.FunctionDef) -> Dict[str, str]:
        """Extract function parameters with types"""
        parameters = {}

        for arg in func_node.args.args:
            param_name = arg.arg

            # Try to infer type from annotation
            if arg.annotation:
                param_type = self._get_type_from_annotation(arg.annotation)
            else:
                param_type = "any"

            parameters[param_name] = param_type

        return parameters

    def _get_type_from_annotation(self, annotation: ast.AST) -> str:
        """Get type string from annotation"""
        if isinstance(annotation, ast.Name):
            return annotation.id.lower()
        elif isinstance(annotation, ast.Constant):
            return str(annotation.value).lower()
        else:
            return "any"

    def _extract_return_type(self, func_node: ast.FunctionDef) -> str:
        """Extract return type from function"""
        if func_node.returns:
            return self._get_type_from_annotation(func_node.returns)
        return "any"

    # ========== Valid Test Generation ==========

    def _generate_valid_tests(self, func_info: Dict[str, Any]) -> List[TestVector]:
        """Generate valid input tests"""
        tests = []

        parameters = func_info['parameters']

        if not parameters:
            # No parameters - single test
            tests.append(TestVector(
                test_id=self._get_test_id("valid"),
                test_type="valid",
                inputs={},
                description=f"Valid call to {func_info['name']} with no parameters",
                priority=1
            ))
        else:
            # Generate combinations of valid values
            for param_name, param_type in parameters.items():
                valid_values = self._generate_valid_values(param_type)

                for i, value in enumerate(valid_values[:3]):  # Limit to 3 per parameter
                    tests.append(TestVector(
                        test_id=self._get_test_id("valid"),
                        test_type="valid",
                        inputs={param_name: value},
                        description=f"Valid {param_type} input for {param_name}",
                        priority=1
                    ))

        return tests

    def _generate_valid_values(self, param_type: str) -> List[Any]:
        """Generate valid values for parameter type"""

        if param_type == "int":
            return [0, 1, 10, 100, -1, -10]
        elif param_type == "float":
            return [0.0, 1.0, 10.5, -1.5, 3.14]
        elif param_type == "str":
            return ["", "hello", "test123", "a" * 10]
        elif param_type == "bool":
            return [True, False]
        elif param_type == "list":
            return [[], [1, 2, 3], ["a", "b", "c"]]
        elif param_type == "dict":
            return [{}, {"key": "value"}, {"a": 1, "b": 2}]
        elif param_type == "tuple":
            return [(), (1, 2), ("a", "b")]
        elif param_type == "set":
            return [set(), {1, 2, 3}, {"a", "b"}]
        else:
            return [None, 0, "", []]

    # ========== Invalid Test Generation ==========

    def _generate_invalid_tests(self, func_info: Dict[str, Any]) -> List[TestVector]:
        """Generate invalid input tests"""
        tests = []

        parameters = func_info['parameters']

        for param_name, param_type in parameters.items():
            invalid_values = self._generate_invalid_values(param_type)

            for i, value in enumerate(invalid_values[:2]):  # Limit to 2 per parameter
                tests.append(TestVector(
                    test_id=self._get_test_id("invalid"),
                    test_type="invalid",
                    inputs={param_name: value},
                    expected_exception="TypeError",
                    description=f"Invalid {type(value).__name__} for {param_name} (expected {param_type})",
                    priority=2
                ))

        return tests

    def _generate_invalid_values(self, param_type: str) -> List[Any]:
        """Generate invalid values for parameter type"""

        if param_type == "int":
            return ["not_int", None, [], {}, 3.14]
        elif param_type == "float":
            return ["not_float", None, [], {}]
        elif param_type == "str":
            return [123, None, [], {}]
        elif param_type == "bool":
            return ["not_bool", 123, None, []]
        elif param_type == "list":
            return ["not_list", 123, None, {}]
        elif param_type == "dict":
            return ["not_dict", 123, None, []]
        elif param_type == "tuple":
            return ["not_tuple", 123, None, {}]
        elif param_type == "set":
            return ["not_set", 123, None, []]
        else:
            return []

    # ========== Edge Case Generation ==========

    def _generate_edge_tests(self, func_info: Dict[str, Any]) -> List[TestVector]:
        """Generate edge case tests"""
        tests = []

        parameters = func_info['parameters']

        for param_name, param_type in parameters.items():
            edge_values = self._generate_edge_values(param_type)

            for i, value in enumerate(edge_values):
                tests.append(TestVector(
                    test_id=self._get_test_id("edge"),
                    test_type="edge",
                    inputs={param_name: value},
                    description=f"Edge case for {param_name}: {self._describe_edge_value(value)}",
                    priority=1
                ))

        return tests

    def _generate_edge_values(self, param_type: str) -> List[Any]:
        """Generate edge case values for parameter type"""

        if param_type == "int":
            return [0, -1, 1, 2**31-1, -2**31]
        elif param_type == "float":
            return [0.0, -0.0, 1e-10, 1e10, float('inf'), float('-inf')]
        elif param_type == "str":
            return ["", " ", "\n", "\t", "a" * 1000]
        elif param_type == "bool":
            return [True, False]
        elif param_type == "list":
            return [[], [None], [1] * 1000]
        elif param_type == "dict":
            return [{}, {None: None}, {"": ""}]
        elif param_type == "tuple":
            return [(), (None,), tuple(range(1000))]
        elif param_type == "set":
            return [set(), {None}, set(range(100))]
        else:
            return [None]

    def _describe_edge_value(self, value: Any) -> str:
        """Describe edge value"""
        if value is None:
            return "None"
        elif isinstance(value, str) and len(value) == 0:
            return "empty string"
        elif isinstance(value, list) and len(value) == 0:
            return "empty list"
        elif isinstance(value, dict) and len(value) == 0:
            return "empty dict"
        elif isinstance(value, (int, float)) and value == 0:
            return "zero"
        elif isinstance(value, float) and value == float('inf'):
            return "infinity"
        elif isinstance(value, float) and value == float('-inf'):
            return "negative infinity"
        elif isinstance(value, str) and len(value) > 100:
            return "very long string"
        elif isinstance(value, (list, tuple)) and len(value) > 100:
            return "very long sequence"
        else:
            return str(value)[:50]

    # ========== Random Test Generation ==========

    def _generate_random_tests(
        self,
        func_info: Dict[str, Any],
        num_tests: int
    ) -> List[TestVector]:
        """Generate random fuzzing tests"""
        tests = []

        parameters = func_info['parameters']

        for i in range(num_tests):
            # Generate random inputs
            inputs = {}
            for param_name, param_type in parameters.items():
                inputs[param_name] = self._generate_random_value(param_type)

            tests.append(TestVector(
                test_id=self._get_test_id("random"),
                test_type="random",
                inputs=inputs,
                description=f"Random fuzzing test #{i+1}",
                priority=4
            ))

        return tests

    def _generate_random_value(self, param_type: str) -> Any:
        """Generate random value for parameter type"""

        if param_type == "int":
            return random.randint(-1000, 1000)
        elif param_type == "float":
            return random.uniform(-1000.0, 1000.0)
        elif param_type == "str":
            length = random.randint(0, 50)
            return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
        elif param_type == "bool":
            return random.choice([True, False])
        elif param_type == "list":
            length = random.randint(0, 10)
            return [random.randint(0, 100) for _ in range(length)]
        elif param_type == "dict":
            size = random.randint(0, 5)
            return {f"key{i}": random.randint(0, 100) for i in range(size)}
        elif param_type == "tuple":
            length = random.randint(0, 10)
            return tuple(random.randint(0, 100) for _ in range(length))
        elif param_type == "set":
            size = random.randint(0, 10)
            return set(random.randint(0, 100) for _ in range(size))
        else:
            return None

    # ========== Utilities ==========

    def _get_test_id(self, test_type: str) -> str:
        """Generate unique test ID"""
        self.test_counter += 1
        return f"{test_type}_{self.test_counter:04d}"

    def get_coverage_summary(self, vectors: List[TestVector]) -> Dict[str, Any]:
        """Get test coverage summary"""
        return {
            'total_tests': len(vectors),
            'valid_tests': len([v for v in vectors if v.test_type == "valid"]),
            'invalid_tests': len([v for v in vectors if v.test_type == "invalid"]),
            'edge_tests': len([v for v in vectors if v.test_type == "edge"]),
            'random_tests': len([v for v in vectors if v.test_type == "random"]),
            'high_priority': len([v for v in vectors if v.priority <= 2]),
            'medium_priority': len([v for v in vectors if v.priority == 3]),
            'low_priority': len([v for v in vectors if v.priority >= 4])
        }

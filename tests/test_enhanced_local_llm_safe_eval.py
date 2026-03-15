"""
Tests: Enhanced Local LLM — Safe Arithmetic Evaluator

Proves that the ``eval()`` call has been replaced with a safe AST-based
evaluator that blocks arbitrary code execution while still computing
valid arithmetic expressions.

Bug Label  : CWE-95 — Improper Neutralization of Directives in
             Dynamically Evaluated Code (Code Injection)
Module     : src/enhanced_local_llm.py
Fixed In   : EnhancedLocalLLM._safe_eval_arithmetic / _safe_eval_node
"""

import sys
import os
import re
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from enhanced_local_llm import EnhancedLocalLLM


class TestSafeEvalArithmetic(unittest.TestCase):
    """_safe_eval_arithmetic must compute numbers and reject everything else."""

    def setUp(self):
        self.llm = EnhancedLocalLLM()

    # ── Valid arithmetic ─────────────────────────────────────────────
    def test_simple_addition(self):
        self.assertEqual(self.llm._safe_eval_arithmetic("2 + 3"), 5)

    def test_multiplication(self):
        self.assertEqual(self.llm._safe_eval_arithmetic("4 * 5"), 20)

    def test_division(self):
        self.assertAlmostEqual(self.llm._safe_eval_arithmetic("10 / 4"), 2.5)

    def test_subtraction(self):
        self.assertEqual(self.llm._safe_eval_arithmetic("10 - 3"), 7)

    def test_exponentiation(self):
        self.assertEqual(self.llm._safe_eval_arithmetic("2 ** 3"), 8)

    def test_caret_exponentiation(self):
        """``^`` is treated as ``**`` (user expectation)."""
        self.assertEqual(self.llm._safe_eval_arithmetic("2 ^ 3"), 8)

    def test_nested_parentheses(self):
        self.assertEqual(self.llm._safe_eval_arithmetic("(2 + 3) * (4 - 1)"), 15)

    def test_negative_number(self):
        self.assertEqual(self.llm._safe_eval_arithmetic("-5 + 3"), -2)

    def test_float_literals(self):
        self.assertAlmostEqual(self.llm._safe_eval_arithmetic("3.14 * 2"), 6.28)

    # ── Injection attempts must raise ValueError ─────────────────────
    def test_rejects_function_call(self):
        with self.assertRaises(ValueError):
            self.llm._safe_eval_arithmetic("__import__('os').system('id')")

    def test_rejects_string_literal(self):
        with self.assertRaises(ValueError):
            self.llm._safe_eval_arithmetic("'hello'")

    def test_rejects_list_comprehension(self):
        with self.assertRaises(Exception):
            self.llm._safe_eval_arithmetic("[x for x in range(10)]")

    def test_rejects_lambda(self):
        with self.assertRaises(Exception):
            self.llm._safe_eval_arithmetic("(lambda: 1)()")

    def test_rejects_attribute_access(self):
        with self.assertRaises(Exception):
            self.llm._safe_eval_arithmetic("().__class__.__bases__")

    def test_rejects_boolean_ops(self):
        with self.assertRaises(Exception):
            self.llm._safe_eval_arithmetic("True and False")


class TestNoEvalInSource(unittest.TestCase):
    """The source file must not contain any bare ``eval(`` call."""

    def test_no_eval_call(self):
        src_path = os.path.join(
            os.path.dirname(__file__), "..", "src", "enhanced_local_llm.py"
        )
        with open(src_path, "r") as f:
            source = f.read()

        # Find all eval( occurrences that are actual calls, not comments
        # or docstrings.  A line is suspicious only if ``eval(`` appears
        # outside of a comment *and* outside of a string/docstring context.
        for lineno, line in enumerate(source.splitlines(), 1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            # Skip lines that are part of a docstring (start with quotes or ```)
            if stripped.startswith(('"""', "'''", '"', "'")):
                continue
            if re.search(r'(?<!["\'])\beval\s*\(', stripped):
                self.fail(
                    f"Forbidden eval() call found at line {lineno}: {stripped!r}"
                )


if __name__ == "__main__":
    unittest.main()

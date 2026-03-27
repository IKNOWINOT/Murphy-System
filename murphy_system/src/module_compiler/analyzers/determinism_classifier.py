"""
Advanced Determinism Classifier

Enhanced determinism classification with function-level analysis,
data flow tracking, and purity detection.

Owner: INONI LLC / Corey Post (corey.gfc@gmail.com)
"""

import ast
import logging
from typing import List, Optional, Set

from ..models.module_spec import DeterminismLevel
from .static_analyzer import CodeStructure, FunctionInfo

logger = logging.getLogger(__name__)


class AdvancedDeterminismClassifier:
    """
    Advanced determinism classification.

    Analyzes functions at a deeper level to determine if they are:
    - Deterministic: Pure functions, same input → same output
    - Probabilistic: Uses randomness
    - External State: Depends on external state (network, files, time, etc.)
    """

    # Modules that indicate non-determinism
    RANDOM_MODULES = {'random', 'numpy.random', 'secrets', 'uuid'}
    TIME_MODULES = {'time', 'datetime'}
    NETWORK_MODULES = {'requests', 'urllib', 'http', 'socket', 'aiohttp', 'httpx'}
    FILESYSTEM_MODULES = {'os', 'pathlib', 'shutil', 'glob', 'tempfile', 'io'}
    DATABASE_MODULES = {'sqlite3', 'psycopg2', 'pymongo', 'sqlalchemy', 'redis'}
    SUBPROCESS_MODULES = {'subprocess'}

    # Functions that indicate non-determinism
    RANDOM_FUNCTIONS = {
        'random', 'randint', 'choice', 'shuffle', 'sample',
        'uuid1', 'uuid4', 'token_bytes', 'token_hex'
    }

    TIME_FUNCTIONS = {
        'now', 'today', 'time', 'clock', 'perf_counter'
    }

    NETWORK_FUNCTIONS = {
        'get', 'post', 'put', 'delete', 'request',
        'urlopen', 'connect', 'send', 'recv'
    }

    FILESYSTEM_FUNCTIONS = {
        'open', 'read', 'write', 'listdir', 'walk',
        'exists', 'isfile', 'isdir', 'stat'
    }

    def __init__(self):
        self.imported_modules: Set[str] = set()

    def classify(
        self,
        func_info: FunctionInfo,
        code_structure: CodeStructure,
        source_code: Optional[str] = None
    ) -> DeterminismLevel:
        """
        Classify function determinism level.

        Args:
            func_info: Function information from static analysis
            code_structure: Complete code structure
            source_code: Optional source code for deeper analysis

        Returns:
            DeterminismLevel classification
        """
        self.imported_modules = code_structure.dependencies

        # Level 1: Check for obvious probabilistic behavior
        if self._is_probabilistic(func_info):
            return DeterminismLevel.PROBABILISTIC

        # Level 2: Check for external state dependencies
        if self._depends_on_external_state(func_info, code_structure):
            return DeterminismLevel.EXTERNAL_STATE

        # Level 3: Check for side effects
        if self._has_side_effects(func_info):
            return DeterminismLevel.EXTERNAL_STATE

        # Level 4: Check if pure function
        if self._is_pure_function(func_info, code_structure):
            return DeterminismLevel.DETERMINISTIC

        # Default: Conservative classification
        return DeterminismLevel.EXTERNAL_STATE

    def _is_probabilistic(self, func_info: FunctionInfo) -> bool:
        """Check if function uses randomness"""
        # Check function-level flags
        if func_info.uses_random:
            return True

        # Check if function name suggests randomness
        if any(rand_func in func_info.name.lower()
               for rand_func in ['random', 'shuffle', 'sample']):
            return True

        return False

    def _depends_on_external_state(
        self,
        func_info: FunctionInfo,
        code_structure: CodeStructure
    ) -> bool:
        """Check if function depends on external state"""

        # Check function-level flags (these are more accurate)
        if func_info.uses_network:
            return True

        if func_info.uses_time:
            return True

        if func_info.uses_filesystem:
            return True

        # Check for global variable access
        # (Functions that read globals depend on external state)
        if self._accesses_global_variables(func_info, code_structure):
            return True

        # Don't check module-level imports here - they're too broad
        # The function-level flags are more accurate

        return False

    def _has_side_effects(self, func_info: FunctionInfo) -> bool:
        """Check if function has side effects"""

        # Functions with side effects are not deterministic
        # Side effects include:
        # - Modifying global state
        # - File I/O
        # - Network I/O
        # - Database operations
        # - Printing to stdout/stderr

        # Check for file/network operations
        if func_info.uses_filesystem or func_info.uses_network:
            return True

        # Check for print statements (side effect)
        if 'print' in func_info.name.lower():
            return True

        # Check for write/save/update in name (suggests side effects)
        side_effect_keywords = ['write', 'save', 'update', 'delete', 'create', 'modify']
        if any(keyword in func_info.name.lower() for keyword in side_effect_keywords):
            return True

        return False

    def _is_pure_function(
        self,
        func_info: FunctionInfo,
        code_structure: CodeStructure
    ) -> bool:
        """
        Check if function is pure.

        A pure function:
        - Always returns the same output for the same input
        - Has no side effects
        - Doesn't depend on external state
        """

        # Must not have side effects
        if self._has_side_effects(func_info):
            return False

        # Must not depend on external state
        if self._depends_on_external_state(func_info, code_structure):
            return False

        # Must not be probabilistic
        if self._is_probabilistic(func_info):
            return False

        # Must have parameters (pure functions take input)
        # Exception: Constants/getters can be pure with no params
        if len(func_info.parameters) == 0:
            # Check if it's a getter/constant
            if func_info.name.startswith('get_') or func_info.name.isupper():
                # But get_current_timestamp is not pure!
                if 'time' in func_info.name.lower() or 'now' in func_info.name.lower():
                    return False
                return True
            return False

        # Must return a value (pure functions return output)
        # Allow None return type if we can't determine it
        if func_info.return_type == 'None':
            return False

        # If all checks pass, likely pure
        return True

    def _accesses_global_variables(
        self,
        func_info: FunctionInfo,
        code_structure: CodeStructure
    ) -> bool:
        """Check if function accesses global variables"""

        # Check if function name suggests it uses globals
        if 'global' in func_info.name.lower():
            return True

        # Check if function has 'global' keyword in its body
        # (This would require AST parsing of the function body)
        # For now, we'll be less conservative and only flag if
        # the function explicitly suggests global access

        return False

    def get_determinism_confidence(
        self,
        func_info: FunctionInfo,
        code_structure: CodeStructure
    ) -> float:
        """
        Get confidence score for determinism classification.

        Returns:
            Float between 0.0 and 1.0
            - 1.0 = Very confident in classification
            - 0.0 = Not confident (needs manual review)
        """
        confidence = 1.0

        # Reduce confidence if function is complex
        if len(func_info.parameters) > 5:
            confidence *= 0.9

        # Reduce confidence if no type hints
        if not func_info.return_type:
            confidence *= 0.8

        # Reduce confidence if no docstring
        if not func_info.docstring:
            confidence *= 0.9

        # Reduce confidence if uses decorators (might change behavior)
        if func_info.decorators:
            confidence *= 0.85

        # Reduce confidence if async (harder to analyze)
        if func_info.is_async:
            confidence *= 0.9

        return confidence

    def get_determinism_explanation(
        self,
        func_info: FunctionInfo,
        level: DeterminismLevel
    ) -> str:
        """Get human-readable explanation of classification"""

        if level == DeterminismLevel.DETERMINISTIC:
            return (
                f"Function '{func_info.name}' is deterministic: "
                f"pure function with no side effects or external dependencies"
            )

        elif level == DeterminismLevel.PROBABILISTIC:
            reasons = []
            if func_info.uses_random:
                reasons.append("uses random number generation")
            if any(r in func_info.name.lower() for r in ['random', 'shuffle']):
                reasons.append("name suggests randomness")

            return (
                f"Function '{func_info.name}' is probabilistic: "
                f"{', '.join(reasons)}"
            )

        else:  # EXTERNAL_STATE
            reasons = []
            if func_info.uses_network:
                reasons.append("makes network calls")
            if func_info.uses_filesystem:
                reasons.append("accesses filesystem")
            if func_info.uses_time:
                reasons.append("depends on current time")
            if self._has_side_effects(func_info):
                reasons.append("has side effects")

            if not reasons:
                reasons.append("may depend on external state")

            return (
                f"Function '{func_info.name}' depends on external state: "
                f"{', '.join(reasons)}"
            )


def classify_capability_determinism(
    func_info: FunctionInfo,
    code_structure: CodeStructure,
    source_code: Optional[str] = None
) -> tuple[DeterminismLevel, float, str]:
    """
    Convenience function to classify capability determinism.

    Args:
        func_info: Function information
        code_structure: Code structure
        source_code: Optional source code

    Returns:
        Tuple of (level, confidence, explanation)
    """
    classifier = AdvancedDeterminismClassifier()

    level = classifier.classify(func_info, code_structure, source_code)
    confidence = classifier.get_determinism_confidence(func_info, code_structure)
    explanation = classifier.get_determinism_explanation(func_info, level)

    return level, confidence, explanation

"""
Gap-closure tests — Round 5.

Gaps addressed:
16. command_system — division by zero when total_weight==0
17. self_improvement_engine — division by zero when relevant list empty after filter
18. telemetry_adapter — division by zero when total_errors==0
19. bare excepts in 6 modules — changed to ``except Exception:``
20. research_engine — eval() replaced with safe AST-based arithmetic parser
"""

import importlib
import inspect
import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ===================================================================
# Gap 16 — command_system: zero-weight division guard
# ===================================================================
class TestCommandSystemZeroWeight:
    """Weighted decision must not crash when every weight is zero."""

    def test_zero_weights_no_crash(self):
        from command_system import ReasonCommand

        cmd = ReasonCommand()
        result = cmd.execute(
            {"facts": [{"option": "A"}, {"option": "B"}]},
            {"criteria": "price,speed", "weights": "0,0", "method": "scoring"},
        )
        assert result is not None

    def test_normal_weights_still_work(self):
        from command_system import ReasonCommand

        cmd = ReasonCommand()
        result = cmd.execute(
            {"facts": [{"price": 10, "speed": 5}, {"price": 5, "speed": 10}]},
            {"criteria": "price,speed", "weights": "1,2", "method": "scoring"},
        )
        assert result is not None
        assert result.success

    def test_source_has_zero_guard(self):
        """The normalisation line must guard against total_weight==0."""
        import command_system as mod

        src = inspect.getsource(mod.ReasonCommand)
        assert "total_weight > 0" in src


# ===================================================================
# Gap 17 — self_improvement_engine: safe division on empty relevant
# ===================================================================
class TestSelfImprovementZeroDiv:
    """get_confidence_calibration must not crash on edge-case inputs."""

    def test_empty_outcomes_returns_default(self):
        from self_improvement_engine import SelfImprovementEngine

        engine = SelfImprovementEngine()
        result = engine.get_confidence_calibration("nonexistent_task")
        assert "calibrated_confidence" in result
        assert result["calibrated_confidence"] == 0.5  # default

    def test_source_has_zero_guard(self):
        """Confirm the division line now has an inline guard."""
        import self_improvement_engine as mod

        src = inspect.getsource(mod.SelfImprovementEngine.get_confidence_calibration)
        assert "total > 0" in src


# ===================================================================
# Gap 18 — telemetry_adapter: safe division on empty error_metrics
# ===================================================================
class TestTelemetryAdapterZeroDiv:
    """Error-frequency calculation must not crash on zero total_errors."""

    def test_source_has_zero_guard(self):
        import telemetry_adapter as mod

        src = inspect.getsource(mod)
        assert "total_errors > 0" in src


# ===================================================================
# Gap 19 — bare excepts replaced with ``except Exception:``
# ===================================================================
class TestNoBareExcepts:
    """No source module may use a bare ``except:`` clause."""

    MODULES = [
        "enhanced_local_llm",
        "llm_swarm_integration",
        "memory_management",
        "murphy_repl",
        "swarm_proposal_generator",
        "unified_mfgc",
    ]

    @pytest.mark.parametrize("module_name", MODULES)
    def test_no_bare_except(self, module_name):
        fpath = os.path.join(
            os.path.dirname(__file__), "..", "src", f"{module_name}.py"
        )
        with open(fpath, encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                stripped = line.strip()
                if stripped == "except:" or stripped == "except: # noqa":
                    pytest.fail(
                        f"{module_name}.py:{i} still has bare 'except:'"
                    )


# ===================================================================
# Gap 20 — research_engine: eval() replaced with safe AST parser
# ===================================================================
class TestResearchEngineSafeCalc:
    """The calculate() code template must use AST parsing, not eval()."""

    def _get_calc_template(self):
        """Read the code template directly from the source file."""
        fpath = os.path.join(
            os.path.dirname(__file__), "..", "src", "research_engine.py"
        )
        with open(fpath, encoding='utf-8') as f:
            src = f.read()

        # Extract the code between the triple-quote markers
        marker = "code = '''def calculate"
        start = src.find(marker)
        assert start != -1, "Could not find calculate template"
        # Find the closing triple quote
        code_start = src.find("'''", start) + 3
        code_end = src.find("'''", code_start)
        return src[code_start:code_end]

    def test_no_eval_in_template(self):
        code = self._get_calc_template()
        assert "eval(" not in code, "calculate() template must not use eval()"

    def test_ast_in_template(self):
        code = self._get_calc_template()
        assert "ast.parse" in code

    def test_template_executes_basic_arithmetic(self):
        """Execute the generated code template and verify it works."""
        code = self._get_calc_template()
        ns = {}
        exec(code, ns)  # safe: we control the code template
        calc = ns["calculate"]
        assert calc("2 + 3") == 5.0
        assert calc("10 - 4") == 6.0
        assert calc("6 * 7") == 42.0
        assert calc("10 / 4") == 2.5

    def test_template_rejects_injection(self):
        code = self._get_calc_template()
        ns = {}
        exec(code, ns)
        calc = ns["calculate"]
        with pytest.raises(ValueError):
            calc("__import__('os').system('echo pwned')")

    def test_template_rejects_strings(self):
        code = self._get_calc_template()
        ns = {}
        exec(code, ns)
        calc = ns["calculate"]
        with pytest.raises(ValueError):
            calc("'hello'")


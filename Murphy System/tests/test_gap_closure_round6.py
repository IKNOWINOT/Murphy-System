"""
Gap-closure tests — Round 6.

Gaps addressed:
21. 9 remaining bare ``except:`` clauses in 7 deeper modules → ``except Exception:``
22. 8 HTTP requests.get/post calls in comms/connectors.py without timeout → ``timeout=30``
"""

import inspect
import os
import re

import pytest



# ===================================================================
# Gap 21 — bare excepts eliminated from 7 deeper modules
# ===================================================================
class TestNoBareExceptsRound2:
    """No source module anywhere in src/ may use a bare ``except:`` clause."""

    MODULES = [
        "compute_plane/solvers/symbolic_solver",
        "governance_framework/stability_controller",
        "execution_orchestrator/executor",
        "execution_orchestrator/rollback",
        "module_compiler/registry/module_registry",
        "confidence_engine/credential_verifier",
        "librarian/document_manager",
        "librarian/semantic_search",
    ]

    @pytest.mark.parametrize("module_path", MODULES)
    def test_no_bare_except(self, module_path):
        fpath = os.path.join(
            os.path.dirname(__file__), "..", "src", f"{module_path}.py"
        )
        with open(fpath, encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                stripped = line.strip()
                if stripped == "except:" or stripped.startswith("except: "):
                    pytest.fail(
                        f"{module_path}.py:{i} still has bare 'except:'"
                    )

    def test_zero_bare_excepts_in_entire_src(self):
        """Global sweep: no bare except anywhere in src/."""
        src_dir = os.path.join(os.path.dirname(__file__), "..", "src")
        violations = []
        for root, _dirs, files in os.walk(src_dir):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                with open(fpath, encoding='utf-8') as f:
                    for i, line in enumerate(f, 1):
                        if re.match(r"^\s*except\s*:", line):
                            rel = os.path.relpath(fpath, src_dir)
                            violations.append(f"{rel}:{i}")
        assert violations == [], f"Bare except: found in: {violations}"


# ===================================================================
# Gap 22 — all HTTP requests in comms/connectors.py have timeout
# ===================================================================
class TestCommsConnectorsTimeout:
    """Every requests.get/post/etc call in connectors.py must include timeout."""

    def _get_connectors_source(self):
        fpath = os.path.join(
            os.path.dirname(__file__), "..", "src", "comms", "connectors.py"
        )
        with open(fpath, encoding='utf-8') as f:
            return f.read()

    def test_all_requests_calls_have_timeout(self):
        content = self._get_connectors_source()
        pattern = r"(?:requests|_requests)\.(post|get|put|delete|patch|head)\("
        missing = []
        for m in re.finditer(pattern, content):
            start = m.start()
            depth = 1
            pos = m.end()
            while pos < len(content) and depth > 0:
                if content[pos] == "(":
                    depth += 1
                elif content[pos] == ")":
                    depth -= 1
                pos += 1
            call_text = content[start:pos]
            if "timeout" not in call_text:
                line = content[:start].count("\n") + 1
                missing.append(f"line {line}: {m.group()}")

        assert missing == [], f"HTTP calls without timeout: {missing}"

    def test_timeout_value_is_positive(self):
        """Every timeout must be a positive number."""
        content = self._get_connectors_source()
        for m in re.finditer(r"timeout\s*=\s*(\d+)", content):
            val = int(m.group(1))
            assert val > 0, f"timeout must be positive, got {val}"

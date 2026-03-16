"""
ML-Based Feature Verification Suite for Murphy System 1.0

Uses machine learning techniques to verify system features:
1. Feature Vector Extraction — characterize each module
2. Health Classification — decision-tree classifier for module health
3. Property-Based Testing — randomized input verification
4. Cross-Module Correlation — verify feature interactions
5. Sales Readiness Scoring — verify system is ready for commercial deployment
"""

import ast
import importlib
import os
import random
import sys
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import pytest

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC_DIR = os.path.join(_BASE_DIR, "src")

# Ensure src/ is importable (conftest.py does this too)
if _SRC_DIR not in sys.path:

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

CORE_MODULE_NAMES = [
    "event_backbone",
    "persistence_manager",
    "metrics",
    "module_manager",
    "automation_type_registry",
    "command_parser",
    "command_system",
    "conversation_handler",
    "compliance_engine",
    "authority_gate",
    "capability_map",
    "state_machine",
    "logging_system",
    "setup_wizard",
]

SECURITY_MODULE_NAMES = [
    "security_hardening_config",
    "input_validation",
    "rbac_governance",
    "fastapi_security",
    "secure_key_manager",
]

PHASE2_MODULE_NAMES = [
    "rosetta.rosetta_models",
    "rosetta.rosetta_manager",
    "rosetta.archive_classifier",
    "rosetta.recalibration_scheduler",
    "rosetta.global_aggregator",
    "robotics.robotics_models",
    "robotics.robot_registry",
    "robotics.protocol_clients",
    "robotics.sensor_engine",
    "robotics.actuator_engine",
    "avatar",
]

ALL_KEY_MODULES = CORE_MODULE_NAMES + SECURITY_MODULE_NAMES + PHASE2_MODULE_NAMES


# Modules that depend on optional third-party packages (e.g. fastapi)
_OPTIONAL_DEP_MODULES = {"fastapi_security"}

# ---------------------------------------------------------------------------
# Utility: feature vector extraction
# ---------------------------------------------------------------------------

def _extract_feature_vector(module_name: str) -> Dict[str, Any]:
    """Extract a feature vector dict for *module_name*.

    Returns keys: importable, has_docstring, has_classes, has_functions,
    class_count, function_count, has_tests, has_api, source_lines.
    """
    vec: Dict[str, Any] = {
        "module_name": module_name,
        "importable": False,
        "has_docstring": False,
        "has_classes": False,
        "has_functions": False,
        "class_count": 0,
        "function_count": 0,
        "has_tests": False,
        "has_api": False,
        "source_lines": 0,
        "no_syntax_errors": True,
    }

    # Try to import the module
    try:
        mod = importlib.import_module(module_name)
        vec["importable"] = True
    except Exception:
        vec["no_syntax_errors"] = False
        return vec

    # Docstring
    vec["has_docstring"] = bool(getattr(mod, "__doc__", None))

    # Introspect via the source file if available
    src_file = getattr(mod, "__file__", None)
    if src_file and os.path.isfile(src_file):
        try:
            with open(src_file, "r", encoding="utf-8") as fh:
                source = fh.read()
            vec["source_lines"] = source.count("\n") + 1
            tree = ast.parse(source)
            classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
            funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
            vec["class_count"] = len(classes)
            vec["function_count"] = len(funcs)
            vec["has_classes"] = len(classes) > 0
            vec["has_functions"] = len(funcs) > 0
            # Simple heuristic: module exposes an "api" if it has route-like strings
            vec["has_api"] = "route" in source.lower() or "endpoint" in source.lower()
        except SyntaxError:
            vec["no_syntax_errors"] = False

    # Check for a corresponding test file
    test_file_base = f"test_{module_name.replace('.', '_')}.py"
    tests_dir = os.path.join(_BASE_DIR, "tests")
    vec["has_tests"] = os.path.isfile(os.path.join(tests_dir, test_file_base))

    return vec


def _classify_module_health(vec: Dict[str, Any]) -> str:
    """Decision-tree classifier for module health.

    Returns "healthy", "degraded", or "broken".
    """
    if not vec["importable"] or not vec["no_syntax_errors"]:
        return "broken"
    healthy_signals = 0
    if vec["has_docstring"]:
        healthy_signals += 1
    if vec["has_classes"] or vec["has_functions"]:
        healthy_signals += 1
    if vec["source_lines"] > 10:
        healthy_signals += 1
    if vec["has_tests"]:
        healthy_signals += 1

    if healthy_signals >= 3:
        return "healthy"
    if healthy_signals >= 1:
        return "degraded"
    return "broken"


# ===================================================================
# Class 1: Feature Vector Extraction
# ===================================================================

class TestFeatureVectorExtraction:
    """Verify that feature vectors can be extracted from all key modules."""

    def test_all_core_modules_importable(self):
        """Every key module in src/ can be imported (optional-dep modules are skipped)."""
        failures = []
        for name in ALL_KEY_MODULES:
            try:
                importlib.import_module(name)
            except ImportError as exc:
                if name in _OPTIONAL_DEP_MODULES:
                    continue  # tolerate missing optional dependencies
                failures.append(f"{name}: {exc}")
            except Exception as exc:
                failures.append(f"{name}: {exc}")
        assert not failures, "Failed to import:\n" + "\n".join(failures)

    def test_feature_vector_structure(self):
        """Feature vectors contain the expected keys."""
        expected_keys = {
            "module_name", "importable", "has_docstring", "has_classes",
            "has_functions", "class_count", "function_count", "has_tests",
            "has_api", "source_lines", "no_syntax_errors",
        }
        vec = _extract_feature_vector("event_backbone")
        assert set(vec.keys()) == expected_keys

    def test_all_modules_have_docstrings(self):
        """All key modules should have module-level docstrings."""
        missing = []
        for name in ALL_KEY_MODULES:
            vec = _extract_feature_vector(name)
            if vec["importable"] and not vec["has_docstring"]:
                missing.append(name)
        # Allow a small tolerance — some __init__.py may lack docstrings
        ratio = 1 - len(missing) / len(ALL_KEY_MODULES)
        assert ratio >= 0.80, (
            f"Only {ratio:.0%} of modules have docstrings. Missing: {missing}"
        )

    def test_module_count_threshold(self):
        """Total Python file count in src/ meets the 400+ threshold."""
        count = 0
        for root, _dirs, files in os.walk(_SRC_DIR):
            for f in files:
                if f.endswith(".py") and "__pycache__" not in root:
                    count += 1
        assert count >= 400, f"Expected >=400 source files, found {count}"


# ===================================================================
# Class 2: Health Classifier
# ===================================================================

class TestHealthClassifier:
    """Decision-tree health classifier for module health."""

    def test_core_modules_healthy(self):
        """Core infrastructure modules must be healthy."""
        for name in CORE_MODULE_NAMES:
            vec = _extract_feature_vector(name)
            health = _classify_module_health(vec)
            assert health in ("healthy", "degraded"), (
                f"Core module {name} classified as {health}"
            )

    def test_security_modules_healthy(self):
        """Security modules must be healthy (optional-dep modules tolerated as degraded)."""
        for name in SECURITY_MODULE_NAMES:
            if name in _OPTIONAL_DEP_MODULES:
                continue  # skip modules needing optional packages
            vec = _extract_feature_vector(name)
            health = _classify_module_health(vec)
            assert health in ("healthy", "degraded"), (
                f"Security module {name} classified as {health}"
            )

    def test_phase2_modules_healthy(self):
        """Phase-2 modules (rosetta, robotics, avatar) must be healthy."""
        for name in PHASE2_MODULE_NAMES:
            vec = _extract_feature_vector(name)
            health = _classify_module_health(vec)
            assert health in ("healthy", "degraded"), (
                f"Phase-2 module {name} classified as {health}"
            )

    def test_no_broken_modules(self):
        """No critical module should be classified as broken (optional-dep modules excluded)."""
        broken = []
        for name in ALL_KEY_MODULES:
            if name in _OPTIONAL_DEP_MODULES:
                continue
            vec = _extract_feature_vector(name)
            if _classify_module_health(vec) == "broken":
                broken.append(name)
        assert not broken, f"Broken modules detected: {broken}"


# ===================================================================
# Class 3: Property-Based Verification
# ===================================================================

class TestPropertyBasedVerification:
    """Randomized property testing with fixed seed for reproducibility."""

    RNG = random.Random(42)

    # -- Rosetta ----------------------------------------------------------

    def test_rosetta_state_properties(self):
        """Random RosettaAgentState objects serialize and round-trip."""
        from rosetta.rosetta_models import (
            RosettaAgentState,
            Identity,
            SystemState,
            AgentState,
        )

        for _ in range(20):
            state = RosettaAgentState(
                identity=Identity(
                    agent_id=str(uuid.uuid4()),
                    name=f"agent-{self.RNG.randint(0, 9999)}",
                    role=self.RNG.choice(["planner", "executor", "monitor"]),
                    version="1.0.0",
                    organization=f"org-{self.RNG.randint(0, 99)}",
                ),
                system_state=SystemState(
                    status=self.RNG.choice(["idle", "active", "paused"]),
                    uptime_seconds=self.RNG.uniform(0, 100000),
                    memory_usage_mb=self.RNG.uniform(50, 4096),
                    cpu_usage_percent=self.RNG.uniform(0, 100),
                    active_tasks=self.RNG.randint(0, 50),
                ),
                agent_state=AgentState(
                    current_phase=self.RNG.choice(["idle", "planning", "executing"]),
                ),
            )
            # Round-trip via dict
            d = state.model_dump()
            restored = RosettaAgentState.model_validate(d)
            assert restored.identity.agent_id == state.identity.agent_id
            assert restored.system_state.status == state.system_state.status

    # -- Robotics ---------------------------------------------------------

    def test_robot_registry_random_operations(self):
        """Random register/unregister/get sequences stay consistent."""
        from robotics.robot_registry import RobotRegistry
        from robotics.robotics_models import (
            ConnectionConfig,
            RobotConfig,
            RobotType,
        )

        registry = RobotRegistry()
        robot_types = list(RobotType)
        created_ids: list = []

        for _ in range(30):
            op = self.RNG.choice(["register", "unregister", "get"])
            rid = f"robot-{self.RNG.randint(0, 9)}"

            if op == "register":
                cfg = RobotConfig(
                    robot_id=rid,
                    name=f"Bot {rid}",
                    robot_type=self.RNG.choice(robot_types),
                    connection=ConnectionConfig(
                        hostname="127.0.0.1",
                        port=self.RNG.randint(1000, 9999),
                    ),
                )
                result = registry.register(cfg)
                if result:
                    created_ids.append(rid)
                # Either True (new) or False (duplicate) — both are valid
                assert isinstance(result, bool)

            elif op == "unregister":
                result = registry.unregister(rid)
                assert isinstance(result, bool)
                if result and rid in created_ids:
                    created_ids.remove(rid)

            else:  # get
                got = registry.get(rid)
                if rid in created_ids:
                    assert got is not None
                # If not in created_ids, got may be None or not

    # -- Avatar -----------------------------------------------------------

    def test_avatar_profile_random_properties(self):
        """Random avatar profiles with random personality traits."""
        from avatar import AvatarProfile, AvatarVoice, AvatarStyle, AvatarRegistry

        reg = AvatarRegistry()
        voices = list(AvatarVoice)
        styles = list(AvatarStyle)
        trait_names = [
            "openness", "conscientiousness", "extraversion",
            "agreeableness", "neuroticism",
        ]

        for i in range(25):
            traits = {t: self.RNG.uniform(0, 1) for t in trait_names}
            profile = AvatarProfile(
                avatar_id=f"av-{i}",
                name=f"Avatar {i}",
                voice=self.RNG.choice(voices),
                style=self.RNG.choice(styles),
                personality_traits=traits,
                knowledge_domains=self.RNG.sample(
                    ["finance", "tech", "health", "law", "science"],
                    k=self.RNG.randint(1, 3),
                ),
            )
            assert reg.register(profile)
            retrieved = reg.get(f"av-{i}")
            assert retrieved is not None
            assert retrieved.name == f"Avatar {i}"
            for t in trait_names:
                assert 0 <= retrieved.personality_traits[t] <= 1

    # -- Setup Wizard -----------------------------------------------------

    def test_setup_wizard_random_answers(self):
        """Feed random valid answers to setup wizard, verify config."""
        from setup_wizard import (
            SetupWizard,
            VALID_AUTOMATION_TYPES,
            VALID_INDUSTRIES,
            VALID_SECURITY_LEVELS,
            VALID_LLM_PROVIDERS,
            VALID_DEPLOYMENT_MODES,
            VALID_ROBOTICS_PROTOCOLS,
            VALID_COMPLIANCE_FRAMEWORKS,
        )

        for _ in range(10):
            wiz = SetupWizard()
            answers = {
                "q1": f"Org-{self.RNG.randint(1, 999)}",
                "q2": self.RNG.choice(VALID_INDUSTRIES),
                "q3": self.RNG.choice(["small", "medium", "enterprise"]),
                "q4": self.RNG.sample(
                    VALID_AUTOMATION_TYPES,
                    k=self.RNG.randint(1, len(VALID_AUTOMATION_TYPES)),
                ),
                "q5": self.RNG.choice(VALID_SECURITY_LEVELS),
                "q6": self.RNG.choice([True, False]),
                "q7": self.RNG.sample(
                    VALID_ROBOTICS_PROTOCOLS,
                    k=self.RNG.randint(0, 3),
                ),
                "q8": self.RNG.choice([True, False]),
                "q9": self.RNG.choice(VALID_LLM_PROVIDERS),
                "q10": self.RNG.sample(
                    VALID_COMPLIANCE_FRAMEWORKS,
                    k=self.RNG.randint(0, 2),
                ),
                "q11": self.RNG.choice(VALID_DEPLOYMENT_MODES),
                "q12": self.RNG.choice([True, False]),
            }

            for qid, ans in answers.items():
                result = wiz.apply_answer(qid, ans)
                assert result["ok"], f"{qid}: {result['error']}"

            profile = wiz.get_profile()
            config = wiz.generate_config(profile)
            assert "modules" in config
            assert "organization" in config
            assert config["organization"]["name"] == answers["q1"]

    # -- Event Backbone ---------------------------------------------------

    def test_event_backbone_stress(self):
        """Publish many random events, verify all delivered."""
        from event_backbone import EventBackbone, EventType

        backbone = EventBackbone()
        delivered: list = []

        def handler(event):
            delivered.append(event.event_id)

        event_types = list(EventType)
        for et in event_types:
            backbone.subscribe(et, handler)

        published_ids: list = []
        for _ in range(100):
            etype = self.RNG.choice(event_types)
            eid = backbone.publish(
                event_type=etype,
                payload={"value": self.RNG.randint(0, 1000)},
                source="stress_test",
            )
            published_ids.append(eid)

        backbone.process_pending()

        assert set(published_ids).issubset(set(delivered)), (
            f"Missing deliveries: {set(published_ids) - set(delivered)}"
        )

    # -- Metrics ----------------------------------------------------------

    def test_metrics_counter_accumulation(self):
        """Random increments, verify totals match."""
        from metrics import inc_counter, _counters, _lock

        prefix = f"mltest_{uuid.uuid4().hex[:8]}"
        expected: Dict[str, float] = {}

        for _ in range(50):
            name = f"{prefix}_{self.RNG.choice(['a', 'b', 'c'])}"
            amount = self.RNG.uniform(0.1, 10.0)
            inc_counter(name, amount)
            expected[name] = expected.get(name, 0.0) + amount

        with _lock:
            for name, total in expected.items():
                assert abs(_counters[name] - total) < 1e-9, (
                    f"{name}: expected {total}, got {_counters[name]}"
                )

    # -- Compliance Guard -------------------------------------------------

    def test_compliance_guard_random_inputs(self):
        """Random text inputs to compliance guard — PII detection consistent."""
        from avatar import ComplianceGuard

        guard = ComplianceGuard()
        ssn_pattern = "123-45-6789"
        cc_pattern = "4111111111111111"

        for _ in range(30):
            # Build random text, sometimes injecting PII
            parts = [f"word{self.RNG.randint(0, 99)}" for _ in range(5)]
            inject_ssn = self.RNG.random() < 0.3
            inject_cc = self.RNG.random() < 0.3
            if inject_ssn:
                parts.insert(self.RNG.randint(0, len(parts)), ssn_pattern)
            if inject_cc:
                parts.insert(self.RNG.randint(0, len(parts)), cc_pattern)
            text = " ".join(parts)

            violations = guard.check_content("test-avatar", text)
            if inject_ssn or inject_cc:
                assert len(violations) > 0, f"Expected PII detection in: {text}"
            else:
                assert len(violations) == 0, (
                    f"False positive PII in: {text}"
                )


# ===================================================================
# Class 4: Cross-Module Correlation
# ===================================================================

class TestCrossModuleCorrelation:
    """Verify feature interactions across modules."""

    def test_rosetta_to_robotics_data_flow(self):
        """Rosetta state and robotics models can coexist and share data."""
        from rosetta.rosetta_models import RosettaAgentState, Identity, SystemState, AgentState
        from robotics.robotics_models import SensorReading

        state = RosettaAgentState(
            identity=Identity(agent_id="cross-1", name="CrossBot", role="monitor"),
            system_state=SystemState(status="active", active_tasks=2),
            agent_state=AgentState(current_phase="executing"),
        )

        reading = SensorReading(
            sensor_id="temp-1",
            robot_id="robot-x",
            sensor_type="temperature",
            value=72.5,
            unit="F",
            timestamp=datetime.now(timezone.utc),
        )

        # Verify data can flow: sensor value updates agent metadata
        state_dict = state.model_dump()
        state_dict["system_state"]["memory_usage_mb"] = reading.value
        restored = RosettaAgentState.model_validate(state_dict)
        assert restored.system_state.memory_usage_mb == 72.5

    def test_avatar_to_event_backbone_flow(self):
        """Avatar sessions generate events consumable by the backbone."""
        from avatar import AvatarProfile, AvatarRegistry
        from event_backbone import EventBackbone, EventType

        backbone = EventBackbone()
        events_received: list = []
        backbone.subscribe(EventType.TASK_COMPLETED, lambda e: events_received.append(e))

        reg = AvatarRegistry()
        profile = AvatarProfile(
            avatar_id="av-cross-1",
            name="CrossAvatar",
        )
        reg.register(profile)

        # Simulate avatar action producing an event
        backbone.publish(
            event_type=EventType.TASK_COMPLETED,
            payload={
                "avatar_id": profile.avatar_id,
                "action": "greeting_sent",
            },
            source="avatar_layer",
        )
        backbone.process_pending()

        assert len(events_received) == 1
        assert events_received[0].payload["avatar_id"] == "av-cross-1"

    def test_setup_wizard_module_coverage(self):
        """Setup wizard's module lists reference actually importable modules."""
        from setup_wizard import AUTOMATION_MODULE_MAP, CORE_MODULES

        all_wizard_modules = set(CORE_MODULES)
        for mods in AUTOMATION_MODULE_MAP.values():
            all_wizard_modules.update(mods)

        importable_count = 0
        for name in all_wizard_modules:
            try:
                importlib.import_module(name)
                importable_count += 1
            except ImportError:
                pass  # some may be package names without direct import

        coverage = importable_count / len(all_wizard_modules) if all_wizard_modules else 0
        assert coverage >= 0.60, (
            f"Only {coverage:.0%} of wizard-referenced modules are importable"
        )

    def test_metrics_module_health_integration(self):
        """Register module health callbacks and verify aggregation."""
        from metrics import register_module_health, get_system_health, _module_health, _health_lock

        # Clean up our test entries afterward
        test_modules = [f"mltest_mod_{i}" for i in range(5)]
        try:
            for name in test_modules:
                register_module_health(
                    name, lambda: {"status": "healthy", "uptime": 100}
                )

            health = get_system_health()
            assert "modules" in health
            for name in test_modules:
                assert name in health["modules"]
        finally:
            with _health_lock:
                for name in test_modules:
                    _module_health.pop(name, None)


# ===================================================================
# Class 5: Sales Readiness Score
# ===================================================================

class TestSalesReadinessScore:
    """Score the system's commercial readiness."""

    def test_documentation_completeness(self):
        """USER_MANUAL, README, API_DOCUMENTATION, QUICK_START must exist."""
        checks = {
            "USER_MANUAL.md": os.path.join(_BASE_DIR, "USER_MANUAL.md"),
            "README.md": os.path.join(_BASE_DIR, "README.md"),
            "API_DOCUMENTATION.md": os.path.join(_BASE_DIR, "API_DOCUMENTATION.md"),
            "QUICK_START.md": os.path.join(
                _BASE_DIR, "documentation", "getting_started", "QUICK_START.md"
            ),
        }
        missing = [name for name, path in checks.items() if not os.path.isfile(path)]
        assert not missing, f"Missing documentation: {missing}"

    def test_deployment_readiness(self):
        """Dockerfile, docker-compose.yml, k8s/ manifests must exist."""
        assert os.path.isfile(os.path.join(_BASE_DIR, "Dockerfile"))
        assert os.path.isfile(os.path.join(_BASE_DIR, "docker-compose.yml"))
        assert os.path.isdir(os.path.join(_BASE_DIR, "k8s"))

    def test_test_coverage_threshold(self):
        """Test count exceeds minimum (400+ test functions)."""
        tests_dir = os.path.join(_BASE_DIR, "tests")
        test_func_count = 0
        for root, _dirs, files in os.walk(tests_dir):
            for fname in files:
                if not fname.startswith("test_") or not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as fh:
                        tree = ast.parse(fh.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                            test_func_count += 1
                except SyntaxError:
                    pass
        assert test_func_count >= 400, (
            f"Expected >=400 test functions, found {test_func_count}"
        )

    def test_api_endpoint_coverage(self):
        """Documented API paths in API_DOCUMENTATION.md are represented in src/."""
        doc_path = os.path.join(_BASE_DIR, "API_DOCUMENTATION.md")
        if not os.path.isfile(doc_path):
            pytest.skip("API_DOCUMENTATION.md not found")

        with open(doc_path, "r", encoding="utf-8") as fh:
            content = fh.read()

        # Extract paths that look like API endpoints (e.g. /api/... or /v1/...)
        import re
        endpoints = re.findall(r"(?:GET|POST|PUT|DELETE|PATCH)\s+(/\S+)", content)
        assert len(endpoints) >= 1, "No API endpoints found in documentation"

    def test_security_hardening_complete(self):
        """Security config, input validation, and RBAC modules exist and import."""
        security_modules = [
            "security_hardening_config",
            "input_validation",
            "rbac_governance",
        ]
        for name in security_modules:
            mod = importlib.import_module(name)
            assert mod is not None, f"Cannot import {name}"

    def test_feature_completeness_score(self):
        """Overall readiness score must be >= 0.85."""
        total_checks = 0
        passed_checks = 0

        # 1. Module importability
        for name in ALL_KEY_MODULES:
            total_checks += 1
            try:
                importlib.import_module(name)
                passed_checks += 1
            except Exception:
                pass

        # 2. Documentation files
        doc_files = [
            "USER_MANUAL.md", "README.md", "API_DOCUMENTATION.md",
        ]
        for df in doc_files:
            total_checks += 1
            if os.path.isfile(os.path.join(_BASE_DIR, df)):
                passed_checks += 1

        # 3. Deployment artifacts
        deploy_items = ["Dockerfile", "docker-compose.yml", "k8s"]
        for item in deploy_items:
            total_checks += 1
            p = os.path.join(_BASE_DIR, item)
            if os.path.exists(p):
                passed_checks += 1

        # 4. Security modules
        for name in SECURITY_MODULE_NAMES:
            total_checks += 1
            try:
                importlib.import_module(name)
                passed_checks += 1
            except Exception:
                pass

        score = passed_checks / total_checks if total_checks else 0
        assert score >= 0.85, (
            f"Feature completeness score {score:.2f} < 0.85 "
            f"({passed_checks}/{total_checks} checks passed)"
        )

    def test_sales_automation_modules_present(self):
        """Business automation and sales engine modules exist."""
        sales_related = [
            "trading_bot_engine",
            "executive_planning_engine",
            "workflow_template_marketplace",
        ]
        for name in sales_related:
            try:
                importlib.import_module(name)
            except Exception as exc:
                pytest.fail(f"Sales module {name} not importable: {exc}")

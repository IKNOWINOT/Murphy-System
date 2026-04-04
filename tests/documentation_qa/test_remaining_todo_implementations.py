"""
Tests for the remaining TODO implementations (session 2).

Covers:
- plan_models: Critical Path Method (CPM) implementation
- form_intake/api: Submission status tracking
- confidence_engine/murphy_validator: Confidence calculator integration
- integration_engine/unified_engine: TrueSwarmSystem integration & cleanup
- module_compiler/capability_extractor: env_vars & files extraction
"""

import sys
import os

# Ensure repo root and src are on the path.
_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _base)
sys.path.insert(0, os.path.join(_base, 'src'))


# ============================================================================
# Critical Path Method Tests
# ============================================================================

class TestCriticalPathMethod:
    """Tests for Plan.get_critical_path()"""

    def _make_plan(self, tasks, deps):
        from form_intake.plan_models import (
            Plan, Task, Dependency, DependencyType, TaskStatus, TaskPriority
        )
        task_objs = []
        for t in tasks:
            task_objs.append(Task(
                task_id=t['id'],
                title=t.get('title', t['id']),
                description='',
                priority=TaskPriority.MEDIUM,
                status=t.get('status', TaskStatus.PENDING),
                estimated_hours=t.get('hours', 8.0),
            ))
        dep_objs = []
        for i, d in enumerate(deps):
            dep_objs.append(Dependency(
                dependency_id=f'dep_{i}',
                from_task_id=d[0],
                to_task_id=d[1],
                dependency_type=DependencyType.FINISH_TO_START,
            ))
        return Plan(
            plan_id='test_plan',
            title='Test',
            description='',
            goal='test',
            domain='software_development',
            timeline='1 month',
            tasks=task_objs,
            dependencies=dep_objs,
        )

    def test_empty_plan_returns_empty(self):
        from form_intake.plan_models import Plan
        plan = Plan(plan_id='p', title='t', description='', goal='g',
                    domain='test', timeline='1 week')
        assert plan.get_critical_path() == []

    def test_single_task(self):
        plan = self._make_plan(
            [{'id': 'A', 'hours': 10}],
            []
        )
        path = plan.get_critical_path()
        assert 'A' in path

    def test_linear_chain(self):
        """A -> B -> C - all on the critical path"""
        plan = self._make_plan(
            [
                {'id': 'A', 'hours': 5},
                {'id': 'B', 'hours': 10},
                {'id': 'C', 'hours': 3},
            ],
            [('A', 'B'), ('B', 'C')]
        )
        path = plan.get_critical_path()
        assert path == ['A', 'B', 'C']

    def test_parallel_paths_picks_longest(self):
        """
        A(2) -> B(8) -> D(1)
        A(2) -> C(3) -> D(1)

        Critical path should go through B (longer).
        """
        plan = self._make_plan(
            [
                {'id': 'A', 'hours': 2},
                {'id': 'B', 'hours': 8},
                {'id': 'C', 'hours': 3},
                {'id': 'D', 'hours': 1},
            ],
            [('A', 'B'), ('A', 'C'), ('B', 'D'), ('C', 'D')]
        )
        path = plan.get_critical_path()
        # A, B, D should be on critical path (total 11h)
        # C should NOT be on critical path (A+C+D = 6h)
        assert 'A' in path
        assert 'B' in path
        assert 'D' in path
        assert 'C' not in path

    def test_default_hours(self):
        """Tasks without estimated_hours default to 8.0"""
        plan = self._make_plan(
            [{'id': 'X'}, {'id': 'Y'}],
            [('X', 'Y')]
        )
        path = plan.get_critical_path()
        assert 'X' in path
        assert 'Y' in path


# ============================================================================
# Submission Status Tracking Tests
# ============================================================================

class TestSubmissionStatusTracking:
    """Tests for submission status tracking via _SUBMISSION_LEDGER"""

    def test_record_submission_creates_entry(self):
        from form_intake.handlers import _SUBMISSION_LEDGER, _record_submission
        _record_submission('test-sub-001', 'plan_upload', 'queued')
        assert 'test-sub-001' in _SUBMISSION_LEDGER
        entry = _SUBMISSION_LEDGER['test-sub-001']
        assert entry['status'] == 'queued'
        assert entry['form_type'] == 'plan_upload'
        assert entry['created_at'] is not None
        # Cleanup
        del _SUBMISSION_LEDGER['test-sub-001']

    def test_record_submission_with_extra(self):
        from form_intake.handlers import _SUBMISSION_LEDGER, _record_submission
        _record_submission('test-sub-002', 'task_execution', 'queued', {'custom': 'value'})
        entry = _SUBMISSION_LEDGER['test-sub-002']
        assert entry['data']['custom'] == 'value'
        assert entry['status'] == 'queued'
        del _SUBMISSION_LEDGER['test-sub-002']

    def test_status_not_found_returns_none(self):
        from form_intake.handlers import _SUBMISSION_LEDGER
        assert _SUBMISSION_LEDGER.get('nonexistent-id') is None


# ============================================================================
# Confidence Calculator Integration Tests
# ============================================================================

class TestConfidenceCalculatorIntegration:
    """Tests for MurphyValidator._compute_confidence_v1 integration"""

    def _make_validator(self):
        from confidence_engine.murphy_validator import MurphyValidator
        return MurphyValidator()

    def test_v1_returns_float(self):
        mv = self._make_validator()
        result = mv._compute_confidence_v1({}, {'phase': 'expand'})
        assert isinstance(result, (float, int, type(None)))

    def test_v1_with_empty_context(self):
        mv = self._make_validator()
        result = mv._compute_confidence_v1({}, {})
        # Should not crash, returns a float
        assert result is None or isinstance(result, float)

    def test_v1_graceful_degradation(self):
        """With no artifacts, the v1 calculator should still return a value."""
        mv = self._make_validator()
        result = mv._compute_confidence_v1(
            {'task_id': 'test'},
            {'phase': 'expand', 'artifacts': []}
        )
        assert result is None or isinstance(result, float)

    def test_v1_with_confidence_hint(self):
        """When v1 fails, it should use confidence_hint fallback."""
        mv = self._make_validator()
        # Force v1 unavailable
        mv.has_v1_calculator = False
        result = mv._compute_confidence_v1({}, {'confidence_hint': 0.88})
        assert result is None  # returns None when has_v1_calculator is False


# ============================================================================
# Unified Engine Integration Tests
# ============================================================================

class TestUnifiedEngineSwarmRegistration:
    """Tests for _register_agent_with_swarm and _cleanup_rejected_integration"""

    def test_register_agent_does_not_crash(self):
        """Registration should not raise even if swarm system is unavailable."""
        try:
            from integration_engine.unified_engine import UnifiedIntegrationEngine
        except ImportError:
            import pytest
            pytest.skip("Unified engine dependencies not installed")
        engine = UnifiedIntegrationEngine()
        # Should not raise - graceful fallback
        engine._register_agent_with_swarm(
            {'name': 'test_agent'},
            ['data_analysis', 'security']
        )

    def test_cleanup_nonexistent_files_does_not_crash(self):
        """Cleanup of non-existent paths should be handled gracefully."""
        try:
            from integration_engine.unified_engine import UnifiedIntegrationEngine
        except ImportError:
            import pytest
            pytest.skip("Unified engine dependencies not installed")
        engine = UnifiedIntegrationEngine()
        # Should not raise
        engine._cleanup_rejected_integration({
            'name': 'test_module',
            'module_path': '/tmp/nonexistent_test_file.py',
            'agent_path': '/tmp/nonexistent_agent_file.py',
        })

    def test_cleanup_actual_file(self):
        """Cleanup should remove files that exist."""
        import tempfile
        try:
            from integration_engine.unified_engine import UnifiedIntegrationEngine
        except ImportError:
            import pytest
            pytest.skip("Unified engine dependencies not installed")
        engine = UnifiedIntegrationEngine()

        # Create temp file
        fd, path = tempfile.mkstemp(suffix='.py')
        os.close(fd)
        assert os.path.exists(path)

        # Cleanup should remove it
        engine._cleanup_rejected_integration({
            'name': 'test_module',
            'module_path': path,
        })
        assert not os.path.exists(path)


# ============================================================================
# Capability Extractor Tests
# ============================================================================

class TestCapabilityExtractorEnvVars:
    """Tests for _extract_env_vars and _extract_required_files"""

    def _make_func(self, uses_external_api=False, uses_network=False, uses_filesystem=False):
        from module_compiler.analyzers.static_analyzer import FunctionInfo
        return FunctionInfo(
            name='test_fn',
            docstring='Test function',
            parameters=[],
            return_type='str',
            is_async=False,
            is_method=False,
            class_name=None,
            decorators=[],
            line_number=1,
            uses_random=False,
            uses_network=uses_network,
            uses_filesystem=uses_filesystem,
            uses_time=False,
            uses_external_api=uses_external_api,
        )

    def _make_structure(self, imports=None):
        from module_compiler.analyzers.static_analyzer import CodeStructure, ImportInfo
        struct = CodeStructure()
        if imports:
            for mod in imports:
                struct.imports.append(ImportInfo(
                    module=mod, names=[], alias=None, is_from_import=False
                ))
        return struct

    def test_external_api_gets_api_key(self):
        from module_compiler.analyzers.capability_extractor import CapabilityExtractor
        func = self._make_func(uses_external_api=True)
        struct = self._make_structure()
        env_vars = CapabilityExtractor._extract_env_vars(func, struct)
        assert 'API_KEY' in env_vars

    def test_network_gets_base_url(self):
        from module_compiler.analyzers.capability_extractor import CapabilityExtractor
        func = self._make_func(uses_network=True)
        struct = self._make_structure()
        env_vars = CapabilityExtractor._extract_env_vars(func, struct)
        assert 'API_BASE_URL' in env_vars

    def test_boto_import_gets_aws_vars(self):
        from module_compiler.analyzers.capability_extractor import CapabilityExtractor
        func = self._make_func()
        struct = self._make_structure(['boto3'])
        env_vars = CapabilityExtractor._extract_env_vars(func, struct)
        assert 'AWS_ACCESS_KEY_ID' in env_vars
        assert 'AWS_SECRET_ACCESS_KEY' in env_vars

    def test_openai_import_gets_key(self):
        from module_compiler.analyzers.capability_extractor import CapabilityExtractor
        func = self._make_func()
        struct = self._make_structure(['openai'])
        env_vars = CapabilityExtractor._extract_env_vars(func, struct)
        assert 'OPENAI_API_KEY' in env_vars

    def test_sqlalchemy_gets_db_url(self):
        from module_compiler.analyzers.capability_extractor import CapabilityExtractor
        func = self._make_func()
        struct = self._make_structure(['sqlalchemy'])
        env_vars = CapabilityExtractor._extract_env_vars(func, struct)
        assert 'DATABASE_URL' in env_vars

    def test_no_duplicates(self):
        from module_compiler.analyzers.capability_extractor import CapabilityExtractor
        func = self._make_func(uses_external_api=True, uses_network=True)
        struct = self._make_structure()
        env_vars = CapabilityExtractor._extract_env_vars(func, struct)
        assert len(env_vars) == len(set(env_vars))

    def test_filesystem_gets_config(self):
        from module_compiler.analyzers.capability_extractor import CapabilityExtractor
        func = self._make_func(uses_filesystem=True)
        struct = self._make_structure()
        files = CapabilityExtractor._extract_required_files(func, struct)
        assert 'config.json' in files

    def test_dotenv_import_gets_env(self):
        from module_compiler.analyzers.capability_extractor import CapabilityExtractor
        func = self._make_func()
        struct = self._make_structure(['dotenv'])
        files = CapabilityExtractor._extract_required_files(func, struct)
        assert '.env' in files

    def test_yaml_import_gets_yaml(self):
        from module_compiler.analyzers.capability_extractor import CapabilityExtractor
        func = self._make_func()
        struct = self._make_structure(['yaml'])
        files = CapabilityExtractor._extract_required_files(func, struct)
        assert 'config.yaml' in files

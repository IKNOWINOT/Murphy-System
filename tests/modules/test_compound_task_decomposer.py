"""
Tests for Compound Task Decomposer and Code Project Validator.

Test Label: CTD-TEST-001 / CPV-TEST-001
Copyright (c) 2020 Inoni Limited Liability Company
License: BSL 1.1
"""


# ===========================================================================
# CTD-TEST-001: Compound Task Decomposer tests
# ===========================================================================


class TestCompoundQueryDetection:
    """Does detect_compound_query identify compound queries correctly?

    Expected: Queries with prerequisite research/analysis + build verbs
    are detected as compound.  Simple queries are not.
    """

    def test_market_research_then_build_detected(self):
        """CTD-TEST-DETECT-001: 'market research ... create' is compound."""
        from compound_task_decomposer import detect_compound_query

        result = detect_compound_query(
            "create me a web APP MVP for a lucrative niche after "
            "performing market research to select the niche"
        )
        assert result.is_compound is True
        assert len(result.phases) >= 2
        assert result.decomposition_confidence > 0.0

    def test_research_then_build_detected(self):
        """CTD-TEST-DETECT-002: 'research X then build Y' is compound."""
        from compound_task_decomposer import detect_compound_query

        result = detect_compound_query(
            "research the best fitness niches then create an MVP app"
        )
        assert result.is_compound is True
        assert any(
            p.phase_type.value == "research" for p in result.phases
        )
        assert any(p.phase_type.value == "build" for p in result.phases)

    def test_simple_build_not_compound(self):
        """CTD-TEST-DETECT-003: 'build me an app' is NOT compound."""
        from compound_task_decomposer import detect_compound_query

        result = detect_compound_query("build me an onboarding app")
        assert result.is_compound is False
        assert len(result.phases) == 0

    def test_empty_query_not_compound(self):
        """CTD-TEST-DETECT-004: Empty query is NOT compound."""
        from compound_task_decomposer import detect_compound_query

        result = detect_compound_query("")
        assert result.is_compound is False

    def test_none_query_not_compound(self):
        """CTD-TEST-DETECT-005: None-ish query handled gracefully."""
        from compound_task_decomposer import detect_compound_query

        result = detect_compound_query("   ")
        assert result.is_compound is False

    def test_lucrative_niche_pattern(self):
        """CTD-TEST-DETECT-006: 'lucrative niche ... build' is compound."""
        from compound_task_decomposer import detect_compound_query

        result = detect_compound_query(
            "find a lucrative niche and build a web app MVP for it"
        )
        # Should match either niche_research_build or select_for_build
        assert result.is_compound is True

    def test_select_for_build_detected(self):
        """CTD-TEST-DETECT-007: 'select X for Y' is compound."""
        from compound_task_decomposer import detect_compound_query

        result = detect_compound_query(
            "select the best market segment for building a SaaS product"
        )
        assert result.is_compound is True

    def test_after_performing_detected(self):
        """CTD-TEST-DETECT-008: 'after performing X, build Y' is compound."""
        from compound_task_decomposer import detect_compound_query

        result = detect_compound_query(
            "after performing competitive analysis create a landing page"
        )
        assert result.is_compound is True


class TestPhaseDecomposition:
    """Does _build_phases produce correct phase ordering?

    Expected: Research/selection phases precede build phases.
    Dependencies are correctly set.
    """

    def test_market_research_produces_three_phases(self):
        """CTD-TEST-PHASE-001: Market research query -> 3 phases."""
        from compound_task_decomposer import detect_compound_query

        result = detect_compound_query(
            "perform market research to select a niche then create an MVP"
        )
        assert result.is_compound is True
        # Should have: research -> selection -> build
        phase_types = [p.phase_type.value for p in result.phases]
        assert "research" in phase_types
        assert "build" in phase_types

    def test_build_phase_depends_on_research(self):
        """CTD-TEST-PHASE-002: Build phase depends on research phase."""
        from compound_task_decomposer import detect_compound_query

        result = detect_compound_query(
            "research the market then build an e-commerce platform"
        )
        assert result.is_compound is True
        build_phases = [
            p for p in result.phases if p.phase_type.value == "build"
        ]
        assert len(build_phases) >= 1
        assert len(build_phases[0].depends_on) > 0

    def test_phases_have_query_fragments(self):
        """CTD-TEST-PHASE-003: Each phase has a query fragment."""
        from compound_task_decomposer import detect_compound_query

        result = detect_compound_query(
            "analyze competitor pricing then create a subscription app"
        )
        assert result.is_compound is True
        for phase in result.phases:
            assert phase.query_fragment
            assert len(phase.query_fragment) > 0

    def test_phases_have_module_hints(self):
        """CTD-TEST-PHASE-004: Phases have module hints for execution."""
        from compound_task_decomposer import detect_compound_query

        result = detect_compound_query(
            "study market trends then develop a health tracking app"
        )
        assert result.is_compound is True
        for phase in result.phases:
            assert isinstance(phase.module_hints, list)


class TestPrerequisiteExecution:
    """Does execute_prerequisite_phases run phases in order?

    Expected: Non-BUILD phases execute. Their output populates
    enriched_context. Failed dependencies skip dependent phases.
    """

    def test_prerequisite_phases_execute(self):
        """CTD-TEST-EXEC-001: Prerequisite phases produce output."""
        from compound_task_decomposer import (
            detect_compound_query,
            execute_prerequisite_phases,
        )

        decomposition = detect_compound_query(
            "research profitable SaaS niches then build an MVP"
        )
        assert decomposition.is_compound is True

        result = execute_prerequisite_phases(decomposition)
        # At least one non-build phase should have succeeded
        non_build = [
            p
            for p in result.phases
            if p.phase_type.value != "build"
        ]
        assert len(non_build) > 0
        assert any(p.success for p in non_build)

    def test_enriched_context_populated(self):
        """CTD-TEST-EXEC-002: Enriched context is populated after execution."""
        from compound_task_decomposer import (
            detect_compound_query,
            execute_prerequisite_phases,
        )

        decomposition = detect_compound_query(
            "perform market research to create a fitness app"
        )
        result = execute_prerequisite_phases(decomposition)

        # enriched_context should contain research findings
        if any(
            p.success
            for p in result.phases
            if p.phase_type.value != "build"
        ):
            assert len(result.enriched_context) > 0
            assert "PREREQUISITE PHASE RESULTS" in result.enriched_context

    def test_non_compound_query_passes_through(self):
        """CTD-TEST-EXEC-003: Non-compound queries are unchanged."""
        from compound_task_decomposer import (
            DecompositionResult,
            execute_prerequisite_phases,
        )

        decomp = DecompositionResult(
            is_compound=False, original_query="just build an app"
        )
        result = execute_prerequisite_phases(decomp)
        assert result.enriched_context == ""

    def test_phase_elapsed_time_tracked(self):
        """CTD-TEST-EXEC-004: Phase elapsed time is recorded."""
        from compound_task_decomposer import (
            detect_compound_query,
            execute_prerequisite_phases,
        )

        decomposition = detect_compound_query(
            "evaluate market opportunities then create a SaaS app"
        )
        result = execute_prerequisite_phases(decomposition)
        non_build = [
            p
            for p in result.phases
            if p.phase_type.value != "build"
        ]
        for phase in non_build:
            # elapsed_ms should be set (>= 0)
            assert phase.elapsed_ms >= 0


class TestDeterministicFallbacks:
    """Do deterministic fallbacks produce valid structured output?

    Expected: When live modules are unavailable, deterministic research
    and selection still produce usable data.
    """

    def test_deterministic_market_research_structure(self):
        """CTD-TEST-FALLBACK-001: Deterministic research has required keys."""
        from compound_task_decomposer import _deterministic_market_research

        result = _deterministic_market_research("find a lucrative niche")
        assert "detected_niches" in result
        assert "top_niches_ranked" in result
        assert "recommendation" in result
        assert len(result["detected_niches"]) > 0
        assert len(result["top_niches_ranked"]) > 0

    def test_deterministic_research_detects_keywords(self):
        """CTD-TEST-FALLBACK-002: Research detects domain keywords."""
        from compound_task_decomposer import _deterministic_market_research

        result = _deterministic_market_research("health and fitness app")
        assert "health" in result["detected_niches"]

    def test_deterministic_research_default_niches(self):
        """CTD-TEST-FALLBACK-003: No keywords -> default niches provided."""
        from compound_task_decomposer import _deterministic_market_research

        result = _deterministic_market_research("something generic")
        assert len(result["detected_niches"]) >= 3

    def test_deterministic_niche_selection(self):
        """CTD-TEST-FALLBACK-004: Niche selection produces valid output."""
        from compound_task_decomposer import _deterministic_niche_selection

        research = {
            "deterministic_research": {
                "top_niches_ranked": [
                    {"niche": "saas", "score": 0.9, "rationale": "test"},
                    {"niche": "health", "score": 0.7, "rationale": "test2"},
                ],
            }
        }
        result = _deterministic_niche_selection("test query", research)
        assert result["selected_niche"] == "saas"
        assert result["confidence"] == 0.9
        assert "alternatives" in result

    def test_niche_selection_empty_research(self):
        """CTD-TEST-FALLBACK-005: Selection with no research -> default."""
        from compound_task_decomposer import _deterministic_niche_selection

        result = _deterministic_niche_selection("test", {})
        assert result["selected_niche"] == "saas"
        assert result["confidence"] > 0.0


class TestTrajectoryTracking:
    """Does RubixCube trajectory tracking work when available?

    Expected: When PathConfidenceRegistry is available, trajectory scores
    are recorded. When unavailable, graceful fallback to empty dict.
    """

    def test_trajectory_scores_populated(self):
        """CTD-TEST-TRAJ-001: Trajectory scores are dict after execution."""
        from compound_task_decomposer import (
            detect_compound_query,
            execute_prerequisite_phases,
        )

        decomposition = detect_compound_query(
            "research AI tool niches then build a dashboard app"
        )
        result = execute_prerequisite_phases(decomposition)
        assert isinstance(result.trajectory_scores, dict)

    def test_trajectory_init_graceful(self):
        """CTD-TEST-TRAJ-002: _init_trajectory_tracker is non-blocking."""
        from compound_task_decomposer import _init_trajectory_tracker

        # Should not raise even if bots module unavailable
        result = _init_trajectory_tracker()
        # Result is either PathConfidenceRegistry or None
        assert result is None or hasattr(result, "update")


# ===========================================================================
# CPV-TEST-001: Code Project Validator tests
# ===========================================================================


class TestCodeProjectValidation:
    """Does validate_code_project catch real issues?

    Expected: Valid projects pass. Empty projects fail.
    Syntax errors are caught. Missing required files are warned.
    """

    def test_valid_project_passes(self):
        """CPV-TEST-001: Valid project with all files passes."""
        from code_project_validator import validate_code_project

        files = {
            "index.html": (
                "<!DOCTYPE html><html><head><title>Test</title></head>"
                "<body>Hello</body></html>"
            ),
            "styles.css": "body { color: red; }",
            "app.js": "console.log('hello');",
            "README.md": "# Test Project\nA test.",
        }
        result = validate_code_project(files)
        assert result.valid is True
        assert result.files_checked == 4

    def test_empty_project_fails(self):
        """CPV-TEST-002: Empty project dict fails validation."""
        from code_project_validator import validate_code_project

        result = validate_code_project({})
        assert result.valid is False
        assert result.error_count >= 1

    def test_empty_file_detected(self):
        """CPV-TEST-003: Empty file content is caught."""
        from code_project_validator import validate_code_project

        files = {
            "index.html": "",
            "README.md": "# Test",
        }
        result = validate_code_project(files)
        assert result.valid is False
        errors = [i for i in result.issues if i.code == "CPV-EMPTY-002"]
        assert len(errors) >= 1

    def test_html_missing_tags_warned(self):
        """CPV-TEST-004: HTML without required tags produces warnings."""
        from code_project_validator import validate_code_project

        files = {
            "index.html": "<div>Just a div</div>",
            "README.md": "# Test",
        }
        result = validate_code_project(files)
        html_issues = [
            i for i in result.issues if i.file_path == "index.html"
        ]
        assert len(html_issues) > 0

    def test_python_syntax_error_caught(self):
        """CPV-TEST-005: Python syntax error is flagged as error."""
        from code_project_validator import validate_code_project

        files = {
            "server.py": "def broken(:\n    pass",
            "README.md": "# Test",
        }
        result = validate_code_project(files)
        py_errors = [
            i
            for i in result.issues
            if i.file_path == "server.py" and i.severity == "error"
        ]
        assert len(py_errors) >= 1

    def test_valid_python_passes(self):
        """CPV-TEST-006: Valid Python file passes."""
        from code_project_validator import validate_code_project

        files = {
            "server.py": "def hello():\n    return 'world'\n",
            "README.md": "# Test",
        }
        result = validate_code_project(files)
        py_errors = [
            i
            for i in result.issues
            if i.file_path == "server.py" and i.severity == "error"
        ]
        assert len(py_errors) == 0

    def test_missing_readme_warned(self):
        """CPV-TEST-007: Missing README.md produces warning."""
        from code_project_validator import validate_code_project

        files = {"index.html": "<!DOCTYPE html><html><head></head><body></body></html>"}
        result = validate_code_project(files)
        readme_issues = [
            i for i in result.issues if "README.md" in i.file_path
        ]
        assert len(readme_issues) >= 1

    def test_css_brace_mismatch_warned(self):
        """CPV-TEST-008: CSS brace mismatch produces warning."""
        from code_project_validator import validate_code_project

        files = {
            "styles.css": "body { color: red; ",  # missing close
            "README.md": "# Test",
        }
        result = validate_code_project(files)
        css_issues = [
            i
            for i in result.issues
            if i.file_path == "styles.css" and i.code == "CPV-CSS-001"
        ]
        assert len(css_issues) >= 1

    def test_js_bracket_mismatch_warned(self):
        """CPV-TEST-009: JS bracket mismatch produces warning."""
        from code_project_validator import validate_code_project

        # 4 openers ({, (, {, () vs 0 closers => difference of 4 > threshold
        files = {
            "app.js": "function a() { if (true) { console.log('x'",
            "README.md": "# Test",
        }
        result = validate_code_project(files)
        js_issues = [
            i
            for i in result.issues
            if i.file_path == "app.js" and i.code == "CPV-JS-001"
        ]
        assert len(js_issues) >= 1


# ===========================================================================
# CTD-WIRE-TEST-001: Integration wiring tests
# ===========================================================================


class TestForgeIntegration:
    """Does the forge pipeline handle compound queries without error?

    Expected: generate_deliverable_with_progress and
    generate_code_project_deliverable accept compound queries
    and produce output with CTD metadata.
    """

    def test_compound_task_decomposer_importable(self):
        """CTD-WIRE-TEST-001: Module is importable."""
        from compound_task_decomposer import (  # noqa: F401
            DecomposedPhase,
            DecompositionResult,
            PhaseType,
            detect_compound_query,
            execute_prerequisite_phases,
        )
        assert callable(detect_compound_query)
        assert callable(execute_prerequisite_phases)

    def test_code_project_validator_importable(self):
        """CPV-WIRE-TEST-001: Module is importable."""
        from code_project_validator import (  # noqa: F401
            ValidationIssue,
            ValidationResult,
            validate_code_project,
        )
        assert callable(validate_code_project)

    def test_forge_stream_imports_cleanly(self):
        """CTD-SSE-TEST-001: forge_stream module imports without error."""
        import forge_stream
        assert hasattr(forge_stream, "forge_stream_generator")

    def test_decomposition_result_dataclass(self):
        """CTD-WIRE-TEST-002: DecompositionResult is a valid dataclass."""
        from compound_task_decomposer import DecompositionResult

        r = DecompositionResult(
            is_compound=True,
            original_query="test",
        )
        assert r.is_compound is True
        assert r.original_query == "test"
        assert r.phases == []
        assert r.enriched_context == ""
        assert r.trajectory_scores == {}

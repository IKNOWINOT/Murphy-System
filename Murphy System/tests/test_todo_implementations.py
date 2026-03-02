"""
Tests for the implementations that replace TODO stubs across the system.

Covers:
- two_phase_orchestrator: intelligent gathering, learning from execution
- universal_control_plane: all 7 engine implementations
- inoni_business_automation: lead parsing, AI scoring, bug parsing
- form_intake/plan_decomposer: document extraction, parsing, goal analysis,
  dependency detection, assumptions, risks
"""

import sys
import os
import tempfile
import textwrap

# Ensure repo root and src are on the path.
_base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _base)
sys.path.insert(0, os.path.join(_base, 'src'))


# ============================================================================
# Two-Phase Orchestrator Tests
# ============================================================================

class TestInformationGatheringAgent:
    """Tests for the enhanced InformationGatheringAgent."""

    def _make_agent(self):
        from two_phase_orchestrator import InformationGatheringAgent
        return InformationGatheringAgent()

    def test_gather_returns_all_keys(self):
        agent = self._make_agent()
        info = agent.gather("Automate blog on WordPress daily", "publishing")
        for key in ('domain', 'request', 'platforms', 'content_source',
                     'schedule', 'approval_required', 'complexity',
                     'automation_type'):
            assert key in info, f"Missing key: {key}"

    def test_extract_platforms_wordpress(self):
        agent = self._make_agent()
        info = agent.gather("Publish to WordPress and Medium weekly", "publishing")
        assert 'wordpress' in info['platforms']
        assert 'medium' in info['platforms']

    def test_extract_platforms_expanded(self):
        agent = self._make_agent()
        info = agent.gather("Deploy to AWS using Docker and Kubernetes", "devops")
        assert 'aws' in info['platforms']
        assert 'docker' in info['platforms']
        assert 'kubernetes' in info['platforms']

    def test_extract_source_notion(self):
        agent = self._make_agent()
        info = agent.gather("Fetch content from Notion and publish", "publishing")
        assert info['content_source'] == 'notion'

    def test_extract_schedule_daily(self):
        agent = self._make_agent()
        info = agent.gather("Run this automation daily", "publishing")
        assert info['schedule'] == 'daily'

    def test_extract_schedule_weekly(self):
        agent = self._make_agent()
        info = agent.gather("Weekly sync to Slack", "publishing")
        assert info['schedule'] == 'weekly'

    def test_complexity_high_many_platforms(self):
        agent = self._make_agent()
        info = agent.gather("Use WordPress, Medium, Twitter, LinkedIn, Slack", "publishing")
        assert info['complexity'] == 'high'

    def test_complexity_medium(self):
        agent = self._make_agent()
        info = agent.gather("Post to WordPress and Medium", "publishing")
        assert info['complexity'] == 'medium'

    def test_complexity_low_single(self):
        agent = self._make_agent()
        info = agent.gather("Generate a report", "publishing")
        assert info['complexity'] == 'low'

    def test_automation_type_devops(self):
        agent = self._make_agent()
        info = agent.gather("Deploy to Docker", "devops")
        assert info['automation_type'] == 'command_system'

    def test_automation_type_hybrid_for_high_complexity(self):
        agent = self._make_agent()
        info = agent.gather("Complex enterprise multi-step pipeline", "publishing")
        assert info['automation_type'] == 'hybrid'


class TestLearningFromExecution:
    """Tests for ProductionExecutionOrchestrator._learn_from_execution."""

    def _make_orchestrator(self):
        from two_phase_orchestrator import TwoPhaseOrchestrator
        return TwoPhaseOrchestrator()

    def test_learning_records_success(self):
        orch = self._make_orchestrator()
        aid = orch.create_automation("Automate blog on WordPress", "publishing")
        result = orch.run_automation(aid)
        patterns = orch.phase2.learned_patterns.get(aid)
        assert patterns is not None
        assert patterns['total_runs'] == 1
        assert patterns['success_count'] == 1
        assert patterns['last_status'] == 'success'

    def test_learning_records_failure(self):
        from two_phase_orchestrator import ProductionExecutionOrchestrator
        prod = ProductionExecutionOrchestrator()
        prod._learn_from_execution('test-auto', {
            'status': 'failure',
            'steps': [
                {'agent': 'Fetcher', 'status': 'failed'},
                {'agent': 'Publisher', 'status': 'success'},
            ]
        })
        patterns = prod.learned_patterns['test-auto']
        assert patterns['failure_count'] == 1
        assert patterns['failed_agents']['Fetcher'] == 1

    def test_learning_accumulates_across_runs(self):
        from two_phase_orchestrator import ProductionExecutionOrchestrator
        prod = ProductionExecutionOrchestrator()
        for _ in range(3):
            prod._learn_from_execution('multi', {'status': 'success', 'steps': [{'status': 'success'}]})
        assert prod.learned_patterns['multi']['total_runs'] == 3
        assert prod.learned_patterns['multi']['avg_steps'] == 1.0


# ============================================================================
# Universal Control Plane Engine Tests
# ============================================================================

class TestSensorEngine:
    def _make(self):
        from universal_control_plane import SensorEngine, ActionType, Action
        engine = SensorEngine()
        engine.load()
        action = Action(
            action_id='t1', action_type=ActionType.READ_SENSOR,
            description='Read temp', parameters={'sensor_id': 'temp_1'},
            preconditions=[], postconditions=[], bound_artifacts=[]
        )
        return engine, action

    def test_sensor_returns_value(self):
        engine, action = self._make()
        result = engine.execute(action)
        assert 'value' in result
        assert isinstance(result['value'], float)
        assert result['sensor_id'] == 'temp_1'

    def test_sensor_consistent_readings(self):
        engine, action = self._make()
        r1 = engine.execute(action)
        r2 = engine.execute(action)
        assert r1['value'] == r2['value']


class TestActuatorEngine:
    def _make(self):
        from universal_control_plane import ActuatorEngine, ActionType, Action
        engine = ActuatorEngine()
        engine.load()
        action = Action(
            action_id='a1', action_type=ActionType.WRITE_ACTUATOR,
            description='Set HVAC', parameters={'actuator_id': 'hvac_1', 'command': 'set_72'},
            preconditions=[], postconditions=[], bound_artifacts=[]
        )
        return engine, action

    def test_actuator_returns_executed(self):
        engine, action = self._make()
        result = engine.execute(action)
        assert result['status'] == 'executed'
        assert result['command'] == 'set_72'

    def test_actuator_records_state(self):
        engine, action = self._make()
        engine.execute(action)
        assert 'hvac_1' in engine._state


class TestDatabaseEngine:
    def _make(self):
        from universal_control_plane import DatabaseEngine, ActionType, Action
        engine = DatabaseEngine()
        engine.load()
        return engine, ActionType, Action

    def test_insert_and_select(self):
        engine, AT, Action = self._make()
        ins = Action(
            action_id='ins', action_type=AT.QUERY_DATABASE,
            description='Insert', parameters={'query': 'INSERT', 'table': 'users', 'data': {'name': 'Alice'}},
            preconditions=[], postconditions=[], bound_artifacts=[]
        )
        engine.execute(ins)

        sel = Action(
            action_id='sel', action_type=AT.QUERY_DATABASE,
            description='Select', parameters={'query': 'SELECT * FROM users', 'table': 'users'},
            preconditions=[], postconditions=[], bound_artifacts=[]
        )
        result = engine.execute(sel)
        assert result['rows_affected'] == 1
        assert result['results'][0]['name'] == 'Alice'


class TestAPIEngine:
    def _make(self):
        from universal_control_plane import APIEngine, ActionType, Action
        engine = APIEngine()
        engine.load()
        action = Action(
            action_id='api1', action_type=ActionType.CALL_API,
            description='Call', parameters={'url': 'https://api.example.com', 'method': 'POST'},
            preconditions=[], postconditions=[], bound_artifacts=[]
        )
        return engine, action

    def test_api_returns_200(self):
        engine, action = self._make()
        result = engine.execute(action)
        assert result['status_code'] == 200

    def test_api_logs_call(self):
        engine, action = self._make()
        engine.execute(action)
        assert len(engine._call_log) == 1
        assert engine._call_log[0]['url'] == 'https://api.example.com'


class TestContentEngine:
    def _make(self):
        from universal_control_plane import ContentEngine, ActionType, Action
        engine = ContentEngine()
        engine.load()
        action = Action(
            action_id='c1', action_type=ActionType.GENERATE_CONTENT,
            description='Gen', parameters={'prompt': 'Murphy AI', 'type': 'blog_post'},
            preconditions=[], postconditions=[], bound_artifacts=[]
        )
        return engine, action

    def test_content_blog_post(self):
        engine, action = self._make()
        result = engine.execute(action)
        assert 'Murphy AI' in result['content']
        assert result['content_type'] == 'blog_post'
        assert result['word_count'] > 0

    def test_content_social_media(self):
        from universal_control_plane import ContentEngine, ActionType, Action
        engine = ContentEngine()
        engine.load()
        action = Action(
            action_id='s1', action_type=ActionType.GENERATE_CONTENT,
            description='Social', parameters={'prompt': 'Launch day', 'type': 'social_media'},
            preconditions=[], postconditions=[], bound_artifacts=[]
        )
        result = engine.execute(action)
        assert '🚀' in result['content']


class TestCommandEngine:
    def _make(self):
        from universal_control_plane import CommandEngine, ActionType, Action
        engine = CommandEngine()
        engine.load()
        action = Action(
            action_id='cmd1', action_type=ActionType.EXECUTE_COMMAND,
            description='Cmd', parameters={'command': 'echo hello'},
            preconditions=[], postconditions=[], bound_artifacts=[]
        )
        return engine, action

    def test_command_returns_zero(self):
        engine, action = self._make()
        result = engine.execute(action)
        assert result['exit_code'] == 0

    def test_command_logs(self):
        engine, action = self._make()
        engine.execute(action)
        assert len(engine._command_log) == 1


class TestAgentEngine:
    def _make(self):
        from universal_control_plane import AgentEngine, ActionType, Action
        engine = AgentEngine()
        engine.load()
        action = Action(
            action_id='ag1', action_type=ActionType.EXECUTE_COMMAND,  # will use generic path
            description='Research task',
            parameters={'agent_type': 'researcher', 'task': 'Find papers', 'agent_count': 2},
            preconditions=[], postconditions=[], bound_artifacts=[]
        )
        return engine, action

    def test_agent_spawns(self):
        engine, action = self._make()
        # AgentEngine doesn't validate action_type strictly; it accepts any action.
        result = engine.execute(action)
        assert result['agent_count'] == 2
        assert len(result['agents_spawned']) == 2


# ============================================================================
# Inoni Business Automation Tests
# ============================================================================

class TestLeadScoring:
    def test_high_fit_increases_score(self):
        from inoni_business_automation import SalesAutomationEngine
        engine = SalesAutomationEngine()
        score = engine._calculate_lead_score({
            'score': 0.7, 'fit': 'high', 'contact': 'a@b.com', 'source': 'github'
        })
        assert score > 0.7

    def test_low_fit_decreases_score(self):
        from inoni_business_automation import SalesAutomationEngine
        engine = SalesAutomationEngine()
        score = engine._calculate_lead_score({
            'score': 0.7, 'fit': 'low', 'contact': '', 'source': 'unknown'
        })
        assert score < 0.7

    def test_score_clamped_to_01(self):
        from inoni_business_automation import SalesAutomationEngine
        engine = SalesAutomationEngine()
        score = engine._calculate_lead_score({'score': 1.0, 'fit': 'high', 'contact': 'x', 'source': 'referral'})
        assert score <= 1.0
        score2 = engine._calculate_lead_score({'score': 0.0, 'fit': 'low', 'contact': '', 'source': ''})
        assert score2 >= 0.0


class TestLeadParsing:
    def test_parse_leads_fallback(self):
        from inoni_business_automation import SalesAutomationEngine
        engine = SalesAutomationEngine()
        leads = engine._parse_leads_from_result({'results': []})
        assert len(leads) >= 1
        assert leads[0]['company'] == 'Example Corp'

    def test_parse_leads_from_api_response(self):
        from inoni_business_automation import SalesAutomationEngine
        engine = SalesAutomationEngine()
        result = {
            'results': [
                {
                    'result': {
                        'response': {
                            'leads': [
                                {'company': 'Acme', 'contact': 'a@acme.com', 'source': 'linkedin', 'score': 0.9, 'fit': 'high'}
                            ]
                        }
                    }
                }
            ]
        }
        leads = engine._parse_leads_from_result(result)
        assert len(leads) == 1
        assert leads[0]['company'] == 'Acme'


class TestBugParsing:
    def test_parse_bugs_fallback(self):
        from inoni_business_automation import RDAutomationEngine
        engine = RDAutomationEngine()
        bugs = engine._parse_bugs_from_result({'results': []})
        assert len(bugs) >= 1
        assert bugs[0]['id'] == 'BUG-001'

    def test_parse_bugs_from_stdout(self):
        from inoni_business_automation import RDAutomationEngine
        engine = RDAutomationEngine()
        result = {
            'results': [
                {'result': {'stdout': 'ERROR: null pointer at line 42'}}
            ]
        }
        bugs = engine._parse_bugs_from_result(result)
        assert len(bugs) == 1
        assert 'null pointer' in bugs[0]['description']


# ============================================================================
# Plan Decomposer Tests
# ============================================================================

class TestPlanDecomposerExtractContent:
    def test_extract_text_file(self):
        from form_intake.plan_decomposer import PlanDecomposer
        pd = PlanDecomposer()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("# My Plan\n- Step 1\n- Step 2\n")
            f.flush()
            content = pd._extract_plan_content(f.name)
        os.unlink(f.name)
        assert 'My Plan' in content

    def test_extract_missing_file(self):
        from form_intake.plan_decomposer import PlanDecomposer
        pd = PlanDecomposer()
        assert pd._extract_plan_content('/nonexistent/path.txt') == ''


class TestPlanDecomposerParsePlan:
    def test_parse_markdown_headings(self):
        from form_intake.plan_decomposer import PlanDecomposer
        pd = PlanDecomposer()
        content = "# My Project\n## Phase 1\n- Design\n- Implement\n## Phase 2\n- Test"
        structure = pd._parse_plan_structure(content, "context")
        assert structure['title'] == 'My Project'
        assert len(structure['sections']) >= 2

    def test_parse_empty_content(self):
        from form_intake.plan_decomposer import PlanDecomposer
        pd = PlanDecomposer()
        structure = pd._parse_plan_structure("", "context")
        assert structure['title'] == 'context'


class TestPlanDecomposerGoalAnalysis:
    def test_analyze_goal_extracts_objectives(self):
        from form_intake.plan_decomposer import PlanDecomposer
        pd = PlanDecomposer()
        analysis = pd._analyze_goal("Build and deploy a new API", "software_development")
        assert 'build' in analysis['key_objectives']
        assert 'deploy' in analysis['key_objectives']

    def test_analyze_goal_domain_factors(self):
        from form_intake.plan_decomposer import PlanDecomposer
        pd = PlanDecomposer()
        analysis = pd._analyze_goal("Launch marketing campaign", "marketing_campaign")
        assert 'Audience reach' in analysis['success_factors']


class TestPlanDecomposerTaskGeneration:
    def test_generate_from_sections(self):
        from form_intake.plan_decomposer import PlanDecomposer
        pd = PlanDecomposer()
        from form_intake.plan_models import Task, TaskPriority, TaskStatus
        structure = {
            'sections': [
                {'heading': 'Phase 1', 'items': ['Design system', 'critical Review spec']}
            ]
        }
        tasks = pd._generate_tasks_from_structure(structure, 'moderate')
        assert len(tasks) == 2
        # 'critical' keyword should flag HIGH priority
        assert any(t.priority == TaskPriority.HIGH for t in tasks)

    def test_generate_fallback_minimal(self):
        from form_intake.plan_decomposer import PlanDecomposer
        pd = PlanDecomposer()
        tasks = pd._generate_tasks_from_structure({'sections': []}, 'minimal')
        assert len(tasks) == 5


class TestPlanDecomposerDependencies:
    def test_sequential_fallback(self):
        from form_intake.plan_decomposer import PlanDecomposer
        pd = PlanDecomposer()
        from form_intake.plan_models import Task, TaskPriority, TaskStatus
        tasks = [
            Task(task_id='t1', title='A', description='', priority=TaskPriority.MEDIUM, status=TaskStatus.PENDING, deliverables=['X']),
            Task(task_id='t2', title='B', description='', priority=TaskPriority.MEDIUM, status=TaskStatus.PENDING, deliverables=['Y']),
        ]
        deps = pd._identify_dependencies(tasks)
        assert len(deps) >= 1


class TestPlanDecomposerAssumptionsRisks:
    def test_assumptions_include_baseline(self):
        from form_intake.plan_decomposer import PlanDecomposer
        pd = PlanDecomposer()
        assumptions = pd._identify_assumptions({'challenges': []}, [])
        assert 'Resources are available as planned' in assumptions

    def test_risks_low_tolerance_extra(self):
        from form_intake.plan_decomposer import PlanDecomposer
        pd = PlanDecomposer()
        risks = pd._identify_risks({'challenges': []}, [], 'low')
        assert any('personnel' in r.lower() for r in risks)

    def test_risks_from_challenges(self):
        from form_intake.plan_decomposer import PlanDecomposer
        pd = PlanDecomposer()
        risks = pd._identify_risks({'challenges': ['Legacy system compatibility']}, [], 'medium')
        assert any('Legacy' in r for r in risks)

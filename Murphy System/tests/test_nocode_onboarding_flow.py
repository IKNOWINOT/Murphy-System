"""
Test Suite: No-Code Workflow Terminal + Onboarding Flow + IP + Credentials
============================================================================
Comprehensive tests validating the full no-code builder experience including:
- Librarian terminal conversation flow
- Agent monitoring dashboard
- Onboarding flow with org chart
- IP classification and trade secret protection
- Credential profiles and automation metrics
- End-to-end user journey from onboarding to workflow builder
"""

import pytest
import json

# ====================== IMPORTS ======================

from src.nocode_workflow_terminal import (
    NoCodeWorkflowTerminal,
    ConversationState,
    StepVisibility,
    WorkflowStep,
    AgentAssignment,
    LibrarianSession,
)

from src.agent_monitor_dashboard import (
    AgentMonitorDashboard,
    AgentState,
    MonitoringMode,
    MonitoredAgent,
    DashboardSnapshot,
)

from src.onboarding_flow import (
    OnboardingFlow,
    CorporateOrgChart,
    OnboardingPhase,
    PositionLevel,
    DepartmentType,
    OrgPosition,
    OnboardingQuestion,
    ShadowAgentProfile,
    OnboardingSession,
)

from src.ip_classification_engine import (
    IPClassificationEngine,
    IPClassification,
    ProtectionLevel,
    LicenseType,
    IPAsset,
    License,
    TradeSecretRecord,
)

from src.credential_profile_system import (
    CredentialProfileSystem,
    ProfileTier,
    InteractionType,
    CredentialProfile,
    InteractionRecord,
    AutomationMetric,
)


# ====================== NOCODE WORKFLOW TERMINAL TESTS ======================


class TestNoCodeWorkflowTerminal:
    """Tests for the Librarian-powered no-code workflow terminal."""

    def test_create_session(self):
        """Session creation returns valid session with greeting."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        assert session is not None
        assert session.session_id
        assert session.state == ConversationState.GREETING
        assert len(session.conversation_history) == 1
        assert session.conversation_history[0].role == "librarian"
        assert "Librarian" in session.conversation_history[0].message

    def test_session_persistence(self):
        """Sessions are persisted and retrievable."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        retrieved = terminal.get_session(session.session_id)
        assert retrieved is not None
        assert retrieved.session_id == session.session_id

    def test_describe_data_processing_workflow(self):
        """Describing data processing creates appropriate steps."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        result = terminal.send_message(
            session.session_id,
            "I need to process CSV files and send email notifications when done"
        )
        assert result["session_id"] == session.session_id
        assert len(result["steps_created"]) >= 2
        assert result["state"] == "building_steps"
        step_types = [s["name"] for s in result["steps_created"]]
        assert any("Data Processing" in s or "Notification" in s for s in step_types)

    def test_describe_monitoring_workflow(self):
        """Describing monitoring creates monitoring steps."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        result = terminal.send_message(
            session.session_id,
            "Monitor our API endpoints and alert on failures"
        )
        assert len(result["steps_created"]) >= 1
        assert result["state"] == "building_steps"

    def test_agents_assigned_to_steps(self):
        """Each step gets an agent assigned."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        result = terminal.send_message(
            session.session_id,
            "Set up a data pipeline with API integration"
        )
        assert len(result["agent_status"]) >= 1
        for agent in result["agent_status"]:
            assert agent["agent_id"]
            assert agent["step_id"]
            assert agent["monitoring_type"] in ["active", "passive"]

    def test_add_more_steps(self):
        """Can add more steps in building phase."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        # Initial description
        terminal.send_message(session.session_id, "I need data processing")
        initial_count = len(session.steps)
        # Add more
        result = terminal.send_message(session.session_id, "Also add notification alerts")
        assert len(session.steps) > initial_count

    def test_finalize_workflow(self):
        """Finalizing marks steps as validated and agents as active."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(session.session_id, "Process data from API endpoints")
        result = terminal.send_message(session.session_id, "finalize")
        assert session.state == ConversationState.COMPLETED
        for step in session.steps:
            assert step.visibility == StepVisibility.VALIDATED
        for agent in session.agent_assignments:
            assert agent.status == "active"

    def test_compile_workflow(self):
        """Compiled workflow has nodes and edges."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(session.session_id, "Build a deployment pipeline with security checks")
        compiled = terminal.compile_workflow(session.session_id)
        assert compiled is not None
        assert compiled["workflow_id"] == session.session_id
        assert len(compiled["nodes"]) >= 1
        assert "agents" in compiled

    def test_review_state(self):
        """Review shows workflow and agent details."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(session.session_id, "Data processing workflow")
        result = terminal.send_message(session.session_id, "review the workflow")
        assert "Review" in result["message"] or "review" in result["message"].lower()

    def test_agent_drill_down(self):
        """Can drill down into specific agent details."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(session.session_id, "Monitor API endpoints")
        if session.agent_assignments:
            agent_id = session.agent_assignments[0].agent_id
            detail = terminal.get_agent_detail(session.session_id, agent_id)
            assert detail is not None
            assert detail["agent"]["agent_id"] == agent_id
            assert "monitored_step" in detail

    def test_unclear_description_asks_clarification(self):
        """Unclear descriptions ask for clarification."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        result = terminal.send_message(session.session_id, "help me with something")
        assert session.state == ConversationState.GATHERING_REQUIREMENTS

    def test_list_sessions(self):
        """Can list all active sessions."""
        terminal = NoCodeWorkflowTerminal()
        terminal.create_session()
        terminal.create_session()
        sessions = terminal.list_sessions()
        assert len(sessions) == 2

    def test_workflow_snapshot(self):
        """Workflow snapshot shows current state."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(session.session_id, "Schedule daily reports")
        result = terminal.send_message(session.session_id, "review")
        snapshot = result.get("workflow_snapshot", {})
        assert snapshot["step_count"] >= 1

    def test_session_to_dict(self):
        """Session serializes to dict correctly."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(session.session_id, "Data pipeline with notifications")
        d = session.to_dict()
        assert d["session_id"] == session.session_id
        assert d["state"] in [s.value for s in ConversationState]
        assert isinstance(d["steps"], list)

    def test_completed_session_rejects_new_messages(self):
        """Completed sessions don't accept new workflow messages."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(session.session_id, "Data processing workflow")
        terminal.send_message(session.session_id, "finalize")
        result = terminal.send_message(session.session_id, "add more steps")
        assert "finalized" in result["message"].lower() or "new session" in result["message"].lower()

    def test_multiple_intents_in_one_message(self):
        """Multiple intents in one message create multiple steps."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        result = terminal.send_message(
            session.session_id,
            "Process data, send notifications, and deploy to production with security checks"
        )
        assert len(result["steps_created"]) >= 3


# ====================== AGENT MONITOR DASHBOARD TESTS ======================


class TestAgentMonitorDashboard:
    """Tests for the agent monitoring dashboard."""

    def test_register_agent(self):
        """Can register an agent for monitoring."""
        dashboard = AgentMonitorDashboard()
        agent = dashboard.register_agent(
            name="Test Agent",
            role="monitor",
            monitoring_mode="active",
            targets=["api-endpoint"],
            metrics=["latency", "errors"],
        )
        assert agent.agent_id
        assert agent.name == "Test Agent"
        assert agent.monitoring_mode == MonitoringMode.ACTIVE
        assert len(agent.activity_log) == 1  # Registration activity

    def test_update_state(self):
        """Can update agent state."""
        dashboard = AgentMonitorDashboard()
        agent = dashboard.register_agent(name="State Agent")
        updated = dashboard.update_state(agent.agent_id, "monitoring")
        assert updated.state == AgentState.MONITORING

    def test_record_heartbeat(self):
        """Can record heartbeats with metrics."""
        dashboard = AgentMonitorDashboard()
        agent = dashboard.register_agent(name="Heartbeat Agent")
        result = dashboard.record_heartbeat(agent.agent_id, {"cpu": 45.0})
        assert result is True

    def test_record_alert(self):
        """Can record alerts from agents."""
        dashboard = AgentMonitorDashboard()
        agent = dashboard.register_agent(name="Alert Agent")
        result = dashboard.record_alert(agent.agent_id, "api-service", "High latency detected")
        assert result is True
        assert agent.alert_count == 1
        assert agent.state == AgentState.ALERTING

    def test_get_agent_detail(self):
        """Can drill down into agent details."""
        dashboard = AgentMonitorDashboard()
        agent = dashboard.register_agent(
            name="Detail Agent",
            role="validator",
            targets=["database"],
        )
        detail = dashboard.get_agent_detail(agent.agent_id)
        assert detail is not None
        assert detail["name"] == "Detail Agent"
        assert detail["role"] == "validator"

    def test_get_agent_activity(self):
        """Can get agent activity log."""
        dashboard = AgentMonitorDashboard()
        agent = dashboard.register_agent(name="Activity Agent")
        dashboard.update_state(agent.agent_id, "monitoring")
        dashboard.record_alert(agent.agent_id, "service", "Issue found")
        activities = dashboard.get_agent_activity(agent.agent_id)
        assert len(activities) >= 3  # register + state_change + alert

    def test_dashboard_snapshot(self):
        """Dashboard snapshot shows aggregate data."""
        dashboard = AgentMonitorDashboard()
        dashboard.register_agent(name="Agent 1", role="monitor")
        dashboard.register_agent(name="Agent 2", role="validator")
        dashboard.register_agent(name="Agent 3", role="monitor")
        snapshot = dashboard.get_dashboard_snapshot()
        assert snapshot.total_agents == 3
        assert snapshot.agents_by_role.get("monitor") == 2
        assert snapshot.agents_by_role.get("validator") == 1

    def test_list_agents_with_filter(self):
        """Can filter agents by state or role."""
        dashboard = AgentMonitorDashboard()
        a1 = dashboard.register_agent(name="Agent 1", role="monitor")
        a2 = dashboard.register_agent(name="Agent 2", role="validator")
        dashboard.update_state(a1.agent_id, "monitoring")
        monitors = dashboard.list_agents(role_filter="monitor")
        assert len(monitors) == 1
        assert monitors[0]["role"] == "monitor"

    def test_deregister_agent(self):
        """Can deregister an agent."""
        dashboard = AgentMonitorDashboard()
        agent = dashboard.register_agent(name="Temp Agent")
        result = dashboard.deregister_agent(agent.agent_id)
        assert result is True
        assert agent.state == AgentState.TERMINATED

    def test_snapshot_to_dict(self):
        """Snapshot serializes correctly."""
        dashboard = AgentMonitorDashboard()
        dashboard.register_agent(name="Snap Agent")
        snapshot = dashboard.get_dashboard_snapshot()
        d = snapshot.to_dict()
        assert d["total_agents"] == 1
        assert isinstance(d["agent_summaries"], list)


# ====================== ONBOARDING FLOW TESTS ======================


class TestCorporateOrgChart:
    """Tests for the corporate org chart."""

    def test_setup_default_org(self):
        """Default org chart creates expected positions."""
        org = CorporateOrgChart()
        positions = org.setup_default_org()
        assert len(positions) >= 10
        titles = [p.title for p in positions]
        assert "Chief Executive Officer" in titles
        assert "Chief Technology Officer" in titles
        assert "VP of Engineering" in titles
        assert "Software Engineer" in titles

    def test_reporting_chains(self):
        """Reporting chains are established correctly."""
        org = CorporateOrgChart()
        org.setup_default_org()
        # Find CEO
        ceo = None
        for pos in org.positions.values():
            if pos.title == "Chief Executive Officer":
                ceo = pos
                break
        assert ceo is not None
        assert ceo.reports_to is None  # CEO has no manager
        assert len(ceo.direct_reports) >= 3  # CTO, COO, CFO

    def test_add_position(self):
        """Can add custom positions."""
        org = CorporateOrgChart()
        pos = org.add_position(
            title="Data Scientist",
            level="individual_contributor",
            department="engineering",
            responsibilities=["ML models", "Data analysis"],
        )
        assert pos.title == "Data Scientist"
        assert pos.level == PositionLevel.INDIVIDUAL_CONTRIBUTOR

    def test_get_org_chart(self):
        """Org chart returns hierarchical structure."""
        org = CorporateOrgChart()
        org.setup_default_org()
        chart = org.get_org_chart()
        assert chart["ip_classification"] == "business_ip"
        assert chart["total_positions"] >= 10
        assert len(chart["hierarchy"]) >= 1

    def test_department_positions(self):
        """Can filter positions by department."""
        org = CorporateOrgChart()
        org.setup_default_org()
        eng = org.get_department_positions("engineering")
        assert len(eng) >= 3  # CTO, VP Eng, Eng Manager, SW Eng

    def test_agentic_positions(self):
        """All positions have agentic shadow config."""
        org = CorporateOrgChart()
        org.setup_default_org()
        for pos in org.positions.values():
            assert pos.is_agentic is True
            assert "monitoring_level" in pos.shadow_agent_config


class TestOnboardingFlow:
    """Tests for the onboarding flow."""

    def test_initialize_org(self):
        """Initializing org returns positions and chart."""
        flow = OnboardingFlow()
        result = flow.initialize_org()
        assert result["positions_created"] >= 10
        assert "org_chart" in result

    def test_start_onboarding(self):
        """Starting onboarding creates a session."""
        flow = OnboardingFlow()
        session = flow.start_onboarding("Jane Doe", "jane@example.com")
        assert session.employee_name == "Jane Doe"
        assert session.phase == OnboardingPhase.INDIVIDUAL_ONBOARDING

    def test_get_questions(self):
        """Onboarding questions are returned sorted by order."""
        flow = OnboardingFlow()
        session = flow.start_onboarding("John Doe", "john@example.com")
        questions = flow.get_questions(session.session_id)
        assert len(questions) >= 10
        orders = [q["order"] for q in questions]
        assert orders == sorted(orders)

    def test_answer_question(self):
        """Can answer onboarding questions."""
        flow = OnboardingFlow()
        session = flow.start_onboarding("Alice", "alice@example.com")
        questions = flow.get_questions(session.session_id)
        result = flow.answer_question(
            session.session_id,
            questions[0]["question_id"],
            "Alice Johnson"
        )
        assert result["questions_answered"] == 1

    def test_assign_shadow_agent(self):
        """Shadow agent is assigned with employee IP classification."""
        flow = OnboardingFlow()
        session = flow.start_onboarding("Bob", "bob@example.com")
        result = flow.assign_shadow_agent(session.session_id)
        assert result["ip_classification"] == "employee_ip"
        assert result["shadow_agent"]["shadow_id"].startswith("shadow-")
        assert session.shadow_agent is not None

    def test_transition_to_workflow_builder(self):
        """Transition produces builder context."""
        flow = OnboardingFlow()
        flow.initialize_org()
        session = flow.start_onboarding("Carol", "carol@example.com")
        flow.assign_shadow_agent(session.session_id)
        result = flow.transition_to_workflow_builder(session.session_id)
        assert "builder_context" in result
        assert result["builder_context"]["employee_name"] == "Carol"
        assert session.phase == OnboardingPhase.COMPLETED

    def test_shadow_agent_with_position(self):
        """Shadow agent inherits capabilities from position."""
        flow = OnboardingFlow()
        positions = flow.initialize_org()
        # Find first position
        first_pos_id = list(flow.org_chart.positions.keys())[0]
        session = flow.start_onboarding("Dave", "dave@example.com")
        result = flow.assign_shadow_agent(session.session_id, first_pos_id)
        assert result["shadow_agent"]["position_id"] == first_pos_id

    def test_infer_capabilities_from_answers(self):
        """Capabilities are inferred from tool answers."""
        flow = OnboardingFlow()
        session = flow.start_onboarding("Eve", "eve@example.com")
        questions = flow.get_questions(session.session_id)
        # Find tools question
        for q in questions:
            if q["category"] == "tools":
                flow.answer_question(session.session_id, q["question_id"], "GitHub, Slack, Jira")
                break
        result = flow.assign_shadow_agent(session.session_id)
        capabilities = result["shadow_agent"]["capabilities"]
        assert "code_management" in capabilities or "communication_automation" in capabilities

    def test_list_sessions(self):
        """Can list all onboarding sessions."""
        flow = OnboardingFlow()
        flow.start_onboarding("A", "a@x.com")
        flow.start_onboarding("B", "b@x.com")
        sessions = flow.list_sessions()
        assert len(sessions) == 2


# ====================== IP CLASSIFICATION TESTS ======================


class TestIPClassificationEngine:
    """Tests for IP classification and trade secret protection."""

    def test_register_employee_ip(self):
        """Employee IP is registered with correct classification."""
        engine = IPClassificationEngine()
        asset = engine.register_employee_ip(
            employee_id="emp-001",
            shadow_agent_id="shadow-001",
            name="Employee Work Patterns",
            description="Shadow agent learning data",
        )
        assert asset.classification == IPClassification.EMPLOYEE_IP
        assert asset.protection_level == ProtectionLevel.CONFIDENTIAL
        assert asset.owner_type == "employee"

    def test_register_business_ip(self):
        """Business IP is registered with correct classification."""
        engine = IPClassificationEngine()
        asset = engine.register_business_ip(
            business_id="biz-001",
            name="Org Chart Interactions",
            description="How departments interact",
        )
        assert asset.classification == IPClassification.BUSINESS_IP
        assert asset.protection_level == ProtectionLevel.RESTRICTED
        assert asset.owner_type == "business"

    def test_register_system_ip(self):
        """System IP is auto-licensed to Murphy."""
        engine = IPClassificationEngine()
        asset = engine.register_system_metrics_ip(
            name="Automation Metrics Q1",
            description="Aggregated automation performance",
        )
        assert asset.classification == IPClassification.SYSTEM_IP
        # Should have auto-created a license
        licenses = engine.list_licenses(asset.asset_id)
        assert len(licenses) >= 1
        assert licenses[0]["licensee"] == "murphy_system"
        assert licenses[0]["license_type"] == "system_license"

    def test_trade_secret_designation(self):
        """Assets can be designated as trade secrets."""
        engine = IPClassificationEngine()
        asset = engine.register_business_ip(
            business_id="biz-001",
            name="Secret Algorithm",
            description="Proprietary process",
            is_trade_secret=True,
        )
        assert asset.is_trade_secret is True
        assert asset.protection_level == ProtectionLevel.TRADE_SECRET
        secrets = engine.list_trade_secrets()
        assert len(secrets) >= 1

    def test_trade_secret_access_control(self):
        """Trade secrets restrict access to authorized users only."""
        engine = IPClassificationEngine()
        asset = engine.register_asset(
            name="Secret Process",
            description="Trade secret data",
            classification="trade_secret",
            owner_id="owner-001",
            owner_type="business",
            is_trade_secret=True,
        )
        # Owner has access
        access = engine.check_access(asset.asset_id, "owner-001")
        assert access["allowed"] is True
        # Random user does NOT have access
        access = engine.check_access(asset.asset_id, "random-user")
        assert access["allowed"] is False
        assert "restricted" in access["reason"].lower()

    def test_licensed_access(self):
        """Licensed users can access assets."""
        engine = IPClassificationEngine()
        asset = engine.register_business_ip(
            business_id="biz-001",
            name="Process Data",
            description="Business process",
        )
        engine.create_license(
            asset_id=asset.asset_id,
            license_type="non_exclusive",
            licensor="biz-001",
            licensee="partner-001",
            scope="Read access",
        )
        access = engine.check_access(asset.asset_id, "partner-001")
        assert access["allowed"] is True

    def test_ip_summary(self):
        """IP summary shows classification breakdown."""
        engine = IPClassificationEngine()
        engine.register_employee_ip("e1", "s1", "Work Patterns", "desc")
        engine.register_business_ip("b1", "Org Chart", "desc")
        engine.register_system_metrics_ip("Metrics", "desc")
        summary = engine.get_ip_summary()
        assert summary["total_assets"] == 3
        assert summary["by_classification"]["employee_ip"] == 1
        assert summary["by_classification"]["business_ip"] == 1
        assert summary["by_classification"]["system_ip"] == 1

    def test_access_logging(self):
        """Access attempts are logged."""
        engine = IPClassificationEngine()
        asset = engine.register_employee_ip("e1", "s1", "Data", "desc")
        engine.check_access(asset.asset_id, "e1")
        engine.check_access(asset.asset_id, "other")
        full_asset = engine.get_asset(asset.asset_id)
        assert full_asset["access_log_count"] >= 2

    def test_designate_existing_asset_as_trade_secret(self):
        """Can designate an existing asset as trade secret."""
        engine = IPClassificationEngine()
        asset = engine.register_business_ip("b1", "Regular Data", "desc")
        assert asset.is_trade_secret is False
        record = engine.designate_trade_secret(
            asset.asset_id, "Strategic importance", "admin"
        )
        assert record is not None
        assert asset.is_trade_secret is True
        assert asset.protection_level == ProtectionLevel.TRADE_SECRET


# ====================== CREDENTIAL PROFILE TESTS ======================


class TestCredentialProfileSystem:
    """Tests for HITL credential profiles and automation metrics."""

    def test_create_profile(self):
        """Can create a credential profile."""
        system = CredentialProfileSystem()
        profile = system.create_profile("user-001", "Jane Doe", "engineer")
        assert profile.user_id == "user-001"
        assert profile.tier == ProfileTier.NEW
        assert profile.automation_trust_score == 0.5

    def test_deduplicate_profile(self):
        """Creating profile for same user returns existing."""
        system = CredentialProfileSystem()
        p1 = system.create_profile("user-001", "Jane Doe", "engineer")
        p2 = system.create_profile("user-001", "Jane Doe", "engineer")
        assert p1.profile_id == p2.profile_id

    def test_record_interaction(self):
        """Can record HITL interactions."""
        system = CredentialProfileSystem()
        profile = system.create_profile("user-001", "Jane", "engineer")
        result = system.record_interaction(
            profile.profile_id,
            interaction_type="approval",
            context="deploy-v2",
            decision="approved",
            confidence_before=0.7,
            confidence_after=0.9,
            response_time_ms=1500.0,
        )
        assert result is not None
        assert profile.total_approvals == 1

    def test_tier_progression(self):
        """Profile tier progresses with interaction count."""
        system = CredentialProfileSystem()
        profile = system.create_profile("user-001", "Jane", "engineer")
        # Record 10 interactions to reach LEARNING
        for i in range(10):
            system.record_interaction(
                profile.profile_id, "approval", f"task-{i}",
                response_time_ms=1000.0,
            )
        assert profile.tier == ProfileTier.LEARNING

    def test_trust_score_updates(self):
        """Trust score increases with approvals."""
        system = CredentialProfileSystem()
        profile = system.create_profile("user-001", "Jane", "engineer")
        for i in range(20):
            system.record_interaction(
                profile.profile_id, "approval", f"task-{i}",
            )
        assert profile.automation_trust_score > 0.5  # Higher than initial

    def test_trust_score_decreases_with_rejections(self):
        """Trust score decreases with rejections."""
        system = CredentialProfileSystem()
        profile = system.create_profile("user-001", "Jane", "engineer")
        for i in range(20):
            system.record_interaction(
                profile.profile_id, "rejection", f"task-{i}",
            )
        assert profile.automation_trust_score < 0.5  # Lower than initial

    def test_record_metric(self):
        """Can record automation metrics."""
        system = CredentialProfileSystem()
        profile = system.create_profile("user-001", "Jane", "engineer")
        result = system.record_metric(
            profile.profile_id,
            metric_name="workflow_completion_time",
            value=45.5,
            unit="seconds",
        )
        assert result is not None
        assert result["metric_name"] == "workflow_completion_time"

    def test_optimal_automation_metrics(self):
        """System-level metrics are computed correctly."""
        system = CredentialProfileSystem()
        p1 = system.create_profile("user-001", "Jane", "engineer")
        p2 = system.create_profile("user-002", "Bob", "manager")
        for i in range(5):
            system.record_interaction(p1.profile_id, "approval", response_time_ms=1000.0)
            system.record_interaction(p2.profile_id, "approval", response_time_ms=2000.0)
        metrics = system.get_optimal_automation_metrics()
        assert metrics["total_profiles"] == 2
        assert metrics["total_interactions"] == 10
        assert metrics["ip_classification"] == "system_ip"
        assert "optimal_thresholds" in metrics

    def test_get_profile_by_user(self):
        """Can retrieve profile by user ID."""
        system = CredentialProfileSystem()
        system.create_profile("user-001", "Jane", "engineer")
        profile = system.get_profile_by_user("user-001")
        assert profile is not None
        assert profile["user_id"] == "user-001"

    def test_list_profiles_with_filter(self):
        """Can filter profiles by tier."""
        system = CredentialProfileSystem()
        p1 = system.create_profile("user-001", "Jane", "engineer")
        p2 = system.create_profile("user-002", "Bob", "manager")
        for i in range(10):
            system.record_interaction(p1.profile_id, "approval")
        new_profiles = system.list_profiles(tier_filter="new")
        learning_profiles = system.list_profiles(tier_filter="learning")
        assert len(new_profiles) == 1
        assert len(learning_profiles) == 1


# ====================== END-TO-END FLOW TESTS ======================


class TestEndToEndOnboardingToBuilder:
    """Test the complete flow from onboarding through to workflow builder."""

    def test_full_onboarding_to_builder_flow(self):
        """Complete flow: org setup → onboard → shadow agent → workflow builder."""
        # Step 1: Initialize org chart
        flow = OnboardingFlow()
        org_result = flow.initialize_org()
        assert org_result["positions_created"] >= 10

        # Step 2: Start onboarding
        session = flow.start_onboarding("Alex Smith", "alex@company.com")
        assert session.phase == OnboardingPhase.INDIVIDUAL_ONBOARDING

        # Step 3: Answer questions
        questions = flow.get_questions(session.session_id)
        for q in questions[:3]:  # Answer first 3
            flow.answer_question(session.session_id, q["question_id"], "Test answer")

        # Step 4: Assign shadow agent with position
        first_pos_id = list(flow.org_chart.positions.keys())[0]
        shadow_result = flow.assign_shadow_agent(session.session_id, first_pos_id)
        assert shadow_result["ip_classification"] == "employee_ip"

        # Step 5: Transition to workflow builder
        transition = flow.transition_to_workflow_builder(session.session_id)
        assert "builder_context" in transition
        assert transition["builder_context"]["shadow_agent_id"] is not None

        # Step 6: Create workflow terminal session
        terminal = NoCodeWorkflowTerminal()
        wf_session = terminal.create_session()
        assert wf_session.state == ConversationState.GREETING

        # Step 7: Build workflow based on position
        result = terminal.send_message(
            wf_session.session_id,
            "I need to monitor API endpoints and send notifications on failures"
        )
        assert len(result["steps_created"]) >= 1
        assert len(result["agent_status"]) >= 1

        # Step 8: Finalize
        terminal.send_message(wf_session.session_id, "finalize")
        assert wf_session.state == ConversationState.COMPLETED

    def test_ip_tracking_through_flow(self):
        """IP is properly classified through the complete flow."""
        # Setup
        flow = OnboardingFlow()
        flow.initialize_org()
        ip_engine = IPClassificationEngine()

        # Onboard employee
        session = flow.start_onboarding("Maya", "maya@co.com")
        flow.assign_shadow_agent(session.session_id)

        # Register IPs
        emp_ip = ip_engine.register_employee_ip(
            session.session_id,
            session.shadow_agent.shadow_id,
            "Maya's Work Patterns",
            "Learning data from Maya's shadow agent",
        )
        biz_ip = ip_engine.register_business_ip(
            "org-001",
            "Department Interactions",
            "How engineering interacts with product",
            is_trade_secret=True,
        )
        sys_ip = ip_engine.register_system_metrics_ip(
            "Automation Metrics",
            "Aggregated performance data",
        )

        # Verify classifications
        assert emp_ip.classification == IPClassification.EMPLOYEE_IP
        assert biz_ip.classification == IPClassification.BUSINESS_IP
        assert biz_ip.is_trade_secret is True
        assert sys_ip.classification == IPClassification.SYSTEM_IP

        # Verify system license
        licenses = ip_engine.list_licenses(sys_ip.asset_id)
        assert any(l["licensee"] == "murphy_system" for l in licenses)

    def test_credential_tracking_through_flow(self):
        """Credential profiles track through agent monitoring."""
        cred_system = CredentialProfileSystem()
        dashboard = AgentMonitorDashboard()

        # Create user profile
        profile = cred_system.create_profile("user-alex", "Alex", "engineer")

        # Register monitoring agent
        agent = dashboard.register_agent(
            name="Alex's Workflow Monitor",
            role="monitor",
            monitoring_mode="active",
        )

        # Record interactions
        for i in range(5):
            cred_system.record_interaction(
                profile.profile_id,
                "approval",
                f"workflow-step-{i}",
                response_time_ms=800.0,
            )
            dashboard.record_heartbeat(agent.agent_id, {"step": i})

        # Check results
        assert profile.total_approvals == 5
        assert profile.tier == ProfileTier.NEW  # 5 interactions; LEARNING requires >=10
        assert dashboard.get_agent_detail(agent.agent_id) is not None

        # Optimal metrics
        metrics = cred_system.get_optimal_automation_metrics()
        assert metrics["total_profiles"] == 1
        assert metrics["total_interactions"] == 5

    def test_agent_dashboard_integration(self):
        """Agent dashboard tracks agents from workflow terminal."""
        terminal = NoCodeWorkflowTerminal()
        dashboard = AgentMonitorDashboard()

        # Create workflow with agents
        session = terminal.create_session()
        terminal.send_message(
            session.session_id,
            "Build a data pipeline with security scanning"
        )

        # Register terminal agents on dashboard
        for agent_assign in session.agent_assignments:
            agent = dashboard.register_agent(
                name=f"WF Agent {agent_assign.agent_id}",
                role=agent_assign.agent_role,
                monitoring_mode=agent_assign.monitoring_type,
                metrics=agent_assign.metrics_tracked,
            )
            dashboard.update_state(agent.agent_id, "monitoring")

        # Verify dashboard
        snapshot = dashboard.get_dashboard_snapshot()
        assert snapshot.total_agents >= 1
        assert "monitoring" in snapshot.agents_by_state


# ====================== GAP CLOSURE VALIDATION ======================


class TestGapClosure:
    """Tests that validate gaps are being closed."""

    def test_gap_librarian_terminal_exists(self):
        """GAP: No-code workflow builder has a conversational terminal."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        assert "Librarian" in session.conversation_history[0].message

    def test_gap_real_time_configuration(self):
        """GAP: Real-time configuration from user input with inference."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        result = terminal.send_message(
            session.session_id,
            "I need a data processing pipeline that monitors for errors"
        )
        assert len(result["inferences"]) >= 1
        assert len(result["steps_created"]) >= 1

    def test_gap_step_visibility(self):
        """GAP: Each step is visible as it's being created."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        result = terminal.send_message(session.session_id, "Process data from API")
        for step in result["steps_created"]:
            assert step["visibility"] in ["creating", "configured", "agent_assigned", "monitoring_active", "validated"]

    def test_gap_agent_monitoring_visibility(self):
        """GAP: Agents are visible with their monitoring config."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        result = terminal.send_message(session.session_id, "Monitor our servers")
        for agent in result["agent_status"]:
            assert "agent_id" in agent
            assert "monitoring_type" in agent
            assert "metrics_tracked" in agent

    def test_gap_agent_drill_down(self):
        """GAP: Can look at what any agent is doing at any point."""
        terminal = NoCodeWorkflowTerminal()
        session = terminal.create_session()
        terminal.send_message(session.session_id, "Data pipeline with notifications")
        for agent in session.agent_assignments:
            detail = terminal.get_agent_detail(session.session_id, agent.agent_id)
            assert detail is not None
            assert "activity_log" in detail

    def test_gap_onboarding_to_builder_transition(self):
        """GAP: Onboarding naturally transitions to no-code builder."""
        flow = OnboardingFlow()
        flow.initialize_org()
        session = flow.start_onboarding("Test User", "test@co.com")
        flow.assign_shadow_agent(session.session_id)
        result = flow.transition_to_workflow_builder(session.session_id)
        assert "builder_context" in result
        assert result["phase"] == "workflow_builder_transition"

    def test_gap_org_chart_positions(self):
        """GAP: Agentic corporate org chart positions are provided."""
        org = CorporateOrgChart()
        org.setup_default_org()
        positions = org.list_positions()
        assert len(positions) >= 10
        for pos in positions:
            assert pos["is_agentic"] is True
            assert pos["shadow_agent_config"] != {}

    def test_gap_onboarding_questions(self):
        """GAP: Questions for onboarding individuals exist."""
        flow = OnboardingFlow()
        session = flow.start_onboarding("Test", "test@co.com")
        questions = flow.get_questions(session.session_id)
        assert len(questions) >= 10
        categories = {q["category"] for q in questions}
        assert "personal" in categories
        assert "role" in categories
        assert "tools" in categories
        assert "automation" in categories

    def test_gap_shadow_agent_is_employee_ip(self):
        """GAP: Shadow agents assigned become the real employee's IP."""
        flow = OnboardingFlow()
        session = flow.start_onboarding("Test", "test@co.com")
        result = flow.assign_shadow_agent(session.session_id)
        assert result["ip_classification"] == "employee_ip"

    def test_gap_org_chart_is_business_ip(self):
        """GAP: Org chart for management of system interactions is business IP."""
        org = CorporateOrgChart()
        assert org.ip_classification == "business_ip"

    def test_gap_system_license_for_metrics(self):
        """GAP: System metrics licensed to Murphy for better recommendations."""
        engine = IPClassificationEngine()
        asset = engine.register_system_metrics_ip("Metrics", "Aggregated data")
        licenses = engine.list_licenses(asset.asset_id)
        assert any(l["licensee"] == "murphy_system" for l in licenses)
        assert any(l["license_type"] == "system_license" for l in licenses)

    def test_gap_trade_secret_protection(self):
        """GAP: Anything titled trade secret is protected."""
        engine = IPClassificationEngine()
        asset = engine.register_asset(
            name="Secret Formula",
            description="Proprietary algorithm",
            classification="trade_secret",
            owner_id="company",
            is_trade_secret=True,
        )
        assert asset.is_trade_secret is True
        assert asset.protection_level == ProtectionLevel.TRADE_SECRET
        # Unauthorized access blocked
        access = engine.check_access(asset.asset_id, "unauthorized")
        assert access["allowed"] is False

    def test_gap_hitl_credential_profiles(self):
        """GAP: Human in the loop credential profiles exist."""
        system = CredentialProfileSystem()
        profile = system.create_profile("user-1", "User One", "engineer")
        assert profile.tier == ProfileTier.NEW
        system.record_interaction(profile.profile_id, "approval")
        assert profile.total_approvals == 1

    def test_gap_optimal_automation_metrics(self):
        """GAP: Statistics of optimal automation metrics are tracked."""
        system = CredentialProfileSystem()
        profile = system.create_profile("user-1", "User One", "engineer")
        for i in range(10):
            system.record_interaction(profile.profile_id, "approval", response_time_ms=500.0)
        metrics = system.get_optimal_automation_metrics()
        assert "optimal_thresholds" in metrics
        assert metrics["ip_classification"] == "system_ip"

    def test_gap_complete_flow_no_gaps(self):
        """FINAL GAP TEST: Complete flow with all components - no gaps remain."""
        # 1. Org chart (Business IP)
        flow = OnboardingFlow()
        org_result = flow.initialize_org()
        assert org_result["positions_created"] >= 10

        # 2. Onboard individual
        session = flow.start_onboarding("Gap Test User", "gap@test.com")
        questions = flow.get_questions(session.session_id)
        assert len(questions) >= 10

        # 3. Shadow agent (Employee IP)
        flow.assign_shadow_agent(session.session_id)
        assert session.shadow_agent is not None
        assert session.shadow_agent.ip_classification == "employee_ip"

        # 4. Transition to builder
        transition = flow.transition_to_workflow_builder(session.session_id)
        assert "builder_context" in transition

        # 5. Librarian terminal
        terminal = NoCodeWorkflowTerminal()
        wf_session = terminal.create_session()
        result = terminal.send_message(wf_session.session_id, "Build a monitoring dashboard")
        assert len(result["steps_created"]) >= 1
        assert len(result["agent_status"]) >= 1

        # 6. Agent monitoring
        for agent in result["agent_status"]:
            detail = terminal.get_agent_detail(wf_session.session_id, agent["agent_id"])
            assert detail is not None

        # 7. IP Classification
        ip_engine = IPClassificationEngine()
        ip_engine.register_employee_ip("emp", "shadow", "Patterns", "desc")
        ip_engine.register_business_ip("biz", "Org Interactions", "desc", is_trade_secret=True)
        ip_engine.register_system_metrics_ip("System Metrics", "desc")
        summary = ip_engine.get_ip_summary()
        assert summary["total_assets"] == 3
        assert summary["trade_secrets"] >= 1

        # 8. Credential profiles
        cred = CredentialProfileSystem()
        profile = cred.create_profile("user", "User", "role")
        cred.record_interaction(profile.profile_id, "approval", response_time_ms=500.0)
        metrics = cred.get_optimal_automation_metrics()
        assert metrics["ip_classification"] == "system_ip"

        # 9. Finalize workflow
        terminal.send_message(wf_session.session_id, "finalize")
        assert wf_session.state == ConversationState.COMPLETED

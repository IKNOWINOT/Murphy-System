"""Tests for agent_module_loader.py — MCP-style agent module system.

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

from __future__ import annotations

import asyncio
import pytest
from datetime import datetime, timezone

import sys
sys.path.insert(0, "src")

from agent_module_loader import (
    # Core classes
    AgentModuleLoader,
    AgentModuleDefinition,
    AgentStatus,
    
    # Multi-cursor
    MultiCursorBrowser,
    MultiCursorActionType,
    MultiCursorTaskStatus,
    MultiCursorSelector,
    MultiCursorAction,
    MultiCursorActionResult,
    
    # Tool registry
    UnifiedToolRegistry,
    ToolCategory,
    DiscoveredTool,
    get_tool_registry,
    
    # Clarification system
    ClarificationSystem,
    ClarificationRequest,
    ClarificationStatus,
    
    # Checklist system
    ChecklistSystem,
    Checklist,
    ChecklistItem,
    ChecklistItemStatus,
    
    # Persistent organizations
    PersistentOrganization,
    PersistentCharacter,
    OrganizationRole,
    OrganizationProject,
    
    # Rosetta bridge
    RosettaHistoryBridge,
    
    # Logging
    ComplianceLogger,
    LogLevel,
    LogFormat,
)


# ============================================================================
# AgentModuleLoader Tests
# ============================================================================

class TestAgentModuleLoader:
    """Test the MCP-style agent module loader."""
    
    def test_loader_initialization(self):
        """Loader initializes with built-in modules."""
        loader = AgentModuleLoader()
        modules = loader.list_modules()
        assert len(modules) >= 6  # At least 6 built-in modules
        
    def test_list_modules_includes_required(self):
        """Required agent modules are registered."""
        loader = AgentModuleLoader()
        module_ids = [m["module_id"] for m in loader.list_modules()]
        
        required = ["security-agent", "devops-agent", "data-agent", 
                    "finance-agent", "comms-agent", "general-agent"]
        for req in required:
            assert req in module_ids, f"Missing required module: {req}"
    
    def test_start_agent(self):
        """Starting an agent returns valid instance."""
        loader = AgentModuleLoader()
        agent = loader.start("security-agent")
        
        assert agent["name"] == "SecurityBot"
        assert agent["status"] == AgentStatus.READY
        assert agent["tool_count"] >= 5
        assert "instance_id" in agent
        assert "session_id" in agent
    
    def test_stop_agent(self):
        """Stopping an agent updates status."""
        loader = AgentModuleLoader()
        agent = loader.start("devops-agent")
        instance_id = agent["instance_id"]
        
        stopped = loader.stop(instance_id)
        assert stopped["status"] == AgentStatus.TERMINATED
    
    def test_list_tools_for_module(self):
        """Each module has tools."""
        loader = AgentModuleLoader()
        
        for module_id in ["security-agent", "devops-agent", "data-agent"]:
            tools = loader.list_tools(module_id)
            assert len(tools) >= 5, f"{module_id} should have at least 5 tools"
    
    def test_general_agent_inherits_all_tools(self):
        """General agent inherits tools from all specialized agents."""
        loader = AgentModuleLoader()
        general_tools = loader.list_tools("general-agent")
        security_tools = loader.list_tools("security-agent")
        
        # General should have more tools than any single specialized agent
        assert len(general_tools) >= len(security_tools)
    
    def test_agent_handoff(self):
        """Handoff transfers context between agents."""
        loader = AgentModuleLoader()
        agent1 = loader.start("security-agent")
        
        result = loader.handoff(
            from_instance_id=agent1["instance_id"],
            to_module_id="devops-agent",
            context={"finding": "vulnerability detected"},
            reason="Needs deployment fix",
        )
        
        assert result["from_agent"] == agent1["instance_id"]
        assert "to_agent" in result
        assert "translated_context" in result


# ============================================================================
# MultiCursorBrowser Tests
# ============================================================================

class TestMultiCursorBrowser:
    """Test Murphy's multi-cursor browser system."""
    
    def test_browser_initialization(self):
        """Browser initializes with default zone."""
        browser = MultiCursorBrowser()
        zones = browser.list_zones()
        assert len(zones) == 1
        assert zones[0]["zone_id"] == "main"
    
    def test_apply_layout_dual_h(self):
        """Dual horizontal layout creates two zones."""
        browser = MultiCursorBrowser()
        zones = browser.apply_layout("dual_h")
        
        assert len(zones) == 2
        assert zones[0]["name"] == "left"
        assert zones[1]["name"] == "right"
    
    def test_apply_layout_quad(self):
        """Quad layout creates four zones."""
        browser = MultiCursorBrowser()
        zones = browser.apply_layout("quad")
        
        assert len(zones) == 4
    
    def test_cursors_created_per_zone(self):
        """Each zone gets its own cursor."""
        browser = MultiCursorBrowser()
        browser.apply_layout("dual_h")
        cursors = browser.list_cursors()
        
        assert len(cursors) == 2
        assert cursors[0]["zone_id"] != cursors[1]["zone_id"]
    
    @pytest.mark.asyncio
    async def test_navigate_action(self):
        """Navigate action completes successfully."""
        browser = MultiCursorBrowser()
        result = await browser.navigate("main", "https://example.com")
        
        assert result.status == MultiCursorTaskStatus.COMPLETED
        assert result.action_type == MultiCursorActionType.NAVIGATE
    
    @pytest.mark.asyncio
    async def test_click_action(self):
        """Click action completes successfully."""
        browser = MultiCursorBrowser()
        result = await browser.click("main", "#button")
        
        assert result.status == MultiCursorTaskStatus.COMPLETED
        assert result.action_type == MultiCursorActionType.CLICK
    
    @pytest.mark.asyncio
    async def test_fill_action(self):
        """Fill action completes successfully."""
        browser = MultiCursorBrowser()
        result = await browser.fill("main", "#input", "test value")
        
        assert result.status == MultiCursorTaskStatus.COMPLETED
        assert result.data.get("value") == "test value"
    
    def test_recording_captures_actions(self):
        """Recording mode captures executed actions."""
        browser = MultiCursorBrowser()
        browser.start_recording()
        
        # Actions would be recorded
        asyncio.run(browser.click("main", "#btn1"))
        asyncio.run(browser.fill("main", "#input", "test"))
        
        recorded = browser.stop_recording()
        assert len(recorded) == 2
    
    @pytest.mark.asyncio
    async def test_checkpoint_and_rollback(self):
        """Checkpoint saves state for rollback."""
        browser = MultiCursorBrowser()
        browser.apply_layout("dual_h")
        
        await browser.checkpoint("cp1")
        
        browser.apply_layout("quad")
        assert len(browser.list_zones()) == 4
        
        await browser.rollback("cp1")
        assert len(browser.list_zones()) == 2
    
    def test_action_history_recorded(self):
        """Action history is maintained."""
        browser = MultiCursorBrowser()
        asyncio.run(browser.navigate("main", "https://example.com"))
        asyncio.run(browser.click("main", "#btn"))
        
        history = browser.get_history()
        assert len(history) == 2
    
    def test_action_type_count(self):
        """All expected action types are defined."""
        # Playwright core + Murphy extensions
        assert len(MultiCursorActionType) >= 70


# ============================================================================
# UnifiedToolRegistry Tests
# ============================================================================

class TestUnifiedToolRegistry:
    """Test the unified tool registry."""
    
    def test_registry_discovers_tools(self):
        """Registry discovers tools from bots and modules."""
        registry = UnifiedToolRegistry()
        count = registry.discover_all()
        
        assert count > 0
        assert registry.get_tool_count() > 100
    
    def test_get_tools_by_category(self):
        """Can filter tools by category."""
        registry = get_tool_registry()
        security_tools = registry.get_tools_by_category(ToolCategory.SECURITY)
        
        assert len(security_tools) > 0
        for tool in security_tools:
            assert tool.category == ToolCategory.SECURITY
    
    def test_get_tools_for_agent(self):
        """Agent type mapping returns appropriate tools."""
        registry = get_tool_registry()
        
        security_tools = registry.get_tools_for_agent("security-agent")
        devops_tools = registry.get_tools_for_agent("devops-agent")
        general_tools = registry.get_tools_for_agent("general-agent")
        
        assert len(security_tools) > 0
        assert len(devops_tools) > 0
        assert len(general_tools) >= len(security_tools)
    
    def test_recommend_tools_for_task(self):
        """Tool recommendation returns relevant tools."""
        registry = get_tool_registry()
        
        tools = registry.recommend_tools(
            "scan for security vulnerabilities",
            agent_type="security-agent",
            max_tools=5,
        )
        
        assert len(tools) <= 5
        assert len(tools) > 0
    
    def test_export_tool_manifest(self):
        """Manifest export includes all categories."""
        registry = get_tool_registry()
        manifest = registry.export_tool_manifest()
        
        assert "total_tools" in manifest
        assert "categories" in manifest
        assert "agents" in manifest
        assert manifest["total_tools"] > 100


# ============================================================================
# ClarificationSystem Tests
# ============================================================================

class TestClarificationSystem:
    """Test the clarification request system."""
    
    def test_request_clarification(self):
        """Can request clarification."""
        system = ClarificationSystem()
        request = system.request_clarification(
            agent_id="test-agent",
            question="What format should the output be?",
            options=["JSON", "XML", "CSV"],
            default_option="JSON",
        )
        
        assert request.status == ClarificationStatus.PENDING
        assert request.question == "What format should the output be?"
        assert len(request.options) == 3
    
    def test_provide_answer(self):
        """Can answer a clarification request."""
        system = ClarificationSystem()
        request = system.request_clarification(
            agent_id="test-agent",
            question="Continue?",
        )
        
        answered = system.provide_answer(request.request_id, "yes")
        
        assert answered.status == ClarificationStatus.ANSWERED
        assert answered.response == "yes"
    
    def test_get_pending_requests(self):
        """Can get pending requests for an agent."""
        system = ClarificationSystem()
        system.request_clarification("agent-1", "Question 1?")
        system.request_clarification("agent-2", "Question 2?")
        system.request_clarification("agent-1", "Question 3?")
        
        agent1_pending = system.get_pending("agent-1")
        assert len(agent1_pending) == 2


# ============================================================================
# ChecklistSystem Tests
# ============================================================================

class TestChecklistSystem:
    """Test the checklist management system."""
    
    def test_create_checklist(self):
        """Can create a checklist."""
        system = ChecklistSystem()
        checklist = system.create_checklist(
            name="Test Checklist",
            items=[
                {"title": "Step 1"},
                {"title": "Step 2"},
            ],
        )
        
        assert checklist.name == "Test Checklist"
        assert len(checklist.items) == 2
        assert checklist.progress == 0.0
    
    def test_create_from_template(self):
        """Can create checklist from template."""
        system = ChecklistSystem()
        checklist = system.create_checklist(
            name="Security Review",
            template="security_review",
        )
        
        assert len(checklist.items) >= 5
    
    def test_update_item_status(self):
        """Can update checklist item status."""
        system = ChecklistSystem()
        checklist = system.create_checklist(
            name="Test",
            items=[{"title": "Task 1"}, {"title": "Task 2"}],
        )
        
        item = system.update_item_status(
            checklist.checklist_id,
            checklist.items[0].item_id,
            ChecklistItemStatus.COMPLETED,
        )
        
        assert item.status == ChecklistItemStatus.COMPLETED
        assert checklist.progress == 50.0
    
    def test_list_templates(self):
        """Default templates are available."""
        system = ChecklistSystem()
        templates = system.get_templates()
        
        assert "agent_onboarding" in templates
        assert "security_review" in templates
        assert "deployment_checklist" in templates
        assert "proposal_completion" in templates


# ============================================================================
# PersistentOrganization Tests
# ============================================================================

class TestPersistentOrganization:
    """Test persistent organization characters."""
    
    def test_create_organization(self):
        """Can create an organization."""
        org = PersistentOrganization(
            organization_id="test-org",
            name="Test Organization",
        )
        
        assert org.organization_id == "test-org"
        assert org.name == "Test Organization"
    
    def test_define_role(self):
        """Can define roles in organization."""
        org = PersistentOrganization("org-1", "Org")
        role = org.define_role(
            role_id="dev-lead",
            title="Development Lead",
            department="Engineering",
            responsibilities=["Code review", "Architecture"],
            required_tools=["coding_bot/generate_code"],
        )
        
        assert role.role_id == "dev-lead"
        assert role.title == "Development Lead"
    
    def test_create_character(self):
        """Can create persistent characters."""
        org = PersistentOrganization("org-1", "Org")
        org.define_role(
            role_id="analyst",
            title="Data Analyst",
            department="Data",
            responsibilities=["Analysis"],
            required_tools=[],
        )
        
        char = org.create_character(
            name="Alice",
            role_id="analyst",
            agent_module="data-agent",
        )
        
        assert char.name == "Alice"
        assert char.role.title == "Data Analyst"
        assert char.agent_module == "data-agent"
    
    def test_create_project(self):
        """Can create projects with characters."""
        org = PersistentOrganization("org-1", "Org")
        org.define_role("lead", "Lead", "Mgmt", [], [])
        char = org.create_character("Bob", "lead", "general-agent")
        
        project = org.create_project(
            name="Test Project",
            description="A test",
            lead_character_id=char.character_id,
        )
        
        assert project.name == "Test Project"
        assert project.lead_character_id == char.character_id
        assert project.phase == "inception"
    
    def test_advance_project_phase(self):
        """Can advance project through phases."""
        org = PersistentOrganization("org-1", "Org")
        org.define_role("lead", "Lead", "Mgmt", [], [])
        char = org.create_character("Charlie", "lead", "general-agent")
        project = org.create_project("Project", "Desc", char.character_id)
        
        org.advance_project_phase(project.project_id, "planning")
        assert project.phase == "planning"
        assert len(project.phase_history) == 1
    
    def test_export_organization_state(self):
        """Can export organization state."""
        org = PersistentOrganization("org-1", "Test Org")
        org.define_role("role-1", "Role", "Dept", [], [])
        org.create_character("Dana", "role-1", "general-agent")
        
        state = org.export_organization_state()
        
        assert state["organization_id"] == "org-1"
        assert len(state["roles"]) == 1
        assert len(state["characters"]) == 1


# ============================================================================
# RosettaHistoryBridge Tests
# ============================================================================

class TestRosettaHistoryBridge:
    """Test Rosetta history translation."""
    
    def test_record_action(self):
        """Can record actions in history."""
        bridge = RosettaHistoryBridge()
        bridge.record_action(
            source_agent="agent-1",
            action="completed_task",
            context={"task_id": "123"},
        )
        
        history = bridge.get_agent_history("agent-1")
        assert len(history) == 1
        assert history[0].action == "completed_task"
    
    def test_register_terminology(self):
        """Can register domain terminology."""
        bridge = RosettaHistoryBridge()
        bridge.register_terminology("security", {
            "problem": "vulnerability",
            "fix": "remediation",
        })
        
        # Terminology is registered (internal state)
        assert "security" in bridge._terminology_maps
    
    def test_handoff_preserves_context(self):
        """Handoff preserves and translates context."""
        bridge = RosettaHistoryBridge()
        bridge.start_session("session-1", {"user": "test"})
        
        result = bridge.handoff(
            session_id="session-1",
            from_agent="agent-1",
            to_agent="agent-2",
            context={"task": "review"},
            reason="Needs specialist",
        )
        
        assert "task" in result
        assert result["task"] == "review"


# ============================================================================
# ComplianceLogger Tests
# ============================================================================

class TestComplianceLogger:
    """Test compliance logging system."""
    
    def test_logger_initialization(self):
        """Logger initializes correctly."""
        log = ComplianceLogger(
            agent_id="test-agent",
            log_format=LogFormat.JSON,
            compliance_standards=["SOC2", "GDPR"],
        )
        
        assert log.agent_id == "test-agent"
        assert log.log_format == LogFormat.JSON
    
    def test_log_levels(self):
        """All log levels work."""
        log = ComplianceLogger("test", LogFormat.JSON)
        
        log.log(LogLevel.INFO, "Info message")
        log.log(LogLevel.WARNING, "Warning message")
        log.log(LogLevel.ERROR, "Error message")
        log.log(LogLevel.AUDIT, "Audit event")
        
        assert len(log._log_buffer) == 4
    
    def test_audit_trail(self):
        """Audit events are tracked separately."""
        log = ComplianceLogger("test", LogFormat.JSON, ["SOC2"])
        
        log.log(LogLevel.INFO, "Normal log")
        log.audit("User login", {"user_id": "123"})
        log.security("Access attempt", {"ip": "1.2.3.4"})
        log.compliance("SOC2-CC1.1", "PASS")
        
        audit_trail = log.get_audit_trail()
        assert len(audit_trail) == 3  # audit, security, compliance
    
    def test_export_different_formats(self):
        """Can export logs in different formats."""
        log = ComplianceLogger("test", LogFormat.JSON)
        log.log(LogLevel.INFO, "Test message")
        
        json_logs = log.export_logs(LogFormat.JSON)
        plain_logs = log.export_logs(LogFormat.PLAIN)
        
        assert len(json_logs) == 1
        assert len(plain_logs) == 1
        assert "Test message" in plain_logs[0]


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for the complete system."""
    
    def test_agent_with_tool_registry(self):
        """Agent can access tool registry."""
        loader = AgentModuleLoader()
        registry = get_tool_registry()
        
        agent = loader.start("security-agent")
        tools = registry.get_tools_for_agent("security-agent")
        
        assert len(tools) > 0
        assert agent["tool_count"] > 0
    
    def test_organization_with_agents(self):
        """Organization can use agent loader."""
        loader = AgentModuleLoader()
        org = PersistentOrganization("org-1", "Test Org")
        
        org.define_role("sec", "Security Lead", "Security", ["Auditing"], ["scan_vulnerabilities"])
        char = org.create_character("Eve", "sec", "security-agent")
        
        session = org.start_session(char.character_id, loader)
        
        assert session["agent"]["name"] == "SecurityBot"
        assert session["character"].name == "Eve"
    
    @pytest.mark.asyncio
    async def test_browser_with_organization(self):
        """Browser can be used in organization context."""
        browser = MultiCursorBrowser()
        zones = browser.apply_layout("dual_h")
        
        # Two agents working in parallel
        result1 = await browser.navigate(zones[0]["zone_id"], "https://app1.example.com")
        result2 = await browser.navigate(zones[1]["zone_id"], "https://app2.example.com")
        
        assert result1.status == MultiCursorTaskStatus.COMPLETED
        assert result2.status == MultiCursorTaskStatus.COMPLETED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

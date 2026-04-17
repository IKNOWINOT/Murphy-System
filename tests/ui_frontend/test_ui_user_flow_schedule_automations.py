"""
End-to-end user-flow tests for the Murphy System UI and scheduled
automation workflows created from natural language prompts.

Simulates a real user:
  1. Signs up and logs in
  2. Navigates protected and public UI pages
  3. Creates automation workflows from natural language descriptions
  4. Verifies schedule metadata is correctly inferred
  5. Manages workflow lifecycle (create → list → get → execute)
  6. Interacts with the platform scheduler
  7. Validates the full generate→schedule→execute pipeline

Copyright © 2020 Inoni Limited Liability Company
Creator: Corey Post
License: BSL 1.1
"""

import os
import sys
import json
import re
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def _app():
    """Create the FastAPI application once per module."""
    os.environ["MURPHY_ENV"] = "development"
    os.environ["MURPHY_RATE_LIMIT_RPM"] = "6000"
    os.environ["MURPHY_RATE_LIMIT_BURST"] = "200"
    from src.runtime.app import create_app
    return create_app()


@pytest.fixture(scope="module")
def client(_app):
    """Module-scoped unauthenticated test client (no session cookies).

    Used for NL workflow generation and public page tests so the free-tier
    daily-action limit is never triggered.
    """
    from starlette.testclient import TestClient
    return TestClient(_app, follow_redirects=False)


@pytest.fixture
def fresh_client():
    """Entirely fresh app + client — no shared state with other tests."""
    os.environ["MURPHY_ENV"] = "development"
    os.environ["MURPHY_RATE_LIMIT_RPM"] = "6000"
    os.environ["MURPHY_RATE_LIMIT_BURST"] = "200"
    from starlette.testclient import TestClient
    from src.runtime.app import create_app
    app = create_app()
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def auth_user(_app):
    """Sign up a fresh user on a *separate* TestClient so the session
    cookie doesn't leak into the module-scoped ``client`` fixture."""
    from starlette.testclient import TestClient
    cli = TestClient(_app, follow_redirects=False)
    email = f"uiflow_{os.urandom(4).hex()}@example.com"
    resp = cli.post("/api/auth/signup", json={
        "email": email,
        "password": "SecurePass123!",
        "full_name": "UI Flow Tester",
        "job_title": "QA Engineer",
        "company": "TestCo",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    assert data["account_id"]
    assert data["email"] == email
    return cli, data


# ===========================================================================
# Part 1 — Full User Signup & Login Flow
# ===========================================================================

class TestUserAuthFlow:
    """Simulate a user signing up, logging in, and accessing their profile.

    Uses ``auth_user`` (which creates its own TestClient) so the
    module-scoped ``client`` stays cookie-free for workflow tests.
    """

    def test_signup_page_accessible(self, client):
        """Public signup page loads without authentication."""
        resp = client.get("/ui/signup")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_login_page_accessible(self, client):
        """Public login page loads without authentication."""
        resp = client.get("/ui/login")
        assert resp.status_code == 200
        assert "text/html" in resp.headers.get("content-type", "")

    def test_signup_creates_session(self, auth_user):
        """POST /api/auth/signup returns account data and sets session cookie."""
        _cli, data = auth_user
        assert data["success"] is True
        assert "account_id" in data
        assert data["tier"] == "free"

    def test_login_with_credentials(self, _app):
        """Sign up then log in with same credentials."""
        from starlette.testclient import TestClient
        cli = TestClient(_app, follow_redirects=False)
        email = f"flow_l_{os.urandom(4).hex()}@example.com"
        pw = "LoginTest123!"
        # Sign up first
        s = cli.post("/api/auth/signup", json={
            "email": email, "password": pw, "full_name": "Login Test",
        })
        assert s.status_code == 200

        # Now log in
        resp = cli.post("/api/auth/login", json={
            "email": email, "password": pw,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_profile_after_auth(self, auth_user):
        """Authenticated user can access /api/profiles/me."""
        cli, acct = auth_user
        resp = cli.get("/api/profiles/me")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("success") is True or "account_id" in data or "email" in data


# ===========================================================================
# Part 2 — UI Page Navigation (simulates user visiting pages)
# ===========================================================================

class TestUIPageNavigation:
    """Verify every public UI page returns 200 and every protected page
    redirects to login for unauthenticated users."""

    PUBLIC_PAGES = [
        "/", "/ui/landing", "/ui/login", "/ui/signup", "/ui/pricing",
        "/ui/docs", "/ui/blog", "/ui/careers", "/ui/legal", "/ui/privacy",
        "/ui/partner", "/ui/smoke-test",
    ]

    PROTECTED_PAGES = [
        "/ui/terminal-unified", "/ui/terminal", "/ui/dashboard",
        "/ui/workflow-canvas", "/ui/onboarding", "/ui/workspace",
        "/ui/compliance", "/ui/wallet", "/ui/management",
        "/ui/calendar", "/ui/meeting-intelligence",
    ]

    @pytest.mark.parametrize("path", PUBLIC_PAGES)
    def test_public_page_loads(self, client, path):
        """Public pages should return 200 without auth."""
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} returned {resp.status_code}"

    @pytest.mark.parametrize("path", PROTECTED_PAGES)
    def test_protected_page_redirects_unauthed(self, fresh_client, path):
        """Protected pages should 302 redirect to login when not authenticated."""
        resp = fresh_client.get(path)
        assert resp.status_code == 302, f"{path} returned {resp.status_code} (expected 302)"
        location = resp.headers.get("location", "")
        assert "/ui/login" in location

    def test_workflow_canvas_accessible_after_auth(self, auth_user):
        """Authenticated user can access the workflow canvas."""
        cli, _ = auth_user
        resp = cli.get("/ui/workflow-canvas")
        assert resp.status_code == 200
        body = resp.text
        assert "Workflow Designer" in body or "workflow" in body.lower()

    def test_dashboard_accessible_after_auth(self, auth_user):
        """Authenticated user can access the dashboard."""
        cli, _ = auth_user
        resp = cli.get("/ui/dashboard")
        assert resp.status_code == 200


# ===========================================================================
# Part 3 — Natural Language → Scheduled Workflow (core pipeline)
# ===========================================================================

class TestNLToScheduledWorkflow:
    """Verify that natural language descriptions produce correctly
    scheduled automation workflows — the full Describe→Schedule pipeline."""

    # ── Daily schedules ──

    def test_daily_email_report(self, client):
        """'Send daily email reports' → daily schedule + SendGrid suggestion."""
        resp = client.post("/api/workflows/generate", json={
            "description": "Send daily email reports to the sales team",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        wf = data["workflow"]

        # Schedule metadata
        assert wf["schedule"]["interval"] == "daily"
        assert wf["schedule"]["enabled"] is True
        assert wf["schedule"]["cron"] == "0 8 * * *"
        assert wf["schedule"]["next_run"]  # ISO timestamp present

        # API suggestion
        api_names = [s["name"] for s in wf.get("api_suggestions", [])]
        assert "SendGrid" in api_names

        # NL source recorded
        assert "daily email" in wf["generated_from"].lower()

    def test_daily_monitoring_alerts(self, client):
        """'Monitor system health every day' → daily schedule."""
        resp = client.post("/api/workflows/generate", json={
            "description": "Monitor system health every day and alert on anomalies",
        })
        assert resp.status_code == 200
        wf = resp.json()["workflow"]
        assert wf["schedule"]["interval"] == "daily"
        assert wf["schedule"]["enabled"] is True
        api_names = [s["name"] for s in wf.get("api_suggestions", [])]
        assert "Datadog" in api_names

    # ── Weekly schedules ──

    def test_weekly_invoice_summary(self, client):
        """'Generate weekly invoice summary' → weekly schedule + Stripe."""
        resp = client.post("/api/workflows/generate", json={
            "description": "Generate weekly invoice summary every week",
        })
        assert resp.status_code == 200
        wf = resp.json()["workflow"]
        assert wf["schedule"]["interval"] == "weekly"
        assert wf["schedule"]["cron"] == "0 8 * * 1"
        assert wf["schedule"]["enabled"] is True
        api_names = [s["name"] for s in wf.get("api_suggestions", [])]
        assert "Stripe" in api_names

    def test_weekly_slack_digest(self, client):
        """'Post a weekly team digest to Slack' → weekly + Slack suggestion."""
        resp = client.post("/api/workflows/generate", json={
            "description": "Post a weekly team digest to Slack each week",
        })
        assert resp.status_code == 200
        wf = resp.json()["workflow"]
        assert wf["schedule"]["interval"] == "weekly"
        api_names = [s["name"] for s in wf.get("api_suggestions", [])]
        assert "Slack" in api_names

    # ── Monthly schedules ──

    def test_monthly_payment_processing(self, client):
        """'Process monthly payment invoices' → monthly + Stripe."""
        resp = client.post("/api/workflows/generate", json={
            "description": "Process monthly payment invoices for clients",
        })
        assert resp.status_code == 200
        wf = resp.json()["workflow"]
        assert wf["schedule"]["interval"] == "monthly"
        assert wf["schedule"]["cron"] == "0 8 1 * *"
        assert wf["schedule"]["enabled"] is True

    def test_monthly_crm_cleanup(self, client):
        """'Clean up CRM contacts every month' → monthly + HubSpot."""
        resp = client.post("/api/workflows/generate", json={
            "description": "Clean up CRM contacts every month",
        })
        assert resp.status_code == 200
        wf = resp.json()["workflow"]
        assert wf["schedule"]["interval"] == "monthly"
        api_names = [s["name"] for s in wf.get("api_suggestions", [])]
        assert "HubSpot" in api_names

    # ── Hourly schedules ──

    def test_hourly_sensor_check(self, client):
        """'Check sensor readings every hour' → hourly + IoT Hub."""
        resp = client.post("/api/workflows/generate", json={
            "description": "Check sensor readings every hour",
        })
        assert resp.status_code == 200
        wf = resp.json()["workflow"]
        assert wf["schedule"]["interval"] == "hourly"
        assert wf["schedule"]["cron"] == "0 * * * *"
        assert wf["schedule"]["enabled"] is True
        api_names = [s["name"] for s in wf.get("api_suggestions", [])]
        assert "IoT Hub" in api_names

    # ── On-demand (no schedule keywords) ──

    def test_on_demand_document_processing(self, client):
        """'Process uploaded documents' → on_demand (no schedule keywords)."""
        resp = client.post("/api/workflows/generate", json={
            "description": "Process uploaded documents and extract data",
        })
        assert resp.status_code == 200
        wf = resp.json()["workflow"]
        assert wf["schedule"]["interval"] == "on_demand"
        assert wf["schedule"]["enabled"] is False
        assert wf["schedule"]["cron"] is None

    # ── Explicit schedule override ──

    def test_explicit_schedule_overrides_inference(self, client):
        """Explicit schedule_interval should override NL inference."""
        resp = client.post("/api/workflows/generate", json={
            "description": "Run a generic report",
            "schedule_interval": "hourly",
        })
        assert resp.status_code == 200
        wf = resp.json()["workflow"]
        assert wf["schedule"]["interval"] == "hourly"
        assert wf["schedule"]["enabled"] is True

    # ── Validation ──

    def test_empty_description_rejected(self, client):
        """Empty description should return 400."""
        resp = client.post("/api/workflows/generate", json={
            "description": "",
        })
        assert resp.status_code == 400
        assert resp.json()["success"] is False


# ===========================================================================
# Part 4 — Workflow CRUD Lifecycle (as a user)
# ===========================================================================

class TestWorkflowCRUDLifecycle:
    """Simulate a user creating, listing, retrieving, and managing workflows."""

    def test_generate_then_list(self, client):
        """Generated workflow appears in the workflow list."""
        # Generate
        gen_resp = client.post("/api/workflows/generate", json={
            "description": "Send daily Slack standup reminders",
        })
        assert gen_resp.status_code == 200
        wf_id = gen_resp.json()["workflow"]["id"]

        # List
        list_resp = client.get("/api/workflows")
        assert list_resp.status_code == 200
        ids = [w["id"] for w in list_resp.json()["workflows"]]
        assert wf_id in ids

    def test_generate_then_get_by_id(self, client):
        """Generated workflow can be retrieved by ID."""
        gen_resp = client.post("/api/workflows/generate", json={
            "description": "Send weekly email digest to subscribers",
        })
        assert gen_resp.status_code == 200
        wf_id = gen_resp.json()["workflow"]["id"]

        get_resp = client.get(f"/api/workflows/{wf_id}")
        assert get_resp.status_code == 200
        wf = get_resp.json()["workflow"]
        assert wf["id"] == wf_id
        assert wf["schedule"]["interval"] == "weekly"
        assert "email" in wf["generated_from"].lower()

    def test_save_custom_workflow(self, client):
        """Users can save a custom-built workflow."""
        resp = client.post("/api/workflows", json={
            "name": "My Custom Automation",
            "nodes": [
                {"id": "t1", "type": "trigger", "subtype": "schedule",
                 "label": "Daily at 9am"},
                {"id": "a1", "type": "action", "subtype": "api-call",
                 "label": "Fetch sales data"},
            ],
            "connections": [{"from": "t1", "to": "a1"}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["workflow"]["name"] == "My Custom Automation"
        assert len(data["workflow"]["nodes"]) == 2

    def test_get_nonexistent_workflow_returns_404(self, client):
        """Requesting a non-existent workflow returns 404."""
        resp = client.get("/api/workflows/does-not-exist-12345")
        assert resp.status_code == 404

    def test_workflow_count_matches_list_length(self, client):
        """The count field matches the actual workflow list length."""
        resp = client.get("/api/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == len(data["workflows"])


# ===========================================================================
# Part 5 — Scheduler Endpoints (platform automation)
# ===========================================================================

class TestSchedulerEndpoints:
    """Test the Murphy platform scheduler API endpoints."""

    def test_scheduler_status(self, client):
        """GET /api/scheduler/status returns success."""
        resp = client.get("/api/scheduler/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    def test_scheduler_start(self, client):
        """POST /api/scheduler/start returns success or 503 (no APScheduler)."""
        resp = client.post("/api/scheduler/start")
        assert resp.status_code in (200, 503)

    def test_scheduler_stop(self, client):
        """POST /api/scheduler/stop returns success or 503."""
        resp = client.post("/api/scheduler/stop")
        assert resp.status_code in (200, 503)

    def test_scheduler_trigger(self, client):
        """POST /api/scheduler/trigger returns success or 503."""
        resp = client.post("/api/scheduler/trigger")
        assert resp.status_code in (200, 503)


# ===========================================================================
# Part 6 — Platform Automation Status
# ===========================================================================

class TestPlatformAutomationStatus:
    """Verify the unified platform automation status endpoint."""

    def test_automation_status_endpoint(self, client):
        """GET /api/platform/automation-status returns all subsystem statuses."""
        resp = client.get("/api/platform/automation-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        systems = data["systems"]
        # All 6 subsystems reported
        for key in ("self_fix_loop", "autonomous_repair", "scheduler",
                     "self_automation_orchestrator", "self_improvement_engine", "mfm"):
            assert key in systems, f"Missing subsystem: {key}"
        assert data["total_systems"] >= 6


# ===========================================================================
# Part 7 — Full User Journey: Signup → Create NL Workflow → Verify Schedule
# ===========================================================================

class TestFullUserJourney:
    """End-to-end user journey from signup through NL workflow creation
    and schedule verification — the core requirement."""

    def test_signup_navigate_create_daily_workflow(self, auth_user):
        """User signs up → navigates to workflow canvas → creates daily
        email automation from natural language → verifies schedule."""
        cli, acct = auth_user

        # Step 1: User navigates to the workflow canvas
        canvas_resp = cli.get("/ui/workflow-canvas")
        assert canvas_resp.status_code == 200
        assert "Workflow Designer" in canvas_resp.text or "workflow" in canvas_resp.text.lower()

        # Step 2: User types NL description and submits
        gen_resp = cli.post("/api/workflows/generate", json={
            "description": "Send daily email reports to the marketing team every day",
        })
        assert gen_resp.status_code == 200
        wf = gen_resp.json()["workflow"]

        # Step 3: Verify the schedule was correctly inferred from NL
        assert wf["schedule"]["interval"] == "daily"
        assert wf["schedule"]["enabled"] is True
        assert wf["schedule"]["cron"] == "0 8 * * *"
        assert wf["generated_from"]  # NL prompt recorded

        # Step 4: Verify API suggestions
        api_names = [s["name"] for s in wf.get("api_suggestions", [])]
        assert "SendGrid" in api_names

        # Step 5: Verify workflow persists in the store
        wf_id = wf["id"]
        get_resp = cli.get(f"/api/workflows/{wf_id}")
        assert get_resp.status_code == 200
        stored = get_resp.json()["workflow"]
        assert stored["schedule"]["interval"] == "daily"

    def test_signup_create_weekly_slack_workflow(self, auth_user):
        """User creates a weekly Slack notification workflow from NL."""
        cli, _ = auth_user

        resp = cli.post("/api/workflows/generate", json={
            "description": "Post a weekly team performance summary to Slack",
        })
        assert resp.status_code == 200
        wf = resp.json()["workflow"]

        assert wf["schedule"]["interval"] == "weekly"
        assert wf["schedule"]["cron"] == "0 8 * * 1"
        assert wf["schedule"]["enabled"] is True
        assert any(s["name"] == "Slack" for s in wf.get("api_suggestions", []))

    def test_signup_create_monthly_invoice_workflow(self, auth_user):
        """User creates a monthly invoice processing workflow from NL."""
        cli, _ = auth_user

        resp = cli.post("/api/workflows/generate", json={
            "description": "Generate monthly invoice reports and send payment reminders",
        })
        assert resp.status_code == 200
        wf = resp.json()["workflow"]

        assert wf["schedule"]["interval"] == "monthly"
        assert wf["schedule"]["cron"] == "0 8 1 * *"
        assert wf["schedule"]["enabled"] is True
        assert any(s["name"] == "Stripe" for s in wf.get("api_suggestions", []))

    def test_user_workflows_appear_in_list(self, auth_user):
        """All workflows created by user appear in the workflow list."""
        cli, _ = auth_user

        # Create two workflows
        r1 = cli.post("/api/workflows/generate", json={
            "description": "Send daily email status updates to managers",
        })
        r2 = cli.post("/api/workflows/generate", json={
            "description": "Run hourly sensor data collection",
        })
        assert r1.status_code == 200
        assert r2.status_code == 200
        id1 = r1.json()["workflow"]["id"]
        id2 = r2.json()["workflow"]["id"]

        # List all workflows
        list_resp = cli.get("/api/workflows")
        assert list_resp.status_code == 200
        all_ids = [w["id"] for w in list_resp.json()["workflows"]]
        assert id1 in all_ids
        assert id2 in all_ids

    def test_user_views_demo_export_with_workflows(self, auth_user):
        """After creating workflows, demo export includes them."""
        cli, _ = auth_user

        # Create a workflow first
        cli.post("/api/workflows/generate", json={
            "description": "Send daily CRM updates to the sales team via email",
        })

        # Fetch demo export
        resp = cli.get("/api/demo/export")
        assert resp.status_code == 200
        data = resp.json()
        # Response may wrap under 'bundle' key
        bundle = data.get("bundle", data)
        assert bundle.get("murphy_demo_export") is True or data.get("success") is True


# ===========================================================================
# Part 8 — Workflow Canvas HTML Content Verification
# ===========================================================================

class TestWorkflowCanvasContent:
    """Verify the workflow canvas HTML has required UI components for
    natural language workflow creation."""

    @pytest.fixture(autouse=True)
    def _load_canvas(self):
        canvas_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "workflow_canvas.html"
        )
        with open(canvas_path, "r", encoding="utf-8") as f:
            self.content = f.read()

    def test_has_nl_input(self):
        """Canvas has a natural language input field."""
        assert "nl-input" in self.content
        lower = self.content.lower()
        assert any(kw in lower for kw in (
            "plain english", "natural language", "describe",
        )), "Workflow canvas missing natural language input prompt"

    def test_has_schedule_trigger_node(self):
        """Canvas palette includes a Schedule trigger node."""
        assert "schedule" in self.content.lower()
        assert 'data-subtype="schedule"' in self.content

    def test_has_save_button(self):
        """Canvas has a save button."""
        assert "btn-save" in self.content

    def test_has_run_button(self):
        """Canvas has a run button."""
        assert "btn-run" in self.content

    def test_has_load_button(self):
        """Canvas has a load button."""
        assert "btn-load" in self.content

    def test_has_node_palette(self):
        """Canvas has a draggable node palette."""
        assert "node-palette" in self.content
        assert "draggable" in self.content

    def test_has_trigger_action_logic_gates(self):
        """Canvas palette has all four node categories."""
        for category in ("Triggers", "Actions", "Logic", "Gates"):
            assert category in self.content, f"Missing palette category: {category}"


# ===========================================================================
# Part 9 — API Suggestion Coverage from NL Descriptions
# ===========================================================================

class TestAPISuggestionsFromNL:
    """Verify the correct API integrations are suggested for various
    natural language workflow descriptions."""

    CASES = [
        ("Send email notifications when tasks complete", "SendGrid"),
        ("Post updates to Slack channel", "Slack"),
        ("Update CRM contacts with new leads", "HubSpot"),
        ("Process payment for monthly subscriptions", "Stripe"),
        ("Schedule calendar events for team meetings", "Google Calendar"),
        ("Sync data to spreadsheet for reporting", "Google Sheets"),
        ("Query the database for analytics", "PostgreSQL"),
        ("Send SMS alerts when thresholds are exceeded", "Twilio"),
        ("Push changes to GitHub repository", "GitHub"),
        ("Monitor application performance metrics", "Datadog"),
        ("Check weather conditions for outdoor events", "OpenWeatherMap"),
    ]

    @pytest.mark.parametrize("description,expected_api", CASES)
    def test_api_suggestion(self, client, description, expected_api):
        """NL description should suggest the correct API integration."""
        resp = client.post("/api/workflows/generate", json={
            "description": description,
        })
        assert resp.status_code == 200
        wf = resp.json()["workflow"]
        api_names = [s["name"] for s in wf.get("api_suggestions", [])]
        assert expected_api in api_names, (
            f"Expected {expected_api} in suggestions for '{description}', "
            f"got {api_names}"
        )


# ===========================================================================
# Part 10 — Schedule Metadata Structure Validation
# ===========================================================================

class TestScheduleMetadataStructure:
    """Validate the structure and correctness of schedule metadata
    attached to generated workflows."""

    CRON_MAP = {
        "daily": "0 8 * * *",
        "weekly": "0 8 * * 1",
        "monthly": "0 8 1 * *",
        "hourly": "0 * * * *",
    }

    @pytest.mark.parametrize("interval,cron", CRON_MAP.items())
    def test_cron_expression_for_interval(self, client, interval, cron):
        """Each schedule interval maps to the correct cron expression."""
        desc_map = {
            "daily": "Run daily data sync",
            "weekly": "Generate weekly report",
            "monthly": "Process monthly billing",
            "hourly": "Check system status every hour",
        }
        resp = client.post("/api/workflows/generate", json={
            "description": desc_map[interval],
        })
        assert resp.status_code == 200
        schedule = resp.json()["workflow"]["schedule"]
        assert schedule["interval"] == interval
        assert schedule["cron"] == cron
        assert schedule["enabled"] is True
        # next_run is a valid ISO timestamp
        assert "T" in schedule["next_run"]

    def test_on_demand_has_no_cron(self, client):
        """On-demand workflows should not have a cron expression."""
        resp = client.post("/api/workflows/generate", json={
            "description": "Analyze uploaded files",
        })
        assert resp.status_code == 200
        schedule = resp.json()["workflow"]["schedule"]
        assert schedule["interval"] == "on_demand"
        assert schedule["enabled"] is False
        assert schedule["cron"] is None

    def test_schedule_fields_present(self, client):
        """All required schedule fields are present."""
        resp = client.post("/api/workflows/generate", json={
            "description": "Send daily digest to the team",
        })
        assert resp.status_code == 200
        schedule = resp.json()["workflow"]["schedule"]
        for field in ("interval", "enabled", "cron", "next_run"):
            assert field in schedule, f"Missing schedule field: {field}"

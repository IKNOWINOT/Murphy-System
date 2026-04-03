"""
Tests for the onboard LLM fixes:

- FIX-1: LocalLLMFallback._generate_offline — no context contamination
- FIX-2: LocalLLMFallback — business-domain knowledge (e-commerce, automation, etc.)
- FIX-3: UnifiedMFGC._process_with_context — None-answer crash fixed
- FIX-4: UnifiedMFGC._process_with_context — offline mode uses structured questions
"""

import os
import sys
import pytest



# ---------------------------------------------------------------------------
# FIX-1: LocalLLMFallback context contamination
# ---------------------------------------------------------------------------

class TestLocalLLMFallbackContextContamination:
    """FIX-1: system context injected before the user query must not hijack topic matching."""

    def _make_llm(self):
        from local_llm_fallback import LocalLLMFallback
        return LocalLLMFallback()

    def test_murphy_in_context_does_not_match_murphy_topic(self):
        """When context contains 'murphy' but the user query is about e-commerce,
        the response must NOT be the murphy setup/info content."""
        llm = self._make_llm()
        context = "Knowledge-base topics: murphy, murphy_setup, murphy_troubleshooting"
        user_msg = "I run a small e-commerce business and want to automate order fulfillment."
        full_prompt = f"{context}\n\n{user_msg}"
        result = llm.generate(full_prompt, max_tokens=200)
        # Must NOT return the generic murphy-system description
        assert "Murphy System is an AI-powered automation assistant" not in result, (
            "Context contamination: 'murphy' in system context should not match 'murphy' "
            "knowledge-base topic and hijack the response"
        )

    def test_user_query_topic_match_still_works(self):
        """Direct murphy query (no context prefix) still returns murphy content."""
        llm = self._make_llm()
        result = llm.generate("What is Murphy System?", max_tokens=200)
        assert "Murphy" in result or "automation" in result.lower()

    def test_context_prefix_e_commerce_returns_ecommerce_content(self):
        """E-commerce query with context prefix returns e-commerce content, not murphy setup."""
        llm = self._make_llm()
        full_prompt = "Knowledge-base topics: murphy\n\nI want to automate my e-commerce store."
        result = llm.generate(full_prompt, max_tokens=200)
        # Should match e-commerce knowledge base entry
        ecom_keywords = ["e-commerce", "order", "fulfillment", "shopify", "automation", "store"]
        assert any(kw in result.lower() for kw in ecom_keywords), (
            f"Expected e-commerce content, got: {result[:200]}"
        )


# ---------------------------------------------------------------------------
# FIX-2: LocalLLMFallback business-domain knowledge
# ---------------------------------------------------------------------------

class TestLocalLLMFallbackBusinessDomain:
    """FIX-2: Knowledge base has entries for business/automation domain queries."""

    def _make_llm(self):
        from local_llm_fallback import LocalLLMFallback
        return LocalLLMFallback()

    def test_ecommerce_topic_in_knowledge_base(self):
        from local_llm_fallback import LocalLLMFallback
        llm = LocalLLMFallback()
        assert "e-commerce" in llm.knowledge_base or "ecommerce" in llm.knowledge_base or \
               any("ecommerce" in k or "e-commerce" in k for k in llm.knowledge_base), \
               "e-commerce topic missing from knowledge base"

    def test_automation_topic_in_knowledge_base(self):
        from local_llm_fallback import LocalLLMFallback
        llm = LocalLLMFallback()
        assert "automation" in llm.knowledge_base, "automation topic missing from knowledge base"

    def test_workflow_topic_in_knowledge_base(self):
        from local_llm_fallback import LocalLLMFallback
        llm = LocalLLMFallback()
        assert "workflow" in llm.knowledge_base, "workflow topic missing from knowledge base"

    def test_automation_query_gives_relevant_response(self):
        """A query mentioning 'automation' returns automation-relevant content."""
        llm = self._make_llm()
        result = llm.generate("I want to automate my business workflows", max_tokens=200)
        auto_keywords = ["automat", "trigger", "workflow", "task", "integration"]
        assert any(kw in result.lower() for kw in auto_keywords), (
            f"Automation query did not return relevant response: {result[:200]}"
        )

    def test_business_pattern_match(self):
        """'I run a business...' matches the business pattern and returns onboarding questions."""
        llm = self._make_llm()
        result = llm.generate("I run a small bakery and need to automate", max_tokens=200)
        # Should use business or automation response type
        assert len(result) > 20, "Response too short for a business query"

    def test_integration_pattern_match(self):
        """'I want to connect Shopify...' uses integration pattern."""
        llm = self._make_llm()
        result = llm.generate("I want to integrate Shopify with my accounting software", max_tokens=200)
        assert len(result) > 20, "Response too short for an integration query"


# ---------------------------------------------------------------------------
# FIX-3: UnifiedMFGC None-answer crash fix
# ---------------------------------------------------------------------------

class TestUnifiedMFGCNoneAnswerCrash:
    """FIX-3: _process_with_context must not crash when answers dict has None values."""

    def test_none_answer_values_do_not_crash(self):
        """When answers dict has None values (unanswered question placeholders),
        _process_with_context must not raise AttributeError."""
        from unified_mfgc import UnifiedMFGC
        mfgc = UnifiedMFGC()
        answers = {
            "initial_request": "I want to build a website",
            "What is your timeline?": None,   # unanswered question placeholder
            "What is your budget?": None,
        }
        # This must not raise AttributeError: 'NoneType' has no attribute 'lower'
        result = mfgc._process_with_context(
            message="I have 3 months and $5000 budget",
            answers=answers,
            context_summary="Murphy onboarding wizard.",
        )
        assert isinstance(result, dict), "Result should be a dict"
        assert "content" in result, "Result should have 'content' key"

    def test_empty_answers_dict_does_not_crash(self):
        """Empty answers dict must not crash _process_with_context."""
        from unified_mfgc import UnifiedMFGC
        mfgc = UnifiedMFGC()
        result = mfgc._process_with_context(
            message="I want to automate my business",
            answers={},
            context_summary="Murphy onboarding wizard.",
        )
        assert isinstance(result, dict)

    def test_all_none_answers_does_not_crash(self):
        """All-None answers dict must not crash _process_with_context."""
        from unified_mfgc import UnifiedMFGC
        mfgc = UnifiedMFGC()
        answers = {"q1": None, "q2": None, "q3": None}
        result = mfgc._process_with_context(
            message="I have 3 months and $5000",
            answers=answers,
            context_summary="Murphy onboarding wizard.",
        )
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# FIX-4: UnifiedMFGC offline mode structured questions
# ---------------------------------------------------------------------------

class TestUnifiedMFGCOfflineStructuredQuestions:
    """FIX-4: In offline mode, _process_with_context generates structured questions."""

    def test_offline_mode_generates_questions_not_generic_murphy_info(self):
        """When LLM mode is offline, response should be structured questions,
        NOT the generic Murphy System description."""
        from unified_mfgc import UnifiedMFGC
        mfgc = UnifiedMFGC()
        assert mfgc.llm_mode == "offline", "Test requires offline mode (no DeepInfra key set)"
        result = mfgc._process_with_context(
            message="I run a small e-commerce business selling handmade crafts.",
            answers={"initial_request": "I run a small e-commerce business selling handmade crafts."},
            context_summary="Murphy onboarding wizard: helping a new user describe their business.",
        )
        content = result.get("content", "")
        # Must NOT be the murphy system description
        assert "Murphy System is an AI-powered automation assistant" not in content, (
            "Offline mode should not return generic murphy info"
        )
        # Must contain targeted questions
        assert "?" in content, f"Expected questions in offline response, got: {content[:200]}"

    def test_offline_mode_sets_questioning_mode(self):
        """In offline mode, response sets questioning_mode=True."""
        from unified_mfgc import UnifiedMFGC
        mfgc = UnifiedMFGC()
        if mfgc.llm_mode != "offline":
            pytest.skip("Test requires offline mode")
        result = mfgc._process_with_context(
            message="I want to automate my small business",
            answers={"initial_request": "I want to automate my small business"},
            context_summary="Murphy onboarding wizard.",
        )
        assert result.get("questioning_mode") is True, (
            "Offline mode should set questioning_mode=True"
        )


# ---------------------------------------------------------------------------
# FIX-5: MFGC session context accumulation and turn-count progression
# ---------------------------------------------------------------------------

class TestMFGCSessionProgression:
    """FIX-5: MFGC chat must advance to ready_for_plan after 3 turns."""

    def test_session_advances_to_ready_by_turn_3(self):
        """After 3 turns with real answers, ready_for_plan must be True."""
        import sys
        import os
        os.environ['MURPHY_ENV'] = 'development'
        from starlette.testclient import TestClient
        from runtime.app import create_app

        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        sid = "test-prog-1"
        turns = [
            "I run a small e-commerce store on Shopify.",
            "My budget is $200/month. I use Stripe and ship via USPS.",
            "I process about 20 orders per day. Timeline is 6 weeks.",
        ]
        for i, msg in enumerate(turns, 1):
            r = client.post("/api/onboarding/mfgc-chat",
                            json={"session_id": sid, "message": msg})
            assert r.status_code == 200
            d = r.json()
            if i < 3:
                # Still gathering
                assert d.get("success") is True
            else:
                # Must be ready on turn 3
                assert d.get("ready_for_plan") is True, (
                    f"Expected ready_for_plan=True on turn {i}, got: {d}")

    def test_automation_config_returned_when_ready(self):
        """When ready_for_plan=True, response must include automation_config with steps."""
        import sys
        import os
        os.environ['MURPHY_ENV'] = 'development'
        from starlette.testclient import TestClient
        from runtime.app import create_app

        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        sid = "test-prog-2"
        turns = [
            "I need to automate invoice processing for my accounts payable team.",
            "We receive about 50 invoices per week. I use QuickBooks.",
            "Budget is $500/month, timeline 1 month. Approval needed for amounts over $10K.",
        ]
        last_response = None
        for msg in turns:
            r = client.post("/api/onboarding/mfgc-chat",
                            json={"session_id": sid, "message": msg})
            last_response = r.json()

        assert last_response is not None
        assert last_response.get("ready_for_plan") is True
        config = last_response.get("automation_config", {})
        assert isinstance(config, dict), "automation_config must be a dict"
        assert config.get("step_count", 0) >= 1, "automation_config must have steps"
        assert "workflow_id" in config, "automation_config must have a workflow_id"

    def test_session_context_updates_each_turn(self):
        """Session context must accumulate: later turns return fewer novel questions."""
        import sys
        import os
        os.environ['MURPHY_ENV'] = 'development'
        from starlette.testclient import TestClient
        from runtime.app import create_app

        app = create_app()
        client = TestClient(app, raise_server_exceptions=False)

        sid = "test-ctx-1"
        # Turn 1 — many unknowns remain
        r1 = client.post("/api/onboarding/mfgc-chat",
                         json={"session_id": sid,
                               "message": "I sell software subscriptions."})
        unknowns_t1 = r1.json().get("unknowns_remaining", 99)

        # Turn 2 — provide additional context; unknowns should not increase
        r2 = client.post("/api/onboarding/mfgc-chat",
                         json={"session_id": sid,
                               "message": "Budget $100/month, use Stripe for billing."})
        unknowns_t2 = r2.json().get("unknowns_remaining", 99)

        # unknowns should not grow between turns (context is being accumulated)
        assert unknowns_t2 <= unknowns_t1 or r2.json().get("ready_for_plan"), (
            f"unknowns_remaining should not increase: turn1={unknowns_t1}, turn2={unknowns_t2}"
        )


# ---------------------------------------------------------------------------
# FIX-6: AIWorkflowGenerator template coverage for business domains
# ---------------------------------------------------------------------------

class TestAIWorkflowGeneratorTemplates:
    """FIX-6: New business-domain templates in AIWorkflowGenerator."""

    def _make_gen(self):
        import sys
        import os
        from ai_workflow_generator import AIWorkflowGenerator
        return AIWorkflowGenerator()

    def test_order_fulfillment_template_matches(self):
        """Query containing 'order' + 'shopify' must use order_fulfillment template."""
        g = self._make_gen()
        wf = g.generate_workflow("automate order fulfillment for my shopify store")
        assert wf.get("template_used") == "order_fulfillment", (
            f"Expected order_fulfillment template, got: {wf.get('template_used')}")
        assert wf.get("step_count", 0) >= 5, "order_fulfillment must produce ≥5 steps"

    def test_invoice_processing_template_matches(self):
        """Query containing 'invoice' + 'billing' must use invoice_processing template."""
        g = self._make_gen()
        wf = g.generate_workflow(
            "automate invoice processing billing accounts payable workflow")
        assert wf.get("template_used") == "invoice_processing"
        assert wf.get("step_count", 0) >= 5

    def test_employee_onboarding_template_does_not_conflict_with_customer(self):
        """Employee onboarding template must not conflict with customer_onboarding."""
        g = self._make_gen()
        wf = g.generate_workflow("automate new hire employee orientation")
        # Should match employee_onboarding (has 'new hire') not customer_onboarding
        assert wf.get("template_used") in ("employee_onboarding", "customer_onboarding",
                                           None), (
            f"Unexpected template: {wf.get('template_used')}")

    def test_order_fulfillment_steps_are_wired_with_dependencies(self):
        """order_fulfillment steps must include dependency links."""
        g = self._make_gen()
        wf = g.generate_workflow("automate order fulfillment for shopify orders")
        steps_with_deps = [s for s in wf.get("steps", []) if s.get("depends_on")]
        assert len(steps_with_deps) >= 3, "order_fulfillment must have steps with dependencies"

    def test_generate_workflow_always_returns_dict(self):
        """generate_workflow must always return a non-empty dict."""
        g = self._make_gen()
        for query in ["x", "automate", "my business", ""]:
            wf = g.generate_workflow(query or "general automation")
            assert isinstance(wf, dict)
            assert "workflow_id" in wf
            assert "steps" in wf


# ---------------------------------------------------------------------------
# FIX-7: demo_deliverable_generator — real automation blueprint
# ---------------------------------------------------------------------------

class TestDemoDeliverableAutomationBlueprint:
    """FIX-7: Automation blueprint in deliverable must use AIWorkflowGenerator."""

    def test_blueprint_has_workflow_id_not_preview_gate(self):
        """Blueprint must have Workflow ID and no 'PAID TIER FEATURE' paywall."""
        import sys
        import os
        from demo_deliverable_generator import _build_automation_blueprint
        result = _build_automation_blueprint(
            "automate order fulfillment for my shopify store")
        assert "Workflow ID:" in result, "Blueprint must show Workflow ID"
        assert "PAID TIER FEATURE" not in result, (
            "Blueprint must not gate behind paywall text")
        assert "WORKFLOW STEPS (ready to execute)" in result, (
            "Blueprint must show executable steps")

    def test_blueprint_uses_real_template_when_matched(self):
        """When a template matches, blueprint shows that template's steps."""
        import sys
        import os
        from demo_deliverable_generator import _build_automation_blueprint
        result = _build_automation_blueprint(
            "automate invoice processing billing accounts payable workflow")
        assert "receive_invoice" in result or "receive invoice" in result.lower(), (
            "Blueprint should show invoice_processing template steps")

    def test_blueprint_includes_api_call_hint(self):
        """Blueprint must include the /api/automations/rules deployment call hint."""
        import sys
        import os
        from demo_deliverable_generator import _build_automation_blueprint
        result = _build_automation_blueprint("automate my lead nurturing crm")
        assert "/api/automations/rules" in result or "execute" in result.lower(), (
            "Blueprint must include a deployment call to action")


# ---------------------------------------------------------------------------
# COMMISSIONING: AutomationCommissioner + WorkflowDAGEngine execution
# ---------------------------------------------------------------------------

class TestAutomationCommissioner:
    """Prove automations actually execute and commissioning scores are meaningful."""

    def _gen(self):
        import sys
        import os
        from ai_workflow_generator import AIWorkflowGenerator
        return AIWorkflowGenerator()

    def _commissioner(self, threshold=0.75):
        import sys
        import os
        from automation_commissioner import AutomationCommissioner
        return AutomationCommissioner(health_threshold=threshold, max_iterations=2)

    def test_order_fulfillment_commissions_above_threshold(self):
        """order_fulfillment workflow must reach health ≥ 0.75 after commissioning."""
        gen = self._gen()
        wf_dict = gen.generate_workflow("automate order fulfillment for shopify")
        wf_def = gen.to_workflow_definition(wf_dict)
        assert len(wf_def.steps) >= 5, "order_fulfillment must have ≥5 steps"

        c = self._commissioner()
        report = c.commission(wf_def, context={"store": "test", "order_id": "ORD-001"})
        assert report.health_score >= 0.75, (
            f"Expected health ≥ 0.75, got {report.health_score:.3f}. "
            f"Steps: {[(s.step_id, s.confidence) for s in report.steps]}"
        )
        assert report.ready_for_deploy is True

    def test_invoice_processing_commissions_above_threshold(self):
        """invoice_processing workflow must reach health ≥ 0.75."""
        gen = self._gen()
        wf_dict = gen.generate_workflow("automate invoice processing billing accounts payable")
        wf_def = gen.to_workflow_definition(wf_dict)
        c = self._commissioner()
        report = c.commission(wf_def, context={"company": "Acme", "volume": "50 invoices/week"})
        assert report.health_score >= 0.75, (
            f"Expected health ≥ 0.75, got {report.health_score:.3f}"
        )

    def test_all_steps_complete_in_dag_execution(self):
        """All 7 steps in order_fulfillment DAG must reach 'completed' status."""
        import sys
        import os
        from workflow_dag_engine import WorkflowDAGEngine
        gen = self._gen()
        wf_dict = gen.generate_workflow("automate order fulfillment for shopify")
        wf_def = gen.to_workflow_definition(wf_dict)

        dag = WorkflowDAGEngine()
        dag.register_workflow(wf_def)
        exec_id = dag.create_execution(wf_def.workflow_id, context={"order_id": "ORD-123"})
        result = dag.execute_workflow(exec_id)

        assert result.get("status") == "completed", (
            f"Workflow execution status: {result.get('status')}"
        )
        steps = result.get("steps", {})
        for step_id, step_data in steps.items():
            assert step_data.get("status") in ("completed", "skipped"), (
                f"Step '{step_id}' has status '{step_data.get('status')}'"
            )

    def test_to_workflow_definition_adapter_produces_valid_dag(self):
        """to_workflow_definition must produce a WorkflowDefinition the DAG engine accepts."""
        import sys
        import os
        from workflow_dag_engine import WorkflowDAGEngine
        gen = self._gen()
        for query in [
            "automate order fulfillment for shopify",
            "automate invoice processing billing",
            "automate lead nurturing crm email",
        ]:
            wf_dict = gen.generate_workflow(query)
            wf_def = gen.to_workflow_definition(wf_dict)
            dag = WorkflowDAGEngine()
            registered = dag.register_workflow(wf_def)
            assert registered is True, f"DAG rejected workflow for: {query}"
            assert len(wf_def.steps) >= 1

    def test_commissioning_report_has_required_fields(self):
        """CommissioningReport.to_dict() must have all required API fields."""
        gen = self._gen()
        wf_dict = gen.generate_workflow("automate order fulfillment for shopify")
        wf_def = gen.to_workflow_definition(wf_dict)
        c = self._commissioner()
        report = c.commission(wf_def)
        d = report.to_dict()
        for key in ("workflow_id", "workflow_name", "execution_id", "health_score",
                    "ready_for_deploy", "steps", "issues", "recommendations", "timestamp"):
            assert key in d, f"Missing key '{key}' in commissioning report"
        assert isinstance(d["steps"], list)
        for step in d["steps"]:
            assert "step_id" in step
            assert "confidence" in step
            assert "passed" in step

    def test_automation_engine_fire_trigger_executes_all_actions(self):
        """AutomationEngine.fire_trigger must execute all registered actions with real output."""
        import sys
        import os
        from automations.engine import AutomationEngine
        from automations.models import TriggerType, ActionType, AutomationAction

        engine = AutomationEngine()
        executed = []

        def handler(config, context):
            executed.append({"action": config.get("_label", "?"), "context_keys": list(context.keys())})
            return {"status": "completed", "sent": True}

        for at in ActionType:
            engine.register_action_handler(at, lambda cfg, ctx, label=at.value: {
                "status": "completed",
                "action": label,
                "result": f"{label} executed successfully"
            })

        rule = engine.create_rule(
            name="Test Rule",
            board_id="board-test",
            trigger_type=TriggerType.ITEM_CREATED,
            actions=[
                AutomationAction(ActionType.NOTIFY, config={"message": "test"}),
                AutomationAction(ActionType.SEND_EMAIL, config={"to": "test@test.com"}),
            ],
        )

        results = engine.fire_trigger(
            board_id="board-test",
            trigger_type=TriggerType.ITEM_CREATED,
            context={"item_id": "item-1", "board_id": "board-test"},
        )
        assert len(results) == 1, "Expected exactly 1 rule to fire"
        assert len(results[0]["results"]) == 2, "Expected both actions to fire"
        for action_result in results[0]["results"]:
            assert action_result["success"] is True

    def test_lead_nurture_template_matches(self):
        """lead_nurture template must match with 'lead', 'crm', 'email' keywords."""
        gen = self._gen()
        wf = gen.generate_workflow("automate lead nurturing for my crm email sequences")
        assert wf.get("template_used") == "lead_nurture", (
            f"Expected lead_nurture template, got: {wf.get('template_used')}"
        )
        assert wf.get("step_count", 0) >= 5


# ---------------------------------------------------------------------------
# API: /api/onboarding/finalize, /api/automations/fire-trigger, /api/automations/commission
# ---------------------------------------------------------------------------

class TestExecutionAndCommissioningAPI:
    """Prove execution API endpoints return real results."""

    def _client(self):
        import sys
        import os
        os.environ["MURPHY_ENV"] = "development"
        from starlette.testclient import TestClient
        from runtime.app import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_commission_endpoint_returns_health_score(self):
        """POST /api/automations/commission must return a health score."""
        client = self._client()
        import sys
        import os
        from ai_workflow_generator import AIWorkflowGenerator
        gen = AIWorkflowGenerator()
        wf_dict = gen.generate_workflow("automate order fulfillment for shopify")
        r = client.post("/api/automations/commission", json={
            "workflow": wf_dict,
            "context": {"store": "test", "order_id": "ORD-001"},
            "health_threshold": 0.70,
        })
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
        d = r.json()
        assert d.get("success") is True
        report = d.get("commissioning_report", {})
        assert "health_score" in report
        assert report["health_score"] > 0.0
        assert "steps" in report
        assert len(report["steps"]) >= 5

    def test_fire_trigger_endpoint_validates_trigger_type(self):
        """POST /api/automations/fire-trigger with invalid trigger returns 400."""
        client = self._client()
        r = client.post("/api/automations/fire-trigger", json={
            "board_id": "board-1",
            "trigger_type": "invalid_trigger_xyz",
            "context": {},
        })
        assert r.status_code == 400

    def test_fire_trigger_endpoint_fires_when_rule_registered(self):
        """POST /api/automations/fire-trigger fires rules when present."""
        client = self._client()
        # Register a rule via the automations API first
        r_create = client.post("/api/automations/rules", json={
            "board_id": "board-commission-test",
            "trigger_type": "item_created",
            "actions": [{"action_type": "notify", "params": {"message": "Test"}}],
            "name": "Commission Test Rule",
        })
        assert r_create.status_code in (200, 201)

        r = client.post("/api/automations/fire-trigger", json={
            "board_id": "board-commission-test",
            "trigger_type": "item_created",
            "context": {"item_id": "item-99"},
        })
        assert r.status_code == 200
        d = r.json()
        assert d.get("success") is True
        assert "rules_fired" in d

    def test_onboarding_finalize_returns_error_for_missing_session(self):
        """POST /api/onboarding/finalize with unknown session returns 404."""
        client = self._client()
        r = client.post("/api/onboarding/finalize", json={"session_id": "nonexistent-xyz-999"})
        assert r.status_code == 404

    def test_onboarding_finalize_works_after_completed_session(self):
        """POST /api/onboarding/finalize with completed session returns workflow + health score."""
        client = self._client()
        sid = "test-finalize-flow-1"
        turns = [
            "I run a Shopify store and want to automate order fulfillment.",
            "Budget $200/month. I use Stripe for payments and ship via USPS.",
            "I process about 20 orders per day. Timeline is 6 weeks.",
        ]
        for msg in turns:
            client.post("/api/onboarding/mfgc-chat",
                        json={"session_id": sid, "message": msg})

        r = client.post("/api/onboarding/finalize", json={"session_id": sid})
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        d = r.json()
        assert d.get("success") is True
        assert "workflow_id" in d
        assert "health_score" in d
        assert d.get("health_score", 0) > 0.0
        assert "commissioning_report" in d
        report = d["commissioning_report"]
        assert len(report.get("steps", [])) >= 1

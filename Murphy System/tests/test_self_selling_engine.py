"""Tests for self_selling_engine.py."""

from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------


from self_selling_engine import (
    BUSINESS_TYPE_CONSTRAINTS,
    ContractorAugmentedIntel,
    MurphySelfSellingEngine,
    OutreachMessage,
    ProspectOnboarder,
    ProspectProfile,
    SelfSellingMetrics,
    SelfSellingOutreach,
    SellCycleResult,
    TrialShadowDeployer,
)


# ---------------------------------------------------------------------------
# Helpers / stubs
# ---------------------------------------------------------------------------

def _make_alert_engine() -> Any:
    """Return a minimal AlertRulesEngine stub."""
    eng = MagicMock()
    eng.add_rule.return_value = None
    return eng


def _make_profile(**overrides) -> ProspectProfile:
    defaults = {
        "prospect_id": "p-001",
        "company_name": "Acme Consulting",
        "contact_name": "Jane Doe",
        "contact_email": "jane@acme.com",
        "business_type": "consulting",
        "industry": "professional_services",
        "estimated_revenue": "1m_10m",
        "tools_detected": ["hubspot", "slack"],
        "pain_points_inferred": ["slow_proposal_creation"],
        "automation_constraints": BUSINESS_TYPE_CONSTRAINTS["consulting"]["primary_constraints"],
        "constraint_alert_rules": ["r-001", "r-002"],
    }
    defaults.update(overrides)
    return ProspectProfile(**defaults)


# ---------------------------------------------------------------------------
# Tests: BUSINESS_TYPE_CONSTRAINTS registry
# ---------------------------------------------------------------------------

class TestBusinessTypeConstraintsRegistry(unittest.TestCase):

    REQUIRED_TYPES = [
        "consulting", "ecommerce", "law_firm", "restaurant", "real_estate",
        "medical_practice", "trades_contractor", "saas", "marketing_agency",
        "accounting_firm", "logistics", "education",
    ]

    def test_minimum_12_business_types(self):
        self.assertGreaterEqual(len(BUSINESS_TYPE_CONSTRAINTS), 12)

    def test_all_required_types_present(self):
        for bt in self.REQUIRED_TYPES:
            with self.subTest(bt=bt):
                self.assertIn(bt, BUSINESS_TYPE_CONSTRAINTS)

    def test_each_type_has_required_keys(self):
        for bt, data in BUSINESS_TYPE_CONSTRAINTS.items():
            with self.subTest(bt=bt):
                self.assertIn("display_name", data, "missing display_name")
                self.assertIn("revenue_model", data, "missing revenue_model")
                self.assertIn("primary_constraints", data, "missing primary_constraints")
                self.assertIn("automation_opportunities", data, "missing automation_opportunities")

    def test_each_constraint_has_metric_comparator_threshold(self):
        for bt, data in BUSINESS_TYPE_CONSTRAINTS.items():
            for c in data["primary_constraints"]:
                with self.subTest(bt=bt, metric=c.get("metric")):
                    self.assertIn("metric", c)
                    self.assertIn("comparator", c)
                    self.assertIn("threshold", c)
                    self.assertIn(c["comparator"], ("gte", "lte", "gt", "lt", "eq"))

    def test_thresholds_are_numeric(self):
        for bt, data in BUSINESS_TYPE_CONSTRAINTS.items():
            for c in data["primary_constraints"]:
                with self.subTest(bt=bt, metric=c.get("metric")):
                    self.assertIsInstance(c["threshold"], (int, float))

    def test_automation_opportunities_non_empty(self):
        for bt, data in BUSINESS_TYPE_CONSTRAINTS.items():
            with self.subTest(bt=bt):
                self.assertGreater(len(data["automation_opportunities"]), 0)


# ---------------------------------------------------------------------------
# Tests: ProspectProfile dataclass
# ---------------------------------------------------------------------------

class TestProspectProfile(unittest.TestCase):

    def test_basic_creation(self):
        p = _make_profile()
        self.assertEqual(p.company_name, "Acme Consulting")
        self.assertEqual(p.business_type, "consulting")

    def test_created_at_is_iso_string(self):
        p = _make_profile()
        # Should be parseable as ISO datetime
        datetime.fromisoformat(p.created_at)

    def test_constraint_alert_rules_list(self):
        p = _make_profile()
        self.assertIsInstance(p.constraint_alert_rules, list)


# ---------------------------------------------------------------------------
# Tests: ProspectOnboarder
# ---------------------------------------------------------------------------

class TestProspectOnboarder(unittest.TestCase):

    def setUp(self):
        self.alert_engine = _make_alert_engine()
        self.onboarder = ProspectOnboarder(alert_engine=self.alert_engine)

    def test_onboard_returns_profile(self):
        profile = self.onboarder.onboard(
            company_name="Acme Consulting",
            contact_name="Jane",
            contact_email="jane@acme.com",
        )
        self.assertIsInstance(profile, ProspectProfile)
        self.assertEqual(profile.company_name, "Acme Consulting")
        self.assertIsNotNone(profile.prospect_id)

    def test_inferred_business_type_law(self):
        profile = self.onboarder.onboard(
            company_name="Smith & Jones Law",
            contact_name="Bob",
            contact_email="bob@smithjones.com",
        )
        self.assertEqual(profile.business_type, "law_firm")

    def test_inferred_business_type_restaurant(self):
        profile = self.onboarder.onboard(
            company_name="The Corner Restaurant",
            contact_name="Alice",
            contact_email="alice@corner.com",
        )
        self.assertEqual(profile.business_type, "restaurant")

    def test_inferred_business_type_real_estate(self):
        profile = self.onboarder.onboard(
            company_name="Sunset Realty Group",
            contact_name="Carol",
            contact_email="carol@sunset.com",
        )
        self.assertEqual(profile.business_type, "real_estate")

    def test_inferred_business_type_saas(self):
        profile = self.onboarder.onboard(
            company_name="CloudSync Software",
            contact_name="Dave",
            contact_email="dave@cloudsync.com",
        )
        self.assertEqual(profile.business_type, "saas")

    def test_inferred_business_type_ecommerce(self):
        profile = self.onboarder.onboard(
            company_name="Best Online Store",
            contact_name="Eve",
            contact_email="eve@beststore.com",
        )
        self.assertEqual(profile.business_type, "ecommerce")

    def test_explicit_business_type_override(self):
        profile = self.onboarder.onboard(
            company_name="GenericCo",
            contact_name="Fred",
            contact_email="fred@generic.com",
            extra_context={"business_type": "medical_practice"},
        )
        self.assertEqual(profile.business_type, "medical_practice")

    def test_constraints_generated(self):
        profile = self.onboarder.onboard(
            company_name="Acme Consulting",
            contact_name="Jane",
            contact_email="jane@acme.com",
        )
        self.assertGreater(len(profile.automation_constraints), 0)

    def test_alert_rules_registered(self):
        profile = self.onboarder.onboard(
            company_name="Acme Consulting",
            contact_name="Jane",
            contact_email="jane@acme.com",
        )
        self.assertGreater(len(profile.constraint_alert_rules), 0)
        self.assertTrue(self.alert_engine.add_rule.called)

    def test_profile_stored_and_retrievable(self):
        profile = self.onboarder.onboard(
            company_name="StoredCo",
            contact_name="X",
            contact_email="x@stored.com",
        )
        retrieved = self.onboarder.get_profile(profile.prospect_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.company_name, "StoredCo")

    def test_list_profiles(self):
        for i in range(3):
            self.onboarder.onboard(
                company_name=f"Co{i}",
                contact_name=f"Person{i}",
                contact_email=f"p{i}@co.com",
            )
        all_profiles = self.onboarder.list_profiles()
        self.assertGreaterEqual(len(all_profiles), 3)

    def test_unknown_prospect_returns_none(self):
        result = self.onboarder.get_profile("nonexistent-id")
        self.assertIsNone(result)

    def test_pain_points_populated(self):
        profile = self.onboarder.onboard(
            company_name="Acme Consulting",
            contact_name="Jane",
            contact_email="jane@acme.com",
        )
        self.assertGreater(len(profile.pain_points_inferred), 0)

    def test_each_business_type_has_constraints(self):
        for bt in BUSINESS_TYPE_CONSTRAINTS:
            profile = self.onboarder.onboard(
                company_name=f"{bt.title()} Co",
                contact_name="Test",
                contact_email="test@test.com",
                extra_context={"business_type": bt},
            )
            with self.subTest(bt=bt):
                self.assertGreater(
                    len(profile.automation_constraints), 0,
                    f"No constraints generated for business type: {bt}",
                )


# ---------------------------------------------------------------------------
# Tests: SelfSellingOutreach
# ---------------------------------------------------------------------------

class TestSelfSellingOutreach(unittest.TestCase):

    def setUp(self):
        self.outreach = SelfSellingOutreach()
        self.profile = _make_profile()
        self.live_stats = {
            "emails_sent": 47,
            "texts_sent": 12,
            "state_changes": 83,
            "projects_active": 6,
            "deliverables_created": ["proposal_draft", "market_report"],
        }

    def test_compose_returns_outreach_message(self):
        msg = self.outreach.compose(self.profile, self.live_stats)
        self.assertIsInstance(msg, OutreachMessage)

    def test_message_contains_email_count(self):
        msg = self.outreach.compose(self.profile, self.live_stats)
        self.assertIn("47", msg.body)

    def test_message_contains_meta_proof(self):
        msg = self.outreach.compose(self.profile, self.live_stats)
        self.assertIn("No human at Inoni", msg.body)

    def test_message_contains_constraint_info(self):
        msg = self.outreach.compose(self.profile, self.live_stats)
        self.assertIn("billable utilization", msg.body.lower().replace("_", " "))

    def test_message_contains_trial_offer(self):
        msg = self.outreach.compose(self.profile, self.live_stats)
        self.assertIn("3 days", msg.body)

    def test_message_references_company_name(self):
        msg = self.outreach.compose(self.profile, self.live_stats)
        self.assertIn("Acme Consulting", msg.body)

    def test_send_marks_message_sent(self):
        msg = self.outreach.compose(self.profile, self.live_stats)
        sent = self.outreach.send(msg)
        self.assertTrue(sent.sent)
        self.assertIsNotNone(sent.sent_at)

    def test_send_connector_called(self):
        connector = MagicMock()
        msg = self.outreach.compose(self.profile, self.live_stats)
        self.outreach.send(msg, connector=connector)
        connector.execute_action.assert_called_once()
        call_args = connector.execute_action.call_args
        self.assertEqual(call_args[0][0], "send_email")

    def test_get_sent_messages(self):
        msg = self.outreach.compose(self.profile, self.live_stats)
        self.outreach.send(msg)
        self.assertEqual(len(self.outreach.get_sent_messages()), 1)

    def test_subject_contains_email_count(self):
        msg = self.outreach.compose(self.profile, self.live_stats)
        self.assertIn("47", msg.subject)

    def test_live_stats_snapshot_stored(self):
        msg = self.outreach.compose(self.profile, self.live_stats)
        self.assertEqual(msg.live_stats_snapshot["emails_sent"], 47)

    def test_compose_for_each_business_type(self):
        for bt in BUSINESS_TYPE_CONSTRAINTS:
            profile = _make_profile(
                business_type=bt,
                automation_constraints=BUSINESS_TYPE_CONSTRAINTS[bt]["primary_constraints"],
            )
            msg = self.outreach.compose(profile, self.live_stats)
            with self.subTest(bt=bt):
                self.assertIsInstance(msg, OutreachMessage)
                self.assertTrue(len(msg.body) > 100)


# ---------------------------------------------------------------------------
# Tests: TrialShadowDeployer
# ---------------------------------------------------------------------------

class TestTrialShadowDeployer(unittest.TestCase):

    def _make_shadow_integration(self):
        mock = MagicMock()
        agent = MagicMock()
        agent.agent_id = "shadow-agent-001"
        mock.create_shadow_agent.return_value = agent
        mock.observe_action.return_value = None
        mock.propose_automation.return_value = {"proposal": "automate_intake"}
        return mock

    def setUp(self):
        self.shadow_int = self._make_shadow_integration()
        self.deployer = TrialShadowDeployer(shadow_integration=self.shadow_int)
        self.profile = _make_profile()

    def test_deploy_returns_record(self):
        record = self.deployer.deploy("trial-001", self.profile)
        self.assertIn("shadow_agent_id", record)
        self.assertEqual(record["trial_id"], "trial-001")

    def test_deploy_calls_create_shadow_agent(self):
        self.deployer.deploy("trial-001", self.profile)
        self.shadow_int.create_shadow_agent.assert_called_once()

    def test_record_observation_increments_count(self):
        self.deployer.deploy("trial-001", self.profile)
        self.deployer.record_observation("trial-001", "email_processed", {"count": 1})
        self.assertEqual(self.deployer.get_observation_count("trial-001"), 1)

    def test_record_observation_unknown_trial_is_noop(self):
        # Should not raise
        self.deployer.record_observation("nonexistent", "action", {})

    def test_generate_proposal_returns_dict(self):
        self.deployer.deploy("trial-001", self.profile)
        proposal = self.deployer.generate_proposal("trial-001")
        self.assertIsNotNone(proposal)
        self.assertIsInstance(proposal, dict)

    def test_generate_proposal_unknown_trial_returns_none(self):
        result = self.deployer.generate_proposal("nonexistent-trial")
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# Tests: ContractorAugmentedIntel
# ---------------------------------------------------------------------------

class TestContractorAugmentedIntel(unittest.TestCase):

    def _make_hitl(self):
        return MagicMock()

    def _make_dispatch(self):
        mock = MagicMock()
        task = MagicMock()
        task.task_id = "task-001"
        mock.create_task.return_value = task
        return mock

    def setUp(self):
        self.hitl = self._make_hitl()
        self.dispatch = self._make_dispatch()
        self.intel = ContractorAugmentedIntel(
            hitl_bridge=self.hitl,
            dispatch_interface=self.dispatch,
        )
        self.profile = _make_profile()

    def test_request_market_data_returns_task_id(self):
        task_id = self.intel.request_market_data(
            self.profile, ["competitor_pricing", "market_size"]
        )
        self.assertIsNotNone(task_id)
        self.assertEqual(task_id, "task-001")

    def test_request_market_data_calls_create_task(self):
        self.intel.request_market_data(self.profile, ["competitor_pricing"])
        self.dispatch.create_task.assert_called_once()

    def test_on_contractor_delivery_returns_automation_ids(self):
        self.intel.request_market_data(self.profile, ["data1"])
        result = self.intel.on_contractor_delivery("task-001", {"data": "value"})
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_on_contractor_delivery_unknown_task_returns_empty(self):
        result = self.intel.on_contractor_delivery("unknown-task", {})
        self.assertEqual(result, [])

    def test_score_and_route_returns_pass(self):
        self.intel.request_market_data(self.profile, ["data"])
        scored = self.intel.score_and_route("task-001")
        self.assertEqual(scored["quality_gate"], "pass")
        self.assertIn("route", scored)

    def test_score_and_route_includes_prospect_id(self):
        self.intel.request_market_data(self.profile, ["data"])
        scored = self.intel.score_and_route("task-001")
        self.assertEqual(scored["prospect_id"], self.profile.prospect_id)


# ---------------------------------------------------------------------------
# Tests: SelfSellingMetrics
# ---------------------------------------------------------------------------

class TestSelfSellingMetrics(unittest.TestCase):

    def test_default_zeroes(self):
        m = SelfSellingMetrics()
        self.assertEqual(m.emails_sent, 0)
        self.assertEqual(m.texts_sent, 0)

    def test_to_dict(self):
        m = SelfSellingMetrics(emails_sent=5, texts_sent=2)
        d = m.to_dict()
        self.assertEqual(d["emails_sent"], 5)
        self.assertEqual(d["texts_sent"], 2)
        self.assertIn("state_changes", d)
        self.assertIn("deliverables_created", d)


# ---------------------------------------------------------------------------
# Tests: MurphySelfSellingEngine
# ---------------------------------------------------------------------------

class TestMurphySelfSellingEngine(unittest.TestCase):

    def _make_engine(self):
        alert_engine = _make_alert_engine()
        shadow_int = MagicMock()
        shadow_agent = MagicMock()
        shadow_agent.agent_id = "shadow-001"
        shadow_int.create_shadow_agent.return_value = shadow_agent
        shadow_int.observe_action.return_value = None
        shadow_int.propose_automation.return_value = {}

        dispatch = MagicMock()
        task = MagicMock()
        task.task_id = "task-001"
        dispatch.create_task.return_value = task

        engine = MurphySelfSellingEngine(
            alert_engine=alert_engine,
            shadow_integration=shadow_int,
            dispatch_interface=dispatch,
        )
        return engine

    def setUp(self):
        self.engine = self._make_engine()

    def test_run_selling_cycle_returns_result(self):
        result = self.engine.run_selling_cycle()
        self.assertIsInstance(result, SellCycleResult)
        self.assertIsNotNone(result.cycle_id)

    def test_run_selling_cycle_increments_cycles(self):
        self.engine.run_selling_cycle()
        self.assertEqual(self.engine.metrics.cycles_completed, 1)

    def test_get_live_system_stats_returns_dict(self):
        stats = self.engine.get_live_system_stats()
        self.assertIn("emails_sent", stats)
        self.assertIn("state_changes", stats)

    def test_compose_outreach_message_with_profile(self):
        profile = self.engine.prospect_onboarder.onboard(
            company_name="Acme Consulting",
            contact_name="Jane",
            contact_email="jane@acme.com",
        )
        msg = self.engine.compose_outreach_message(profile)
        self.assertIsInstance(msg, OutreachMessage)
        self.assertFalse(msg.sent)

    def test_handle_prospect_reply_unknown_prospect(self):
        result = self.engine.handle_prospect_reply("nonexistent", "yes interested")
        self.assertEqual(result, "unknown_prospect")

    def test_handle_prospect_reply_negative_routes_to_nurture(self):
        profile = self.engine.prospect_onboarder.onboard(
            company_name="NurtureCo",
            contact_name="X",
            contact_email="x@nurture.com",
        )
        result = self.engine.handle_prospect_reply(
            profile.prospect_id, "not interested right now"
        )
        self.assertEqual(result, "nurture")

    def test_handle_prospect_reply_positive_starts_trial(self):
        profile = self.engine.prospect_onboarder.onboard(
            company_name="ReadyCo",
            contact_name="Y",
            contact_email="y@ready.com",
        )
        result = self.engine.handle_prospect_reply(
            profile.prospect_id, "Yes, sign me up for the free trial!"
        )
        self.assertIn(result, ("trial_started", "nurture"))  # nurture if trial raises

    def test_positive_reply_signals(self):
        positive_replies = [
            "Yes I'm interested",
            "Sounds good, let's do it",
            "Tell me more please",
            "Sign me up",
            "Sure, go ahead",
        ]
        for reply in positive_replies:
            with self.subTest(reply=reply):
                self.assertTrue(MurphySelfSellingEngine._is_positive_reply(reply))

    def test_negative_reply_signals(self):
        negative_replies = [
            "No thanks",
            "Not interested",
            "Please remove me from your list",
        ]
        for reply in negative_replies:
            with self.subTest(reply=reply):
                self.assertFalse(MurphySelfSellingEngine._is_positive_reply(reply))


if __name__ == "__main__":
    unittest.main()

"""Tests for the sales_automation module."""

import unittest

from sales_automation import (
    INDUSTRY_FEATURES,
    VALID_STATUSES,
    LeadProfile,
    SalesAutomationConfig,
    SalesAutomationEngine,
)


def _make_lead(**overrides) -> LeadProfile:
    defaults = {
        "company_name": "Acme Corp",
        "contact_name": "Jane Doe",
        "contact_email": "jane@acme.com",
        "industry": "manufacturing",
        "company_size": "medium",
        "interests": ["robotics integration", "predictive maintenance"],
    }
    defaults.update(overrides)
    return LeadProfile(**defaults)


class TestSalesAutomationConfig(unittest.TestCase):
    def test_default_config(self):
        cfg = SalesAutomationConfig()
        self.assertEqual(cfg.company_name, "Inoni LLC")
        self.assertEqual(cfg.product_name, "murphy_system")
        self.assertTrue(cfg.demo_mode_enabled)
        self.assertEqual(len(cfg.editions), 3)
        self.assertIn("website", cfg.sales_channels)

    def test_custom_config(self):
        cfg = SalesAutomationConfig(company_name="TestCo", demo_mode_enabled=False)
        self.assertEqual(cfg.company_name, "TestCo")
        self.assertFalse(cfg.demo_mode_enabled)


class TestLeadProfile(unittest.TestCase):
    def test_lead_creation(self):
        lead = _make_lead()
        self.assertEqual(lead.company_name, "Acme Corp")
        self.assertEqual(lead.status, "new")
        self.assertIsNotNone(lead.lead_id)
        self.assertIsNotNone(lead.created_at)
        self.assertEqual(lead.score, 0.0)

    def test_lead_registration(self):
        engine = SalesAutomationEngine()
        lead = _make_lead()
        lid = engine.register_lead(lead)
        self.assertEqual(lid, lead.lead_id)
        self.assertIn(lid, engine._pipeline)


class TestLeadScoring(unittest.TestCase):
    def test_score_small_company(self):
        engine = SalesAutomationEngine()
        lead = _make_lead(company_size="small", industry="manufacturing", interests=[])
        score = engine.score_lead(lead)
        # small=10 + industry_match=20 + interests=0 = 30
        self.assertEqual(score, 30)

    def test_score_medium_company(self):
        engine = SalesAutomationEngine()
        lead = _make_lead(company_size="medium", industry="technology", interests=["a", "b"])
        score = engine.score_lead(lead)
        # medium=30 + industry=20 + interests=10 = 60
        self.assertEqual(score, 60)

    def test_score_enterprise_company(self):
        engine = SalesAutomationEngine()
        lead = _make_lead(company_size="enterprise", industry="finance", interests=["a"])
        score = engine.score_lead(lead)
        # enterprise=50 + industry=20 + interests=5 = 75
        self.assertEqual(score, 75)

    def test_score_non_target_industry(self):
        engine = SalesAutomationEngine()
        lead = _make_lead(company_size="small", industry="agriculture", interests=[])
        score = engine.score_lead(lead)
        # small=10 + no industry match + 0 interests = 10
        self.assertEqual(score, 10)

    def test_score_interests_capped(self):
        engine = SalesAutomationEngine()
        lead = _make_lead(
            company_size="small",
            industry="agriculture",
            interests=[f"i{n}" for n in range(10)],
        )
        score = engine.score_lead(lead)
        # small=10 + 0 + min(50,30)=30 => 40
        self.assertEqual(score, 40)


class TestLeadQualification(unittest.TestCase):
    def test_qualified_lead(self):
        engine = SalesAutomationEngine()
        lead = _make_lead(company_size="enterprise", industry="technology")
        result = engine.qualify_lead(lead)
        self.assertTrue(result["qualified"])
        self.assertEqual(lead.status, "qualified")

    def test_unqualified_lead(self):
        engine = SalesAutomationEngine()
        lead = _make_lead(company_size="small", industry="agriculture", interests=[])
        result = engine.qualify_lead(lead)
        self.assertFalse(result["qualified"])
        self.assertEqual(lead.status, "not_qualified")


class TestEditionRecommendation(unittest.TestCase):
    def test_small_gets_community(self):
        engine = SalesAutomationEngine()
        self.assertEqual(engine.recommend_edition(_make_lead(company_size="small")), "community")

    def test_medium_gets_professional(self):
        engine = SalesAutomationEngine()
        self.assertEqual(engine.recommend_edition(_make_lead(company_size="medium")), "professional")

    def test_enterprise_gets_enterprise(self):
        engine = SalesAutomationEngine()
        self.assertEqual(engine.recommend_edition(_make_lead(company_size="enterprise")), "enterprise")


class TestDemoScript(unittest.TestCase):
    def test_demo_script_structure(self):
        engine = SalesAutomationEngine()
        lead = _make_lead(industry="manufacturing")
        script = engine.generate_demo_script(lead)
        self.assertIn("greeting", script)
        self.assertIn("feature_highlights", script)
        self.assertIn("demo_steps", script)
        self.assertIn("closing", script)
        self.assertIsInstance(script["demo_steps"], list)

    def test_demo_script_personalisation(self):
        engine = SalesAutomationEngine()
        lead = _make_lead(industry="finance")
        script = engine.generate_demo_script(lead)
        self.assertIn("finance", script["greeting"])
        self.assertIn("trading bot", script["feature_highlights"])


class TestProposal(unittest.TestCase):
    def test_proposal_structure(self):
        engine = SalesAutomationEngine()
        lead = _make_lead(company_size="enterprise", industry="healthcare")
        proposal = engine.generate_proposal(lead)
        for key in ("executive_summary", "recommended_edition", "features_included",
                     "pricing", "implementation_plan", "timeline"):
            self.assertIn(key, proposal)

    def test_proposal_edition_and_pricing(self):
        engine = SalesAutomationEngine()
        lead = _make_lead(company_size="medium")
        proposal = engine.generate_proposal(lead)
        self.assertEqual(proposal["recommended_edition"], "professional")
        self.assertEqual(proposal["pricing"], "Per-Seat")


class TestPipelineAndAdvancement(unittest.TestCase):
    def test_pipeline_summary(self):
        engine = SalesAutomationEngine()
        engine.register_lead(_make_lead())
        engine.register_lead(_make_lead(company_name="Beta Inc"))
        summary = engine.get_pipeline_summary()
        self.assertEqual(summary["total_leads"], 2)
        self.assertEqual(len(summary["by_status"]["new"]), 2)

    def test_advance_lead(self):
        engine = SalesAutomationEngine()
        lead = _make_lead()
        engine.register_lead(lead)
        self.assertTrue(engine.advance_lead(lead.lead_id, "qualified"))
        self.assertEqual(lead.status, "qualified")

    def test_advance_lead_invalid_status(self):
        engine = SalesAutomationEngine()
        lead = _make_lead()
        engine.register_lead(lead)
        self.assertFalse(engine.advance_lead(lead.lead_id, "bogus_status"))

    def test_advance_lead_missing_id(self):
        engine = SalesAutomationEngine()
        self.assertFalse(engine.advance_lead("nonexistent", "qualified"))


class TestFeatureHighlights(unittest.TestCase):
    def test_known_industries(self):
        engine = SalesAutomationEngine()
        for industry, expected in INDUSTRY_FEATURES.items():
            self.assertEqual(engine.get_feature_highlights(industry), expected)

    def test_unknown_industry_fallback(self):
        engine = SalesAutomationEngine()
        highlights = engine.get_feature_highlights("agriculture")
        self.assertIsInstance(highlights, list)
        self.assertTrue(len(highlights) > 0)


if __name__ == "__main__":
    unittest.main()

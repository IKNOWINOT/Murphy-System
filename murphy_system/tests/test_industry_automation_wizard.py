"""
Tests for Industry Automation Wizard module
"""
import sys
import unittest
from pathlib import Path
import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from industry_automation_wizard import (
    IndustryAutomationWizard,
    IndustryType,
    AUTOMATION_CATALOG,
    QUESTION_BANK,
    AutomationType,
    IndustryWizardQuestion,
    IndustryAutomationSpec,
    IndustryAutomationSession
)

pytestmark = [pytest.mark.timeout(30)]


class TestAutomationCatalog(unittest.TestCase):
    def test_all_10_industries_present(self):
        """Test all 10 industries are in catalog"""
        expected_industries = [
            IndustryType.TECHNOLOGY,
            IndustryType.HEALTHCARE,
            IndustryType.FINANCE,
            IndustryType.RETAIL,
            IndustryType.MANUFACTURING,
            IndustryType.EDUCATION,
            IndustryType.PROFESSIONAL_SERVICES,
            IndustryType.MEDIA,
            IndustryType.NONPROFIT,
            IndustryType.OTHER
        ]
        
        for industry in expected_industries:
            self.assertIn(industry, AUTOMATION_CATALOG)
    
    def test_each_has_at_least_5_automation_types(self):
        """Test each industry has at least 5 automation types"""
        for industry, automations in AUTOMATION_CATALOG.items():
            self.assertGreaterEqual(len(automations), 5, f"{industry.value} has less than 5 automation types")
    
    def test_manufacturing_has_bas_subtypes(self):
        """Test MANUFACTURING has BAS/EMS sub-types"""
        manufacturing_types = AUTOMATION_CATALOG[IndustryType.MANUFACTURING]
        type_ids = [at.type_id for at in manufacturing_types]
        
        bas_types = ["bas_energy_management", "bas_hvac_control", "industrial_plc_integration"]
        for bas_type in bas_types:
            self.assertIn(bas_type, type_ids)


class TestSessionCreation(unittest.TestCase):
    def test_create_with_industry_preset(self):
        """Test creating session with industry pre-set"""
        wizard = IndustryAutomationWizard()
        session = wizard.create_session(industry="Technology")
        
        self.assertEqual(session.industry, "Technology")
        self.assertIsNotNone(session.session_id)
    
    def test_create_with_onboarding_context(self):
        """Test creating session with onboarding context"""
        wizard = IndustryAutomationWizard()
        context = {"team_size": "10-50", "tools": "github,slack"}
        session = wizard.create_session(onboarding_context=context)
        
        self.assertEqual(session.onboarding_context, context)
    
    def test_create_without_anything_asks_industry_first(self):
        """Test creating session without anything asks industry first"""
        wizard = IndustryAutomationWizard()
        session = wizard.create_session()
        
        next_q = wizard.next_question(session.session_id)
        
        self.assertIsNotNone(next_q)
        self.assertEqual(next_q["question_id"], "industry_selection")


class TestQuestionFlow(unittest.TestCase):
    def test_can_complete_session_with_minimal_answers_technology(self):
        """Test can complete session for Technology"""
        self._test_industry("Technology")
    
    def test_can_complete_session_with_minimal_answers_healthcare(self):
        """Test can complete session for Healthcare"""
        self._test_industry("Healthcare")
    
    def test_can_complete_session_with_minimal_answers_finance(self):
        """Test can complete session for Finance"""
        self._test_industry("Finance")
    
    def test_can_complete_session_with_minimal_answers_retail(self):
        """Test can complete session for Retail"""
        self._test_industry("Retail")
    
    def test_can_complete_session_with_minimal_answers_manufacturing(self):
        """Test can complete session for Manufacturing"""
        self._test_industry("Manufacturing")
    
    def _test_industry(self, industry):
        """Helper to test an industry"""
        wizard = IndustryAutomationWizard()
        session = wizard.create_session()
        
        # Answer industry
        wizard.answer(session.session_id, "industry_selection", industry)
        
        # Answer automation type (use first available)
        automation_types = wizard.get_automation_types(industry)
        if automation_types:
            wizard.answer(session.session_id, "automation_type_selection", automation_types[0]["id"])
        
        # Answer required universal questions
        wizard.answer(session.session_id, "goal", "Reduce manual work")
        wizard.answer(session.session_id, "stakeholders", "Team leads")
        wizard.answer(session.session_id, "timeline", "Short-term (1 month)")
        
        # Should be able to generate spec
        spec = wizard.generate_spec(session.session_id)
        
        self.assertIsNotNone(spec)
        self.assertEqual(spec.industry, industry)
    
    def test_next_question_returns_none_when_done(self):
        """Test next_question returns None when all answered"""
        wizard = IndustryAutomationWizard()
        session = wizard.create_session(industry="Technology", automation_type="ci_cd_pipeline")
        
        # Answer all required questions
        wizard.answer(session.session_id, "goal", "Improve accuracy")
        wizard.answer(session.session_id, "stakeholders", "Engineers")
        wizard.answer(session.session_id, "timeline", "Immediate (1-2 weeks)")
        
        # Keep answering until no more questions
        while True:
            next_q = wizard.next_question(session.session_id)
            if next_q is None:
                break
            # Answer with first option or empty
            answer = next_q["options"][0] if next_q.get("options") else "test"
            wizard.answer(session.session_id, next_q["question_id"], answer)
        
        final_q = wizard.next_question(session.session_id)
        self.assertIsNone(final_q)


class TestInlineRecommendations(unittest.TestCase):
    def test_every_question_with_recommendation_returns_it(self):
        """Test questions with recommendations return them"""
        wizard = IndustryAutomationWizard()
        session = wizard.create_session()
        
        next_q = wizard.next_question(session.session_id)
        
        self.assertIn("recommendation", next_q)
        self.assertIsInstance(next_q["recommendation"], str)
    
    def test_bas_questions_include_ashrae_reference(self):
        """Test BAS questions include ASHRAE references"""
        wizard = IndustryAutomationWizard()
        session = wizard.create_session(industry="Manufacturing", automation_type="bas_energy_management")
        
        # Answer initial questions
        wizard.answer(session.session_id, "goal", "Reduce energy costs")
        wizard.answer(session.session_id, "stakeholders", "Facility managers")
        wizard.answer(session.session_id, "timeline", "Medium-term (3 months)")
        
        # Generate spec to get all recommendations
        spec = wizard.generate_spec(session.session_id)
        
        # Check for ASHRAE in recommendations (from automation type or added during spec generation)
        has_ashrae = any("ASHRAE" in r for r in spec.recommendations)
        
        self.assertTrue(has_ashrae)


class TestOnboardingContextInjection(unittest.TestCase):
    def test_prefilled_from_onboarding_context(self):
        """Test questions are pre-filled from onboarding context"""
        wizard = IndustryAutomationWizard()
        context = {"team_size": "10-50"}
        session = wizard.create_session(onboarding_context=context)
        
        # Check if any questions were pre-filled
        self.assertIsNotNone(session.pre_filled)
    
    def test_prefilled_questions_are_skipped(self):
        """Test pre-filled questions are skipped"""
        wizard = IndustryAutomationWizard()
        session = wizard.create_session(industry="Technology")
        
        # Industry is pre-filled, so first question should be automation_type
        next_q = wizard.next_question(session.session_id)
        
        self.assertNotEqual(next_q["question_id"], "industry_selection")
    
    def test_onboarding_context_used_populated_in_spec(self):
        """Test onboarding_context_used is populated in spec"""
        wizard = IndustryAutomationWizard()
        context = {"team_size": "10-50", "tools": "github"}
        session = wizard.create_session(industry="Technology", automation_type="ci_cd_pipeline", onboarding_context=context)
        
        wizard.answer(session.session_id, "goal", "Automate")
        wizard.answer(session.session_id, "stakeholders", "Engineers")
        wizard.answer(session.session_id, "timeline", "Short-term (1 month)")
        
        spec = wizard.generate_spec(session.session_id)
        
        self.assertIsNotNone(spec.onboarding_context_used)


class TestBASFlow(unittest.TestCase):
    def test_bas_energy_management_includes_equipment_questions(self):
        """Test BAS energy management includes equipment-related questions"""
        wizard = IndustryAutomationWizard()
        session = wizard.create_session(industry="Manufacturing", automation_type="bas_energy_management")
        
        wizard.answer(session.session_id, "goal", "Energy monitoring")
        wizard.answer(session.session_id, "stakeholders", "Facility team")
        wizard.answer(session.session_id, "timeline", "Medium-term (3 months)")
        
        # Look for equipment-related questions
        equipment_question_found = False
        for _ in range(10):  # Check next several questions
            next_q = wizard.next_question(session.session_id)
            if next_q is None:
                break
            if "equipment" in next_q["question_id"].lower() or "protocol" in next_q["question_id"].lower():
                equipment_question_found = True
                break
            # Answer to move forward
            answer = next_q["options"][0] if next_q.get("options") else "test"
            wizard.answer(session.session_id, next_q["question_id"], answer)
        
        self.assertTrue(equipment_question_found)
    
    def test_generate_spec_includes_equipment_recommendations(self):
        """Test BAS spec includes equipment-specific recommendations"""
        wizard = IndustryAutomationWizard()
        session = wizard.create_session(industry="Manufacturing", automation_type="bas_hvac_control")
        
        wizard.answer(session.session_id, "goal", "HVAC optimization")
        wizard.answer(session.session_id, "stakeholders", "Building ops")
        wizard.answer(session.session_id, "timeline", "Long-term (6+ months)")
        
        spec = wizard.generate_spec(session.session_id)
        
        self.assertIsNotNone(spec)
        self.assertGreater(len(spec.recommendations), 0)


class TestSpecGeneration(unittest.TestCase):
    def test_spec_has_all_required_fields(self):
        """Test generated spec has all required fields"""
        wizard = IndustryAutomationWizard()
        session = wizard.create_session(industry="Technology", automation_type="code_review_automation")
        
        wizard.answer(session.session_id, "goal", "Improve code quality")
        wizard.answer(session.session_id, "stakeholders", "Developers")
        wizard.answer(session.session_id, "timeline", "Immediate (1-2 weeks)")
        
        spec = wizard.generate_spec(session.session_id)
        
        self.assertIsNotNone(spec.spec_id)
        self.assertIsNotNone(spec.industry)
        self.assertIsNotNone(spec.automation_type)
        self.assertIsNotNone(spec.title)
        self.assertIsNotNone(spec.workflow_steps)
        self.assertIsNotNone(spec.recommendations)
    
    def test_workflow_steps_non_empty(self):
        """Test workflow steps is non-empty"""
        wizard = IndustryAutomationWizard()
        session = wizard.create_session(industry="Healthcare", automation_type="patient_intake")
        
        wizard.answer(session.session_id, "goal", "Streamline intake")
        wizard.answer(session.session_id, "stakeholders", "Front desk")
        wizard.answer(session.session_id, "timeline", "Medium-term (3 months)")
        
        spec = wizard.generate_spec(session.session_id)
        
        self.assertGreater(len(spec.workflow_steps), 0)
    
    def test_to_dict_serializable(self):
        """Test spec to_dict is serializable"""
        wizard = IndustryAutomationWizard()
        session = wizard.create_session(industry="Finance", automation_type="fraud_detection")
        
        wizard.answer(session.session_id, "goal", "Detect fraud")
        wizard.answer(session.session_id, "stakeholders", "Security team")
        wizard.answer(session.session_id, "timeline", "Short-term (1 month)")
        
        spec = wizard.generate_spec(session.session_id)
        spec_dict = spec.to_dict()
        
        self.assertIn("spec_id", spec_dict)
        self.assertIn("workflow_steps", spec_dict)
        self.assertIsInstance(spec_dict, dict)
    
    def test_estimated_setup_time_set(self):
        """Test estimated_setup_time is set"""
        wizard = IndustryAutomationWizard()
        session = wizard.create_session(industry="Retail", automation_type="inventory_management")
        
        wizard.answer(session.session_id, "goal", "Track inventory")
        wizard.answer(session.session_id, "stakeholders", "Warehouse staff")
        wizard.answer(session.session_id, "timeline", "Short-term (1 month)")
        
        spec = wizard.generate_spec(session.session_id)
        
        self.assertIsNotNone(spec.estimated_setup_time)
        self.assertGreater(len(spec.estimated_setup_time), 0)


class TestGetAutomationTypes(unittest.TestCase):
    def test_returns_list_for_technology(self):
        """Test returns automation types list for Technology"""
        wizard = IndustryAutomationWizard()
        types = wizard.get_automation_types("Technology")
        
        self.assertIsInstance(types, list)
        self.assertGreater(len(types), 0)
        self.assertIn("id", types[0])
        self.assertIn("name", types[0])
    
    def test_returns_list_for_healthcare(self):
        """Test returns automation types list for Healthcare"""
        wizard = IndustryAutomationWizard()
        types = wizard.get_automation_types("Healthcare")
        
        self.assertGreater(len(types), 0)
    
    def test_unknown_industry_returns_empty_list(self):
        """Test unknown industry returns empty list"""
        wizard = IndustryAutomationWizard()
        types = wizard.get_automation_types("UnknownIndustry")
        
        self.assertEqual(len(types), 0)


class TestGetRecommendations(unittest.TestCase):
    def test_returns_list_of_strings(self):
        """Test get_recommendations returns list of strings"""
        wizard = IndustryAutomationWizard()
        session = wizard.create_session(industry="Education", automation_type="grade_automation")
        
        wizard.answer(session.session_id, "goal", "Automate grading")
        wizard.answer(session.session_id, "stakeholders", "Teachers")
        
        recs = wizard.get_recommendations(session.session_id)
        
        self.assertIsInstance(recs, list)
        for rec in recs:
            self.assertIsInstance(rec, str)
    
    def test_non_empty_after_answering_questions(self):
        """Test recommendations non-empty after answering questions"""
        wizard = IndustryAutomationWizard()
        session = wizard.create_session(industry="Media", automation_type="content_publishing_workflow")
        
        wizard.answer(session.session_id, "goal", "Streamline publishing")
        wizard.answer(session.session_id, "stakeholders", "Content team")
        wizard.answer(session.session_id, "timeline", "Short-term (1 month)")
        
        recs = wizard.get_recommendations(session.session_id)
        
        self.assertGreater(len(recs), 0)


class TestParametrizedIndustries(unittest.TestCase):
    """Parametrized test for all 10 industries"""
    
    def test_all_industries_create_session(self):
        """Test all 10 industries can create session and generate spec"""
        industries = [
            "Technology", "Healthcare", "Finance", "Retail", "Manufacturing",
            "Education", "Professional Services", "Media", "Nonprofit", "Other"
        ]
        
        for industry in industries:
            with self.subTest(industry=industry):
                wizard = IndustryAutomationWizard()
                session = wizard.create_session(industry=industry)
                
                # Get automation types
                types = wizard.get_automation_types(industry)
                self.assertGreater(len(types), 0, f"{industry} has no automation types")
                
                # Select first automation type
                wizard.answer(session.session_id, "automation_type_selection", types[0]["id"])
                
                # Answer required questions
                wizard.answer(session.session_id, "goal", "Test goal")
                wizard.answer(session.session_id, "stakeholders", "Test stakeholders")
                wizard.answer(session.session_id, "timeline", "Short-term (1 month)")
                
                # Generate spec
                spec = wizard.generate_spec(session.session_id)
                
                self.assertIsNotNone(spec)
                self.assertEqual(spec.industry, industry)


if __name__ == "__main__":
    unittest.main()

"""Tests for AutomationTypeRegistry."""

import os
import unittest


from automation_type_registry import (
    AutomationTypeRegistry,
    AutomationTemplate,
    AutomationCategory,
    ComplexityLevel,
)


class TestAutomationTypeRegistry(unittest.TestCase):

    def setUp(self):
        self.registry = AutomationTypeRegistry()

    def test_default_templates_registered(self):
        templates = self.registry.list_templates()
        self.assertGreater(len(templates), 10)

    def test_list_templates_by_category(self):
        it = self.registry.list_templates(AutomationCategory.IT_OPERATIONS)
        self.assertGreater(len(it), 0)
        for t in it:
            self.assertEqual(t["category"], "it_operations")

    def test_get_template(self):
        t = self.registry.get_template("it_incident_response")
        self.assertIsNotNone(t)
        self.assertEqual(t.name, "IT Incident Response")

    def test_get_template_not_found(self):
        self.assertIsNone(self.registry.get_template("nonexistent"))

    def test_register_custom_template(self):
        template = AutomationTemplate(
            template_id="custom_task",
            name="Custom Task",
            category=AutomationCategory.CUSTOM,
            description="A custom automation",
            complexity=ComplexityLevel.SIMPLE,
        )
        self.assertTrue(self.registry.register_template(template))
        self.assertIsNotNone(self.registry.get_template("custom_task"))

    def test_list_categories(self):
        categories = self.registry.list_categories()
        self.assertGreater(len(categories), 5)
        category_names = [c["category"] for c in categories]
        for expected in ["it_operations", "business_process", "marketing", "security", "devops"]:
            self.assertIn(expected, category_names)

    def test_templates_for_platform(self):
        slack_templates = self.registry.get_templates_for_platform("slack")
        self.assertGreater(len(slack_templates), 0)

    def test_templates_for_github(self):
        gh_templates = self.registry.get_templates_for_platform("github")
        self.assertGreater(len(gh_templates), 0)

    def test_required_platforms(self):
        platforms = self.registry.get_required_platforms()
        self.assertIn("slack", platforms)
        self.assertIn("github", platforms)

    def test_record_execution(self):
        self.registry.record_execution("it_incident_response")
        self.registry.record_execution("it_incident_response")
        stats = self.registry.get_statistics()
        self.assertEqual(stats["total_executions"], 2)
        self.assertGreater(len(stats["most_used"]), 0)

    def test_hitl_templates_counted(self):
        stats = self.registry.get_statistics()
        self.assertGreater(stats["hitl_required_templates"], 0)

    def test_critical_templates_counted(self):
        stats = self.registry.get_statistics()
        self.assertGreater(stats["critical_templates"], 0)

    def test_compliance_frameworks(self):
        t = self.registry.get_template("fin_invoice_processing")
        self.assertIn("SOC2", t.compliance_frameworks)
        self.assertIn("PCI-DSS", t.compliance_frameworks)

    def test_all_default_categories_covered(self):
        categories = self.registry.list_categories()
        cat_names = set(c["category"] for c in categories)
        for expected in ["it_operations", "data_pipeline", "marketing", "customer_service",
                         "hr_onboarding", "financial", "content_generation", "security",
                         "devops", "compliance"]:
            self.assertIn(expected, cat_names)

    def test_template_steps_populated(self):
        t = self.registry.get_template("devops_ci_cd")
        self.assertGreater(len(t.steps), 3)

    def test_statistics(self):
        stats = self.registry.get_statistics()
        self.assertGreater(stats["total_templates"], 10)
        self.assertGreater(stats["total_categories"], 5)

    def test_status(self):
        status = self.registry.status()
        self.assertEqual(status["module"], "automation_type_registry")
        self.assertIn("statistics", status)
        self.assertIn("categories", status)

    def test_business_process_templates(self):
        bp = self.registry.list_templates(AutomationCategory.BUSINESS_PROCESS)
        self.assertGreater(len(bp), 0)

    def test_data_pipeline_templates(self):
        dp = self.registry.list_templates(AutomationCategory.DATA_PIPELINE)
        self.assertGreater(len(dp), 0)

    def test_supply_chain_category_exists(self):
        # Category exists even if no default templates
        self.assertEqual(AutomationCategory.SUPPLY_CHAIN.value, "supply_chain")

    def test_template_estimated_duration(self):
        templates = self.registry.list_templates()
        for t in templates:
            self.assertIn("estimated_duration_minutes", t)


if __name__ == "__main__":
    unittest.main()

"""Tests for ai_workflow_generator.py"""

import os
import unittest

from ai_workflow_generator import AIWorkflowGenerator, WORKFLOW_TEMPLATES


class TestAIWorkflowGenerator(unittest.TestCase):

    def setUp(self):
        self.gen = AIWorkflowGenerator()

    # --- Template matching ---
    def test_generate_etl_workflow(self):
        wf = self.gen.generate_workflow("Build an ETL pipeline to extract, transform, and load data")
        self.assertEqual(wf["strategy"], "template_match")
        self.assertEqual(wf["template_used"], "etl_pipeline")
        self.assertTrue(len(wf["steps"]) >= 3)

    def test_generate_cicd_workflow(self):
        wf = self.gen.generate_workflow("Create a CI/CD pipeline to build, test, and deploy")
        self.assertEqual(wf["strategy"], "template_match")
        self.assertEqual(wf["template_used"], "ci_cd")

    def test_generate_incident_response(self):
        wf = self.gen.generate_workflow("Handle an incident with alert triage, respond to outage, and escalate")
        self.assertEqual(wf["strategy"], "template_match")
        self.assertEqual(wf["template_used"], "incident_response")

    def test_generate_data_report(self):
        wf = self.gen.generate_workflow("Analyze data and generate a report with summary metrics")
        self.assertEqual(wf["strategy"], "template_match")

    def test_generate_security_scan(self):
        wf = self.gen.generate_workflow("Run a security scan for vulnerability audit and compliance")
        self.assertEqual(wf["strategy"], "template_match")
        self.assertEqual(wf["template_used"], "security_scan")

    def test_generate_customer_onboarding(self):
        wf = self.gen.generate_workflow("Onboard a new customer account with provisioning and setup")
        self.assertEqual(wf["strategy"], "template_match")
        self.assertEqual(wf["template_used"], "customer_onboarding")

    # --- Keyword inference ---
    def test_keyword_inference(self):
        wf = self.gen.generate_workflow("Fetch data from API, validate the records, then send notification")
        self.assertEqual(wf["strategy"], "keyword_inference")
        self.assertTrue(len(wf["steps"]) >= 3)

    def test_keyword_inference_steps_have_types(self):
        wf = self.gen.generate_workflow("Read files, transform the content, and save results")
        for step in wf["steps"]:
            self.assertIn("type", step)
            self.assertIn("name", step)

    # --- Generic fallback ---
    def test_generic_fallback(self):
        wf = self.gen.generate_workflow("Do something very unusual and creative with no keywords")
        self.assertEqual(wf["strategy"], "generic_fallback")
        self.assertTrue(len(wf["steps"]) >= 2)

    # --- Dependency resolution ---
    def test_dependencies_resolved(self):
        wf = self.gen.generate_workflow("Fetch records, transform them, then send an email notification")
        step_names = {s["name"] for s in wf["steps"]}
        for step in wf["steps"]:
            for dep in step.get("depends_on", []):
                self.assertIn(dep, step_names)

    # --- Workflow structure ---
    def test_workflow_has_required_fields(self):
        wf = self.gen.generate_workflow("Simple test workflow")
        self.assertIn("workflow_id", wf)
        self.assertIn("name", wf)
        self.assertIn("description", wf)
        self.assertIn("steps", wf)
        self.assertIn("step_count", wf)
        self.assertIn("strategy", wf)
        self.assertIn("generated_at", wf)

    def test_workflow_name_generation(self):
        wf = self.gen.generate_workflow("Process customer invoices monthly")
        self.assertIn("workflow", wf["name"])

    def test_workflow_context_passthrough(self):
        ctx = {"project": "alpha", "team": "backend"}
        wf = self.gen.generate_workflow("Test workflow", context=ctx)
        self.assertEqual(wf["context"], ctx)

    # --- Custom templates ---
    def test_add_custom_template(self):
        result = self.gen.add_template("my_template", {
            "description": "Custom workflow",
            "keywords": ["custom", "special"],
            "steps": [{"name": "step1", "type": "execution", "description": "do thing"}],
        })
        self.assertTrue(result["added"])

    def test_add_template_missing_field(self):
        result = self.gen.add_template("bad", {"description": "missing fields"})
        self.assertFalse(result["added"])

    def test_custom_template_matching(self):
        self.gen.add_template("custom_flow", {
            "description": "Custom",
            "keywords": ["unicorn", "rainbow"],
            "steps": [{"name": "s1", "type": "execution", "description": "unicorn step"}],
        })
        wf = self.gen.generate_workflow("Do a unicorn and rainbow task")
        self.assertEqual(wf["template_used"], "custom_flow")

    # --- Template listing ---
    def test_list_templates(self):
        templates = self.gen.list_templates()
        self.assertTrue(len(templates) >= len(WORKFLOW_TEMPLATES))
        for t in templates:
            self.assertIn("name", t)
            self.assertIn("description", t)

    # --- Step type registration ---
    def test_register_step_type(self):
        self.gen.register_step_type("ml_training", {"gpu": True, "timeout": 3600})
        status = self.gen.get_status()
        self.assertEqual(status["custom_step_types"], 1)

    # --- History ---
    def test_generation_history(self):
        self.gen.generate_workflow("First workflow")
        self.gen.generate_workflow("Second workflow")
        history = self.gen.get_generation_history()
        self.assertEqual(len(history), 2)

    # --- Status ---
    def test_status(self):
        status = self.gen.get_status()
        self.assertEqual(status["module"], "ai_workflow_generator")
        self.assertIn("template_count", status)
        self.assertIn("supported_step_keywords", status)

    # --- Multiple keywords ---
    def test_multiple_action_keywords(self):
        wf = self.gen.generate_workflow("Fetch data, filter invalid records, compute stats, and export CSV")
        self.assertEqual(wf["strategy"], "keyword_inference")
        step_types = [s["type"] for s in wf["steps"]]
        self.assertIn("data_retrieval", step_types)


if __name__ == "__main__":
    unittest.main()

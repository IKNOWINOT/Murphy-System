"""Tests for workflow_template_marketplace.py"""

import os
import unittest

from workflow_template_marketplace import WorkflowTemplateMarketplace


def _make_template(name="etl-basic", version="1.0.0", **overrides):
    base = {
        "name": name,
        "version": version,
        "author": "Murphy Team",
        "description": "A basic ETL workflow template",
        "category": "data_pipeline",
        "steps": [
            {"name": "extract", "type": "data_retrieval"},
            {"name": "transform", "type": "data_transformation"},
            {"name": "load", "type": "data_output"},
        ],
        "tags": ["etl", "data", "pipeline"],
    }
    base.update(overrides)
    return base


class TestWorkflowTemplateMarketplace(unittest.TestCase):

    def setUp(self):
        self.mp = WorkflowTemplateMarketplace()

    # --- Publish ---
    def test_publish_template(self):
        result = self.mp.publish_template(_make_template())
        self.assertTrue(result["published"])
        self.assertEqual(result["name"], "etl-basic")

    def test_publish_missing_field(self):
        t = _make_template()
        del t["name"]
        result = self.mp.publish_template(t)
        self.assertFalse(result["published"])

    def test_publish_invalid_category(self):
        result = self.mp.publish_template(_make_template(category="invalid"))
        self.assertFalse(result["published"])

    def test_publish_duplicate_version(self):
        self.mp.publish_template(_make_template())
        result = self.mp.publish_template(_make_template())
        self.assertFalse(result["published"])

    def test_publish_new_version(self):
        self.mp.publish_template(_make_template())
        result = self.mp.publish_template(_make_template(version="2.0.0"))
        self.assertTrue(result["published"])

    # --- Search ---
    def test_search_by_query(self):
        self.mp.publish_template(_make_template())
        results = self.mp.search_templates(query="etl")
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0]["name"], "etl-basic")

    def test_search_by_category(self):
        self.mp.publish_template(_make_template())
        self.mp.publish_template(_make_template(name="ci-runner", category="ci_cd"))
        results = self.mp.search_templates(category="data_pipeline")
        self.assertEqual(len(results), 1)

    def test_search_by_tags(self):
        self.mp.publish_template(_make_template())
        results = self.mp.search_templates(tags=["etl"])
        self.assertTrue(len(results) >= 1)

    def test_search_no_results(self):
        results = self.mp.search_templates(query="nonexistent")
        self.assertEqual(len(results), 0)

    def test_search_all(self):
        self.mp.publish_template(_make_template(name="t1"))
        self.mp.publish_template(_make_template(name="t2"))
        results = self.mp.search_templates()
        self.assertEqual(len(results), 2)

    def test_search_sort_by_rating(self):
        self.mp.publish_template(_make_template(name="t1"))
        self.mp.publish_template(_make_template(name="t2"))
        self.mp.rate_template("t1", 5.0, "user1")
        self.mp.rate_template("t2", 3.0, "user1")
        results = self.mp.search_templates(sort_by="rating")
        self.assertEqual(results[0]["name"], "t1")

    # --- Install ---
    def test_install_template(self):
        self.mp.publish_template(_make_template())
        result = self.mp.install_template("etl-basic")
        self.assertTrue(result["installed"])
        self.assertEqual(result["step_count"], 3)

    def test_install_not_found(self):
        result = self.mp.install_template("nonexistent")
        self.assertFalse(result["installed"])

    def test_install_increments_downloads(self):
        self.mp.publish_template(_make_template())
        self.mp.install_template("etl-basic")
        tmpl = self.mp.get_template("etl-basic")
        self.assertEqual(tmpl["downloads"], 1)

    # --- Uninstall ---
    def test_uninstall_template(self):
        self.mp.publish_template(_make_template())
        self.mp.install_template("etl-basic")
        result = self.mp.uninstall_template("etl-basic")
        self.assertTrue(result["uninstalled"])

    def test_uninstall_not_installed(self):
        result = self.mp.uninstall_template("nonexistent")
        self.assertFalse(result["uninstalled"])

    # --- Rating ---
    def test_rate_template(self):
        self.mp.publish_template(_make_template())
        result = self.mp.rate_template("etl-basic", 4.5, "user1", "Great!")
        self.assertTrue(result["rated"])
        self.assertEqual(result["avg_rating"], 4.5)

    def test_rate_invalid_rating(self):
        self.mp.publish_template(_make_template())
        result = self.mp.rate_template("etl-basic", 6.0, "user1")
        self.assertFalse(result["rated"])

    def test_rate_not_found(self):
        result = self.mp.rate_template("nonexistent", 4.0, "user1")
        self.assertFalse(result["rated"])

    def test_multiple_ratings(self):
        self.mp.publish_template(_make_template())
        self.mp.rate_template("etl-basic", 5.0, "user1")
        self.mp.rate_template("etl-basic", 3.0, "user2")
        result = self.mp.rate_template("etl-basic", 4.0, "user3")
        self.assertEqual(result["avg_rating"], 4.0)
        self.assertEqual(result["total_ratings"], 3)

    # --- Get template ---
    def test_get_template(self):
        self.mp.publish_template(_make_template())
        tmpl = self.mp.get_template("etl-basic")
        self.assertIsNotNone(tmpl)
        self.assertEqual(tmpl["name"], "etl-basic")
        self.assertIn("rating", tmpl)

    def test_get_template_not_found(self):
        self.assertIsNone(self.mp.get_template("nonexistent"))

    # --- List installed ---
    def test_list_installed(self):
        self.mp.publish_template(_make_template())
        self.mp.install_template("etl-basic")
        installed = self.mp.list_installed()
        self.assertEqual(len(installed), 1)
        self.assertEqual(installed[0]["name"], "etl-basic")

    # --- Categories ---
    def test_list_categories(self):
        cats = self.mp.list_categories()
        self.assertIn("data_pipeline", cats)
        self.assertIn("ci_cd", cats)

    # --- Status ---
    def test_status(self):
        status = self.mp.get_status()
        self.assertEqual(status["module"], "workflow_template_marketplace")
        self.assertIn("total_templates", status)
        self.assertIn("installed_templates", status)

    # --- Min rating filter ---
    def test_search_min_rating(self):
        self.mp.publish_template(_make_template(name="good-one"))
        self.mp.publish_template(_make_template(name="bad-one"))
        self.mp.rate_template("good-one", 5.0, "user1")
        self.mp.rate_template("bad-one", 2.0, "user1")
        results = self.mp.search_templates(min_rating=4.0)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "good-one")


if __name__ == "__main__":
    unittest.main()

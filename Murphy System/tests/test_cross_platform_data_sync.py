"""Tests for cross_platform_data_sync.py"""

import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from cross_platform_data_sync import CrossPlatformDataSync


class TestCrossPlatformDataSync(unittest.TestCase):

    def setUp(self):
        self.sync = CrossPlatformDataSync()
        self.sync.register_connector("salesforce")
        self.sync.register_connector("hubspot")

    # --- Connector registration ---
    def test_register_connector(self):
        s = CrossPlatformDataSync()
        result = s.register_connector("jira")
        self.assertTrue(result["registered"])

    def test_register_with_functions(self):
        s = CrossPlatformDataSync()
        result = s.register_connector("jira", read_fn=lambda t: [], write_fn=lambda t, d: None)
        self.assertTrue(result["registered"])

    # --- Mapping creation ---
    def test_create_mapping(self):
        result = self.sync.create_mapping(
            "salesforce", "hubspot", "contact",
            {"first_name": "firstname", "last_name": "lastname", "email": "email"}
        )
        self.assertTrue(result["created"])
        self.assertEqual(result["fields_mapped"], 3)

    def test_create_mapping_unregistered_source(self):
        result = self.sync.create_mapping("unknown", "hubspot", "contact", {})
        self.assertFalse(result["created"])

    def test_create_mapping_unregistered_target(self):
        result = self.sync.create_mapping("salesforce", "unknown", "contact", {})
        self.assertFalse(result["created"])

    def test_create_mapping_invalid_direction(self):
        result = self.sync.create_mapping("salesforce", "hubspot", "contact", {},
                                          direction="invalid")
        self.assertFalse(result["created"])

    def test_create_mapping_invalid_conflict(self):
        result = self.sync.create_mapping("salesforce", "hubspot", "contact", {},
                                          conflict_strategy="invalid")
        self.assertFalse(result["created"])

    # --- Sync execution ---
    def test_sync_with_source_data(self):
        result = self.sync.create_mapping(
            "salesforce", "hubspot", "contact",
            {"name": "contact_name", "email": "contact_email"}
        )
        mapping_id = result["mapping_id"]
        source = [
            {"name": "Alice", "email": "alice@test.com"},
            {"name": "Bob", "email": "bob@test.com"},
        ]
        sync_result = self.sync.sync(mapping_id=mapping_id, source_data=source)
        self.assertTrue(sync_result["synced"])
        self.assertEqual(sync_result["total_records_synced"], 2)

    def test_sync_all_mappings(self):
        self.sync.create_mapping("salesforce", "hubspot", "contact",
                                 {"name": "cn"})
        self.sync.create_mapping("hubspot", "salesforce", "deal",
                                 {"title": "deal_name"})
        result = self.sync.sync(source_data=[{"name": "x", "title": "y"}])
        self.assertTrue(result["synced"])
        self.assertEqual(result["mappings_processed"], 2)

    def test_sync_not_found(self):
        result = self.sync.sync(mapping_id="nonexistent")
        self.assertFalse(result["synced"])

    def test_sync_with_read_function(self):
        s = CrossPlatformDataSync()
        s.register_connector("src", read_fn=lambda t: [{"id": 1, "name": "A"}])
        s.register_connector("tgt")
        s.create_mapping("src", "tgt", "item", {"id": "item_id", "name": "item_name"})
        result = s.sync()
        self.assertTrue(result["synced"])
        self.assertEqual(result["total_records_synced"], 1)

    def test_sync_with_write_function(self):
        written = []
        s = CrossPlatformDataSync()
        s.register_connector("src", read_fn=lambda t: [{"val": 42}])
        s.register_connector("tgt", write_fn=lambda t, d: written.extend(d))
        s.create_mapping("src", "tgt", "metric", {"val": "value"})
        s.sync()
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0]["value"], 42)

    def test_sync_with_transform(self):
        def upper_transform(record):
            return {k: v.upper() if isinstance(v, str) else v for k, v in record.items()}
        self.sync.create_mapping("salesforce", "hubspot", "contact",
                                 {"name": "contact_name"},
                                 transform=upper_transform)
        result = self.sync.sync(source_data=[{"name": "alice"}])
        self.assertTrue(result["synced"])

    # --- Change tracking ---
    def test_push_change(self):
        result = self.sync.push_change("salesforce", "contact", "c001",
                                       {"name": "Updated"})
        self.assertTrue(result["pushed"])

    def test_push_change_unregistered(self):
        result = self.sync.push_change("unknown", "contact", "c001", {})
        self.assertFalse(result["pushed"])

    def test_get_pending_changes(self):
        self.sync.push_change("salesforce", "contact", "c001", {"name": "A"})
        self.sync.push_change("salesforce", "contact", "c002", {"name": "B"})
        changes = self.sync.get_pending_changes("salesforce")
        self.assertEqual(len(changes), 2)

    def test_get_all_pending_changes(self):
        self.sync.push_change("salesforce", "contact", "c001", {})
        self.sync.push_change("hubspot", "contact", "h001", {})
        changes = self.sync.get_pending_changes()
        self.assertEqual(len(changes), 2)

    # --- Conflict resolution ---
    def test_resolve_conflict_not_found(self):
        result = self.sync.resolve_conflict("nonexistent", "source_wins")
        self.assertFalse(result["resolved"])

    # --- Listing ---
    def test_list_mappings(self):
        self.sync.create_mapping("salesforce", "hubspot", "contact", {"a": "b"})
        mappings = self.sync.list_mappings()
        self.assertEqual(len(mappings), 1)
        self.assertEqual(mappings[0]["entity_type"], "contact")

    # --- Sync log ---
    def test_sync_log(self):
        self.sync.create_mapping("salesforce", "hubspot", "contact", {"a": "b"})
        self.sync.sync(source_data=[{"a": 1}])
        log = self.sync.get_sync_log()
        self.assertTrue(len(log) >= 1)
        self.assertEqual(log[0]["status"], "success")

    # --- Status ---
    def test_status(self):
        status = self.sync.get_status()
        self.assertEqual(status["module"], "cross_platform_data_sync")
        self.assertEqual(status["connectors"], 2)
        self.assertIn("mappings", status)

    # --- Unidirectional sync ---
    def test_unidirectional_mapping(self):
        result = self.sync.create_mapping(
            "salesforce", "hubspot", "contact",
            {"a": "b"}, direction="unidirectional"
        )
        self.assertTrue(result["created"])

    # --- Field mapping ---
    def test_field_mapping_only_maps_matching_fields(self):
        self.sync.create_mapping("salesforce", "hubspot", "contact",
                                 {"name": "cn", "email": "ce"})
        result = self.sync.sync(source_data=[{"name": "Alice", "phone": "555"}])
        self.assertTrue(result["synced"])

    # --- Read error handling ---
    def test_sync_read_error(self):
        s = CrossPlatformDataSync()
        s.register_connector("bad-src", read_fn=lambda t: (_ for _ in ()).throw(RuntimeError("fail")))
        s.register_connector("tgt")
        s.create_mapping("bad-src", "tgt", "item", {"a": "b"})
        result = s.sync()
        self.assertTrue(result["synced"])  # overall sync still returns
        self.assertEqual(result["results"][0]["status"], "error")


if __name__ == "__main__":
    unittest.main()

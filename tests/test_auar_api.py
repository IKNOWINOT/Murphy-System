"""
Tests for the AUAR API Integration Module.

Validates the handler functions that wire AUAR into the Murphy System
runtime API surface.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from auar_api import (
    AUARComponents,
    initialize_auar,
    handle_route,
    handle_register,
    handle_stats,
    handle_health,
)


class TestAUARAPIInitialization:
    """Tests for AUAR subsystem initialization."""

    def test_initialize_returns_components(self):
        components = initialize_auar()
        assert isinstance(components, AUARComponents)
        assert components.pipeline is not None
        assert components.graph is not None
        assert components.interpreter is not None

    def test_health_check(self):
        components = initialize_auar()
        health = handle_health(components)
        assert health["status"] == "healthy"
        assert health["version"] == "0.1.0"
        assert health["codename"] == "FAPI"


class TestAUARAPIRegistration:
    """Tests for capability + provider registration via API."""

    def test_register_capability_and_provider(self):
        components = initialize_auar()
        result = handle_register(components, {
            "capability": {
                "name": "send_email",
                "domain": "communication",
                "category": "email",
                "required_params": ["to", "subject", "body"],
                "semantic_tags": ["email", "messaging"],
            },
            "provider": {
                "name": "SendGrid",
                "base_url": "https://api.sendgrid.com",
                "auth_method": "api_key",
                "cost_per_call": 0.001,
            },
            "schema_mappings": [
                {
                    "direction": "request",
                    "field_mappings": [
                        {"source_field": "to", "target_field": "personalizations.to"},
                        {"source_field": "subject", "target_field": "subject"},
                        {"source_field": "body", "target_field": "content.value"},
                    ],
                }
            ],
        })
        assert "capability:send_email" in result["registered"]
        assert "provider:SendGrid" in result["registered"]
        assert "schema_mapping:request" in result["registered"]
        assert result["capability_id"]
        assert result["provider_id"]

    def test_register_capability_only(self):
        components = initialize_auar()
        result = handle_register(components, {
            "capability": {
                "name": "process_payment",
                "domain": "payments",
            },
        })
        assert "capability:process_payment" in result["registered"]
        assert len(result["registered"]) == 1

    def test_register_empty_body(self):
        components = initialize_auar()
        result = handle_register(components, {})
        assert result["registered"] == []


class TestAUARAPIRouting:
    """Tests for the full AUAR pipeline via API handler."""

    def _setup_components(self):
        """Create components with a registered capability + provider."""
        components = initialize_auar()
        handle_register(components, {
            "capability": {
                "name": "send_email",
                "domain": "communication",
                "category": "email",
                "required_params": ["to", "subject", "body"],
            },
            "provider": {
                "name": "SendGrid",
                "base_url": "https://api.sendgrid.com",
                "auth_method": "api_key",
                "cost_per_call": 0.001,
            },
            "schema_mappings": [
                {
                    "direction": "request",
                    "field_mappings": [
                        {"source_field": "to", "target_field": "personalizations.to"},
                        {"source_field": "subject", "target_field": "subject"},
                        {"source_field": "body", "target_field": "content.value"},
                    ],
                }
            ],
        })
        return components

    def test_route_success(self):
        components = self._setup_components()
        result = handle_route(components, {
            "capability": "send_email",
            "parameters": {"to": "user@example.com", "subject": "Test", "body": "Hello"},
            "tenant_id": "tenant1",
        })
        assert result["success"] is True
        assert result["capability"] == "send_email"
        assert result["provider_name"] == "SendGrid"
        assert result["total_latency_ms"] > 0
        assert result["trace_id"] != ""

    def test_route_unknown_capability(self):
        components = self._setup_components()
        result = handle_route(components, {
            "capability": "nonexistent_action",
            "parameters": {},
        })
        # Should either fail or have low confidence
        assert result["success"] is False or result["confidence_score"] < 0.85

    def test_route_empty_request(self):
        components = self._setup_components()
        result = handle_route(components, {})
        assert result["success"] is False
        assert result["requires_clarification"] is True


class TestAUARAPIStats:
    """Tests for the stats endpoint."""

    def test_stats_after_routing(self):
        components = initialize_auar()
        handle_register(components, {
            "capability": {"name": "test_cap"},
            "provider": {"name": "TestProvider", "base_url": "http://test"},
        })
        handle_route(components, {
            "capability": "test_cap",
            "parameters": {},
        })
        stats = handle_stats(components)
        assert "graph" in stats
        assert "interpreter" in stats
        assert "routing" in stats
        assert "ml" in stats
        assert "observability" in stats
        assert stats["interpreter"]["total"] >= 1

    def test_stats_initial_state(self):
        components = initialize_auar()
        stats = handle_stats(components)
        assert stats["graph"]["total_capabilities"] == 0
        assert stats["ml"]["total_observations"] == 0

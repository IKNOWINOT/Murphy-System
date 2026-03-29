# Copyright 2020 Inoni Limited Liability Company
# Creator: Corey Post
# License: BSL 1.1
"""
Module: tests/test_error_system.py
Subsystem: Error Handling
Purpose: Commission the Murphy error code system (src/errors/).
Status: Production

Commissioning answers:
  1. Does it do what it was designed to do? — Yes: provides error codes,
     registry lookup, catalogue, and FastAPI exception handlers.
  2. What is it supposed to do? — Map 21 existing exception classes to
     MURPHY-Exxx codes, return structured JSON on errors, expose
     /api/errors/{code} and /api/errors/catalog endpoints.
  3. What conditions are possible? — Valid code lookup, invalid code lookup,
     full catalogue retrieval, unhandled exception classification.
  4. Does the test profile reflect full range? — Yes: covers all conditions.
  5. Expected result? — See assertions below.
  6. Actual result? — Run: pytest tests/test_error_system.py -v
  7. Problems? — N/A (green on initial commission).
  8. Documentation updated? — codes.py docstring, ERROR_CATALOG.md (TODO).
  9. Hardening applied? — Typed exceptions, frozen dataclass, singleton.
  10. Re-commissioned? — Yes, after initial creation.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.errors.codes import ErrorCode, SUBSYSTEM_RANGES
from src.errors.registry import ErrorRegistry, ErrorEntry
from src.errors.handlers import register_error_handlers, _classify_exception


# ---------------------------------------------------------------------------
# Unit tests — ErrorCode enum
# ---------------------------------------------------------------------------

class TestErrorCodes:
    """Commission: ErrorCode enum covers all subsystem ranges."""

    def test_all_codes_start_with_murphy_prefix(self):
        for code in ErrorCode:
            assert code.value.startswith("MURPHY-E"), f"{code.name} missing prefix"

    def test_subsystem_ranges_documented(self):
        assert len(SUBSYSTEM_RANGES) >= 10, "Expected at least 10 subsystem ranges"
        assert "E0xx" in SUBSYSTEM_RANGES
        assert "E9xx" in SUBSYSTEM_RANGES

    def test_code_values_are_unique(self):
        values = [c.value for c in ErrorCode]
        assert len(values) == len(set(values)), "Duplicate error code values found"


# ---------------------------------------------------------------------------
# Unit tests — ErrorRegistry
# ---------------------------------------------------------------------------

class TestErrorRegistry:
    """Commission: ErrorRegistry maps codes to metadata."""

    def test_singleton_pattern(self):
        r1 = ErrorRegistry.get()
        r2 = ErrorRegistry.get()
        assert r1 is r2

    def test_lookup_valid_code(self):
        registry = ErrorRegistry.get()
        entry = registry.lookup("MURPHY-E001")
        assert entry is not None
        assert entry.code == ErrorCode.E001
        assert entry.severity == "critical"

    def test_lookup_invalid_code_returns_none(self):
        registry = ErrorRegistry.get()
        assert registry.lookup("MURPHY-E000") is None
        assert registry.lookup("BOGUS") is None

    def test_catalog_returns_all_entries(self):
        registry = ErrorRegistry.get()
        catalog = registry.catalog()
        assert isinstance(catalog, list)
        assert len(catalog) >= 20, f"Expected >=20 entries, got {len(catalog)}"
        for entry in catalog:
            assert "code" in entry
            assert "message" in entry
            assert "severity" in entry

    def test_all_enum_codes_have_registry_entries(self):
        registry = ErrorRegistry.get()
        for code in ErrorCode:
            entry = registry.lookup(code.value)
            assert entry is not None, f"{code.value} missing from registry"

    def test_existing_exception_mappings(self):
        """Verify key existing exception classes are mapped."""
        registry = ErrorRegistry.get()
        mapped_classes = [
            e["exception_class"]
            for e in registry.catalog()
            if e["exception_class"]
        ]
        assert len(mapped_classes) >= 15, (
            f"Expected >=15 exception mappings, got {len(mapped_classes)}"
        )

    def test_entry_has_required_fields(self):
        registry = ErrorRegistry.get()
        entry = registry.lookup("MURPHY-E101")
        assert entry is not None
        assert entry.message
        assert entry.cause
        assert entry.fix
        assert entry.severity in ("critical", "high", "medium", "low")
        assert 100 <= entry.http_status <= 599


# ---------------------------------------------------------------------------
# Unit tests — Exception classification
# ---------------------------------------------------------------------------

class TestExceptionClassification:
    """Commission: _classify_exception maps Python exceptions to codes."""

    def test_value_error_maps_to_e200(self):
        code = _classify_exception(ValueError("bad input"))
        assert code == ErrorCode.E200

    def test_permission_error_maps_to_e100(self):
        code = _classify_exception(PermissionError("denied"))
        assert code == ErrorCode.E100

    def test_key_error_maps_to_e304(self):
        code = _classify_exception(KeyError("missing"))
        assert code == ErrorCode.E304

    def test_connection_error_maps_to_e400(self):
        code = _classify_exception(ConnectionError("timeout"))
        assert code == ErrorCode.E400

    def test_os_error_maps_to_e500(self):
        code = _classify_exception(OSError("disk full"))
        assert code == ErrorCode.E500

    def test_unknown_exception_maps_to_e999(self):
        code = _classify_exception(Exception("mystery"))
        assert code == ErrorCode.E999


# ---------------------------------------------------------------------------
# Integration tests — FastAPI endpoints
# ---------------------------------------------------------------------------

@pytest.fixture()
def error_client():
    """Create a test app with error handlers registered."""
    test_app = FastAPI()
    register_error_handlers(test_app)

    @test_app.get("/test-raise")
    async def _raise_error():
        raise ValueError("test validation failure")

    return TestClient(test_app, raise_server_exceptions=False)


class TestErrorEndpoints:
    """Commission: /api/errors/* endpoints return structured JSON."""

    def test_error_lookup_valid(self, error_client):
        resp = error_client.get("/api/errors/MURPHY-E001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["data"]["code"] == "MURPHY-E001"
        assert data["data"]["severity"] == "critical"

    def test_error_lookup_invalid(self, error_client):
        resp = error_client.get("/api/errors/MURPHY-E000")
        assert resp.status_code == 404
        data = resp.json()
        assert data["success"] is False

    def test_error_catalog(self, error_client):
        resp = error_client.get("/api/errors/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
        assert len(data["data"]) >= 20

    def test_unhandled_exception_returns_structured_json(self, error_client):
        resp = error_client.get("/test-raise")
        assert resp.status_code == 400
        data = resp.json()
        assert data["success"] is False
        assert "code" in data["error"]
        assert data["error"]["code"].startswith("MURPHY-E")

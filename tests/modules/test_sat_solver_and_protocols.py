"""
Tests for SAT Solver Integration and gRPC/SOAP Protocol Support

Validates:
- SAT solver handles satisfiable and unsatisfiable CNF formulas
- SAT solver returns correct assignments
- gRPC protocol preparation produces correct payload structure
- SOAP protocol preparation produces XML envelope

Copyright © 2020 Inoni Limited Liability Company
License: BSL 1.1
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent.parent
for _p in (_ROOT, _ROOT / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


# ---------------------------------------------------------------------------
# SAT Solver Tests
# ---------------------------------------------------------------------------


class TestSATSolver:
    """Test the DPLL SAT solver in ComputeService."""

    def _get_service(self):
        from src.compute_plane.service import ComputeService
        return ComputeService()

    def test_simple_satisfiable(self):
        service = self._get_service()
        # (x1 OR x2) AND (NOT x1 OR x2)
        sat, assignment = service._dpll_solve([[1, 2], [-1, 2]])
        assert sat is True
        assert assignment.get(2) is True  # x2 must be True

    def test_simple_unsatisfiable(self):
        service = self._get_service()
        # (x1) AND (NOT x1)
        sat, assignment = service._dpll_solve([[1], [-1]])
        assert sat is False

    def test_single_variable_true(self):
        service = self._get_service()
        sat, assignment = service._dpll_solve([[1]])
        assert sat is True
        assert assignment[1] is True

    def test_single_variable_false(self):
        service = self._get_service()
        sat, assignment = service._dpll_solve([[-1]])
        assert sat is True
        assert assignment[1] is False

    def test_three_variable_satisfiable(self):
        service = self._get_service()
        # (x1 OR x2 OR x3) AND (NOT x1 OR NOT x2) AND (NOT x2 OR NOT x3)
        cnf = [[1, 2, 3], [-1, -2], [-2, -3]]
        sat, assignment = service._dpll_solve(cnf)
        assert sat is True
        # Verify assignment satisfies all clauses
        for clause in cnf:
            assert any(
                (lit > 0) == assignment.get(abs(lit), False)
                for lit in clause
            )

    def test_execute_sat_with_valid_cnf(self):
        service = self._get_service()
        from src.compute_plane.models.compute_request import ComputeRequest
        request = ComputeRequest(
            expression="[[1, 2], [-1, 2]]",
            language="sat",
            request_id="test-sat-1",
        )
        result = service._execute_sat(request, {"cnf": [[1, 2], [-1, 2]]})
        assert result.status.value in ("success", "SUCCESS")
        assert result.result["satisfiable"] is True

    def test_execute_sat_missing_cnf_key(self):
        service = self._get_service()
        from src.compute_plane.models.compute_request import ComputeRequest
        request = ComputeRequest(
            expression="not_cnf",
            language="sat",
            request_id="test-sat-2",
        )
        result = service._execute_sat(request, {"formula": "not cnf"})
        assert result.status.value in ("fail", "FAIL")


# ---------------------------------------------------------------------------
# gRPC Protocol Tests
# ---------------------------------------------------------------------------


class TestGRPCProtocol:
    """Test gRPC request preparation."""

    def _make_adapter(self, protocol_name="grpc"):
        from src.auar.provider_adapter import AdapterConfig, Protocol, ProviderAdapter
        config = AdapterConfig(
            provider_id="test-grpc",
            provider_name="TestGRPC",
            base_url="http://localhost:50051",
            protocol=Protocol.GRPC,
        )
        return ProviderAdapter(config)

    def test_grpc_prepare_adds_content_type(self):
        adapter = self._make_adapter()
        result = adapter._prepare_grpc_request({
            "body": {"service": "mypackage.MyService", "method": "GetUser", "user_id": "123"},
        })
        assert result["headers"]["Content-Type"] == "application/grpc+json"
        assert result["method"] == "POST"

    def test_grpc_prepare_builds_path(self):
        adapter = self._make_adapter()
        result = adapter._prepare_grpc_request({
            "body": {"service": "mypackage.MyService", "method": "GetUser"},
        })
        assert result["path"] == "/mypackage.MyService/GetUser"

    def test_grpc_prepare_strips_service_method_from_body(self):
        adapter = self._make_adapter()
        result = adapter._prepare_grpc_request({
            "body": {"service": "svc", "method": "m", "field1": "val1"},
        })
        assert "service" not in result["body"]
        assert "method" not in result["body"]
        assert result["body"]["field1"] == "val1"


# ---------------------------------------------------------------------------
# SOAP Protocol Tests
# ---------------------------------------------------------------------------


class TestSOAPProtocol:
    """Test SOAP request preparation."""

    def _make_adapter(self):
        from src.auar.provider_adapter import AdapterConfig, Protocol, ProviderAdapter
        config = AdapterConfig(
            provider_id="test-soap",
            provider_name="TestSOAP",
            base_url="http://localhost:8080",
            protocol=Protocol.SOAP,
        )
        return ProviderAdapter(config)

    def test_soap_prepare_wraps_in_envelope(self):
        adapter = self._make_adapter()
        result = adapter._prepare_soap_request({
            "body": {"soap_action": "GetWeather", "city": "London"},
        })
        body = result["body"]
        assert "soap:Envelope" in body
        assert "<city>London</city>" in body

    def test_soap_sets_content_type(self):
        adapter = self._make_adapter()
        result = adapter._prepare_soap_request({
            "body": {"soap_action": "Test"},
        })
        assert "application/soap+xml" in result["headers"]["Content-Type"]

    def test_soap_action_header(self):
        adapter = self._make_adapter()
        result = adapter._prepare_soap_request({
            "body": {"soap_action": "MyAction"},
        })
        assert result["headers"]["SOAPAction"] == "MyAction"

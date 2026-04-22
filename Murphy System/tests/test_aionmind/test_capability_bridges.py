"""Per-bridge unit tests (Phase 2 / F34 + C16 + C17).

For each capability bridge:
- Importing the bridge module in isolation succeeds.
- Loading into a fresh kernel registers ≥1 capability.
- Every registered capability has a non-empty input + output schema
  (C17 — schema discipline).
- Every registered capability has a callable handler.
- Calling a handler in "subsystem unavailable" mode returns a
  structured ``status: unavailable`` payload rather than raising.
"""

from __future__ import annotations

import importlib

import pytest

from aionmind._bridge_base import (
    BridgeCapability,
    CapabilitySchemaError,
    make_unavailable_handler,
)
from aionmind.runtime_kernel import AionMindKernel


# (logical_name, module_path, loader_attr, expected_min_caps)
_BRIDGES = [
    ("automations", "aionmind.automations_capability_bridge",
     "load_automations_capabilities_into_kernel", 6),
    ("hitl", "aionmind.hitl_capability_bridge",
     "load_hitl_capabilities_into_kernel", 4),
    ("boards", "aionmind.boards_capability_bridge",
     "load_boards_capabilities_into_kernel", 5),
    ("founder", "aionmind.founder_capability_bridge",
     "load_founder_capabilities_into_kernel", 3),
    ("production", "aionmind.production_capability_bridge",
     "load_production_capabilities_into_kernel", 5),
    ("integration_bus", "aionmind.integration_bus_capability_bridge",
     "load_integration_bus_capabilities_into_kernel", 1),
    ("document", "aionmind.document_capability_bridge",
     "load_document_capabilities_into_kernel", 4),
]


@pytest.mark.parametrize("name,module_path,loader_name,min_caps", _BRIDGES)
def test_bridge_imports_and_registers(name, module_path, loader_name, min_caps):
    module = importlib.import_module(module_path)
    loader = getattr(module, loader_name)
    kernel = AionMindKernel(auto_bridge_bots=False, auto_discover_rsc=False)
    before = kernel.registry.count()
    count = loader(kernel)
    after = kernel.registry.count()
    assert count >= min_caps, f"{name}: expected ≥{min_caps} caps, got {count}"
    assert after - before == count


@pytest.mark.parametrize("name,module_path,loader_name,min_caps", _BRIDGES)
def test_bridge_capabilities_have_schemas_and_handlers(
    name, module_path, loader_name, min_caps
):
    """C17 — every registered capability has non-empty schemas
    and a callable handler."""
    module = importlib.import_module(module_path)
    loader = getattr(module, loader_name)
    kernel = AionMindKernel(auto_bridge_bots=False, auto_discover_rsc=False)
    loader(kernel)
    for cap in kernel.registry.list_all():
        if cap.provider != name and not cap.capability_id.startswith(name):
            # IntegrationBus uses provider "integration_bus" — match either.
            continue
        assert cap.input_schema, f"{cap.capability_id} missing input_schema"
        assert cap.output_schema, f"{cap.capability_id} missing output_schema"
        handler = kernel._orchestration._handlers.get(cap.capability_id)
        assert callable(handler), f"{cap.capability_id} has no callable handler"


def test_unavailable_handler_returns_structured_payload():
    handler = make_unavailable_handler("widgets", "missing_module")

    class _Node:
        capability_id = "widgets.do"

    out = handler(_Node())
    assert out["status"] == "unavailable"
    assert out["subsystem"] == "widgets"
    assert out["reason"] == "missing_module"
    assert out["capability_id"] == "widgets.do"


def test_schema_discipline_rejects_empty_input_schema():
    bad = BridgeCapability(
        capability_id="x.bad",
        name="bad",
        description="",
        provider="x",
        input_schema={},
        output_schema={"status": {"type": "string"}},
    )
    with pytest.raises(CapabilitySchemaError):
        bad.to_capability()


def test_schema_discipline_rejects_empty_output_schema():
    bad = BridgeCapability(
        capability_id="x.bad",
        name="bad",
        description="",
        provider="x",
        input_schema={"_": {"type": "null"}},
        output_schema={},
    )
    with pytest.raises(CapabilitySchemaError):
        bad.to_capability()


def test_kernel_auto_loads_all_subsystem_bridges():
    """C16 — the kernel registers every Phase-2 bridge at __init__."""
    kernel = AionMindKernel(auto_bridge_bots=True, auto_discover_rsc=False)
    counts = kernel.status()["bridge_counts"]
    # Every Phase-2 bridge should report a non-zero count.
    for name, *_ in _BRIDGES:
        assert counts.get(name, 0) > 0, (
            f"bridge {name!r} did not register any capabilities "
            f"(counts={counts})"
        )


def test_status_exposes_bridge_counts_and_total():
    """F38 — capability count + per-subsystem totals are visible."""
    kernel = AionMindKernel(auto_bridge_bots=True, auto_discover_rsc=False)
    status = kernel.status()
    assert "capabilities_registered" in status
    assert "bridge_counts" in status
    # Sum of bridge counts must not exceed total registered count.
    assert sum(status["bridge_counts"].values()) <= status["capabilities_registered"]
    # And for the Phase-2 bridges specifically, total ≥ 28
    # (6+4+5+3+5+1+4 = 28 minimum from the bridges list).
    phase2_total = sum(
        status["bridge_counts"].get(n, 0) for n, *_ in _BRIDGES
    )
    assert phase2_total >= 28

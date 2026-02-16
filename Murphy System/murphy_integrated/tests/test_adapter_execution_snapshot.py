from murphy_system_1.0_runtime import MurphySystem


def test_adapter_execution_snapshot_reports_available_adapters():
    murphy = MurphySystem.create_test_instance()
    snapshot = murphy._build_adapter_execution_snapshot()

    assert snapshot["summary"]["total"] == len(murphy.CORE_ADAPTER_CANDIDATES)
    for adapter in snapshot["adapters"]:
        assert adapter["status"] in {"configured", "available", "needs_integration"}


def test_adapter_execution_snapshot_marks_configured_adapters():
    murphy = MurphySystem.create_test_instance()
    murphy.integration_connectors["telemetry_adapter"] = {"status": "configured"}

    snapshot = murphy._build_adapter_execution_snapshot()
    telemetry = next(item for item in snapshot["adapters"] if item["id"] == "telemetry_adapter")

    assert telemetry["status"] == "configured"
    assert snapshot["summary"]["configured"] == 1

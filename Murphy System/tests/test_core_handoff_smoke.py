from src.runtime.core_handoff import CoreHandoff


def test_handoff_chat_to_core():
    handoff = CoreHandoff(prefer_core=True)
    result = handoff.handoff_chat({"message": "route this through core"})
    assert result["status_code"] == 200
    assert result["delegated_to"] == "murphy_core"
    assert result["payload"]["trace_id"]


def test_handoff_execute_to_core():
    handoff = CoreHandoff(prefer_core=True)
    result = handoff.handoff_execute({"task_description": "execute workflow build"})
    assert result["status_code"] == 200
    assert result["delegated_to"] == "murphy_core"
    assert result["payload"]["route"]

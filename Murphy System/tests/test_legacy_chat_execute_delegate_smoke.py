from src.runtime.legacy_chat_execute_delegate import LegacyChatExecuteDelegate


def test_delegate_chat_routes_to_core():
    delegate = LegacyChatExecuteDelegate(prefer_core=True)
    result = delegate.delegate_chat({"message": "route this chat through core"})
    assert result["delegated"] is True
    assert result["delegated_to"] == "murphy_core"
    assert result["payload"]["trace_id"]


def test_delegate_execute_routes_to_core():
    delegate = LegacyChatExecuteDelegate(prefer_core=True)
    result = delegate.delegate_execute({"task_description": "execute this through core"})
    assert result["delegated"] is True
    assert result["delegated_to"] == "murphy_core"
    assert result["payload"]["route"]

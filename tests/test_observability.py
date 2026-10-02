from multimodal_agents.observability import Telemetry, _redact


def test_redact_removes_sensitive_fields_recursively() -> None:
    assert _redact(
        {
            "token": "secret-token",
            "nested": {"authorization_header": "Bearer hidden"},
            "safe": ["completed", {"evidence_id": "ev-1"}],
        }
    ) == {
        "token": "[REDACTED]",
        "nested": {"authorization_header": "[REDACTED]"},
        "safe": ["completed", {"evidence_id": "ev-1"}],
    }


def test_telemetry_is_a_no_op_without_keys(monkeypatch) -> None:
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    telemetry = Telemetry()
    assert telemetry.enabled is False
    with telemetry.orchestration("trace-reader", 24) as observation:
        assert observation is None
    with telemetry.specialist("vision") as observation:
        assert observation is None

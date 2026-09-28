from multimodal_agents.policy_gate import (
    ActionRequest,
    Approval,
    decide,
    parameter_digest,
)


def request(**updates):
    values = {
        "action_id": "action-1",
        "actor": "operator-7",
        "tool": "issue_refund",
        "target": "order-A1002",
        "parameters": {"amount_usd": 45},
        "risk": "high",
        "evidence_ids": ("obs-order", "obs-identity"),
    }
    values.update(updates)
    return ActionRequest(**values)


def approval(item):
    return Approval(
        "approval-88",
        item.actor,
        item.tool,
        item.target,
        parameter_digest(item.parameters),
        "2026-01-01T09:05:00+00:00",
    )


def test_high_risk_action_waits_for_approval():
    assert decide(request())["outcome"] == "pending"


def test_bound_approval_allows_exact_action():
    item = request()
    result = decide(item, approval(item))
    assert result["outcome"] == "allowed"
    assert result["approval_id"] == "approval-88"


def test_changed_parameters_invalidate_approval():
    item = request()
    token = approval(item)
    changed = request(parameters={"amount_usd": 450})
    assert decide(changed, token)["reason"] == "approval scope mismatch"


def test_expired_approval_is_denied():
    item = request()
    result = decide(item, approval(item), now="2026-01-01T09:05:00+00:00")
    assert result["outcome"] == "denied"
    assert result["reason"] == "approval expired"


def test_open_conflict_denies_action_even_with_approval():
    item = request(conflict_ids=("conflict-door-0001",))
    assert decide(item, approval(item))["outcome"] == "denied"


def test_missing_evidence_is_denied():
    assert decide(request(evidence_ids=()))["outcome"] == "denied"


def test_low_risk_supported_read_is_allowed():
    result = decide(request(risk="low", tool="read_status"))
    assert result["outcome"] == "allowed"
    assert result["policy_version"] == "action-policy-v1"

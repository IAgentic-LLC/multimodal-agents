import json
from pathlib import Path

from multimodal_agents.policy_gate import (
    ActionRequest,
    Approval,
    decide,
    parameter_digest,
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    refund = ActionRequest(
        "action-refund-1",
        "operator-7",
        "issue_refund",
        "order-A1002",
        {"amount_usd": 45},
        "high",
        ("obs-order", "obs-identity"),
    )
    approval = Approval(
        "approval-88",
        refund.actor,
        refund.tool,
        refund.target,
        parameter_digest(refund.parameters),
        "2026-01-01T09:05:00+00:00",
    )
    changed = ActionRequest(**{
        **refund.__dict__,
        "action_id": "action-refund-mutated",
        "parameters": {"amount_usd": 450},
    })
    conflicted = ActionRequest(
        "action-lock-1",
        "operator-7",
        "lock_door",
        "warehouse-door",
        {},
        "high",
        ("obs-camera-door", "obs-reed-door"),
        ("conflict-door-0001",),
    )
    result = {
        "without_approval": decide(refund),
        "with_approval": decide(refund, approval),
        "mutated_parameters": decide(changed, approval),
        "open_conflict": decide(conflicted, approval),
    }
    output = root / "runs" / "gate-26" / "policy-decisions.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

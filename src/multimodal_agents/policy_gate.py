import hashlib
import json
from dataclasses import dataclass
from datetime import datetime


def parameter_digest(parameters: dict) -> str:
    encoded = json.dumps(parameters, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


@dataclass(frozen=True)
class ActionRequest:
    action_id: str
    actor: str
    tool: str
    target: str
    parameters: dict
    risk: str
    evidence_ids: tuple[str, ...]
    conflict_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Approval:
    approval_id: str
    actor: str
    tool: str
    target: str
    parameter_digest: str
    expires_at: str


def decide(
    request: ActionRequest,
    approval: Approval | None = None,
    now: str = "2026-01-01T09:00:00+00:00",
) -> dict:
    if request.conflict_ids:
        return _result(request, "denied", "open evidence conflict")
    if not request.evidence_ids:
        return _result(request, "denied", "missing supporting evidence")
    if request.risk == "low":
        return _result(request, "allowed", "low-risk policy")
    if approval is None:
        return _result(
            request,
            "pending",
            "parameter-bound approval required",
        )
    expired = datetime.fromisoformat(now) >= datetime.fromisoformat(
        approval.expires_at,
    )
    if expired:
        return _result(request, "denied", "approval expired")
    matches = (
        approval.actor == request.actor
        and approval.tool == request.tool
        and approval.target == request.target
        and approval.parameter_digest == parameter_digest(request.parameters)
    )
    if not matches:
        return _result(request, "denied", "approval scope mismatch")
    return {
        **_result(request, "allowed", "valid parameter-bound approval"),
        "approval_id": approval.approval_id,
    }


def _result(request: ActionRequest, outcome: str, reason: str) -> dict:
    return {
        "action_id": request.action_id,
        "outcome": outcome,
        "reason": reason,
        "policy_version": "action-policy-v1",
        "evidence_ids": list(request.evidence_ids),
        "conflict_ids": list(request.conflict_ids),
    }

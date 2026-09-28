from dataclasses import dataclass, field

from multimodal_agents.safe_actions import TargetSnapshot, validate_target


@dataclass(frozen=True)
class ActionRequest:
    action_id: str
    target: TargetSnapshot
    permission: str
    expected_status: str
    approval_id: str | None = None


@dataclass
class LocalReleaseSandbox:
    revision: str = "release-42"
    status: str = "ready"
    completed_actions: set[str] = field(default_factory=set)

    def deploy(self, action_id: str) -> None:
        if action_id in self.completed_actions:
            return
        self.revision = "release-43"
        self.status = "deployed"
        self.completed_actions.add(action_id)


def run_action(
    request: ActionRequest,
    current: TargetSnapshot,
    permissions: set[str],
    sandbox: LocalReleaseSandbox,
    receives_events: bool = True,
) -> list[dict[str, str]]:
    trace: list[dict[str, str]] = []
    trace.append({"event": "action.requested", "action_id": request.action_id})
    if request.permission not in permissions:
        trace.append({"event": "action.refused", "reason": "permission denied"})
        return trace
    if not request.approval_id:
        trace.append({"event": "action.refused", "reason": "approval required"})
        return trace
    decision = validate_target(request.target, current, receives_events)
    if decision.status == "rejected":
        trace.append({"event": "action.refused", "reason": decision.reason})
        return trace
    already_done = request.action_id in sandbox.completed_actions
    sandbox.deploy(request.action_id)
    trace.append({
        "event": "action.recovered" if already_done else "action.executed",
        "revision": sandbox.revision,
    })
    if sandbox.status == request.expected_status:
        trace.append({"event": "postcondition.proved", "status": sandbox.status})
    else:
        trace.append({"event": "postcondition.failed", "status": sandbox.status})
    return trace

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class TargetSnapshot:
    stable_id: str
    role: str
    name: str
    revision: str
    bounds: tuple[int, int, int, int]


@dataclass(frozen=True)
class ActionDecision:
    status: Literal["allowed", "rejected"]
    reason: str


def validate_target(
    observed: TargetSnapshot,
    current: TargetSnapshot,
    receives_events: bool,
) -> ActionDecision:
    if observed.stable_id != current.stable_id:
        return ActionDecision("rejected", "target identity changed")
    if observed.revision != current.revision:
        return ActionDecision("rejected", "target revision is stale")
    if (observed.role, observed.name) != (current.role, current.name):
        return ActionDecision("rejected", "target semantics changed")
    if observed.bounds != current.bounds:
        return ActionDecision("rejected", "target geometry changed")
    if not receives_events:
        return ActionDecision("rejected", "target does not receive events")
    return ActionDecision("allowed", "all preconditions hold")


def verify_postcondition(
    before_revision: str,
    after_revision: str,
    expected_status: str,
    observed_status: str,
) -> ActionDecision:
    if before_revision == after_revision:
        return ActionDecision("rejected", "application revision did not change")
    if observed_status != expected_status:
        return ActionDecision("rejected", "expected state was not observed")
    return ActionDecision("allowed", "postcondition proved")

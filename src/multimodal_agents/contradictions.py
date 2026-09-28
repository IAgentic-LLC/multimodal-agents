from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

from multimodal_agents.sensor_world import Observation


@dataclass(frozen=True)
class Contradiction:
    contradiction_id: str
    kind: str
    property: str
    observation_ids: tuple[str, str]
    values: tuple[Any, Any]
    status: str
    detected_at: str
    resolution_id: str | None = None
    resolution_reason: str | None = None

    def as_record(self) -> dict:
        return asdict(self)


def detect_value_conflict(
    left: Observation,
    right: Observation,
    tolerance_s: float = 1.0,
) -> Contradiction | None:
    if left.property != right.property:
        return None
    if left.quality != "good" or right.quality != "good":
        return None
    elapsed = abs(
        (
            datetime.fromisoformat(left.phenomenon_time)
            - datetime.fromisoformat(right.phenomenon_time)
        ).total_seconds()
    )
    if elapsed > tolerance_s or left.value == right.value:
        return None
    detected_at = max(left.result_time, right.result_time)
    return Contradiction(
        contradiction_id="conflict-door-0001",
        kind="value_conflict",
        property=left.property,
        observation_ids=(left.observation_id, right.observation_id),
        values=(left.value, right.value),
        status="open",
        detected_at=detected_at,
    )


def resolve_with_observation(
    conflict: Contradiction,
    resolution: Observation,
    reason: str,
) -> Contradiction:
    if conflict.status != "open":
        raise ValueError("only an open contradiction can be resolved")
    if resolution.property != conflict.property:
        raise ValueError("resolution must observe the conflicted property")
    if resolution.quality != "good":
        raise ValueError("resolution observation quality must be good")
    if resolution.value not in conflict.values:
        raise ValueError("resolution must support one recorded value")
    return Contradiction(
        **{
            **conflict.as_record(),
            "status": "resolved",
            "resolution_id": resolution.observation_id,
            "resolution_reason": reason,
        }
    )

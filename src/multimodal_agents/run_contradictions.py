import json
from pathlib import Path

from multimodal_agents.contradictions import (
    detect_value_conflict,
    resolve_with_observation,
)
from multimodal_agents.run_sensor_world import fixture
from multimodal_agents.sensor_world import Observation


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    observations = fixture()
    conflict = detect_value_conflict(observations[0], observations[1])
    if conflict is None:
        raise RuntimeError("fixture did not create the expected conflict")
    review = Observation(
        "obs-human-door",
        "human-review-4",
        "door_state",
        "open",
        None,
        "2026-01-01T09:00:03+00:00",
        "2026-01-01T09:00:08+00:00",
        "good",
        1.0,
        "review/door/41",
    )
    resolved = resolve_with_observation(
        conflict,
        review,
        "on-site reviewer inspected the physical latch",
    )
    result = {
        "open": conflict.as_record(),
        "resolved": resolved.as_record(),
        "retained_observations": [
            observations[0].observation_id,
            observations[1].observation_id,
            review.observation_id,
        ],
        "action_allowed_while_open": False,
    }
    output = root / "runs" / "gate-25" / "contradiction-lifecycle.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

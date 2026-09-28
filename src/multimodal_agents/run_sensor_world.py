import json
from pathlib import Path

from multimodal_agents.sensor_world import Observation, build_world_state


def fixture() -> list[Observation]:
    base = {
        "result_time": "2026-01-01T09:00:02+00:00",
        "quality": "good",
    }
    return [
        Observation(
            "obs-camera-door",
            "camera-7",
            "door_state",
            "closed",
            None,
            "2026-01-01T09:00:00.000+00:00",
            reliability=0.72,
            locator="video/warehouse.mp4#t=8,10",
            **base,
        ),
        Observation(
            "obs-reed-door",
            "reed-switch-2",
            "door_state",
            "open",
            None,
            "2026-01-01T09:00:00.100+00:00",
            reliability=0.99,
            locator="iot/reed-switch-2/8841",
            **base,
        ),
        Observation(
            "obs-temperature",
            "thermocouple-4",
            "temperature",
            68.0,
            "Cel",
            "2026-01-01T09:00:00.500+00:00",
            reliability=0.97,
            locator="iot/thermocouple-4/9918",
            **base,
        ),
        Observation(
            "obs-alarm",
            "microphone-3",
            "acoustic_event",
            "alarm",
            None,
            "2026-01-01T09:00:01.200+00:00",
            reliability=0.88,
            locator="audio/warehouse.wav#t=1.0,1.8",
            **base,
        ),
    ]


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    output = root / "runs" / "gate-24" / "sensor-world-state.json"
    result = build_world_state(fixture())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

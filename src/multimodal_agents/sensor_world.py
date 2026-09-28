from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class Observation:
    observation_id: str
    source: str
    property: str
    value: Any
    unit: str | None
    phenomenon_time: str
    result_time: str
    quality: str
    reliability: float
    locator: str

    def as_record(self) -> dict:
        return asdict(self)


def seconds_between(left: str, right: str) -> float:
    difference = datetime.fromisoformat(left) - datetime.fromisoformat(right)
    return abs(difference.total_seconds())


def build_world_state(observations: list[Observation]) -> dict:
    by_property: dict[str, list[Observation]] = {}
    for observation in observations:
        by_property.setdefault(observation.property, []).append(observation)

    properties = {}
    for name, members in by_property.items():
        usable = [item for item in members if item.quality == "good"]
        values = {str(item.value) for item in usable}
        properties[name] = {
            "status": "agreed" if len(values) <= 1 else "conflicted",
            "observations": [item.as_record() for item in members],
        }

    temperatures = [
        item for item in observations
        if item.property == "temperature" and item.quality == "good"
    ]
    alarms = [
        item for item in observations
        if item.property == "acoustic_event"
        and item.value == "alarm"
        and item.quality == "good"
    ]
    supported_pairs = [
        (temperature, alarm)
        for temperature in temperatures
        for alarm in alarms
        if temperature.unit == "Cel"
        and float(temperature.value) >= 60
        and seconds_between(
            temperature.phenomenon_time,
            alarm.phenomenon_time,
        ) <= 2
    ]
    hazard = {
        "status": "supported" if supported_pairs else "unsupported",
        "claim": "high temperature with concurrent alarm",
        "evidence": [
            item.observation_id
            for pair in supported_pairs[:1]
            for item in pair
        ],
    }
    return {"properties": properties, "derived_claims": {"hazard": hazard}}

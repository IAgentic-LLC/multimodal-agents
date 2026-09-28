import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ScenarioEvent:
    at_ms: int
    modality: str
    kind: str
    payload: dict


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    seed: int
    events: tuple[ScenarioEvent, ...]
    expected: dict


def replay(scenario: Scenario) -> dict:
    ordered = sorted(
        enumerate(scenario.events),
        key=lambda item: (item[1].at_ms, item[0]),
    )
    trace = [
        {"sequence": index, **asdict(event)}
        for index, (_, event) in enumerate(ordered)
    ]
    encoded = json.dumps(trace, sort_keys=True, separators=(",", ":"))
    return {
        "scenario_id": scenario.scenario_id,
        "seed": scenario.seed,
        "trace": trace,
        "trace_digest": hashlib.sha256(encoded.encode()).hexdigest(),
    }


def score(scenario: Scenario, result: dict) -> dict:
    checks = {
        key: result.get(key) == expected
        for key, expected in scenario.expected.items()
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "passed_count": sum(checks.values()),
        "total_count": len(checks),
    }

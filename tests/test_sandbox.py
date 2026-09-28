from multimodal_agents.run_sandbox import fixture
from multimodal_agents.sandbox import ScenarioEvent, replay, score


def test_same_scenario_replays_to_same_digest():
    scenario = fixture()
    first = replay(scenario)["trace_digest"]
    second = replay(scenario)["trace_digest"]
    assert first == second


def test_equal_timestamps_keep_declared_order():
    scenario = fixture()
    events = scenario.events + (
        ScenarioEvent(1400, "tool", "policy", {"value": "deny"}),
    )
    trace = replay(type(scenario)(
        scenario.scenario_id,
        scenario.seed,
        events,
        scenario.expected,
    ))["trace"]
    assert [item["modality"] for item in trace[-2:]] == ["voice", "tool"]


def test_expected_result_scores_all_boundaries():
    scenario = fixture()
    result = score(scenario, {
        "hazard": "supported",
        "door_state": "conflicted",
        "action": "denied",
    })
    assert result == {
        "passed": True,
        "checks": {"hazard": True, "door_state": True, "action": True},
        "passed_count": 3,
        "total_count": 3,
    }


def test_unsafe_action_fails_without_hiding_other_passes():
    result = score(fixture(), {
        "hazard": "supported",
        "door_state": "conflicted",
        "action": "allowed",
    })
    assert result["passed"] is False
    assert result["checks"] == {
        "hazard": True,
        "door_state": True,
        "action": False,
    }

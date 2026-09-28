from multimodal_agents.run_sensor_world import fixture
from multimodal_agents.sensor_world import Observation, build_world_state


def test_conflicting_sensor_values_are_preserved():
    state = build_world_state(fixture())
    door = state["properties"]["door_state"]
    assert door["status"] == "conflicted"
    assert [item["value"] for item in door["observations"]] == [
        "closed",
        "open",
    ]


def test_hazard_requires_two_time_aligned_sources():
    state = build_world_state(fixture())
    hazard = state["derived_claims"]["hazard"]
    assert hazard["status"] == "supported"
    assert hazard["evidence"] == ["obs-temperature", "obs-alarm"]


def test_bad_quality_observation_cannot_support_hazard():
    items = fixture()
    alarm = items[-1]
    items[-1] = Observation(**{**alarm.as_record(), "quality": "bad"})
    state = build_world_state(items)
    assert state["derived_claims"]["hazard"]["status"] == "unsupported"


def test_distant_events_cannot_support_concurrent_hazard():
    items = fixture()
    alarm = items[-1]
    items[-1] = Observation(**{
        **alarm.as_record(),
        "phenomenon_time": "2026-01-01T09:00:10+00:00",
    })
    state = build_world_state(items)
    assert state["derived_claims"]["hazard"]["status"] == "unsupported"

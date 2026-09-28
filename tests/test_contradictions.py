import pytest

from multimodal_agents.contradictions import (
    detect_value_conflict,
    resolve_with_observation,
)
from multimodal_agents.run_contradictions import Observation
from multimodal_agents.run_sensor_world import fixture


def review(value="open", quality="good", property="door_state"):
    return Observation(
        "obs-review",
        "human-review",
        property,
        value,
        None,
        "2026-01-01T09:00:03+00:00",
        "2026-01-01T09:00:08+00:00",
        quality,
        1.0,
        "review/door/41",
    )


def test_detects_overlapping_value_conflict_without_picking_winner():
    items = fixture()
    conflict = detect_value_conflict(items[0], items[1])
    assert conflict is not None
    assert conflict.status == "open"
    assert conflict.values == ("closed", "open")
    assert conflict.observation_ids == (
        "obs-camera-door",
        "obs-reed-door",
    )


def test_different_properties_do_not_conflict():
    items = fixture()
    assert detect_value_conflict(items[1], items[2]) is None


def test_reliability_does_not_auto_resolve_conflict():
    items = fixture()
    conflict = detect_value_conflict(items[0], items[1])
    assert conflict is not None
    assert items[1].reliability > items[0].reliability
    assert conflict.status == "open"


def test_resolution_links_new_evidence_and_keeps_originals():
    items = fixture()
    conflict = detect_value_conflict(items[0], items[1])
    assert conflict is not None
    resolved = resolve_with_observation(conflict, review(), "latch inspected")
    assert resolved.status == "resolved"
    assert resolved.resolution_id == "obs-review"
    assert resolved.observation_ids == conflict.observation_ids


@pytest.mark.parametrize(
    "observation",
    [review("ajar"), review(quality="bad"), review(property="window_state")],
)
def test_unsupported_resolution_is_rejected(observation):
    items = fixture()
    conflict = detect_value_conflict(items[0], items[1])
    assert conflict is not None
    with pytest.raises(ValueError):
        resolve_with_observation(conflict, observation, "unsupported")

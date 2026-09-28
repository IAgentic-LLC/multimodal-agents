from dataclasses import replace

from multimodal_agents.production_controls import (
    evaluate_release,
    release_controls,
)


def test_complete_control_set_is_ready():
    result = evaluate_release(release_controls())
    assert result["ready"] is True
    assert result["summary"]["passed"] == 8
    assert result["summary"]["total"] == 8


def test_missing_required_area_blocks_release():
    controls = [
        control for control in release_controls()
        if control.area != "tenant_isolation"
    ]
    result = evaluate_release(controls)
    assert result["ready"] is False
    assert result["summary"]["missing_areas"] == ["tenant_isolation"]


def test_failed_control_blocks_release():
    controls = release_controls()
    controls[0] = replace(controls[0], implemented=False)
    result = evaluate_release(controls)
    assert result["ready"] is False
    assert result["summary"]["failed_controls"] == ["CTL-ACCESS-01"]


def test_duplicate_area_is_rejected_as_ambiguous():
    controls = release_controls()
    controls.append(replace(controls[0], control_id="CTL-ACCESS-02"))
    result = evaluate_release(controls)
    assert result["ready"] is False
    assert result["summary"]["duplicate_areas"] == ["access"]


def test_mapping_is_not_presented_as_certification():
    result = evaluate_release(release_controls())
    assert "not a legal opinion or certification" in result["mapping_notice"]

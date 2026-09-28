from multimodal_agents.screen_fusion import (
    ScreenObservation,
    action_allowed,
    fuse_property,
)


def observation(source: str, value: str, offset_ms: int = 1000):
    return ScreenObservation(
        observation_id=f"obs-{source}",
        source=source,  # type: ignore[arg-type]
        subject="deploy-build",
        property_name="actionable",
        value=value,
        offset_ms=offset_ms,
        revision="release-42",
    )


def test_agreement_allows_expected_action():
    fused = fuse_property(
        [observation("pixels", "true"), observation("dom", "true")],
        "deploy-build",
        "actionable",
    )
    assert fused.status == "agreed"
    assert action_allowed(fused, "true")


def test_disagreement_is_retained_and_blocks_action():
    fused = fuse_property(
        [observation("pixels", "false"), observation("dom", "true")],
        "deploy-build",
        "actionable",
    )
    assert fused.status == "conflicted"
    assert len(fused.observations) == 2
    assert not action_allowed(fused, "true")


def test_newer_value_does_not_erase_older_source():
    fused = fuse_property(
        [
            observation("pixels", "false", 1000),
            observation("api", "true", 1100),
        ],
        "deploy-build",
        "actionable",
    )
    assert [item.source for item in fused.observations] == ["pixels", "api"]
    assert fused.status == "conflicted"


def test_missing_property_is_not_actionable():
    fused = fuse_property([], "deploy-build", "actionable")
    assert fused.status == "missing"
    assert not action_allowed(fused, "true")

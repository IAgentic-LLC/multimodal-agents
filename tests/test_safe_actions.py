from multimodal_agents.safe_actions import (
    TargetSnapshot,
    validate_target,
    verify_postcondition,
)


def target(revision="rev-1", bounds=(20, 30, 120, 48)):
    return TargetSnapshot(
        stable_id="deploy-build",
        role="button",
        name="Deploy build",
        revision=revision,
        bounds=bounds,
    )


def test_current_target_is_allowed():
    assert validate_target(target(), target(), True).status == "allowed"


def test_stale_revision_is_rejected():
    decision = validate_target(target("rev-1"), target("rev-2"), True)
    assert decision.reason == "target revision is stale"


def test_changed_geometry_is_rejected():
    decision = validate_target(target(), target(bounds=(40, 30, 120, 48)), True)
    assert decision.reason == "target geometry changed"


def test_occluded_target_is_rejected():
    decision = validate_target(target(), target(), False)
    assert decision.reason == "target does not receive events"


def test_postcondition_requires_new_revision_and_expected_state():
    stale = verify_postcondition("rev-1", "rev-1", "deployed", "deployed")
    wrong = verify_postcondition("rev-1", "rev-2", "deployed", "failed")
    proved = verify_postcondition("rev-1", "rev-2", "deployed", "deployed")
    assert stale.status == "rejected"
    assert wrong.status == "rejected"
    assert proved.reason == "postcondition proved"

from multimodal_agents.safe_actions import TargetSnapshot
from multimodal_agents.screen_agent import (
    ActionRequest,
    LocalReleaseSandbox,
    run_action,
)


def target(revision="rev-42"):
    return TargetSnapshot(
        stable_id="deploy-build",
        role="button",
        name="Deploy build",
        revision=revision,
        bounds=(20, 30, 120, 48),
    )


def request(revision="rev-42", approval="approval-7"):
    return ActionRequest(
        action_id="action-001",
        target=target(revision),
        permission="release.deploy",
        expected_status="deployed",
        approval_id=approval,
    )


def test_complete_local_task_and_prove_result():
    sandbox = LocalReleaseSandbox()
    trace = run_action(
        request(), target(), {"release.deploy"}, sandbox,
    )
    assert [item["event"] for item in trace] == [
        "action.requested",
        "action.executed",
        "postcondition.proved",
    ]
    assert sandbox.status == "deployed"


def test_stale_action_is_refused_without_side_effect():
    sandbox = LocalReleaseSandbox()
    trace = run_action(
        request("rev-41"), target(), {"release.deploy"}, sandbox,
    )
    assert trace[-1]["reason"] == "target revision is stale"
    assert sandbox.status == "ready"


def test_permission_and_approval_are_independent_gates():
    sandbox = LocalReleaseSandbox()
    denied = run_action(request(), target(), set(), sandbox)
    unapproved = run_action(
        request(approval=None), target(), {"release.deploy"}, sandbox,
    )
    assert denied[-1]["reason"] == "permission denied"
    assert unapproved[-1]["reason"] == "approval required"


def test_recovery_is_idempotent_and_proves_existing_result():
    sandbox = LocalReleaseSandbox()
    run_action(request(), target(), {"release.deploy"}, sandbox)
    trace = run_action(request(), target(), {"release.deploy"}, sandbox)
    assert trace[-2]["event"] == "action.recovered"
    assert trace[-1]["event"] == "postcondition.proved"
    assert sandbox.completed_actions == {"action-001"}

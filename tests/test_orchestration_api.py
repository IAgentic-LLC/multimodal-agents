import asyncio

from multimodal_agents import orchestration_api
from multimodal_agents.orchestration_api import OrchestrationRequest, build_result


def test_roles_now_include_all_five_capstone_specialists() -> None:
    assert orchestration_api.ROLES == (
        "vision",
        "retrieval",
        "analysis",
        "visualization",
        "edit-proposal",
    )


def test_build_result_requires_all_five_for_completed_status() -> None:
    specialists = [
        {"role": role, "status": "completed"} for role in orchestration_api.ROLES
    ]
    result = build_result("trace-1", specialists, 42)
    assert result["status"] == "completed"
    assert result["evidence_backed_claims"] == 5
    assert result["duration_ms"] == 42


def test_build_result_treats_proposed_pending_approval_as_supported() -> None:
    specialists = [
        {"role": "vision", "status": "completed"},
        {"role": "retrieval", "status": "completed"},
        {"role": "analysis", "status": "completed"},
        {"role": "visualization", "status": "completed"},
        {"role": "edit-proposal", "status": "proposed_pending_approval"},
    ]
    result = build_result("trace-2", specialists, 10)
    assert result["status"] == "completed"
    assert result["evidence_backed_claims"] == 5


def test_build_result_does_not_count_edit_proposal_refusal_as_supported() -> None:
    specialists = [
        {"role": "vision", "status": "completed"},
        {"role": "retrieval", "status": "completed"},
        {"role": "analysis", "status": "completed"},
        {"role": "visualization", "status": "completed"},
        {"role": "edit-proposal", "status": "refused"},
    ]
    result = build_result("trace-3", specialists, 10)
    assert result["status"] == "partial_failure"
    assert result["evidence_backed_claims"] == 4


def test_a2a_url_env_var_converts_hyphenated_role_to_underscored_name() -> None:
    assert orchestration_api.a2a_url_env_var("edit-proposal") == (
        "EDIT_PROPOSAL_A2A_URL"
    )
    assert orchestration_api.a2a_url_env_var("vision") == "VISION_A2A_URL"


def test_artifact_payload_unwraps_send_message_response() -> None:
    response = {
        "result": {
            "task": {
                "artifacts": [
                    {
                        "parts": [
                            {
                                "text": (
                                    '{"claim":"closed","evidence_ids":["e1"]}'
                                )
                            }
                        ]
                    }
                ]
            }
        }
    }
    assert orchestration_api.artifact_payload(response) == {
        "claim": "closed",
        "evidence_ids": ["e1"],
    }


def test_orchestration_completes_with_five_specialists(monkeypatch) -> None:
    async def fake_token() -> str:
        return "token"

    async def fake_delegate(
        role: str, question: str, token: str, trace_id: str
    ) -> dict:
        assert question == "Is the door closed?"
        assert token == "token"
        assert trace_id.startswith("trace-")
        return {
            "role": role,
            "status": "completed",
            "claim": "closed",
            "evidence_ids": [f"{role}-evidence"],
        }

    monkeypatch.setattr(orchestration_api, "access_token", fake_token)
    monkeypatch.setattr(orchestration_api, "delegate", fake_delegate)
    result = asyncio.run(
        orchestration_api.orchestrate(
            OrchestrationRequest(question="Is the door closed?")
        )
    )
    assert result["status"] == "completed"
    assert result["evidence_backed_claims"] == 5
    assert result["action_gate"] == "blocked_without_explicit_authority"


def test_orchestration_preserves_partial_failure(monkeypatch) -> None:
    async def fake_token() -> str:
        return "token"

    async def fake_delegate(
        role: str, question: str, token: str, trace_id: str
    ) -> dict:
        if role == "retrieval":
            raise RuntimeError("unavailable")
        return {"role": role, "status": "completed"}

    monkeypatch.setattr(orchestration_api, "access_token", fake_token)
    monkeypatch.setattr(orchestration_api, "delegate", fake_delegate)
    result = asyncio.run(
        orchestration_api.orchestrate(
            OrchestrationRequest(question="Is the door closed?")
        )
    )
    assert result["status"] == "partial_failure"
    assert result["evidence_backed_claims"] == 4
    assert result["specialists"][1]["detail"] == "unavailable"

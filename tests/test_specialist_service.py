from fastapi.testclient import TestClient

from multimodal_agents.specialist_service import app


def test_specialist_requires_tenant_token_and_observe_authority() -> None:
    client = TestClient(app)
    payload = {
        "task_id": "t",
        "capability": "locate door",
        "evidence_ids": ["frame"],
        "authority": "observe",
    }
    headers = {
        "Authorization": "Bearer local-smoke-token",
        "X-Tenant-Id": "tenant-blue",
        "X-Trace-Id": "trace",
    }
    assert client.post("/tasks", json=payload).status_code == 422
    ok = client.post("/tasks", json=payload, headers=headers)
    assert ok.status_code == 200 and ok.json()["trace_id"] == "trace"
    payload["authority"] = "mutate"
    assert (
        client.post("/tasks", json=payload, headers=headers).status_code
        == 403
    )

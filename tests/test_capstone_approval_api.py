import json

from fastapi.testclient import TestClient

from multimodal_agents.capstone_approval_api import (
    EditDecisionRequest,
    app,
    record_decision,
)


def test_approved_decision_is_appended_but_never_applied(tmp_path, monkeypatch):
    log_path = tmp_path / "decisions.jsonl"
    monkeypatch.setattr(
        "multimodal_agents.capstone_approval_api.AUDIT_LOG_PATH", log_path
    )
    request = EditDecisionRequest(
        claim="proposed edit grounded in runs/gate-36/medical-segmentation.json: widen the threshold",
        evidence_ids=["runs/gate-36/medical-segmentation.json"],
        chapter=9,
        decision="approved",
        reviewer="adrian",
    )
    entry = record_decision(request)
    assert entry["decision"] == "approved"
    assert entry["applied"] is False
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["decision_id"] == entry["decision_id"]


def test_rejected_decision_is_also_only_logged(tmp_path, monkeypatch):
    log_path = tmp_path / "decisions.jsonl"
    monkeypatch.setattr(
        "multimodal_agents.capstone_approval_api.AUDIT_LOG_PATH", log_path
    )
    request = EditDecisionRequest(
        claim="proposed edit grounded in runs/gate-36/video-tracking.json: drop track 7",
        evidence_ids=["runs/gate-36/video-tracking.json"],
        decision="rejected",
        reviewer="adrian",
    )
    entry = record_decision(request)
    assert entry["decision"] == "rejected"
    assert entry["applied"] is False


def test_invalid_decision_value_is_rejected_by_validation():
    try:
        EditDecisionRequest(
            claim="x", decision="maybe", reviewer="adrian"
        )
        raised = False
    except Exception:
        raised = True
    assert raised


def test_decide_endpoint_records_and_never_sets_applied_true(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "multimodal_agents.capstone_approval_api.AUDIT_LOG_PATH",
        tmp_path / "decisions.jsonl",
    )
    client = TestClient(app)
    response = client.post(
        "/api/edit-proposals/decide",
        json={
            "claim": "widen the threshold",
            "evidence_ids": ["runs/gate-36/medical-segmentation.json"],
            "chapter": 9,
            "decision": "approved",
            "reviewer": "adrian",
        },
    )
    assert response.status_code == 200
    assert response.json()["applied"] is False


def test_evidence_image_rejects_path_traversal(tmp_path, monkeypatch):
    figures_dir = tmp_path / "figures"
    figures_dir.mkdir()
    (figures_dir / "ch09-real.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    secret = tmp_path / "secret.png"
    secret.write_bytes(b"not a real figure")
    monkeypatch.setattr(
        "multimodal_agents.capstone_approval_api.FIGURES_DIR", figures_dir
    )
    client = TestClient(app)

    ok = client.get("/api/evidence-image", params={"source_file": "ch09-real.png"})
    assert ok.status_code == 200

    traversal = client.get(
        "/api/evidence-image",
        params={"source_file": "../secret.png"},
    )
    assert traversal.status_code == 404

    missing = client.get(
        "/api/evidence-image", params={"source_file": "does-not-exist.png"}
    )
    assert missing.status_code == 404

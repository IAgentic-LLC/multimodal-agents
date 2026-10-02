"""The only path that can act on an edit-proposal specialist's output: a
human decision, appended to an audit log. This never touches the book's
own retained evidence files, which stay immutable; it only ever appends a
new, separately-labeled decision record.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

AUDIT_LOG_PATH = Path(
    os.getenv("EDIT_DECISION_LOG", "runs/capstone-edit-decisions.jsonl")
)
_DEFAULT_FIGURES_DIR = (
    Path(__file__).resolve().parents[2].parent
    / "multimodal-agents-book"
    / "figures"
)
FIGURES_DIR = Path(os.getenv("EVIDENCE_FIGURES_DIR", str(_DEFAULT_FIGURES_DIR))).resolve()


class EditDecisionRequest(BaseModel):
    claim: str = Field(min_length=1, max_length=500)
    evidence_ids: list[str] = Field(default_factory=list)
    chapter: int | None = None
    decision: str = Field(pattern="^(approved|rejected)$")
    reviewer: str = Field(min_length=1, max_length=120)


def record_decision(request: EditDecisionRequest) -> dict:
    entry = {
        "decision_id": f"decision-{uuid.uuid4().hex[:12]}",
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "claim": request.claim,
        "evidence_ids": request.evidence_ids,
        "chapter": request.chapter,
        "decision": request.decision,
        "reviewer": request.reviewer,
        "applied": False,
    }
    AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


router = APIRouter()


@router.post("/api/edit-proposals/decide")
async def decide(request: EditDecisionRequest) -> dict:
    """Record a human decision on a proposed edit. ``applied`` is always
    false: this endpoint logs a decision, it never mutates any retained
    evidence file, approved or not.
    """
    return record_decision(request)


@router.get("/api/evidence-image")
async def evidence_image(source_file: str) -> FileResponse:
    """Serve one real committed figure by its evidence source_file path,
    read-only, and only from inside FIGURES_DIR. source_file comes from a
    search hit, not raw user input, but is still validated the same way.
    """
    name = Path(source_file).name
    if not name.endswith(".png"):
        raise HTTPException(400, "only .png evidence images are servable")
    candidate = (FIGURES_DIR / name).resolve()
    if candidate.parent != FIGURES_DIR or not candidate.is_file():
        raise HTTPException(404, "evidence image not found")
    return FileResponse(candidate, media_type="image/png")


app = FastAPI(title="IAgentic Capstone Edit Decisions", docs_url=None)
app.include_router(router)


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "capstone-edit-decisions"}

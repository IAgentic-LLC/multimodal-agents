"""Independently runnable specialist for the Chapter 35 smoke test."""

import os

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

ROLE = os.getenv("SPECIALIST_ROLE", "vision")
TOKEN = os.getenv("SPECIALIST_TOKEN", "local-smoke-token")
app = FastAPI(title=f"{ROLE} specialist")


class Task(BaseModel):
    task_id: str
    capability: str
    evidence_ids: list[str]
    authority: str = "observe"


@app.get("/.well-known/agent-card.json")
def card() -> dict[str, object]:
    skills = ["locate door"] if ROLE == "vision" else ["find door state"]
    return {"name": f"{ROLE}-specialist", "role": ROLE, "skills": skills}


@app.get("/healthz")
def health() -> dict[str, str]:
    return {"status": "ok", "role": ROLE}


@app.post("/tasks")
def task(
    item: Task,
    x_tenant_id: str = Header(),
    x_trace_id: str = Header(),
    authorization: str = Header(),
) -> dict[str, object]:
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(401, "invalid specialist token")
    if x_tenant_id != "tenant-blue":
        raise HTTPException(403, "tenant not allowed")
    if item.authority != "observe":
        raise HTTPException(403, "mutation authority not delegated")
    if ROLE == "vision":
        claim, evidence = "door appears closed", ["frame-087#region-door"]
    else:
        claim, evidence = "sensor event reports closed", ["sensor-door-441"]
    return {
        "task_id": item.task_id,
        "specialist": ROLE,
        "status": "completed",
        "claim": claim,
        "evidence_ids": evidence,
        "trace_id": x_trace_id,
    }

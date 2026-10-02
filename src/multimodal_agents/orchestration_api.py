"""Public, read-only coordinator for the Chapter 35 live demonstration."""

from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from multimodal_agents.capstone_approval_api import router as capstone_router
from multimodal_agents.observability import telemetry
from multimodal_agents.tenant_studio_api import router as tenant_studio_router


class OrchestrationRequest(BaseModel):
    question: str = Field(min_length=3, max_length=240)


ROLES: tuple[str, ...] = (
    "vision",
    "retrieval",
    "analysis",
    "visualization",
    "edit-proposal",
)

# A specialist delegation is "supported" when it produced a grounded
# result: either a completed observation, or edit-proposal's own
# proposed-but-not-yet-approved outcome. "refused" (edit-proposal found no
# evidence to ground a proposal) and "failed"/"timed_out" are not.
SUPPORTED_STATUSES: frozenset[str] = frozenset(
    {"completed", "proposed_pending_approval"}
)


def build_result(
    trace_id: str, specialists: list[dict], duration_ms: int
) -> dict:
    """Pure result-shape builder, kept separate from the HTTP handler so it
    can be unit tested without a live A2A/Auth0 round trip.
    """
    supported = sum(
        item.get("status") in SUPPORTED_STATUSES for item in specialists
    )
    return {
        "trace_id": trace_id,
        "authority": "observe_only",
        "status": "completed" if supported == len(ROLES) else "partial_failure",
        "duration_ms": duration_ms,
        "specialists": specialists,
        "evidence_backed_claims": supported,
        "action_gate": "blocked_without_explicit_authority",
    }


@dataclass(frozen=True)
class Token:
    value: str
    expires_at: float


_token: Token | None = None
_token_lock = asyncio.Lock()


def a2a_url_env_var(role: str) -> str:
    return f"{role.upper().replace('-', '_')}_A2A_URL"


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def post_json(url: str, payload: dict, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        message = f"upstream returned {error.code}: {detail}"
        raise RuntimeError(message) from error


async def access_token() -> str:
    global _token
    async with _token_lock:
        now = time.time()
        if _token and _token.expires_at > now + 30:
            return _token.value
        domain = required("AUTH0_DOMAIN").removeprefix("https://").rstrip("/")
        form = urllib.parse.urlencode(
            {
                "grant_type": "client_credentials",
                "client_id": required("AUTH0_CLIENT_ID"),
                "client_secret": required("AUTH0_CLIENT_SECRET"),
                "audience": required("AUTH0_AUDIENCE"),
                "organization": required("AUTH0_ORGANIZATION"),
            }
        ).encode()
        request = urllib.request.Request(
            f"https://{domain}/oauth/token",
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            response = await asyncio.to_thread(
                lambda: urllib.request.urlopen(request, timeout=12)
            )
            with response:
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")[:500]
            raise RuntimeError(
                f"Auth0 token exchange failed ({error.code}): {detail}"
            ) from error
        except (urllib.error.URLError, ValueError) as error:
            raise RuntimeError("Auth0 token exchange failed") from error
        value = payload.get("access_token")
        if not isinstance(value, str):
            raise RuntimeError("Auth0 returned no access token")
        _token = Token(value, now + int(payload.get("expires_in", 300)))
        return value


def artifact_payload(response: dict) -> dict:
    result = response.get("result", {})
    task = result.get("task", result)
    artifacts = task.get("artifacts", [])
    for artifact in artifacts:
        for part in artifact.get("parts", []):
            text = part.get("text")
            if isinstance(text, str):
                return json.loads(text)
    raise RuntimeError("specialist returned no evidence artifact")


async def delegate(
    role: str, question: str, token: str, trace_id: str
) -> dict:
    with telemetry().specialist(role) as observation:
        base = required(a2a_url_env_var(role)).rstrip("/")
        message_id = str(uuid.uuid4())
        body = {
            "jsonrpc": "2.0",
            "id": message_id,
            "method": "SendMessage",
            "params": {
                "message": {
                    "role": "ROLE_USER",
                    "parts": [{"text": question}],
                    "messageId": message_id,
                    "metadata": {"trace_id": trace_id},
                }
            },
        }
        started = time.perf_counter()
        try:
            response = await asyncio.to_thread(
                post_json,
                f"{base}/a2a/jsonrpc/",
                body,
                {
                    "Authorization": f"Bearer {token}",
                    "A2A-Version": "1.0",
                    "X-Trace-Id": trace_id,
                },
            )
            if "error" in response:
                raise RuntimeError(f"A2A error: {response['error']}")
            evidence = artifact_payload(response)
            result = {
                "role": role,
                "status": "completed",
                "latency_ms": round((time.perf_counter() - started) * 1000),
                **evidence,
            }
            if observation:
                observation.update(
                    output={
                        "status": "completed",
                        "latency_ms": result["latency_ms"],
                        "evidence_id": evidence.get("evidence_id"),
                    }
                )
            return result
        except Exception as error:
            if observation:
                observation.update(
                    level="ERROR",
                    status_message=type(error).__name__,
                    output={"status": "failed"},
                )
            raise


app = FastAPI(title="IAgentic Multimodal Coordinator", docs_url=None)
app.include_router(capstone_router)
app.include_router(tenant_studio_router)


@app.get("/healthz")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "multimodal-coordinator"}


@app.post("/api/orchestrations")
async def orchestrate(request: OrchestrationRequest) -> dict:
    trace_id = f"trace-{uuid.uuid4().hex[:12]}"
    started = time.perf_counter()
    with telemetry().orchestration(
        trace_id, len(request.question)
    ) as observation:
        try:
            token = await access_token()
            outcomes = await asyncio.gather(
                *(
                    delegate(role, request.question, token, trace_id)
                    for role in ROLES
                ),
                return_exceptions=True,
            )
        except RuntimeError as error:
            if observation:
                observation.update(
                    level="ERROR",
                    status_message="Auth0 token exchange failed",
                    output={"status": "unavailable"},
                )
            raise HTTPException(503, str(error)) from error
        specialists = []
        for role, outcome in zip(ROLES, outcomes, strict=True):
            if isinstance(outcome, Exception):
                specialists.append(
                    {"role": role, "status": "failed", "detail": str(outcome)}
                )
            else:
                specialists.append(outcome)
        result = build_result(
            trace_id,
            specialists,
            round((time.perf_counter() - started) * 1000),
        )
        if observation:
            observation.update(
                output={
                    "status": result["status"],
                    "duration_ms": result["duration_ms"],
                    "evidence_backed_claims": result["evidence_backed_claims"],
                    "action_gate": result["action_gate"],
                }
            )
        return result

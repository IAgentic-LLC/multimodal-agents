"""Protocol-conformant A2A specialist with OAuth-enforced task routes."""

from __future__ import annotations

import json
import logging
import os

from a2a.helpers.proto_helpers import new_task_from_user_message
from a2a.server.agent_execution.agent_executor import AgentExecutor
from a2a.server.agent_execution.context import RequestContext
from a2a.server.events.event_queue import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import (
    add_a2a_routes_to_fastapi,
    create_agent_card_routes,
    create_jsonrpc_routes,
    create_rest_routes,
)
from a2a.server.tasks.inmemory_task_store import InMemoryTaskStore
from a2a.server.tasks.task_updater import TaskUpdater
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
    ClientCredentialsOAuthFlow,
    OAuth2SecurityScheme,
    OAuthFlows,
    Part,
    SecurityRequirement,
    SecurityScheme,
    SendMessageRequest,
    StringList,
    Task,
    TaskState,
    TaskStatus,
)
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value

from .capstone_specialists import analyze, propose_edit, visualize
from .identity import decode_auth0_token, identity_from_claims

CAPSTONE_HANDLERS = {
    "analysis": analyze,
    "visualization": visualize,
    "edit-proposal": propose_edit,
}

ROLE = os.getenv("SPECIALIST_ROLE", "vision")
PUBLIC_BASE_URL = os.getenv("A2A_PUBLIC_BASE_URL", "http://127.0.0.1:8761")
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "example.auth0.com")
REQUIRED_SCOPE = os.getenv("A2A_REQUIRED_SCOPE", "read:sessions")
ALLOWED_ORGANIZATION = os.getenv("A2A_ALLOWED_ORGANIZATION", "")
LOGGER = logging.getLogger("multimodal.a2a.auth")


class EvidenceSpecialist(AgentExecutor):
    """Return one evidence-backed observation through the A2A lifecycle."""

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        missing_context = any(
            item is None
            for item in (context.task_id, context.context_id, context.message)
        )
        if missing_context:
            return
        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=context.task_id,
            context_id=context.context_id,
        )
        await event_queue.enqueue_event(
            Task(
                id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.TASK_STATE_SUBMITTED),
                history=[context.message],
            )
        )
        await updater.start_work()
        if ROLE in CAPSTONE_HANDLERS:
            question = next(
                (part.text for part in context.message.parts if part.text),
                "",
            )
            payload = await CAPSTONE_HANDLERS[ROLE](question)
        elif ROLE == "vision":
            payload = {
                "specialist": ROLE,
                "claim": "door appears closed",
                "evidence_ids": ["frame-087#region-door"],
            }
        else:
            payload = {
                "specialist": ROLE,
                "claim": "sensor event reports closed",
                "evidence_ids": ["sensor-door-441"],
            }
        await updater.add_artifact(
            parts=[Part(text=json.dumps(payload, sort_keys=True))],
            name="evidence-backed-observation",
            last_chunk=True,
        )
        await updater.complete()

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        if not context.task_id or not context.context_id:
            return
        updater = TaskUpdater(
            event_queue=event_queue,
            task_id=context.task_id,
            context_id=context.context_id,
        )
        await updater.cancel()


class TckSpecialist(AgentExecutor):
    """Deterministic protocol fixture used only when the official TCK runs."""

    async def execute(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        required = (context.task_id, context.context_id, context.message)
        if any(item is None for item in required):
            return
        updater = TaskUpdater(
            event_queue, context.task_id, context.context_id
        )
        if context.current_task is None:
            await event_queue.enqueue_event(
                new_task_from_user_message(context.message)
            )
        message_id = context.message.message_id
        if message_id.startswith("tck-message-response"):
            await event_queue.enqueue_event(
                updater.new_agent_message(
                    [Part(text="Direct message response")]
                )
            )
            return
        if message_id.startswith("tck-artifact-file-url"):
            part = Part(
                url="https://example.com/output.txt",
                media_type="text/plain",
                filename="output.txt",
            )
        elif message_id.startswith("tck-artifact-file"):
            part = Part(
                raw=b"tck", media_type="text/plain", filename="output.txt"
            )
        elif message_id.startswith("tck-artifact-data"):
            data = json_format.Parse('{"key":"value","count":42}', Value())
            part = Part(data=data)
        elif message_id.startswith("tck-artifact-text"):
            part = Part(text="Generated text content")
        else:
            await updater.complete(
                updater.new_agent_message([Part(text="TCK task completed")])
            )
            return
        await updater.add_artifact(parts=[part], last_chunk=True)
        await updater.complete()

    async def cancel(
        self, context: RequestContext, event_queue: EventQueue
    ) -> None:
        if context.task_id and context.context_id:
            updater = TaskUpdater(
                event_queue, context.task_id, context.context_id
            )
            await updater.cancel()


def agent_card() -> AgentCard:
    """Describe only the transports and capabilities actually implemented."""
    token_url = f"https://{AUTH0_DOMAIN}/oauth/token"
    oauth = SecurityScheme(
        oauth2_security_scheme=OAuth2SecurityScheme(
            description="Auth0 client-credentials access token",
            flows=OAuthFlows(
                client_credentials=ClientCredentialsOAuthFlow(
                    token_url=token_url,
                    scopes={REQUIRED_SCOPE: "Delegate an observation task"},
                )
            ),
        )
    )
    requirement = SecurityRequirement(
        schemes={"auth0M2M": StringList(list=[REQUIRED_SCOPE])}
    )
    skill_names = {
        "vision": "Locate visible evidence",
        "retrieval": "Retrieve evidence",
        "analysis": "Answer a question with cited retained evidence",
        "visualization": "Name the retained figure that best answers a question",
        "edit-proposal": "Propose a bounded, human-gated edit grounded in evidence",
    }
    skill_name = skill_names.get(ROLE, "Retrieve evidence")
    return AgentCard(
        name=f"IAgentic {ROLE.title()} Specialist",
        description="Returns a bounded claim with evidence identifiers.",
        provider=AgentProvider(
            organization="IAgentic LLC", url="https://iagentic.dev"
        ),
        version="1.0.0",
        capabilities=AgentCapabilities(
            streaming=False,
            push_notifications=False,
        ),
        security_schemes={"auth0M2M": oauth},
        security_requirements=[requirement],
        default_input_modes=["text/plain"],
        default_output_modes=["application/json"],
        skills=[
            AgentSkill(
                id=f"{ROLE}-evidence",
                name=skill_name,
                description="Return one observation and its evidence IDs.",
                tags=[ROLE, "evidence", "observation"],
                examples=["Determine whether the door is closed."],
                input_modes=["text/plain"],
                output_modes=["application/json"],
                security_requirements=[requirement],
            )
        ],
        supported_interfaces=[
            AgentInterface(
                protocol_binding="JSONRPC",
                protocol_version="1.0",
                url=f"{PUBLIC_BASE_URL}/a2a/jsonrpc/",
            ),
            AgentInterface(
                protocol_binding="HTTP+JSON",
                protocol_version="1.0",
                url=f"{PUBLIC_BASE_URL}/a2a/rest",
            ),
        ],
    )


def create_app() -> FastAPI:
    card = agent_card()
    executor = (
        TckSpecialist()
        if os.getenv("AUTH_MODE", "auth0") == "tck"
        else EvidenceSpecialist()
    )
    handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
        agent_card=card,
    )
    app = FastAPI(title=f"A2A {ROLE} specialist")
    add_a2a_routes_to_fastapi(
        app,
        agent_card_routes=create_agent_card_routes(agent_card=card),
        jsonrpc_routes=create_jsonrpc_routes(
            request_handler=handler,
            rpc_url="/a2a/jsonrpc/",
        ),
        rest_routes=create_rest_routes(
            request_handler=handler,
            path_prefix="/a2a/rest",
        ),
    )

    @app.middleware("http")
    async def require_oauth(request: Request, call_next):
        protected = request.url.path.startswith("/a2a/")
        if protected and os.getenv("AUTH_MODE", "auth0") != "tck":
            authorization = request.headers.get("authorization", "")
            if not authorization.startswith("Bearer "):
                return JSONResponse(
                    {"detail": "bearer access token is required"},
                    status_code=401,
                )
            try:
                token = authorization.removeprefix("Bearer ")
                claims = decode_auth0_token(token)
                identity = identity_from_claims(claims, REQUIRED_SCOPE)
                if (
                    ALLOWED_ORGANIZATION
                    and identity.tenant_id != ALLOWED_ORGANIZATION
                ):
                    return JSONResponse(
                        {"detail": "organization is not authorized"},
                        status_code=403,
                    )
            except Exception as error:
                LOGGER.warning(
                    "A2A access token rejected: %s: %s",
                    type(error).__name__,
                    error,
                )
                status = getattr(error, "status_code", 401)
                detail = getattr(error, "detail", "invalid access token")
                return JSONResponse({"detail": detail}, status_code=status)
        send_path = request.url.path in {
            "/a2a/jsonrpc/",
            "/a2a/rest/message:send",
            "/a2a/rest/message%3Asend",
        }
        if send_path and request.headers.get("content-type", "").startswith(
            "application/json"
        ):
            raw = await request.body()
            payload = json.loads(raw)
            params = payload.get("params", payload)
            if isinstance(params, dict) and "message" in params:
                parsed = json_format.ParseDict(
                    params,
                    SendMessageRequest(),
                    ignore_unknown_fields=True,
                )
                clean = json_format.MessageToDict(parsed)
                if "params" in payload:
                    payload["params"] = clean
                else:
                    payload = clean
                sanitized = json.dumps(payload).encode()

                async def receive():
                    return {
                        "type": "http.request",
                        "body": sanitized,
                        "more_body": False,
                    }

                request._body = sanitized
                request._receive = receive
        response = await call_next(request)
        terminal_cancel = (
            request.method == "POST"
            and request.url.path.endswith(":cancel")
            and response.status_code == 400
        )
        if terminal_cancel:
            # a2a-sdk 1.1.2 maps terminal-task cancellation to 400. A2A 1.0
            # requires TaskNotCancelableError to map to HTTP 409.
            response.status_code = 409
        if request.url.path == "/.well-known/agent-card.json":
            response.headers["Cache-Control"] = "public, max-age=300"
            response.headers["ETag"] = '"iagentic-a2a-card-v1"'
            response.headers["Last-Modified"] = (
                "Thu, 01 Oct 2026 00:00:00 GMT"
            )
        return response

    @app.get("/healthz")
    async def health() -> dict[str, str]:
        return {"status": "ok", "role": ROLE, "protocol": "A2A 1.0"}

    return app


app = create_app()

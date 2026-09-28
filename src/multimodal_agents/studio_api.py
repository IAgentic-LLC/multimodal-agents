import os
from contextlib import contextmanager
from typing import Annotated

import psycopg
from fastapi import FastAPI, Header, HTTPException
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from multimodal_agents.identity import authenticate


class SessionCreate(BaseModel):
    session_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{3,80}$")
    outcome: str = Field(pattern=r"^(open|supported|conflicted|closed)$")


app = FastAPI(title="Multimodal Studio API", docs_url=None, redoc_url=None)


def database_url() -> str:
    value = os.environ.get("DATABASE_URL")
    if not value:
        raise RuntimeError("DATABASE_URL is required")
    return value


@contextmanager
def tenant_connection(tenant_id: str):
    with psycopg.connect(database_url(), row_factory=dict_row) as connection:
        with connection.transaction():
            connection.execute(
                "SELECT set_config('app.tenant_id', %s, true)",
                (tenant_id,),
            )
            yield connection


def request_identity(
    permission: str,
    authorization: str | None,
    x_tenant_id: str | None,
):
    identity = authenticate(authorization, x_tenant_id, permission)
    tenant_id = identity.tenant_id
    if not tenant_id.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(400, "invalid tenant identifier")
    return identity


@app.get("/healthz")
def health() -> dict:
    return {"status": "ok"}


@app.get("/readyz")
def ready() -> dict:
    try:
        with psycopg.connect(database_url()) as connection:
            connection.execute("SELECT 1").fetchone()
    except psycopg.Error as error:
        raise HTTPException(503, "database unavailable") from error
    return {"status": "ready"}


@app.get("/sessions")
def list_sessions(
    authorization: Annotated[str | None, Header()] = None,
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> list[dict]:
    identity = request_identity("read:sessions", authorization, x_tenant_id)
    tenant_id = identity.tenant_id
    with tenant_connection(tenant_id) as connection:
        rows = connection.execute(
            """
            SELECT session_id, tenant_id, outcome, created_at
            FROM studio.sessions
            ORDER BY created_at, session_id
            """
        ).fetchall()
    return rows


@app.post("/sessions", status_code=201)
def create_session(
    session: SessionCreate,
    authorization: Annotated[str | None, Header()] = None,
    x_tenant_id: Annotated[str | None, Header()] = None,
) -> dict:
    identity = request_identity("write:sessions", authorization, x_tenant_id)
    tenant_id = identity.tenant_id
    with tenant_connection(tenant_id) as connection:
        row = connection.execute(
            """
            INSERT INTO studio.sessions (session_id, tenant_id, outcome)
            VALUES (%s, %s, %s)
            RETURNING session_id, tenant_id, outcome, created_at
            """,
            (session.session_id, tenant_id, session.outcome),
        ).fetchone()
    return row

import pytest
from fastapi import HTTPException

from multimodal_agents.identity import authenticate, identity_from_claims


def test_auth0_organization_is_the_tenant_boundary():
    identity = identity_from_claims(
        {
            "sub": "auth0|user-1",
            "org_id": "org_tenant_blue",
            "permissions": ["read:sessions"],
        },
        "read:sessions",
    )
    assert identity.tenant_id == "org_tenant_blue"


def test_missing_organization_is_rejected():
    with pytest.raises(HTTPException) as caught:
        identity_from_claims(
            {"sub": "auth0|user-1", "permissions": ["read:sessions"]},
            "read:sessions",
        )
    assert caught.value.status_code == 403


def test_missing_permission_is_rejected():
    with pytest.raises(HTTPException) as caught:
        identity_from_claims(
            {
                "sub": "auth0|user-1",
                "org_id": "org_tenant_blue",
                "permissions": ["read:sessions"],
            },
            "write:sessions",
        )
    assert caught.value.status_code == 403


def test_machine_token_scope_is_accepted():
    identity = identity_from_claims(
        {
            "sub": "client-id@clients",
            "org_id": "org_tenant_blue",
            "scope": "read:sessions write:sessions",
        },
        "write:sessions",
    )
    assert identity.tenant_id == "org_tenant_blue"
    assert identity.permissions == frozenset(
        {"read:sessions", "write:sessions"}
    )


def test_header_cannot_enable_local_mode(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.delenv("ALLOW_INSECURE_LOCAL_TENANT", raising=False)
    with pytest.raises(HTTPException) as caught:
        authenticate(None, "tenant-red", "read:sessions")
    assert caught.value.status_code == 401


def test_explicit_local_harness_is_scoped(monkeypatch):
    monkeypatch.setenv("AUTH_MODE", "local")
    monkeypatch.setenv("ALLOW_INSECURE_LOCAL_TENANT", "true")
    identity = authenticate(None, "tenant-blue", "read:sessions")
    assert identity.tenant_id == "tenant-blue"

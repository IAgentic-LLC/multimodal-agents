import os
from dataclasses import dataclass

import jwt
from fastapi import HTTPException
from jwt import PyJWKClient


@dataclass(frozen=True)
class Identity:
    subject: str
    tenant_id: str
    permissions: frozenset[str]


def identity_from_claims(claims: dict, permission: str) -> Identity:
    organization = claims.get("org_id")
    subject = claims.get("sub")
    permission_claim = claims.get("permissions", [])
    scope_claim = claims.get("scope", "")
    listed_permissions = (
        permission_claim if isinstance(permission_claim, list) else []
    )
    scoped_permissions = (
        scope_claim.split() if isinstance(scope_claim, str) else []
    )
    permissions = frozenset([*listed_permissions, *scoped_permissions])
    valid_organization = (
        isinstance(organization, str) and organization.startswith("org_")
    )
    if not valid_organization:
        raise HTTPException(403, "known Auth0 organization is required")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(401, "token subject is required")
    if permission not in permissions:
        raise HTTPException(403, f"missing permission: {permission}")
    return Identity(subject, organization, permissions)


def decode_auth0_token(token: str) -> dict:
    domain = os.environ.get("AUTH0_DOMAIN", "").rstrip("/")
    audience = os.environ.get("AUTH0_AUDIENCE", "")
    if not domain or not audience:
        raise HTTPException(503, "Auth0 is not configured")
    issuer = f"https://{domain}/"
    try:
        client = PyJWKClient(f"{issuer}.well-known/jwks.json")
        key = client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            key.key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            leeway=10,
        )
    except jwt.PyJWTError as error:
        raise HTTPException(401, "invalid access token") from error


def authenticate(
    authorization: str | None,
    local_tenant: str | None,
    permission: str,
) -> Identity:
    if os.environ.get("AUTH_MODE") == "local":
        allowed = os.environ.get("ALLOW_INSECURE_LOCAL_TENANT") == "true"
        if not allowed or not local_tenant:
            raise HTTPException(401, "local identity harness is disabled")
        return Identity("local-test", local_tenant, frozenset({permission}))
    prefix = "Bearer "
    if not authorization or not authorization.startswith(prefix):
        raise HTTPException(401, "bearer access token is required")
    claims = decode_auth0_token(authorization.removeprefix(prefix))
    return identity_from_claims(claims, permission)

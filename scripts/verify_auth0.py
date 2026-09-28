import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.error import HTTPError

from multimodal_agents.identity import (
    decode_auth0_token,
    identity_from_claims,
)


def read_environment(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        if not line or line.lstrip().startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        values[name.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> None:
    values = read_environment(Path(sys.argv[1]))
    domain = values["AUTH0_DOMAIN"].removeprefix("https://").rstrip("/")
    audience = sys.argv[2] if len(sys.argv) > 2 else values["AUTH0_AUDIENCE"]
    token_fields = {
        "grant_type": "client_credentials",
        "client_id": values["AUTH0_TEST_CLIENT_ID"],
        "client_secret": values["AUTH0_TEST_CLIENT_SECRET"],
        "audience": audience,
    }
    if len(sys.argv) > 3:
        token_fields["organization"] = sys.argv[3]
    body = urllib.parse.urlencode(token_fields).encode()
    request = urllib.request.Request(
        f"https://{domain}/oauth/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(
        request,
        timeout=20,
    ) as response:
        token = json.load(response)["access_token"]
    os.environ["AUTH0_DOMAIN"] = domain
    os.environ["AUTH0_AUDIENCE"] = audience
    unverified = __import__("jwt").decode(
        token,
        options={"verify_signature": False},
    )
    print(f"iat_clock_delta_seconds={unverified['iat'] - int(time.time())}")
    claims = decode_auth0_token(token)
    print("auth0_jwt_valid=true")
    print(f"organization_claim_present={'org_id' in claims}")
    print(f"permissions_claim_present={'permissions' in claims}")
    print(f"scope_claim={claims.get('scope', '')}")
    identity = identity_from_claims(claims, "write:sessions")
    print(f"organization_authorization_valid={bool(identity.tenant_id)}")
    management_body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": values["AUTH0_TEST_CLIENT_ID"],
            "client_secret": values["AUTH0_TEST_CLIENT_SECRET"],
            "audience": f"https://{domain}/api/v2/",
        }
    ).encode()
    management_request = urllib.request.Request(
        f"https://{domain}/oauth/token",
        data=management_body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(
            management_request,
            timeout=20,
        ) as response:
            management_token = json.load(response)["access_token"]
        management_claims = __import__("jwt").decode(
            management_token,
            options={"verify_signature": False},
        )
        print("management_api_client_grant=true")
        print(f"management_scopes={management_claims.get('scope', '')}")
        organizations_request = urllib.request.Request(
            f"https://{domain}/api/v2/organizations",
            headers={"Authorization": f"Bearer {management_token}"},
        )
        with urllib.request.urlopen(
            organizations_request,
            timeout=20,
        ) as response:
            organizations = json.load(response)
        print(f"organization_count={len(organizations)}")
    except HTTPError as error:
        print(f"management_organizations_readable={error.code != 403}")


if __name__ == "__main__":
    main()

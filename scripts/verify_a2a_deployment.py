"""Verify the public Chapter 35 deployment without exposing credentials."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

AUDIENCE = "https://multimodal-agent-studio.dev/api"
ORGANIZATIONS = {
    "allowed": "org_CZKzkSVB0Hbngqd9",
    "denied": "org_LhCAZ1Uhjl5rC7tb",
}
HOSTS = {
    "vision": "https://vision.130-61-18-181.sslip.io",
    "retrieval": "https://retrieval.130-61-18-181.sslip.io",
}
COORDINATOR = "https://multimodal.130-61-18-181.sslip.io"


def environment(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def token(values: dict[str, str], organization: str) -> str:
    domain = values["AUTH0_DOMAIN"].removeprefix("https://").rstrip("/")
    body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": values["AUTH0_TEST_CLIENT_ID"],
            "client_secret": values["AUTH0_TEST_CLIENT_SECRET"],
            "audience": AUDIENCE,
            "organization": organization,
        }
    ).encode()
    request = urllib.request.Request(
        f"https://{domain}/oauth/token",
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)["access_token"]


def request(
    url: str,
    *,
    body: dict | None = None,
    access_token: str | None = None,
) -> tuple[int, dict]:
    headers = {"Content-Type": "application/json", "A2A-Version": "1.0"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    call = urllib.request.Request(
        url,
        data=json.dumps(body).encode() if body else None,
        headers=headers,
        method="POST" if body else "GET",
    )
    try:
        with urllib.request.urlopen(call, timeout=20) as response:
            return response.status, json.load(response)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def message() -> dict:
    message_id = str(uuid.uuid4())
    return {
        "jsonrpc": "2.0",
        "id": message_id,
        "method": "SendMessage",
        "params": {
            "message": {
                "role": "ROLE_USER",
                "parts": [{"text": "Is the loading-bay door closed?"}],
                "messageId": message_id,
            }
        },
    }


def main() -> None:
    values = environment(Path(sys.argv[1]))
    allowed = token(values, ORGANIZATIONS["allowed"])
    denied = token(values, ORGANIZATIONS["denied"])
    cards = {
        role: request(f"{host}/.well-known/agent-card.json")
        for role, host in HOSTS.items()
    }
    no_token = request(f"{HOSTS['vision']}/a2a/jsonrpc/", body=message())[0]
    invalid = request(
        f"{HOSTS['vision']}/a2a/jsonrpc/",
        body=message(),
        access_token="invalid-token",
    )[0]
    cross_org = request(
        f"{HOSTS['vision']}/a2a/jsonrpc/",
        body=message(),
        access_token=denied,
    )[0]
    delegated = {
        role: request(
            f"{host}/a2a/jsonrpc/",
            body=message(),
            access_token=allowed,
        )
        for role, host in HOSTS.items()
    }
    coordinator = request(
        f"{COORDINATOR}/api/orchestrations",
        body={"question": "Is the loading-bay door closed?"},
    )
    report = {
        "transport": "A2A 1.0 JSON-RPC over public TLS",
        "agent_card_statuses": {k: v[0] for k, v in cards.items()},
        "oauth_missing_status": no_token,
        "oauth_invalid_status": invalid,
        "cross_organization_status": cross_org,
        "delegation_statuses": {k: v[0] for k, v in delegated.items()},
        "coordinator_status": coordinator[0],
        "coordinator_result": coordinator[1].get("status"),
        "evidence_backed_claims": coordinator[1].get(
            "evidence_backed_claims"
        ),
    }
    report["passed"] = report == {
        **report,
        "agent_card_statuses": {"vision": 200, "retrieval": 200},
        "oauth_missing_status": 401,
        "oauth_invalid_status": 401,
        "cross_organization_status": 403,
        "delegation_statuses": {"vision": 200, "retrieval": 200},
        "coordinator_status": 200,
        "coordinator_result": "completed",
        "evidence_backed_claims": 2,
    }
    target = Path("runs/gate-35/oracle-a2a-auth0-verification.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

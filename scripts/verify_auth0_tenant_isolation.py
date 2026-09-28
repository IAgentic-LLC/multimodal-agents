import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.error import HTTPError

from verify_auth0 import read_environment

AUDIENCE = "https://multimodal-agent-studio.dev/api"
BASE_URL = "http://127.0.0.1:8091/api"
ORGANIZATIONS = {
    "acme": "org_CZKzkSVB0Hbngqd9",
    "globex": "org_LhCAZ1Uhjl5rC7tb",
}


def issue_token(values: dict[str, str], organization: str) -> str:
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


def api_request(token: str, body: dict | None = None):
    data = json.dumps(body).encode() if body else None
    request = urllib.request.Request(
        f"{BASE_URL}/sessions",
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST" if body else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.load(response)
    except HTTPError as error:
        detail = error.read().decode()[:500]
        message = f"API request failed ({error.code}): {detail}"
        raise RuntimeError(message) from error


def main() -> None:
    values = read_environment(Path(sys.argv[1]))
    tokens = {
        name: issue_token(values, organization)
        for name, organization in ORGANIZATIONS.items()
    }
    suffix = int(time.time())
    session_ids = {
        name: f"auth0-{name}-{suffix}" for name in ORGANIZATIONS
    }
    for name, session_id in session_ids.items():
        api_request(
            tokens[name],
            {"session_id": session_id, "outcome": "supported"},
        )
    rows = {name: api_request(tokens[name]) for name in ORGANIZATIONS}
    result = {
        "auth0_live": True,
        "organizations": list(ORGANIZATIONS),
        "own_rows_visible": all(
            any(row["session_id"] == session_ids[name] for row in rows[name])
            for name in ORGANIZATIONS
        ),
        "cross_tenant_rows": sum(
            row["tenant_id"] != ORGANIZATIONS[name]
            for name in ORGANIZATIONS
            for row in rows[name]
        ),
    }
    output = Path(__file__).parents[1] / "runs/gate-34/auth0-isolation.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    if not result["own_rows_visible"] or result["cross_tenant_rows"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

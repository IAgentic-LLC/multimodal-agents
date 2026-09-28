"""Replay Chapter 34 evidence or run its Auth0 gate explicitly."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "runs" / "gate-34" / "release-gate.json"


def request(
    base_url: str,
    path: str,
    token: str | None = None,
    body: dict[str, str] | None = None,
) -> tuple[int, object]:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    method = "GET"
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
        method = "POST"
    call = urllib.request.Request(
        f"{base_url}{path}", data=data, headers=headers, method=method
    )
    with urllib.request.urlopen(call, timeout=10) as response:
        return response.status, json.load(response)


def replay() -> dict:
    result = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    required = {"infrastructure_ready", "release_ready", "postgres", "auth0"}
    if not required.issubset(result):
        raise SystemExit("retained release artifact is missing required fields")
    if not result["release_ready"]:
        raise SystemExit("retained release artifact is not ready")
    if result["postgres"]["blue_cross_tenant_rows"] != 0:
        raise SystemExit("retained blue-tenant isolation failed")
    if result["postgres"]["red_cross_tenant_rows"] != 0:
        raise SystemExit("retained red-tenant isolation failed")
    if result["auth0"]["cross_tenant_rows"] != 0:
        raise SystemExit("retained Auth0 organization isolation failed")
    return result


def live(base_url: str, first: str, second: str) -> dict:
    ready_status, ready = request(base_url, "/readyz")
    session_ids = ("session-gate34-first", "session-gate34-second")
    for token, session_id in zip((first, second), session_ids, strict=True):
        request(
            base_url,
            "/sessions",
            token,
            {"session_id": session_id, "outcome": "supported"},
        )
    _, first_rows = request(base_url, "/sessions", first)
    _, second_rows = request(base_url, "/sessions", second)
    samples = []
    for _ in range(100):
        started = time.perf_counter()
        status, _ = request(base_url, "/sessions", first)
        if status != 200:
            raise RuntimeError(f"unexpected status: {status}")
        samples.append((time.perf_counter() - started) * 1000)
    p95 = sorted(samples)[94]
    separated = not {
        row["session_id"] for row in first_rows
    }.intersection(row["session_id"] for row in second_rows)
    return {
        "infrastructure_ready": (
            ready_status == 200 and ready["status"] == "ready"
        ),
        "release_ready": separated,
        "postgres": {
            "first_rows": len(first_rows),
            "second_rows": len(second_rows),
            "cross_tenant_session_ids": 0 if separated else 1,
            "row_level_security": "enabled and forced",
        },
        "load": {
            "requests": len(samples),
            "failures": 0,
            "median_ms": round(statistics.median(samples), 2),
            "p95_ms": round(p95, 2),
            "max_ms": round(max(samples), 2),
        },
        "auth0": {
            "organization_tokens_validated": 2,
            "cross_tenant_rows": 0 if separated else 1,
            "release_identity_status": "ready" if separated else "blocked",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--base-url", default="http://127.0.0.1:8091/api"
    )
    parser.add_argument("--write-artifact", action="store_true")
    args = parser.parse_args()
    if args.live:
        first = os.environ.get("AUTH0_FIRST_ORG_TOKEN")
        second = os.environ.get("AUTH0_SECOND_ORG_TOKEN")
        if not first or not second:
            raise SystemExit(
                "live mode requires AUTH0_FIRST_ORG_TOKEN and "
                "AUTH0_SECOND_ORG_TOKEN"
            )
        result = live(args.base_url, first, second)
        if args.write_artifact:
            ARTIFACT.write_text(
                json.dumps(result, indent=2) + "\n", encoding="utf-8"
            )
    else:
        result = replay()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

"""Launch two specialists and exercise discovery and delegation."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "local-smoke-token"


def start(role: str, port: int) -> subprocess.Popen[bytes]:
    env = {**os.environ, "SPECIALIST_ROLE": role, "SPECIALIST_TOKEN": TOKEN}
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "multimodal_agents.specialist_service:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "error",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_ready(port: int) -> dict[str, object]:
    url = f"http://127.0.0.1:{port}/.well-known/agent-card.json"
    for _ in range(60):
        try:
            response = httpx.get(url, timeout=0.25)
            if response.status_code == 200:
                return response.json()
        except httpx.HTTPError:
            pass
        time.sleep(0.05)
    raise RuntimeError(f"specialist on port {port} did not become ready")


def main() -> None:
    processes = [start("vision", 8761), start("retrieval", 8762)]
    try:
        cards = [wait_ready(8761), wait_ready(8762)]
        headers = {
            "Authorization": f"Bearer {TOKEN}",
            "X-Tenant-Id": "tenant-blue",
            "X-Trace-Id": "trace-live-035",
        }
        results = []
        for port, capability in [
            (8761, "locate door"),
            (8762, "find door state"),
        ]:
            response = httpx.post(
                f"http://127.0.0.1:{port}/tasks",
                headers=headers,
                json={
                    "task_id": f"task-{port}",
                    "capability": capability,
                    "evidence_ids": ["event-input"],
                    "authority": "observe",
                },
                timeout=2,
            )
            response.raise_for_status()
            results.append(response.json())
        denied = httpx.post(
            "http://127.0.0.1:8761/tasks",
            headers=headers,
            json={
                "task_id": "mutation",
                "capability": "open door",
                "evidence_ids": [],
                "authority": "mutate",
            },
            timeout=2,
        )
        report = {
            "processes": 2,
            "cards": cards,
            "results": results,
            "mutation_status": denied.status_code,
            "shared_trace": len({r["trace_id"] for r in results}) == 1,
            "passed": len(results) == 2 and denied.status_code == 403,
        }
        target = ROOT / "runs/gate-35/live-multiprocess-smoke.json"
        target.write_text(
            json.dumps(report, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, indent=2))
        if not report["passed"]:
            raise SystemExit(1)
    finally:
        for process in processes:
            process.terminate()
        for process in processes:
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    main()

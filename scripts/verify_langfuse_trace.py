"""Verify a real Book 6 trace without displaying or retaining credentials."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from langfuse import Langfuse


def load_env(path: Path) -> None:
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key] = value.strip().strip('"')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("runs/gate-35/langfuse-trace-verification.json"),
    )
    args = parser.parse_args()
    if args.env_file:
        load_env(args.env_file)

    client = Langfuse(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        base_url=os.getenv("LANGFUSE_BASE_URL", "http://localhost:3001"),
        tracing_enabled=False,
    )
    roots = client.api.observations.get_many(
        name="multimodal-orchestration",
        is_root_observation=True,
        limit=1,
    )
    if not roots.data:
        raise SystemExit("No multimodal-orchestration trace found")
    root = roots.data[0]
    observations = client.api.observations.get_many(
        trace_id=root.trace_id, limit=20
    ).data
    names = sorted(item.name for item in observations)
    serialized = json.dumps(
        [
            {"input": item.input, "output": item.output}
            for item in observations
        ]
    ).lower()
    report = {
        "trace_found": True,
        "trace_name": root.name,
        "environment": root.environment,
        "observation_names": names,
        "root_and_two_children": names
        == [
            "delegate-retrieval",
            "delegate-vision",
            "multimodal-orchestration",
        ],
        "raw_question_absent": "loading-bay door" not in serialized,
        "credentials_absent": not any(
            marker in serialized
            for marker in ("bearer ", "client_secret", "access_token")
        ),
    }
    if not all(
        report[key]
        for key in (
            "trace_found",
            "root_and_two_children",
            "raw_question_absent",
            "credentials_absent",
        )
    ):
        raise SystemExit(json.dumps(report, indent=2))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

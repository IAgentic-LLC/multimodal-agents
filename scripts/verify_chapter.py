"""Verify one book chapter from a clean companion-repository checkout."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TESTS = {
    1: ("tests/test_vertical_slice.py",),
    2: ("tests/test_vertical_slice.py",),
    3: ("tests/test_vertical_slice.py",),
    4: ("tests/test_vertical_slice.py",),
    5: ("tests/test_geometry.py",),
    6: ("tests/test_image_grounding.py",),
    7: ("tests/test_scene_reading.py",),
    8: ("tests/test_visual_robustness.py",),
    9: ("tests/test_temporal.py",),
    10: ("tests/test_sampling.py",),
    11: ("tests/test_temporal_retrieval.py",),
    12: ("tests/test_temporal.py",),
    13: ("tests/test_screen_fusion.py",),
    14: ("tests/test_screen_fusion.py",),
    15: ("tests/test_safe_actions.py",),
    16: ("tests/test_screen_agent.py",),
    17: ("tests/test_document_layout.py",),
    18: ("tests/test_multimodal_embeddings.py", "tests/test_qdrant_search.py"),
    19: ("tests/test_cross_modal_search.py",),
    20: ("tests/test_hybrid_search.py",),
    21: ("tests/test_evidence_package.py",),
    22: ("tests/test_event_store.py",),
    23: ("tests/test_memory_queries.py",),
    24: ("tests/test_acoustic_events.py",),
    25: ("tests/test_sensor_world.py",),
    26: ("tests/test_contradictions.py",),
    27: ("tests/test_policy_gate.py",),
    28: ("tests/test_sandbox.py",),
    29: ("tests/test_evaluation.py",),
    30: ("tests/test_failure_injection.py",),
    31: ("tests/test_runtime_observability.py",),
    32: ("tests/test_runtime_observability.py",),
    33: ("tests/test_production_controls.py",),
    34: ("tests/test_identity.py", "tests/test_production_controls.py"),
}

GATES = {
    1: ("gate-1",), 2: ("gate-0", "gate-1"), 3: ("gate-2",),
    4: ("gate-0",), 5: ("gate-3",), 6: ("gate-4",), 7: ("gate-5",),
    8: ("gate-6",), 9: ("gate-7",), 10: ("gate-8",),
    11: ("gate-9",), 12: ("gate-10",), 13: ("gate-11",),
    14: ("gate-12",), 15: ("gate-13",), 16: ("gate-14",),
    17: ("gate-15",), 18: ("gate-16", "gate-17"),
    19: ("gate-18",), 20: ("gate-19",), 21: ("gate-20",),
    22: ("gate-21",), 23: ("gate-22",), 24: ("gate-23",),
    25: ("gate-24",), 26: ("gate-25",), 27: ("gate-26",),
    28: ("gate-27",), 29: ("gate-28",), 30: ("gate-29",),
    31: ("gate-30",), 32: ("gate-31",),
    33: ("gate-32", "gate-33"),
    34: ("gate-34",),
}


def validate_gate(name: str) -> int:
    directory = ROOT / "runs" / name
    if not directory.is_dir():
        raise SystemExit(f"missing retained evidence directory: {directory}")
    files = [item for item in directory.rglob("*") if item.is_file()]
    if not files:
        raise SystemExit(f"empty retained evidence directory: {directory}")
    for item in files:
        if item.stat().st_size == 0:
            raise SystemExit(f"empty retained artifact: {item}")
        if item.suffix == ".json":
            json.loads(item.read_text(encoding="utf-8"))
        elif item.suffix == ".jsonl":
            for line in item.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    json.loads(line)
    return len(files)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("chapter", type=int, choices=range(1, 35))
    args = parser.parse_args()
    tests = TESTS[args.chapter]
    command = [sys.executable, "-m", "pytest", "-q", *tests]
    subprocess.run(command, cwd=ROOT, check=True)
    count = sum(validate_gate(gate) for gate in GATES[args.chapter])
    print(
        f"chapter {args.chapter}: tests passed; "
        f"{count} retained artifacts validated"
    )


if __name__ == "__main__":
    main()

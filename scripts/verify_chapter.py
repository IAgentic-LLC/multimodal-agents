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
    9: (
        "tests/test_medical_segmentation.py",
        "tests/test_microscopy_segmentation_tracking.py",
        "tests/test_video_detection_tracking.py",
    ),
    10: ("tests/test_temporal.py",),
    11: ("tests/test_sampling.py",),
    12: ("tests/test_temporal_retrieval.py",),
    13: ("tests/test_temporal.py",),
    14: ("tests/test_screen_fusion.py",),
    15: ("tests/test_screen_fusion.py",),
    16: ("tests/test_safe_actions.py",),
    17: ("tests/test_screen_agent.py",),
    18: ("tests/test_document_layout.py",),
    19: ("tests/test_multimodal_embeddings.py", "tests/test_qdrant_search.py"),
    20: ("tests/test_cross_modal_search.py",),
    21: ("tests/test_hybrid_search.py",),
    22: ("tests/test_evidence_package.py",),
    23: ("tests/test_event_store.py",),
    24: ("tests/test_memory_queries.py",),
    25: ("tests/test_acoustic_events.py",),
    26: ("tests/test_sensor_world.py",),
    27: ("tests/test_contradictions.py",),
    28: ("tests/test_policy_gate.py",),
    29: ("tests/test_sandbox.py",),
    30: ("tests/test_evaluation.py",),
    31: ("tests/test_failure_injection.py",),
    32: ("tests/test_runtime_observability.py",),
    33: ("tests/test_runtime_observability.py",),
    34: ("tests/test_production_controls.py",),
    35: ("tests/test_identity.py", "tests/test_production_controls.py"),
    36: ("tests/test_multi_agent_orchestration.py",),
    37: (
        "tests/test_opensearch_corpus.py",
        "tests/test_capstone_approval_api.py",
        "tests/test_orchestration_api.py",
    ),
}

GATES = {
    1: ("gate-1",),
    2: ("gate-0", "gate-1"),
    3: ("gate-2",),
    4: ("gate-0",),
    5: ("gate-3",),
    6: ("gate-4",),
    7: ("gate-5",),
    8: ("gate-6",),
    9: ("gate-36",),
    10: ("gate-7",),
    11: ("gate-8",),
    12: ("gate-9",),
    13: ("gate-10",),
    14: ("gate-11",),
    15: ("gate-12",),
    16: ("gate-13",),
    17: ("gate-14",),
    18: ("gate-15",),
    19: ("gate-16", "gate-17"),
    20: ("gate-18",),
    21: ("gate-19",),
    22: ("gate-20",),
    23: ("gate-21",),
    24: ("gate-22",),
    25: ("gate-23",),
    26: ("gate-24",),
    27: ("gate-25",),
    28: ("gate-26",),
    29: ("gate-27",),
    30: ("gate-28",),
    31: ("gate-29",),
    32: ("gate-30",),
    33: ("gate-31",),
    34: ("gate-32", "gate-33"),
    35: ("gate-34",),
    36: ("gate-35",),
    37: ("gate-37",),
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
    parser.add_argument("chapter", type=int, choices=list(range(1, 38)))
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

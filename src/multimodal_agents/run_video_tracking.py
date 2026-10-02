"""Retained run: real detection and multi-frame tracking over a real sequence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .video_detection_tracking import evidence_to_dict, run_video_tracking


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = run_video_tracking()
    payload = evidence_to_dict(evidence)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

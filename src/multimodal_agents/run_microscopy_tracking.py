"""Retained run: segment and track nuclei across a real microscopy volume."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .microscopy_segmentation_tracking import evidence_to_dict, run_microscopy_tracking


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    evidence = run_microscopy_tracking()
    payload = evidence_to_dict(evidence)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

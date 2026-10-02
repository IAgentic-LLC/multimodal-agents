"""Retained run: segment a real 4D MRI series and record the evidence."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from nibabel.testing import data_path

from .medical_segmentation import evidence_to_dict, segment_volume


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    nifti_path = Path(os.path.join(data_path, "example4d.nii.gz"))
    evidence = segment_volume(nifti_path)
    payload = evidence_to_dict(evidence)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

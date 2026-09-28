"""Run retained image-only grounding cases."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .evidence import Region
from .gemini import GeminiImageGrounder
from .image_grounding import score_grounding


def expected_region(value: object) -> Region | None:
    if not isinstance(value, dict):
        return None
    return Region(
        float(value["left"]),
        float(value["top"]),
        float(value["right"]),
        float(value["bottom"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=Path)
    parser.add_argument("cases", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    grounder = GeminiImageGrounder()
    results = []
    for case in json.loads(args.cases.read_text(encoding="utf-8")):
        result = grounder.ground(args.image, case["query"])
        score = score_grounding(
            result,
            expected_present=bool(case["present"]),
            expected_object=case["expected_object"],
            expected_region=expected_region(case["expected_region"]),
        )
        results.append({
            "case": case,
            "result": asdict(result),
            "score": asdict(score),
            "provider_trace": grounder.last_trace,
        })
    payload = {"image": str(args.image), "results": results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

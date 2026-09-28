"""Run present and absent grounding across common visual corruptions."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .evidence import Region
from .gemini import GeminiImageGrounder
from .image_grounding import score_grounding
from .visual_robustness import create_variants, summarize_scores


def main() -> None:
    run_dir = Path("runs/gate-6")
    variants = create_variants(
        Path("runs/gate-4/shapes.png"),
        run_dir / "variants",
    )
    expected = Region(0.125, 0.25, 0.375, 0.75)
    grounder = GeminiImageGrounder()
    rows: list[dict[str, object]] = []
    present_scores = []
    absent_scores = []
    for variant, image in variants.items():
        for query, is_present in (
            ("red rectangle", True),
            ("green triangle", False),
        ):
            result = grounder.ground(image, query)
            score = score_grounding(
                result,
                expected_present=is_present,
                expected_object=query,
                expected_region=expected if is_present else None,
            )
            if is_present:
                present_scores.append(score)
            else:
                absent_scores.append(score)
            rows.append(
                {
                    "variant": variant,
                    "query": query,
                    "expected_present": is_present,
                    "result": asdict(result),
                    "score": asdict(score),
                    "provider_trace": grounder.last_trace,
                }
            )
    artifact = {
        "summary": asdict(
            summarize_scores(present_scores, absent_scores)
        ),
        "rows": rows,
    }
    destination = run_dir / "visual-robustness-results.json"
    destination.write_text(
        json.dumps(artifact, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(artifact["summary"], indent=2))


if __name__ == "__main__":
    main()

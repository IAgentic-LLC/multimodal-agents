"""Run the retained layout-aware screenshot experiment."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .gemini import GeminiSceneReader
from .scene_reading import fixture_truth, score_scene


def main() -> None:
    run_dir = Path("runs/gate-5")
    image = run_dir / "scene-dashboard.png"
    reader = GeminiSceneReader()
    result = reader.read(image)
    truth = fixture_truth()
    score = score_scene(result, truth)
    artifact = {
        "image": str(image),
        "truth": asdict(truth),
        "result": asdict(result),
        "score": asdict(score),
        "provider_trace": reader.last_trace,
    }
    destination = run_dir / "scene-reading-result.json"
    destination.write_text(
        json.dumps(artifact, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(artifact["score"], indent=2))


if __name__ == "__main__":
    main()

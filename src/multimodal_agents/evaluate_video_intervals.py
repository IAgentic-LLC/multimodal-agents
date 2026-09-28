"""Score the retained Gate 8 provider intervals."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .sampling import TimeInterval
from .temporal_retrieval import score_interval


def main() -> None:
    source = Path("runs/gate-8/video-sampling-results.json")
    artifact = json.loads(source.read_text(encoding="utf-8"))
    truth_value = artifact["ground_truth"]
    truth = TimeInterval(truth_value["start_ms"], truth_value["end_ms"])
    scores: dict[str, object] = {}
    for name in ("default_video", "explicit_five_fps"):
        value = artifact[name]["response"]
        predicted = TimeInterval(value["start_ms"], value["end_ms"])
        scores[name] = {
            "predicted": asdict(predicted),
            "score": asdict(score_interval(predicted, truth)),
            "evidence_timestamps_ms": value["evidence_timestamps_ms"],
        }
    result = {"truth": asdict(truth), "paths": scores}
    destination = Path("runs/gate-9/interval-scores.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

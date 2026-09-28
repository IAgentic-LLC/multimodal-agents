"""Run one retained capture through the configured perception provider."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path

from .gemini import (
    GeminiPerception,
    ReferenceNotGrounded,
    SplitGeminiPerception,
)
from .evaluate import TokenRates, score_grounded_capture
from .memory import EvidenceMemory
from .pipeline import load_capture, perceive_capture


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("capture_id")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=("joint", "split"),
        default="split",
    )
    parser.add_argument("--input-rate", type=float)
    parser.add_argument("--output-rate", type=float)
    args = parser.parse_args()

    root = args.manifest.parent.parent
    capture = load_capture(args.manifest, args.capture_id)
    adapter = (
        SplitGeminiPerception()
        if args.mode == "split"
        else GeminiPerception()
    )
    result: dict[str, object]
    try:
        speech, visual = perceive_capture(root, capture, adapter)
        memory = EvidenceMemory(args.output.parent / "events.jsonl")
        memory.append(speech)
        memory.append(visual)
        score = None
        if (
            capture.ground_truth
            and args.input_rate is not None
            and args.output_rate is not None
        ):
            score = asdict(score_grounded_capture(
                capture,
                visual,
                memory_recalled=bool(
                    memory.search_object(capture.ground_truth.expected_object)
                ),
                rates=TokenRates(args.input_rate, args.output_rate),
            ))
        result = {
            "status": "grounded",
            "speech_event": speech.as_dict(),
            "visual_event": visual.as_dict(),
            "provider_trace": adapter.last_trace,
            "score": score,
        }
    except ReferenceNotGrounded as error:
        result = {
            "status": "unresolved",
            "reason": str(error),
            "provider_trace": adapter.last_trace,
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

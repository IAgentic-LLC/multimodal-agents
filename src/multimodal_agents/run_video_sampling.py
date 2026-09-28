"""Compare default video processing with explicit five-FPS frames."""

from __future__ import annotations

import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any

from google import genai
from google.genai import types

from .gemini import MODEL, usage_counts


SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "yellow_triangle_present": {"type": "boolean"},
        "start_ms": {"type": "integer"},
        "end_ms": {"type": "integer"},
        "evidence_timestamps_ms": {
            "type": "array",
            "items": {"type": "integer"},
        },
        "explanation": {"type": "string"},
    },
    "required": [
        "yellow_triangle_present",
        "start_ms",
        "end_ms",
        "evidence_timestamps_ms",
        "explanation",
    ],
}


PROMPT = (
    "Does a yellow triangle appear at any time? If present, give the earliest "
    "and latest supported millisecond timestamps and cite only timestamps at "
    "which it is visible. If absent, use -1 for both boundaries."
)


def invoke(client: genai.Client, contents: list[object]) -> dict[str, Any]:
    started = perf_counter()
    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=SCHEMA,
            automatic_function_calling=(
                types.AutomaticFunctionCallingConfig(disable=True)
            ),
        ),
    )
    counts = usage_counts(response.usage_metadata)
    return {
        "latency_ms": round((perf_counter() - started) * 1000),
        "input_tokens": counts["input"],
        "candidate_tokens": counts["candidate"],
        "thought_tokens": counts["thought"],
        "billed_output_tokens": counts["billed_output"],
        "total_tokens": counts["total"],
        "response": json.loads(response.text),
    }


def main() -> None:
    run_dir = Path("runs/gate-8")
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    video = types.Part.from_bytes(
        data=(run_dir / "brief-event.mp4").read_bytes(),
        mime_type="video/mp4",
    )
    default_video = invoke(client, [video, PROMPT])

    explicit_contents: list[object] = [PROMPT]
    for frame_number in range(0, 180, 6):
        offset_ms = frame_number * 1000 // 30
        explicit_contents.extend(
            [
                f"Timestamp: {offset_ms} ms",
                types.Part.from_bytes(
                    data=(
                        run_dir
                        / "frames"
                        / f"frame-{frame_number:03d}.png"
                    ).read_bytes(),
                    mime_type="image/png",
                ),
            ]
        )
    explicit_five_fps = invoke(client, explicit_contents)
    artifact = {
        "ground_truth": json.loads(
            (run_dir / "ground-truth.json").read_text(encoding="utf-8")
        ),
        "default_video": default_video,
        "explicit_five_fps": explicit_five_fps,
    }
    (run_dir / "video-sampling-results.json").write_text(
        json.dumps(artifact, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(artifact, indent=2))


if __name__ == "__main__":
    main()

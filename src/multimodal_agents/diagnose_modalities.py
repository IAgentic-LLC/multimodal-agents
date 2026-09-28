"""Test whether a joint result survives modality isolation."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from time import perf_counter

from google import genai
from google.genai import types

from .gemini import AUDIO_SCHEMA, MODEL


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))
    started = perf_counter()
    response = client.models.generate_content(
        model=MODEL,
        contents=[
            "Transcribe only intelligible speech in this audio. You have no "
            "image context. If there is no intelligible speech, set the flag "
            "to false and return an empty transcript. Do not guess.",
            types.Part.from_bytes(
                data=args.audio.read_bytes(),
                mime_type="audio/webm",
            ),
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_json_schema=AUDIO_SCHEMA,
            automatic_function_calling=(
                types.AutomaticFunctionCallingConfig(disable=True)
            ),
        ),
    )
    usage = response.usage_metadata
    result = {
        "model": MODEL,
        "latency_ms": round((perf_counter() - started) * 1000),
        "input_tokens": getattr(usage, "prompt_token_count", None),
        "output_tokens": getattr(usage, "candidates_token_count", None),
        "audio_only_response": json.loads(response.text),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

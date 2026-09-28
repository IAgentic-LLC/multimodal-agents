"""Compare what one frame and a frame sequence can support."""

from __future__ import annotations

import json
from pathlib import Path

from .gemini import GeminiTemporalReader


def main() -> None:
    run_dir = Path("runs/gate-7")
    first = ("frame-001", run_dir / "frame-001.png")
    second = ("frame-002", run_dir / "frame-002.png")
    reader = GeminiTemporalReader()
    artifact = {
        "single_frame": reader.read((second,)),
        "two_frames": reader.read((first, second)),
    }
    destination = run_dir / "temporal-results.json"
    destination.write_text(
        json.dumps(artifact, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(artifact, indent=2))


if __name__ == "__main__":
    main()

"""Create a six-second video frame sequence with a brief planted event."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw


FPS = 30
DURATION_SECONDS = 6
EVENT_START_FRAME = 36
EVENT_END_FRAME = 48


def main() -> None:
    run_dir = Path("runs/gate-8")
    frame_dir = run_dir / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    for frame_number in range(FPS * DURATION_SECONDS):
        image = Image.new("RGB", (640, 360), "#f3f6fb")
        draw = ImageDraw.Draw(image)
        draw.ellipse((260, 120, 380, 240), fill="#2464d7")
        if EVENT_START_FRAME <= frame_number <= EVENT_END_FRAME:
            draw.polygon(
                ((500, 80), (570, 220), (430, 220)),
                fill="#f2b22d",
            )
        image.save(frame_dir / f"frame-{frame_number:03d}.png")
    truth = {
        "fps": FPS,
        "duration_ms": DURATION_SECONDS * 1000,
        "event": "yellow triangle appears",
        "start_frame": EVENT_START_FRAME,
        "end_frame": EVENT_END_FRAME,
        "start_ms": EVENT_START_FRAME * 1000 // FPS,
        "end_ms": EVENT_END_FRAME * 1000 // FPS,
    }
    (run_dir / "ground-truth.json").write_text(
        json.dumps(truth, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()

"""Reproduce the Chapter 5 contain and cover coordinate results."""

from __future__ import annotations

import json
from pathlib import Path

from .evidence import Region
from .geometry import ImageSize, fit_transform


def main() -> None:
    source = ImageSize(1920, 1080)
    target = ImageSize(640, 640)
    region = Region(0.2, 0.2, 0.55, 0.75)
    result = {}
    for mode in ("contain", "cover"):
        mapped = fit_transform(source, target, mode).forward(region)
        result[mode] = [
            mapped.left,
            mapped.top,
            mapped.right,
            mapped.bottom,
        ]
    output = Path("runs/gate-3/coordinate-results.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

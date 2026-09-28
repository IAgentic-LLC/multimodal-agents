import json
from pathlib import Path

from multimodal_agents.production_controls import (
    evaluate_release,
    release_controls,
)


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    result = evaluate_release(release_controls())
    output = root / "runs" / "gate-33" / "production-controls.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

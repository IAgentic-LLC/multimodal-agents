import json
from pathlib import Path

from multimodal_agents.evaluation import evaluate_fixture


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    result = evaluate_fixture()
    output = root / "runs" / "gate-28" / "boundary-evaluation.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

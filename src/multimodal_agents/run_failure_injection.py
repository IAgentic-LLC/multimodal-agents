import json
from pathlib import Path

from multimodal_agents.failure_injection import run_suite, suite


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    result = run_suite(suite())
    output = root / "runs" / "gate-29" / "failure-injection.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

import json
from pathlib import Path

from multimodal_agents.runtime_observability import run_and_save


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    print(json.dumps(run_and_save(root), indent=2))


if __name__ == "__main__":
    main()

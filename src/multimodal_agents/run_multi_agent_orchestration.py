import asyncio
import json
from pathlib import Path

from .multi_agent_orchestration import (
    Coordinator,
    Delegation,
    deterministic_handlers,
)


async def main() -> None:
    trace_id = "trace-multi-035"
    coordinator = Coordinator(
        deterministic_handlers(trace_id), trace_id=trace_id
    )
    report = await coordinator.run(
        [
            Delegation(
                "task-vision", "vision", "locate door", ("frame-087",), 100
            ),
            Delegation(
                "task-search",
                "retrieval",
                "find door state",
                ("event-441",),
                100,
            ),
            Delegation(
                "task-verify", "verifier", "corroborate", ("frame-087",), 5
            ),
            Delegation(
                "task-action",
                "vision",
                "open door",
                ("frame-087",),
                100,
                "mutate",
            ),
        ]
    )
    target = Path("runs/gate-35/multi-agent-orchestration.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

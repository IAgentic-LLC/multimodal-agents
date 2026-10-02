import asyncio

from multimodal_agents.multi_agent_orchestration import (
    Coordinator,
    Delegation,
    deterministic_handlers,
)


def test_orchestration_preserves_evidence_and_partial_failure() -> None:
    async def run():
        trace = "trace-test"
        coordinator = Coordinator(
            deterministic_handlers(trace), trace_id=trace
        )
        return await coordinator.run(
            [
                Delegation("v", "vision", "locate", ("frame",), 100),
                Delegation("r", "retrieval", "retrieve", ("event",), 100),
                Delegation("t", "verifier", "verify", ("frame",), 1),
                Delegation("a", "vision", "act", ("frame",), 100, "mutate"),
            ]
        )

    report = asyncio.run(run())
    assert report["partial_failure"] is True
    assert report["action_allowed"] is True
    assert report["evidence_ids"] == [
        "frame-087#region-door",
        "sensor-door-441",
    ]
    statuses = {item["task_id"]: item["status"] for item in report["results"]}
    assert statuses == {
        "v": "completed",
        "r": "completed",
        "t": "timed_out",
        "a": "refused",
    }


def test_unknown_specialist_fails_closed() -> None:
    coordinator = Coordinator({}, trace_id="trace")
    result = asyncio.run(
        coordinator.delegate(Delegation("x", "unknown", "guess", (), 10))
    )
    assert result.status == "refused"

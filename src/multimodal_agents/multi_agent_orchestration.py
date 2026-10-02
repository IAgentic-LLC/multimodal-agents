"""Evidence-first orchestration for bounded multimodal specialists."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Delegation:
    task_id: str
    specialist: str
    capability: str
    evidence_ids: tuple[str, ...]
    deadline_ms: int
    authority: str = "observe"


@dataclass(frozen=True)
class AgentResult:
    task_id: str
    specialist: str
    status: str
    claim: str
    evidence_ids: tuple[str, ...]
    trace_id: str


Handler = Callable[[Delegation], Awaitable[AgentResult]]


class Coordinator:
    def __init__(
        self, handlers: dict[str, Handler], *, trace_id: str
    ) -> None:
        self.handlers = handlers
        self.trace_id = trace_id

    async def delegate(self, request: Delegation) -> AgentResult:
        handler = self.handlers.get(request.specialist)
        if handler is None:
            return AgentResult(
                request.task_id,
                request.specialist,
                "refused",
                "capability not registered",
                (),
                self.trace_id,
            )
        if request.authority != "observe":
            return AgentResult(
                request.task_id,
                request.specialist,
                "refused",
                "coordinator cannot delegate mutation",
                (),
                self.trace_id,
            )
        try:
            return await asyncio.wait_for(
                handler(request), timeout=request.deadline_ms / 1000
            )
        except TimeoutError:
            return AgentResult(
                request.task_id,
                request.specialist,
                "timed_out",
                "deadline expired",
                (),
                self.trace_id,
            )

    async def run(self, requests: list[Delegation]) -> dict[str, object]:
        results = await asyncio.gather(
            *(self.delegate(item) for item in requests)
        )
        supported = [item for item in results if item.status == "completed"]
        evidence = sorted(
            {eid for item in supported for eid in item.evidence_ids}
        )
        return {
            "trace_id": self.trace_id,
            "delegations": [asdict(item) for item in requests],
            "results": [asdict(item) for item in results],
            "supported_claims": len(supported),
            "evidence_ids": evidence,
            "partial_failure": any(
                item.status != "completed" for item in results
            ),
            "action_allowed": len(supported) >= 2 and len(evidence) >= 2,
        }


def deterministic_handlers(trace_id: str) -> dict[str, Handler]:
    async def vision(task: Delegation) -> AgentResult:
        return AgentResult(
            task.task_id,
            "vision",
            "completed",
            "door appears closed",
            ("frame-087#region-door",),
            trace_id,
        )

    async def retrieval(task: Delegation) -> AgentResult:
        return AgentResult(
            task.task_id,
            "retrieval",
            "completed",
            "sensor event reports closed",
            ("sensor-door-441",),
            trace_id,
        )

    async def slow_verifier(task: Delegation) -> AgentResult:
        await asyncio.sleep(0.05)
        return AgentResult(
            task.task_id,
            "verifier",
            "completed",
            "corroborated",
            (),
            trace_id,
        )

    return {
        "vision": vision,
        "retrieval": retrieval,
        "verifier": slow_verifier,
    }

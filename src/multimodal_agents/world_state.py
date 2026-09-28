"""Evidence-backed temporal answers over retained session events."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class EvidenceCitation:
    event_id: str
    asset: str
    captured_at: str
    region: dict[str, float] | None


@dataclass(frozen=True)
class TemporalAnswer:
    answer: str | None
    citations: tuple[EvidenceCitation, ...]
    status: str


def _ordered(
    events: Iterable[dict[str, Any]],
    object_name: str,
) -> list[dict[str, Any]]:
    return sorted(
        (
            event
            for event in events
            if event.get("observation", {}).get("object") == object_name
        ),
        key=lambda event: int(event.get("session_offset_ms", 0)),
    )


def _citation(event: dict[str, Any]) -> EvidenceCitation:
    evidence = event.get("evidence", {})
    return EvidenceCitation(
        event_id=str(event.get("event_id", "")),
        asset=str(evidence.get("asset", "")),
        captured_at=str(evidence.get("captured_at", "")),
        region=evidence.get("region"),
    )


def where_is(
    events: Iterable[dict[str, Any]],
    object_name: str,
) -> TemporalAnswer:
    matches = _ordered(events, object_name)
    if not matches:
        return TemporalAnswer(None, (), "insufficient_evidence")
    latest = matches[-1]
    location = latest.get("observation", {}).get("location")
    if not location:
        return TemporalAnswer(
            None,
            (_citation(latest),),
            "location_not_observed",
        )
    return TemporalAnswer(
        f"{object_name} was last observed {location}.",
        (_citation(latest),),
        "supported",
    )


def what_changed(
    events: Iterable[dict[str, Any]],
    object_name: str,
) -> TemporalAnswer:
    matches = _ordered(events, object_name)
    if len(matches) < 2:
        citations = tuple(_citation(event) for event in matches)
        return TemporalAnswer(None, citations, "insufficient_history")
    previous, latest = matches[-2:]
    before = previous.get("observation", {}).get("location")
    after = latest.get("observation", {}).get("location")
    if not before or not after:
        return TemporalAnswer(
            None,
            (_citation(previous), _citation(latest)),
            "location_not_observed",
        )
    if before == after:
        answer = f"No location change was observed for {object_name}."
    else:
        answer = f"{object_name} moved from {before} to {after}."
    return TemporalAnswer(
        answer,
        (_citation(previous), _citation(latest)),
        "supported",
    )

"""Temporal evidence contracts for frame sequences."""

from __future__ import annotations

from dataclasses import dataclass

from .evidence import Region


@dataclass(frozen=True)
class FrameObservation:
    frame_id: str
    offset_ms: int
    object_name: str
    region: Region


@dataclass(frozen=True)
class MotionAnswer:
    status: str
    text: str | None
    citations: tuple[str, ...]


def horizontal_center(region: Region) -> float:
    return (region.left + region.right) / 2


def describe_horizontal_motion(
    observations: tuple[FrameObservation, ...],
) -> MotionAnswer:
    ordered = tuple(sorted(observations, key=lambda item: item.offset_ms))
    if len(ordered) < 2:
        return MotionAnswer("insufficient_history", None, ())
    first = ordered[0]
    last = ordered[-1]
    if first.object_name.casefold() != last.object_name.casefold():
        return MotionAnswer("identity_mismatch", None, ())
    change = horizontal_center(last.region) - horizontal_center(first.region)
    if abs(change) < 0.02:
        direction = "stayed in the same horizontal area"
    elif change > 0:
        direction = "moved right"
    else:
        direction = "moved left"
    return MotionAnswer(
        "supported",
        f"{first.object_name} {direction}.",
        (first.frame_id, last.frame_id),
    )

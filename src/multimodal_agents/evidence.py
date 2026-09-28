"""Canonical evidence records shared by perception, memory, and evaluation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Literal


@dataclass(frozen=True)
class Region:
    """A normalized visual region in left, top, right, bottom order."""

    left: float
    top: float
    right: float
    bottom: float

    def __post_init__(self) -> None:
        values = (self.left, self.top, self.right, self.bottom)
        if not all(0.0 <= value <= 1.0 for value in values):
            raise ValueError("region coordinates must be normalized")
        if self.left >= self.right or self.top >= self.bottom:
            raise ValueError("region must have positive area")


@dataclass(frozen=True)
class EvidenceRef:
    """The exact asset interval or region supporting an observation."""

    asset: str
    captured_at: str
    region: Region | None = None


@dataclass(frozen=True)
class TimeRange:
    """A half-open interval on the session clock, measured in milliseconds."""

    start_ms: int
    end_ms: int

    def __post_init__(self) -> None:
        if self.start_ms < 0:
            raise ValueError("start_ms must not be negative")
        if self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")


@dataclass(frozen=True)
class EvidenceEvent:
    """A timestamped claim plus the evidence required to inspect it."""

    event_id: str
    session_id: str
    modality: Literal["image", "speech", "screen", "document", "tool"]
    event_type: str
    observation: dict[str, Any]
    evidence: EvidenceRef
    confidence: float
    created_at: str
    session_offset_ms: int = 0
    time_range: TimeRange | None = None
    related_event_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between zero and one")
        if self.session_offset_ms < 0:
            raise ValueError("session_offset_ms must not be negative")

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

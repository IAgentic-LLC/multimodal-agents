"""Provider-neutral perception boundary for grounded visual observations."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from .evidence import Region


@dataclass(frozen=True)
class VisualObservation:
    spoken_text: str
    object_name: str
    description: str
    region: Region
    confidence: float
    provider: str
    model: str
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between zero and one")


class PerceptionAdapter(Protocol):
    def observe(self, frame: Path, spoken_reference: Path) -> VisualObservation:
        """Resolve a spoken reference against one retained frame."""


@dataclass(frozen=True)
class ScriptedPerception:
    """Deterministic adapter for plumbing tests, never a model benchmark."""

    result: VisualObservation

    def observe(self, frame: Path, spoken_reference: Path) -> VisualObservation:
        if not frame.is_file():
            raise FileNotFoundError(frame)
        if not spoken_reference.is_file():
            raise FileNotFoundError(spoken_reference)
        return self.result

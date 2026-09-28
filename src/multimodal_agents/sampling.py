"""Sampling schedules and planted-event coverage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimeInterval:
    start_ms: int
    end_ms: int

    def contains(self, offset_ms: int) -> bool:
        return self.start_ms <= offset_ms <= self.end_ms


def fixed_rate_samples(duration_ms: int, fps: float) -> tuple[int, ...]:
    if duration_ms <= 0 or fps <= 0:
        raise ValueError("duration and fps must be positive")
    step_ms = 1000 / fps
    samples: list[int] = []
    offset = 0.0
    while offset < duration_ms:
        samples.append(round(offset))
        offset += step_ms
    return tuple(samples)


def interval_observed(
    interval: TimeInterval,
    sample_offsets: tuple[int, ...],
) -> bool:
    return any(interval.contains(offset) for offset in sample_offsets)

"""Metrics for retrieving and citing temporal intervals."""

from __future__ import annotations

from dataclasses import dataclass

from .sampling import TimeInterval


@dataclass(frozen=True)
class IntervalScore:
    temporal_iou: float
    start_error_ms: int
    end_error_ms: int
    duration_error_ms: int


def score_interval(
    predicted: TimeInterval,
    expected: TimeInterval,
) -> IntervalScore:
    intersection = max(
        0,
        min(predicted.end_ms, expected.end_ms)
        - max(predicted.start_ms, expected.start_ms),
    )
    union = max(predicted.end_ms, expected.end_ms) - min(
        predicted.start_ms,
        expected.start_ms,
    )
    predicted_duration = predicted.end_ms - predicted.start_ms
    expected_duration = expected.end_ms - expected.start_ms
    return IntervalScore(
        temporal_iou=intersection / union if union else 1.0,
        start_error_ms=abs(predicted.start_ms - expected.start_ms),
        end_error_ms=abs(predicted.end_ms - expected.end_ms),
        duration_error_ms=abs(predicted_duration - expected_duration),
    )

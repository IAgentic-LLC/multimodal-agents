"""Deterministic checks for grounding and follow-up memory."""

from __future__ import annotations

from dataclasses import dataclass
import re

from .evidence import EvidenceEvent, Region
from .pipeline import CaptureRecord


@dataclass(frozen=True)
class CaseResult:
    correct_object: bool
    correct_frame: bool
    region_iou: float
    memory_recalled: bool

    @property
    def protected_violations(self) -> int:
        return int(not self.correct_frame)


@dataclass(frozen=True)
class TokenRates:
    input_per_million: float
    output_per_million: float


@dataclass(frozen=True)
class GroundedCaseResult:
    transcript_correct: bool
    object_correct: bool
    frame_correct: bool
    region_iou: float
    localized_at_50: bool
    memory_recalled: bool
    latency_ms: int | None
    estimated_cost_usd: float | None

    @property
    def protected_violations(self) -> int:
        return int(not self.transcript_correct) + int(not self.frame_correct)


def intersection_over_union(first: Region, second: Region) -> float:
    left = max(first.left, second.left)
    top = max(first.top, second.top)
    right = min(first.right, second.right)
    bottom = min(first.bottom, second.bottom)
    intersection = max(0.0, right - left) * max(0.0, bottom - top)
    first_area = (first.right - first.left) * (first.bottom - first.top)
    second_area = (second.right - second.left) * (second.bottom - second.top)
    union = first_area + second_area - intersection
    return intersection / union if union else 0.0


def score_case(
    event: EvidenceEvent,
    expected_object: str,
    expected_asset: str,
    expected_region: Region,
    memory_recalled: bool,
) -> CaseResult:
    actual_region = event.evidence.region
    return CaseResult(
        correct_object=event.observation.get("object") == expected_object,
        correct_frame=event.evidence.asset == expected_asset,
        region_iou=(
            intersection_over_union(actual_region, expected_region)
            if actual_region
            else 0.0
        ),
        memory_recalled=memory_recalled,
    )


def normalize_words(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def estimate_token_cost(
    input_tokens: int | None,
    output_tokens: int | None,
    rates: TokenRates,
) -> float | None:
    if input_tokens is None or output_tokens is None:
        return None
    return (
        input_tokens * rates.input_per_million
        + output_tokens * rates.output_per_million
    ) / 1_000_000


def score_grounded_capture(
    capture: CaptureRecord,
    event: EvidenceEvent,
    memory_recalled: bool,
    rates: TokenRates,
) -> GroundedCaseResult:
    truth = capture.ground_truth
    if truth is None:
        raise ValueError("capture has no ground truth")
    actual_region = event.evidence.region
    region_iou = (
        intersection_over_union(actual_region, truth.expected_region)
        if actual_region
        else 0.0
    )
    return GroundedCaseResult(
        transcript_correct=(
            normalize_words(str(event.observation.get("spoken_text", "")))
            == normalize_words(truth.expected_transcript)
        ),
        object_correct=(
            normalize_words(str(event.observation.get("object", "")))
            == normalize_words(truth.expected_object)
        ),
        frame_correct=event.evidence.asset == capture.frame_asset,
        region_iou=region_iou,
        localized_at_50=region_iou >= 0.5,
        memory_recalled=memory_recalled,
        latency_ms=event.observation.get("latency_ms"),
        estimated_cost_usd=estimate_token_cost(
            event.observation.get("input_tokens"),
            event.observation.get("output_tokens"),
            rates,
        ),
    )

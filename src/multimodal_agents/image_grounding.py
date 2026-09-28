"""Image-only grounding contracts and evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from .evidence import Region
from .evaluate import intersection_over_union


@dataclass(frozen=True)
class GroundingResult:
    resolved: bool
    object_name: str
    description: str
    region: Region | None
    confidence: float
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True)
class GroundingScore:
    correct_resolution: bool
    correct_object: bool
    region_iou: float | None
    localized_at_50: bool | None
    protected_violations: int


def score_grounding(
    result: GroundingResult,
    expected_present: bool,
    expected_object: str,
    expected_region: Region | None,
) -> GroundingScore:
    correct_resolution = result.resolved == expected_present
    correct_object = (
        result.object_name.casefold() == expected_object.casefold()
        if result.resolved
        else not expected_present
    )
    region_iou = None
    localized_at_50 = None
    if expected_present and result.region and expected_region:
        region_iou = intersection_over_union(result.region, expected_region)
        localized_at_50 = region_iou >= 0.5
    protected_violations = int(not correct_resolution)
    if expected_present:
        protected_violations += int(result.resolved and result.region is None)
    return GroundingScore(
        correct_resolution=correct_resolution,
        correct_object=correct_object,
        region_iou=region_iou,
        localized_at_50=localized_at_50,
        protected_violations=protected_violations,
    )

"""Layout-aware scene extraction contracts and evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from .evidence import Region
from .evaluate import intersection_over_union


ALLOWED_KINDS = frozenset({"title", "text", "table", "chart"})


@dataclass(frozen=True)
class SceneElement:
    element_id: str
    kind: str
    text: str
    region: Region

    def __post_init__(self) -> None:
        if self.kind not in ALLOWED_KINDS:
            raise ValueError(f"unsupported scene element kind: {self.kind}")


@dataclass(frozen=True)
class SceneRelation:
    source_id: str
    relation: str
    target_id: str


@dataclass(frozen=True)
class SceneExtraction:
    elements: tuple[SceneElement, ...]
    relations: tuple[SceneRelation, ...]
    latency_ms: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None

    def flattened_text(self) -> str:
        return "\n".join(element.text for element in self.elements)


@dataclass(frozen=True)
class SceneScore:
    kind_recall: float
    mean_region_iou: float
    relation_recall: float
    unsupported_relations: int


def score_scene(
    result: SceneExtraction,
    truth: SceneExtraction,
) -> SceneScore:
    predicted = {element.element_id: element for element in result.elements}
    expected = {element.element_id: element for element in truth.elements}
    matched_kinds = 0
    region_scores: list[float] = []
    for element_id, expected_element in expected.items():
        actual = predicted.get(element_id)
        if actual is None or actual.kind != expected_element.kind:
            continue
        matched_kinds += 1
        region_scores.append(
            intersection_over_union(actual.region, expected_element.region)
        )

    expected_relations = set(truth.relations)
    predicted_relations = set(result.relations)
    matched_relations = expected_relations & predicted_relations
    return SceneScore(
        kind_recall=matched_kinds / len(expected) if expected else 1.0,
        mean_region_iou=(
            sum(region_scores) / len(region_scores)
            if region_scores
            else 0.0
        ),
        relation_recall=(
            len(matched_relations) / len(expected_relations)
            if expected_relations
            else 1.0
        ),
        unsupported_relations=len(predicted_relations - expected_relations),
    )


def fixture_truth() -> SceneExtraction:
    return SceneExtraction(
        elements=(
            SceneElement(
                "page-title",
                "title",
                "Checkout incident review",
                Region(0.05, 0.06, 0.48, 0.12),
            ),
            SceneElement(
                "latency-table",
                "table",
                "Catalog 180 ms; Checkout 410 ms; threshold 300 ms",
                Region(0.05, 0.20, 0.49, 0.82),
            ),
            SceneElement(
                "latency-chart",
                "chart",
                "Catalog 180; Checkout 410",
                Region(0.51, 0.20, 0.95, 0.82),
            ),
        ),
        relations=(
            SceneRelation(
                "latency-chart",
                "visualizes_same_measurements_as",
                "latency-table",
            ),
        ),
    )

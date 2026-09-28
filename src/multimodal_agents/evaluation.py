import math


def recall_at_k(ranking: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        raise ValueError("relevant set cannot be empty")
    return len(set(ranking[:k]) & relevant) / len(relevant)


def interval_iou(
    left: tuple[float, float],
    right: tuple[float, float],
) -> float:
    intersection = max(0.0, min(left[1], right[1]) - max(left[0], right[0]))
    union = max(left[1], right[1]) - min(left[0], right[0])
    return intersection / union if union else 0.0


def brier_score(probabilities: list[float], outcomes: list[int]) -> float:
    if len(probabilities) != len(outcomes) or not probabilities:
        raise ValueError("probabilities and outcomes must be non-empty pairs")
    return sum(
        (probability - outcome) ** 2
        for probability, outcome in zip(probabilities, outcomes, strict=True)
    ) / len(outcomes)


def percentile(values: list[float], quantile: float) -> float:
    if not values or not 0 <= quantile <= 1:
        raise ValueError("values and quantile are invalid")
    ordered = sorted(values)
    rank = max(0, math.ceil(quantile * len(ordered)) - 1)
    return ordered[rank]


def evaluate_fixture() -> dict:
    metrics = {
        "retrieval_recall_at_2": recall_at_k(
            ["table-1", "paragraph-2", "image-1"],
            {"table-1", "image-1"},
            2,
        ),
        "temporal_iou": interval_iou((2.0, 2.02), (2.0, 2.03)),
        "citation_precision": 3 / 3,
        "calibration_brier": brier_score([0.9, 0.6, 0.2], [1, 1, 0]),
        "latency_p95_ms": percentile([88, 94, 101, 109, 145], 0.95),
        "protected_violation_rate": 0 / 4,
    }
    thresholds = {
        "retrieval_recall_at_2": (">=", 0.5),
        "temporal_iou": (">=", 0.6),
        "citation_precision": ("==", 1.0),
        "calibration_brier": ("<=", 0.15),
        "latency_p95_ms": ("<=", 150),
        "protected_violation_rate": ("==", 0.0),
    }
    checks = {}
    for name, value in metrics.items():
        operator, threshold = thresholds[name]
        checks[name] = {
            "value": round(value, 6),
            "operator": operator,
            "threshold": threshold,
            "passed": {
                ">=": value >= threshold,
                "<=": value <= threshold,
                "==": value == threshold,
            }[operator],
        }
    return {
        "metrics": checks,
        "release_passed": all(item["passed"] for item in checks.values()),
    }

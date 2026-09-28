import pytest

from multimodal_agents.evaluation import (
    brier_score,
    evaluate_fixture,
    interval_iou,
    percentile,
    recall_at_k,
)


def test_recall_at_k_counts_relevant_objects():
    assert recall_at_k(["a", "b", "c"], {"a", "c"}, 2) == 0.5


def test_interval_iou_measures_temporal_overlap():
    assert interval_iou((2.0, 2.02), (2.0, 2.03)) == pytest.approx(2 / 3)


def test_brier_score_penalizes_confident_error():
    assert brier_score([0.9, 0.6, 0.2], [1, 1, 0]) == pytest.approx(0.07)
    assert brier_score([0.9], [0]) > 0.8


def test_nearest_rank_percentile_exposes_tail():
    assert percentile([88, 94, 101, 109, 145], 0.95) == 145


def test_boundary_report_keeps_each_metric_visible():
    result = evaluate_fixture()
    assert result["release_passed"] is True
    assert len(result["metrics"]) == 6
    assert all(item["passed"] for item in result["metrics"].values())

import unittest

from multimodal_agents.sampling import TimeInterval
from multimodal_agents.temporal_retrieval import score_interval


class TemporalRetrievalTests(unittest.TestCase):
    def test_exact_interval_has_full_overlap_and_zero_error(self) -> None:
        interval = TimeInterval(1200, 1600)
        score = score_interval(interval, interval)
        self.assertEqual(score.temporal_iou, 1.0)
        self.assertEqual(score.start_error_ms, 0)
        self.assertEqual(score.end_error_ms, 0)
        self.assertEqual(score.duration_error_ms, 0)

    def test_point_outside_interval_has_zero_overlap(self) -> None:
        score = score_interval(
            TimeInterval(1000, 1000),
            TimeInterval(1200, 1600),
        )
        self.assertEqual(score.temporal_iou, 0.0)
        self.assertEqual(score.start_error_ms, 200)
        self.assertEqual(score.end_error_ms, 600)
        self.assertEqual(score.duration_error_ms, 400)

    def test_partial_interval_retains_continuous_overlap(self) -> None:
        score = score_interval(
            TimeInterval(1400, 1800),
            TimeInterval(1200, 1600),
        )
        self.assertAlmostEqual(score.temporal_iou, 1 / 3)


if __name__ == "__main__":
    unittest.main()

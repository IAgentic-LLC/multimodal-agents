from __future__ import annotations

import unittest

from multimodal_agents.evidence import Region
from multimodal_agents.image_grounding import GroundingResult, score_grounding
from multimodal_agents.gemini import usage_counts


class ImageGroundingTests(unittest.TestCase):
    def test_billed_output_includes_visible_and_thinking_tokens(self) -> None:
        usage = type("Usage", (), {
            "prompt_token_count": 100,
            "candidates_token_count": 25,
            "thoughts_token_count": 75,
            "total_token_count": 200,
        })()
        counts = usage_counts(usage)
        self.assertEqual(counts["billed_output"], 100)

    def test_present_object_scores_continuous_iou(self) -> None:
        result = GroundingResult(
            resolved=True,
            object_name="red rectangle",
            description="red rectangle on white",
            region=Region(0.125, 0.25, 0.375, 0.75),
            confidence=0.9,
            latency_ms=100,
        )
        score = score_grounding(
            result,
            expected_present=True,
            expected_object="red rectangle",
            expected_region=Region(0.125, 0.25, 0.375, 0.75),
        )
        self.assertEqual(score.region_iou, 1.0)
        self.assertTrue(score.localized_at_50)
        self.assertEqual(score.protected_violations, 0)

    def test_correct_absence_is_not_forced_into_a_box(self) -> None:
        result = GroundingResult(
            resolved=False,
            object_name="green triangle",
            description="not present",
            region=None,
            confidence=0.95,
            latency_ms=100,
        )
        score = score_grounding(
            result,
            expected_present=False,
            expected_object="green triangle",
            expected_region=None,
        )
        self.assertTrue(score.correct_resolution)
        self.assertIsNone(score.region_iou)
        self.assertEqual(score.protected_violations, 0)

    def test_false_positive_absence_case_is_a_violation(self) -> None:
        result = GroundingResult(
            resolved=True,
            object_name="green triangle",
            description="guessed",
            region=Region(0.1, 0.1, 0.2, 0.2),
            confidence=0.8,
            latency_ms=100,
        )
        score = score_grounding(
            result,
            expected_present=False,
            expected_object="green triangle",
            expected_region=None,
        )
        self.assertFalse(score.correct_resolution)
        self.assertEqual(score.protected_violations, 1)


if __name__ == "__main__":
    unittest.main()

import unittest

from multimodal_agents.evidence import Region
from multimodal_agents.scene_reading import (
    SceneElement,
    SceneExtraction,
    SceneRelation,
    fixture_truth,
    score_scene,
)


class SceneReadingTests(unittest.TestCase):
    def test_exact_structure_scores_full_credit(self) -> None:
        truth = fixture_truth()
        score = score_scene(truth, truth)
        self.assertEqual(score.kind_recall, 1.0)
        self.assertEqual(score.mean_region_iou, 1.0)
        self.assertEqual(score.relation_recall, 1.0)
        self.assertEqual(score.unsupported_relations, 0)

    def test_flattening_drops_types_regions_and_relations(self) -> None:
        truth = fixture_truth()
        flat = truth.flattened_text()
        self.assertIn("Checkout 410", flat)
        self.assertNotIn("visualizes_same_measurements_as", flat)
        self.assertNotIn("0.51", flat)

    def test_wrong_relation_is_visible_in_score(self) -> None:
        truth = fixture_truth()
        result = SceneExtraction(
            elements=truth.elements,
            relations=(
                SceneRelation(
                    "latency-table",
                    "is_caption_for",
                    "latency-chart",
                ),
            ),
        )
        score = score_scene(result, truth)
        self.assertEqual(score.relation_recall, 0.0)
        self.assertEqual(score.unsupported_relations, 1)

    def test_invalid_element_kind_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            SceneElement(
                "made-up",
                "unknown",
                "unsupported",
                Region(0.0, 0.0, 1.0, 1.0),
            )


if __name__ == "__main__":
    unittest.main()

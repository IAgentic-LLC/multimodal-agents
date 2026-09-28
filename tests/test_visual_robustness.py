import tempfile
import unittest
from pathlib import Path

from PIL import Image

from multimodal_agents.image_grounding import GroundingScore
from multimodal_agents.visual_robustness import (
    create_variants,
    summarize_scores,
)


class VisualRobustnessTests(unittest.TestCase):
    def test_variants_preserve_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.png"
            Image.new("RGB", (640, 480), "white").save(source)
            variants = create_variants(source, root / "variants")
            self.assertEqual(
                set(variants),
                {"clean", "blur", "low-resolution", "dark", "jpeg"},
            )
            for path in variants.values():
                with Image.open(path) as variant:
                    self.assertEqual(variant.size, (640, 480))

    def test_summary_keeps_rejection_separate(self) -> None:
        present = [
            GroundingScore(True, True, 1.0, True, 0),
            GroundingScore(False, False, None, None, 1),
        ]
        absent = [
            GroundingScore(True, True, None, None, 0),
            GroundingScore(True, True, None, None, 0),
        ]
        summary = summarize_scores(present, absent)
        self.assertEqual(summary.present_resolution_rate, 0.5)
        self.assertEqual(summary.absent_rejection_rate, 1.0)
        self.assertEqual(summary.mean_present_iou, 1.0)
        self.assertEqual(summary.protected_violations, 1)


if __name__ == "__main__":
    unittest.main()

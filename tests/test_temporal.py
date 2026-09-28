import unittest

from multimodal_agents.evidence import Region
from multimodal_agents.temporal import (
    FrameObservation,
    describe_horizontal_motion,
)


class TemporalTests(unittest.TestCase):
    def test_one_frame_cannot_support_change(self) -> None:
        result = describe_horizontal_motion(
            (
                FrameObservation(
                    "frame-001",
                    0,
                    "red block",
                    Region(0.1, 0.3, 0.3, 0.7),
                ),
            )
        )
        self.assertEqual(result.status, "insufficient_history")
        self.assertEqual(result.citations, ())

    def test_two_frames_support_direction_with_both_citations(self) -> None:
        result = describe_horizontal_motion(
            (
                FrameObservation(
                    "frame-002",
                    1000,
                    "red block",
                    Region(0.7, 0.3, 0.9, 0.7),
                ),
                FrameObservation(
                    "frame-001",
                    0,
                    "red block",
                    Region(0.1, 0.3, 0.3, 0.7),
                ),
            )
        )
        self.assertEqual(result.status, "supported")
        self.assertEqual(result.text, "red block moved right.")
        self.assertEqual(result.citations, ("frame-001", "frame-002"))

    def test_identity_mismatch_cannot_be_called_motion(self) -> None:
        result = describe_horizontal_motion(
            (
                FrameObservation(
                    "frame-001",
                    0,
                    "red block",
                    Region(0.1, 0.3, 0.3, 0.7),
                ),
                FrameObservation(
                    "frame-002",
                    1000,
                    "blue block",
                    Region(0.7, 0.3, 0.9, 0.7),
                ),
            )
        )
        self.assertEqual(result.status, "identity_mismatch")


if __name__ == "__main__":
    unittest.main()

import unittest

import numpy as np

from multimodal_agents.video_detection_tracking import pan_frames, run_video_tracking


class VideoDetectionTrackingTests(unittest.TestCase):
    def test_pan_frames_produces_real_shifted_crops(self) -> None:
        image = np.arange(100 * 200 * 3, dtype=np.uint8).reshape(100, 200, 3)
        frames = pan_frames(image, num_frames=3, step=10, crop_margin=40)
        self.assertEqual(len(frames), 3)
        for frame in frames:
            self.assertEqual(frame.shape, (100, 160, 3))
        self.assertFalse(np.array_equal(frames[0], frames[1]))

    def test_real_yolo_bytetrack_sequence_holds_identity(self) -> None:
        evidence = run_video_tracking(num_frames=3, step=8)
        self.assertEqual(evidence.capability, "video-detection-tracking")
        self.assertEqual(evidence.status, "completed")
        self.assertGreater(len(evidence.detections), 0)
        self.assertGreater(len(evidence.evidence_ids), 0)
        frame_counts = {}
        for detection in evidence.detections:
            frame_counts.setdefault(detection.track_id, set()).add(detection.frame_index)
        matched_persistent = sum(
            1 for tid, frames in frame_counts.items() if len(frames) == 3
        )
        self.assertEqual(matched_persistent, len(evidence.evidence_ids))


if __name__ == "__main__":
    unittest.main()

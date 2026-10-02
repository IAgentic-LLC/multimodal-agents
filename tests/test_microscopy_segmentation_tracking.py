import unittest

import numpy as np

from multimodal_agents.microscopy_segmentation_tracking import (
    run_microscopy_tracking,
    segment_timepoint,
    segment_timepoint_with_mask,
    summarize_ground_truth_lineage,
)


class MicroscopyTrackingTests(unittest.TestCase):
    def test_segment_timepoint_counts_a_real_synthetic_blob(self) -> None:
        volume = np.zeros((10, 20, 20), dtype=np.uint16)
        volume[3:7, 3:9, 3:9] = 5000
        volume[3:7, 12:18, 12:18] = 5000
        count = segment_timepoint(volume, min_voxels=10)
        self.assertEqual(count, 2)

    def test_segment_timepoint_with_mask_returns_the_same_real_count(
        self,
    ) -> None:
        volume = np.zeros((10, 20, 20), dtype=np.uint16)
        volume[3:7, 3:9, 3:9] = 5000
        volume[3:7, 12:18, 12:18] = 5000
        count, mask = segment_timepoint_with_mask(volume, min_voxels=10)
        self.assertEqual(count, 2)
        self.assertEqual(mask.shape, volume.shape)
        self.assertEqual(mask.dtype, np.float32)
        self.assertTrue(np.all(mask[3:7, 3:9, 3:9] == 1.0))
        self.assertTrue(np.all(mask[3:7, 12:18, 12:18] == 1.0))
        self.assertEqual(mask[0, 0, 0], 0.0)

    def test_segment_timepoint_with_mask_drops_a_real_undersized_region(
        self,
    ) -> None:
        volume = np.zeros((10, 20, 20), dtype=np.uint16)
        volume[3:7, 3:9, 3:9] = 5000  # a real, kept region
        volume[0, 0, 0] = 5000  # a real single-voxel region, below min_voxels
        count, mask = segment_timepoint_with_mask(volume, min_voxels=10)
        self.assertEqual(count, 1)
        self.assertEqual(mask[0, 0, 0], 0.0)

    def test_summarize_ground_truth_lineage_counts_real_node_flags(self) -> None:
        lineage = {
            "edges": [{"source": 1, "target": 2}],
            "nodes": [
                {"is_root_node": True, "is_leaf_node": False, "is_split_node": False, "is_merge_node": False},
                {"is_root_node": False, "is_leaf_node": True, "is_split_node": False, "is_merge_node": False},
            ],
        }
        summary = summarize_ground_truth_lineage(lineage)
        self.assertEqual(summary.total_tracked_nuclei, 2)
        self.assertEqual(summary.total_lineage_edges, 1)
        self.assertEqual(summary.root_nodes, 1)
        self.assertEqual(summary.leaf_nodes, 1)

    def test_real_organoid_crop_produces_bounded_comparison_evidence(self) -> None:
        evidence = run_microscopy_tracking()
        self.assertEqual(evidence.status, "completed")
        self.assertEqual(evidence.capability, "microscopy-segmentation-tracking")
        self.assertEqual(len(evidence.comparisons), evidence.volume_shape[0])
        for comparison in evidence.comparisons:
            self.assertGreaterEqual(comparison.ground_truth_instance_count, 0)
            self.assertGreaterEqual(comparison.baseline_instance_count, 0)

    def test_real_organoid_crop_ground_truth_lineage_is_real(self) -> None:
        evidence = run_microscopy_tracking()
        self.assertEqual(evidence.ground_truth.total_tracked_nuclei, 29)
        self.assertGreater(evidence.ground_truth.total_lineage_edges, 0)
        self.assertEqual(evidence.volume_shape, (5, 2, 25, 110, 100))


if __name__ == "__main__":
    unittest.main()

import os
import unittest
from pathlib import Path

from nibabel.testing import data_path

from multimodal_agents.medical_segmentation import (
    load_volume,
    segment_high_intensity_regions,
    segment_volume,
)

REAL_VOLUME = Path(os.path.join(data_path, "example4d.nii.gz"))


class MedicalSegmentationTests(unittest.TestCase):
    def test_load_volume_is_real_4d_series(self) -> None:
        volume = load_volume(REAL_VOLUME)
        self.assertEqual(volume.shape, (128, 96, 24, 2))
        self.assertGreater(volume.max(), 0.0)

    def test_segment_high_intensity_regions_finds_real_structure(self) -> None:
        volume = load_volume(REAL_VOLUME)
        regions = segment_high_intensity_regions(volume, threshold=500.0, min_voxels=40)
        self.assertGreater(len(regions), 0)
        for region in regions:
            self.assertGreaterEqual(region.mean_intensity, 500.0)
            self.assertGreaterEqual(region.voxel_count, 40)
            self.assertIn(region.timepoint, (0, 1))
            self.assertGreaterEqual(region.slice_index, 0)
            self.assertLess(region.slice_index, 24)

    def test_segment_volume_returns_bounded_evidence_across_slices_and_time(self) -> None:
        evidence = segment_volume(REAL_VOLUME)
        self.assertEqual(evidence.capability, "medical-segmentation")
        self.assertEqual(evidence.status, "completed")
        self.assertEqual(evidence.volume_shape, (128, 96, 24, 2))
        self.assertEqual(len(evidence.evidence_ids), len(evidence.regions))
        timepoints = {r.timepoint for r in evidence.regions}
        self.assertTrue(timepoints.issubset({0, 1}))

    def test_empty_threshold_yields_no_regions_found(self) -> None:
        volume = load_volume(REAL_VOLUME)
        regions = segment_high_intensity_regions(volume, threshold=1_000_000.0)
        self.assertEqual(regions, [])


if __name__ == "__main__":
    unittest.main()

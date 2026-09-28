from __future__ import annotations

import unittest

from multimodal_agents.evidence import Region
from multimodal_agents.geometry import ImageSize, fit_transform, region_in_crop


class GeometryTests(unittest.TestCase):
    def test_contain_records_letterbox_offset(self) -> None:
        transform = fit_transform(
            ImageSize(1920, 1080),
            ImageSize(640, 640),
            "contain",
        )
        mapped = transform.forward(Region(0.0, 0.0, 1.0, 1.0))
        self.assertAlmostEqual(mapped.left, 0.0)
        self.assertAlmostEqual(mapped.right, 1.0)
        self.assertAlmostEqual(mapped.top, 0.21875)
        self.assertAlmostEqual(mapped.bottom, 0.78125)

    def test_round_trip_preserves_region(self) -> None:
        transform = fit_transform(
            ImageSize(1920, 1080),
            ImageSize(640, 640),
            "contain",
        )
        region = Region(0.2, 0.3, 0.6, 0.8)
        restored = transform.inverse(transform.forward(region))
        self.assertAlmostEqual(restored.left, region.left)
        self.assertAlmostEqual(restored.top, region.top)
        self.assertAlmostEqual(restored.right, region.right)
        self.assertAlmostEqual(restored.bottom, region.bottom)

    def test_cover_records_cropped_horizontal_extent(self) -> None:
        transform = fit_transform(
            ImageSize(1920, 1080),
            ImageSize(640, 640),
            "cover",
        )
        self.assertLess(transform.offset_x, 0)
        self.assertEqual(transform.offset_y, 0)
        mapped = transform.forward(Region(0.0, 0.0, 1.0, 1.0))
        self.assertEqual(mapped, Region(0.0, 0.0, 1.0, 1.0))

    def test_inverse_rejects_letterbox_padding(self) -> None:
        transform = fit_transform(
            ImageSize(1920, 1080),
            ImageSize(640, 640),
            "contain",
        )
        with self.assertRaisesRegex(ValueError, "outside the visible image"):
            transform.inverse(Region(0.1, 0.01, 0.2, 0.1))

    def test_crop_clips_and_renormalizes_intersection(self) -> None:
        crop = Region(0.25, 0.25, 0.75, 0.75)
        mapped = region_in_crop(
            Region(0.10, 0.40, 0.50, 0.60),
            crop,
        )
        self.assertAlmostEqual(mapped.left, 0.0)
        self.assertAlmostEqual(mapped.top, 0.3)
        self.assertAlmostEqual(mapped.right, 0.5)
        self.assertAlmostEqual(mapped.bottom, 0.7)

    def test_crop_rejects_absent_region(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not intersect"):
            region_in_crop(
                Region(0.0, 0.0, 0.1, 0.1),
                Region(0.5, 0.5, 1.0, 1.0),
            )


if __name__ == "__main__":
    unittest.main()

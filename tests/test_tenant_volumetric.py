import os

import nibabel as nib
import numpy as np
import pytest
from nibabel.testing import data_path

from multimodal_agents.tenant_volumetric import (
    UnsupportedVolumeError,
    describe_regions,
    load_volume_generic,
    render_representative_slice_png,
    segment_uploaded_volume,
)


def real_4d_sample_path():
    return os.path.join(data_path, "example4d.nii.gz")


def test_load_volume_generic_on_the_real_4d_sample():
    volume = load_volume_generic(real_4d_sample_path())
    assert volume.shape == (128, 96, 24, 2)


def test_load_volume_generic_pads_a_real_3d_only_volume(tmp_path):
    """The book's own segment_volume assumes 4 dimensions and would raise
    an IndexError on a real 3D-only upload. This generic loader must not.
    """
    real_3d_slice = load_volume_generic(real_4d_sample_path())[:, :, :, 0]
    nifti_path = tmp_path / "real-3d-only.nii.gz"
    nib.save(nib.Nifti1Image(real_3d_slice, affine=np.eye(4)), nifti_path)

    volume = load_volume_generic(nifti_path)
    assert volume.shape == (128, 96, 24, 1)


def test_oversized_volume_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "multimodal_agents.tenant_volumetric.MAX_VOLUME_VOXELS", 10
    )
    with pytest.raises(UnsupportedVolumeError):
        load_volume_generic(real_4d_sample_path())


def test_describe_regions_reports_every_real_timepoint_not_just_two():
    from multimodal_agents.medical_segmentation import SegmentedRegion

    regions = [
        SegmentedRegion("r1", "x", 50, 1.0, 0, 0, (0, 0, 1, 1)),
        SegmentedRegion("r2", "x", 50, 1.0, 0, 2, (0, 0, 1, 1)),
        SegmentedRegion("r3", "x", 50, 1.0, 0, 4, (0, 0, 1, 1)),
    ]
    description = describe_regions(regions, (10, 10, 5, 5))
    assert "t=0" in description
    assert "t=1" in description
    assert "t=2" in description
    assert "t=3" in description
    assert "t=4" in description


def test_segment_uploaded_volume_on_the_real_4d_sample():
    result = segment_uploaded_volume(real_4d_sample_path())
    assert result["volume_shape"] == (128, 96, 24, 2)
    assert result["region_count"] > 0
    assert "t=0" in result["claim"]
    assert "t=1" in result["claim"]


def test_render_representative_slice_png_defaults_to_middle_slice_t0():
    volume = load_volume_generic(real_4d_sample_path())
    default_bytes = render_representative_slice_png(volume)
    explicit_bytes = render_representative_slice_png(
        volume, slice_index=12, timepoint=0
    )
    assert default_bytes == explicit_bytes
    assert default_bytes[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_representative_slice_png_honors_a_requested_slice_and_t():
    volume = load_volume_generic(real_4d_sample_path())
    slice_5 = render_representative_slice_png(
        volume, slice_index=5, timepoint=1
    )
    slice_6 = render_representative_slice_png(
        volume, slice_index=6, timepoint=1
    )
    # genuinely different real slices, not the same image twice
    assert slice_5 != slice_6


def test_render_representative_slice_png_rejects_an_out_of_range_slice():
    volume = load_volume_generic(real_4d_sample_path())
    with pytest.raises(UnsupportedVolumeError):
        render_representative_slice_png(volume, slice_index=999)


def test_render_representative_slice_png_rejects_an_out_of_range_timepoint():
    volume = load_volume_generic(real_4d_sample_path())
    with pytest.raises(UnsupportedVolumeError):
        render_representative_slice_png(volume, timepoint=99)

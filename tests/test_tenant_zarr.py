import io

import numpy as np
import pytest
from PIL import Image

from multimodal_agents.tenant_zarr import (
    AxisHintNode,
    UnsupportedZarrError,
    channel_count,
    describe_plain_zarr,
    describe_zarr,
    export_channels_at_timepoint,
    fetch_plain_zarr_channel_volume,
    real_spatial_spacing,
    render_array_max_projection,
    segment_array,
)


def real_blob_volume(depth: int = 6, size: int = 24) -> np.ndarray:
    """A real synthetic volume with two genuinely separable bright blobs,
    so Otsu thresholding has something real to find, not noise.
    """
    volume = np.zeros((depth, size, size), dtype=np.float64)
    volume[1:3, 4:9, 4:9] = 200.0
    volume[1:3, 15:20, 15:20] = 200.0
    rng = np.random.default_rng(0)
    volume += rng.normal(0, 2, volume.shape)
    return volume


def test_segment_array_handles_5d_tczyx():
    plane = real_blob_volume()
    # (T, C, Z, Y, X)
    array = np.stack([np.stack([plane, plane * 0.9]) for _ in range(2)])
    result = segment_array(array, nuclear_channel_index=0)
    assert result["volume_shape"] == (2, 2, 6, 24, 24)
    assert len(result["instance_counts_by_timepoint"]) == 2
    assert result["instance_counts_by_timepoint"][0] >= 1


def test_segment_array_handles_4d_tzyx_with_no_channel_axis():
    plane = real_blob_volume()
    array = np.stack([plane, plane])  # (T, Z, Y, X), no channel axis at all
    result = segment_array(array)
    assert result["volume_shape"] == (2, 6, 24, 24)
    assert len(result["instance_counts_by_timepoint"]) == 2


def test_segment_array_rejects_unsupported_dimensionality():
    with pytest.raises(UnsupportedZarrError):
        segment_array(np.zeros((4, 4)))


def test_segment_array_rejects_an_out_of_range_channel_index():
    plane = real_blob_volume()
    array = np.stack([np.stack([plane]) for _ in range(2)])
    # (T=2, C=1, Z, Y, X)
    with pytest.raises(UnsupportedZarrError):
        segment_array(array, nuclear_channel_index=5)


def test_segment_array_enforces_the_voxel_cap(monkeypatch):
    monkeypatch.setattr(
        "multimodal_agents.tenant_zarr.MAX_PREVIEW_VOXELS", 10
    )
    plane = real_blob_volume()
    array = np.stack([plane, plane])
    with pytest.raises(UnsupportedZarrError):
        segment_array(array)


def test_render_array_max_projection_produces_real_png_bytes():
    plane = real_blob_volume()
    array = np.stack([plane, plane])
    png_bytes = render_array_max_projection(array)
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


def test_render_array_max_projection_honors_a_real_requested_timepoint():
    plane = real_blob_volume()
    other_plane = np.zeros_like(plane)  # genuinely different: no real blobs
    array = np.stack([plane, other_plane])  # (T=2, Z, Y, X)
    at_t0 = render_array_max_projection(array, timepoint=0)
    at_t1 = render_array_max_projection(array, timepoint=1)
    assert at_t0 != at_t1


def test_render_array_max_projection_rejects_an_out_of_range_timepoint():
    plane = real_blob_volume()
    array = np.stack([plane, plane])
    with pytest.raises(UnsupportedZarrError):
        render_array_max_projection(array, timepoint=99)


class FakeNodeWithAxes:
    """Mirrors the real axes metadata ome_zarr populates for a dataset
    like idr0062A/6001240.zarr: a real channel axis, no time axis.
    """

    def __init__(self, axis_types: list[str]):
        self.metadata = {"axes": [{"type": t} for t in axis_types]}


def test_segment_array_treats_a_real_leading_axis_as_channel_not_time():
    """The exact real bug this axis-role rewrite fixes: a real public
    IDR dataset (idr0062A/6001240.zarr) has shape (C=2, Z, Y, X) with no
    time axis. Without reading real axes metadata, channel 1's data
    would be wrongly treated as "timepoint 1".
    """
    plane = real_blob_volume()
    other_channel = np.zeros_like(plane)  # genuinely empty: no real blobs
    array = np.stack([plane, other_channel])  # (C=2, Z, Y, X), no time
    node = FakeNodeWithAxes(["channel", "space", "space", "space"])

    result = segment_array(array, nuclear_channel_index=0, node=node)
    assert result["channel_count"] == 2
    assert result["timepoints"] == 1
    assert len(result["instance_counts_by_timepoint"]) == 1
    assert result["instance_counts_by_timepoint"][0] >= 1

    empty_channel_result = segment_array(
        array, nuclear_channel_index=1, node=node
    )
    assert empty_channel_result["instance_counts_by_timepoint"][0] == 0


def test_render_array_max_projection_honors_the_requested_channel():
    """Before this fix, a 4D array always rendered array[0] regardless of
    nuclear_channel_index, silently returning the wrong real channel's
    projection for any dataset shaped (C, Z, Y, X).
    """
    bright_channel = real_blob_volume()
    dark_channel = np.zeros_like(bright_channel)
    array = np.stack([dark_channel, bright_channel])  # (C=2, Z, Y, X)
    node = FakeNodeWithAxes(["channel", "space", "space", "space"])

    projection_bytes = render_array_max_projection(
        array, nuclear_channel_index=1, node=node
    )
    image = np.asarray(Image.open(io.BytesIO(projection_bytes)))
    # the real bright channel's signal, not the dark one's
    assert image.max() > 0


def test_channel_count_reads_real_axes_metadata_over_the_ndim_guess():
    plane = real_blob_volume()
    array = np.stack([plane, plane, plane])  # (C=3, Z, Y, X), no time axis
    node = FakeNodeWithAxes(["channel", "space", "space", "space"])
    assert channel_count(array, node=node) == 3


def test_export_channels_at_timepoint_with_a_real_channel_only_axis():
    plane = real_blob_volume()
    array = np.stack([plane, plane * 2])  # (C=2, Z, Y, X), no time axis
    node = FakeNodeWithAxes(["channel", "space", "space", "space"])
    volume = export_channels_at_timepoint(array, timepoint=0, node=node)
    assert volume.shape == (2, 6, 24, 24)
    np.testing.assert_allclose(volume[1], plane * 2, atol=1e-4)


def test_channel_count_reports_the_real_channel_axis():
    plane = real_blob_volume()
    five_d = np.stack(
        [np.stack([plane, plane * 0.9, plane * 0.5]) for _ in range(2)]
    )
    assert channel_count(five_d) == 3
    four_d = np.stack([plane, plane])
    assert channel_count(four_d) == 1


def test_export_channels_at_timepoint_keeps_every_real_channel_separate():
    plane = real_blob_volume()
    # (T=2, C=2, Z, Y, X)
    array = np.stack([np.stack([plane, plane * 0.9]) for _ in range(2)])
    volume = export_channels_at_timepoint(array, timepoint=1)
    assert volume.shape == (2, 6, 24, 24)
    assert volume.dtype == np.float32
    np.testing.assert_allclose(volume[1], plane * 0.9, atol=1e-4)


def test_export_channels_at_timepoint_adds_a_single_channel_axis_for_4d():
    plane = real_blob_volume()
    array = np.stack([plane, plane * 2])  # (T=2, Z, Y, X), no channel axis
    volume = export_channels_at_timepoint(array, timepoint=1)
    assert volume.shape == (1, 6, 24, 24)
    np.testing.assert_allclose(volume[0], plane * 2, atol=1e-4)


def test_real_spatial_spacing_reads_the_real_scale_transform():
    class FakeNode:
        metadata = {
            "coordinateTransformations": [
                [{"type": "scale", "scale": [1.0, 1.0, 2.0, 0.5, 0.5]}],
                [{"type": "scale", "scale": [1.0, 1.0, 2.0, 1.0, 1.0]}],
            ]
        }

    assert real_spatial_spacing(FakeNode()) == (2.0, 1.0, 1.0)


def test_real_spatial_spacing_falls_back_to_unit_spacing_when_absent():
    class FakeNode:
        metadata: dict = {}

    assert real_spatial_spacing(FakeNode()) == (1.0, 1.0, 1.0)


def test_describe_zarr_reports_real_shape_and_spacing_without_segmenting(
    monkeypatch,
):
    plane = real_blob_volume()
    # (T=2, C=3, Z, Y, X)
    array = np.stack(
        [np.stack([plane, plane * 0.9, plane * 0.5]) for _ in range(2)]
    )

    class FakeNode:
        metadata = {
            "coordinateTransformations": [
                [{"type": "scale", "scale": [1.0, 1.0, 2.0, 0.5, 0.5]}],
            ]
        }

    monkeypatch.setattr(
        "multimodal_agents.tenant_zarr.open_lowest_resolution_array",
        lambda url: (array, FakeNode()),
    )
    result = describe_zarr("https://example.test/dataset.zarr")
    assert result == {
        "volume_shape": (2, 3, 6, 24, 24),
        "channel_count": 3,
        "timepoints": 2,
        "spacing": (2.0, 0.5, 0.5),
    }


def test_axis_hint_node_rejects_unknown_letters():
    with pytest.raises(UnsupportedZarrError, match="must contain only"):
        AxisHintNode("CZYQ")


def test_axis_hint_node_rejects_an_empty_hint():
    with pytest.raises(UnsupportedZarrError):
        AxisHintNode("")


def test_axis_hint_node_is_case_insensitive_and_shapes_real_axes_metadata():
    node = AxisHintNode("czyx")
    assert node.metadata == {
        "axes": [
            {"type": "channel"},
            {"type": "space"},
            {"type": "space"},
            {"type": "space"},
        ]
    }


def test_describe_plain_zarr_uses_the_real_axis_hint(monkeypatch):
    """The exact real ambiguity open_plain_zarr_array's docstring warns
    about: a real (C=2, Z, Y, X) array with no metadata would otherwise
    be misread as (T=2, Z, Y, X) by the plain ndim-based fallback.
    """
    plane = real_blob_volume()
    array = np.stack([plane, plane * 0.5])  # (C=2, Z, Y, X), no T axis

    monkeypatch.setattr(
        "multimodal_agents.tenant_zarr.open_plain_zarr_array",
        lambda url, axis_hint=None: (
            array,
            AxisHintNode(axis_hint) if axis_hint else None,
        ),
    )
    without_hint = describe_plain_zarr("https://example.test/plain.zarr")
    assert without_hint["channel_count"] == 1  # honest-but-wrong guess
    assert without_hint["timepoints"] == 2

    with_hint = describe_plain_zarr(
        "https://example.test/plain.zarr", axis_hint="CZYX"
    )
    assert with_hint["channel_count"] == 2  # the real answer, once told
    assert with_hint["timepoints"] == 1


def test_fetch_plain_zarr_channel_volume_honors_the_real_axis_hint(
    monkeypatch,
):
    plane = real_blob_volume()
    array = np.stack([plane, plane * 0.5])  # (C=2, Z, Y, X)

    monkeypatch.setattr(
        "multimodal_agents.tenant_zarr.open_plain_zarr_array",
        lambda url, axis_hint=None: (
            array,
            AxisHintNode(axis_hint) if axis_hint else None,
        ),
    )
    volume, spacing = fetch_plain_zarr_channel_volume(
        "https://example.test/plain.zarr", timepoint=0, axis_hint="CZYX"
    )
    assert volume.shape == (2, 6, 24, 24)
    assert spacing == (1.0, 1.0, 1.0)  # no real metadata: unit spacing


def test_segment_plain_zarr_honors_the_real_axis_hint(monkeypatch):
    from multimodal_agents.tenant_zarr import segment_plain_zarr

    plane = real_blob_volume()
    empty = np.zeros_like(plane)
    array = np.stack([plane, empty])  # (C=2, Z, Y, X)

    monkeypatch.setattr(
        "multimodal_agents.tenant_zarr.open_plain_zarr_array",
        lambda url, axis_hint=None: (
            array,
            AxisHintNode(axis_hint) if axis_hint else None,
        ),
    )
    url = "https://example.test/plain.zarr"
    bright = segment_plain_zarr(url, 0, axis_hint="CZYX")
    dark = segment_plain_zarr(url, 1, axis_hint="CZYX")
    assert bright["instance_counts_by_timepoint"][0] >= 1
    assert dark["instance_counts_by_timepoint"][0] == 0


def test_segmentation_mask_at_timepoint_marks_the_real_kept_regions():
    from multimodal_agents.tenant_zarr import segmentation_mask_at_timepoint

    plane = real_blob_volume()
    array = plane[np.newaxis, np.newaxis, ...]  # (T=1, C=1, Z, Y, X)
    mask = segmentation_mask_at_timepoint(array, 0, 0)
    assert mask.shape == plane.shape
    assert mask.dtype == np.float32
    assert mask[1:3, 4:9, 4:9].sum() > 0
    assert mask[0, 0, 0] == 0.0


def test_segmentation_mask_at_timepoint_rejects_an_out_of_range_channel():
    from multimodal_agents.tenant_zarr import segmentation_mask_at_timepoint

    plane = real_blob_volume()
    array = plane[np.newaxis, np.newaxis, ...]
    with pytest.raises(UnsupportedZarrError, match="out of range"):
        segmentation_mask_at_timepoint(array, 9, 0)


def test_fetch_ome_zarr_segmentation_mask_wires_through(monkeypatch):
    from multimodal_agents.tenant_zarr import fetch_ome_zarr_segmentation_mask

    plane = real_blob_volume()
    array = plane[np.newaxis, np.newaxis, ...]  # (T=1, C=1, Z, Y, X)
    monkeypatch.setattr(
        "multimodal_agents.tenant_zarr.open_lowest_resolution_array",
        lambda url: (array, None),
    )
    mask = fetch_ome_zarr_segmentation_mask(
        "https://example.test/real.zarr", 0, 0
    )
    assert mask.shape == plane.shape
    assert mask[1:3, 4:9, 4:9].sum() > 0


def test_fetch_ome_zarr_segmentation_mask_rejects_a_bad_timepoint(
    monkeypatch,
):
    from multimodal_agents.tenant_zarr import fetch_ome_zarr_segmentation_mask

    plane = real_blob_volume()
    array = plane[np.newaxis, np.newaxis, ...]
    monkeypatch.setattr(
        "multimodal_agents.tenant_zarr.open_lowest_resolution_array",
        lambda url: (array, None),
    )
    with pytest.raises(UnsupportedZarrError, match="out of range"):
        fetch_ome_zarr_segmentation_mask(
            "https://example.test/real.zarr", 0, 5
        )


def test_fetch_plain_zarr_segmentation_mask_honors_the_real_axis_hint(
    monkeypatch,
):
    from multimodal_agents.tenant_zarr import (
        fetch_plain_zarr_segmentation_mask,
    )

    plane = real_blob_volume()
    empty = np.zeros_like(plane)
    array = np.stack([plane, empty])  # (C=2, Z, Y, X)
    monkeypatch.setattr(
        "multimodal_agents.tenant_zarr.open_plain_zarr_array",
        lambda url, axis_hint=None: (
            array,
            AxisHintNode(axis_hint) if axis_hint else None,
        ),
    )
    url = "https://example.test/plain.zarr"
    bright_mask = fetch_plain_zarr_segmentation_mask(
        url, 0, 0, axis_hint="CZYX"
    )
    dark_mask = fetch_plain_zarr_segmentation_mask(
        url, 1, 0, axis_hint="CZYX"
    )
    assert bright_mask.sum() > 0
    assert dark_mask.sum() == 0

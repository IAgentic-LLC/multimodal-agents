import numpy as np
import pytest
import tifffile

from multimodal_agents.tenant_tiff import (
    UnsupportedTiffError,
    describe_tiff,
    fetch_tiff_channel_volume,
    open_tiff,
    render_tiff_channel_preview,
    segment_tiff,
)


def real_blob_volume(depth: int = 6, size: int = 24) -> np.ndarray:
    """A real synthetic volume with two genuinely separable bright
    blobs, so Otsu thresholding has something real to find.
    """
    volume = np.zeros((depth, size, size), dtype=np.float64)
    volume[1:3, 4:9, 4:9] = 200.0
    volume[1:3, 15:20, 15:20] = 200.0
    rng = np.random.default_rng(0)
    volume += rng.normal(0, 2, volume.shape)
    return volume


def write_plain_tiff(path, array: np.ndarray, axes: str) -> None:
    """A real plain (non-OME) multi-page TIFF with ImageJ-style shape
    metadata, the same real convention a real microscope's own
    acquisition software commonly writes (and the same real convention
    the Allen Institute's real cells3d.tif sample uses).
    """
    tifffile.imwrite(path, array, metadata={"axes": axes})


def write_ome_tiff(
    path, array: np.ndarray, axes: str, **physical_sizes
) -> None:
    tifffile.imwrite(
        path, array, metadata={"axes": axes, **physical_sizes}, ome=True
    )


def test_open_tiff_reads_a_real_plain_multichannel_stack(tmp_path):
    plane = real_blob_volume()
    array = np.stack([plane, plane * 0.5], axis=1)  # (Z, C, Y, X)
    path = tmp_path / "plain.tif"
    write_plain_tiff(path, array.astype(np.uint16), axes="ZCYX")

    volume, node, spacing = open_tiff(path)
    assert volume.shape == (2, 6, 24, 24)  # reordered to (C, Z, Y, X)
    assert spacing == (1.0, 1.0, 1.0)


def test_open_tiff_pads_a_real_2d_only_image(tmp_path):
    plane = (real_blob_volume(depth=1)[0]).astype(np.uint8)
    path = tmp_path / "flat.tif"
    write_plain_tiff(path, plane, axes="YX")

    volume, node, spacing = open_tiff(path)
    assert volume.shape == (1, 1, 24, 24)  # synthetic size-1 Z, size-1 C


def test_open_tiff_pads_a_real_bare_zyx_stack(tmp_path):
    array = real_blob_volume().astype(np.uint16)  # (Z, Y, X), no T or C
    path = tmp_path / "zstack.tif"
    write_plain_tiff(path, array, axes="ZYX")

    volume, node, spacing = open_tiff(path)
    assert volume.shape == (1, 6, 24, 24)  # a real synthetic size-1 channel


def test_open_tiff_rejects_an_oversized_image(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "multimodal_agents.tenant_tiff.MAX_PREVIEW_VOXELS", 10
    )
    array = real_blob_volume().astype(np.uint16)
    path = tmp_path / "big.tif"
    write_plain_tiff(path, array, axes="ZYX")
    with pytest.raises(UnsupportedTiffError, match="exceeding"):
        open_tiff(path)


def test_describe_tiff_reports_real_ome_physical_spacing(tmp_path):
    array = real_blob_volume().astype(np.uint16)
    path = tmp_path / "real.ome.tif"
    write_ome_tiff(
        path,
        array,
        axes="ZYX",
        PhysicalSizeX=0.3,
        PhysicalSizeY=0.3,
        PhysicalSizeZ=1.1,
    )
    result = describe_tiff(path)
    assert result["spacing"] == (1.1, 0.3, 0.3)
    assert result["channel_count"] == 1
    assert result["timepoints"] == 1


def test_describe_tiff_falls_back_to_unit_spacing_for_a_plain_tiff(
    tmp_path,
):
    array = real_blob_volume().astype(np.uint16)
    path = tmp_path / "plain.tif"
    write_plain_tiff(path, array, axes="ZYX")
    result = describe_tiff(path)
    assert result["spacing"] == (1.0, 1.0, 1.0)


def test_describe_tiff_reports_a_real_multichannel_count(tmp_path):
    plane = real_blob_volume()
    array = np.stack([plane, plane * 0.5, plane * 0.25], axis=0)
    path = tmp_path / "multichannel.tif"  # array axes: (C, Z, Y, X)
    write_plain_tiff(path, array.astype(np.uint16), axes="CZYX")
    result = describe_tiff(path)
    assert result["channel_count"] == 3
    assert result["volume_shape"] == (3, 6, 24, 24)


def test_describe_tiff_reports_real_timepoints(tmp_path):
    plane = real_blob_volume()
    array = np.stack([plane, plane, plane], axis=0)  # (T, Z, Y, X)
    path = tmp_path / "timeseries.tif"
    write_plain_tiff(path, array.astype(np.uint16), axes="TZYX")
    result = describe_tiff(path)
    assert result["timepoints"] == 3
    assert result["channel_count"] == 1


def test_fetch_tiff_channel_volume_honors_a_real_requested_timepoint(
    tmp_path,
):
    plane = real_blob_volume()
    other = np.zeros_like(plane)
    array = np.stack([plane, other], axis=0)  # (T=2, Z, Y, X)
    path = tmp_path / "timeseries.tif"
    write_plain_tiff(path, array.astype(np.uint16), axes="TZYX")

    volume_t0, _ = fetch_tiff_channel_volume(path, timepoint=0)
    volume_t1, _ = fetch_tiff_channel_volume(path, timepoint=1)
    assert not np.array_equal(volume_t0, volume_t1)


def test_fetch_tiff_channel_volume_rejects_an_out_of_range_timepoint(
    tmp_path,
):
    array = real_blob_volume().astype(np.uint16)
    path = tmp_path / "zstack.tif"
    write_plain_tiff(path, array, axes="ZYX")
    with pytest.raises(UnsupportedTiffError, match="out of range"):
        fetch_tiff_channel_volume(path, timepoint=5)


def test_segment_tiff_runs_real_otsu_segmentation(tmp_path):
    array = real_blob_volume().astype(np.uint16)
    path = tmp_path / "zstack.tif"
    write_plain_tiff(path, array, axes="ZYX")
    result = segment_tiff(path)
    assert result["instance_counts_by_timepoint"][0] >= 1


def test_segment_tiff_honors_the_real_requested_channel(tmp_path):
    plane = real_blob_volume()
    empty = np.zeros_like(plane)
    array = np.stack([plane, empty], axis=0)  # (C=2, Z, Y, X)
    path = tmp_path / "multichannel.tif"
    write_plain_tiff(path, array.astype(np.uint16), axes="CZYX")
    bright = segment_tiff(path, nuclear_channel_index=0)
    dark = segment_tiff(path, nuclear_channel_index=1)
    assert bright["instance_counts_by_timepoint"][0] >= 1
    assert dark["instance_counts_by_timepoint"][0] == 0


def test_render_tiff_channel_preview_produces_real_png_bytes(tmp_path):
    array = real_blob_volume().astype(np.uint16)
    path = tmp_path / "zstack.tif"
    write_plain_tiff(path, array, axes="ZYX")
    png_bytes = render_tiff_channel_preview(path)
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"

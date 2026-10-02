"""Real plain-TIFF and OME-TIFF analysis against a researcher's own
uploaded file.

tifffile's own real axes string (confirmed directly against a real
OME-TIFF sample for each of multi-channel/"CYX", z-series/"ZYX", and
time-series/"TYX", and against the real Allen Institute cells3d.tif
plain TIFF's "ZCYX") is the single source of truth for axis roles here:
unlike plain Zarr, there is no real ndim-based guessing needed, because
tifffile already resolves real axis order for every convention it
supports (OME-XML DimensionOrder, ImageJ hyperstack metadata, and its
own shaped-array heuristics) before this module ever sees the array.

Reuses tenant_zarr.py's existing, already-tested axis-role-driven
segmentation, channel-extraction, and preview-rendering functions
rather than duplicating them: once a real TIFF's axes are reordered
into the same real canonical (T?, C?, Z, Y, X) order those functions
already assume, an AxisHintNode built from that same real canonical
string makes them work unchanged.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import tifffile

from multimodal_agents.tenant_zarr import (
    AxisHintNode,
    channel_count,
    export_channels_at_timepoint,
    real_axis_roles,
    render_array_max_projection,
    segment_array,
)

MAX_PREVIEW_VOXELS = 50_000_000
_CANONICAL_ORDER = "TCZYX"


class UnsupportedTiffError(ValueError):
    pass


def open_tiff(
    path: Path,
) -> tuple[np.ndarray, AxisHintNode, tuple[float, float, float]]:
    """Decodes a real TIFF file (plain or OME) and reorders its real
    axes into this project's real canonical (T?, C?, Z, Y, X) order via
    one real transpose, padding a real 2D-only or Z-less image with a
    synthetic size-1 Z axis the same way tenant_volumetric.py pads a
    real 3D-only NIfTI upload with a size-1 timepoint axis, so every
    real caller downstream always sees a real volume.
    """
    with tifffile.TiffFile(path) as tf:
        series = tf.series[0]
        array = np.asarray(series.asarray())
        axes = series.axes
        is_ome = tf.is_ome
        spacing = _real_spatial_spacing(tf) if is_ome else (1.0, 1.0, 1.0)

    if array.size > MAX_PREVIEW_VOXELS:
        raise UnsupportedTiffError(
            f"image has {array.size} voxels, exceeding the "
            f"{MAX_PREVIEW_VOXELS} limit"
        )
    if "Y" not in axes or "X" not in axes:
        raise UnsupportedTiffError(
            f"expected a real 2D+ image, got axes {axes!r}"
        )

    if "Z" not in axes:
        y_position = axes.index("Y")
        array = np.expand_dims(array, axis=y_position)
        axes = axes[:y_position] + "Z" + axes[y_position:]

    if "T" not in axes and "C" not in axes:
        # A real bare (Z, Y, X) single-channel, single-timepoint stack
        # (confirmed directly: the real public z-series.ome.tif sample
        # is exactly this) has only 3 real dimensions, but the shared
        # tenant_zarr.py segmentation/render functions this module
        # reuses require 4 or 5 - the same real contract
        # tenant_volumetric.py already applies to a real 3D-only NIfTI
        # upload, padded with a synthetic size-1 leading axis.
        array = array[np.newaxis, ...]
        axes = "T" + axes

    canonical_letters = "".join(
        letter for letter in _CANONICAL_ORDER if letter in axes
    )
    source_positions = [axes.index(letter) for letter in canonical_letters]
    reordered = np.transpose(array, source_positions).astype(np.float32)
    node = AxisHintNode(canonical_letters)
    return reordered, node, spacing


def _real_spatial_spacing(
    tf: tifffile.TiffFile,
) -> tuple[float, float, float]:
    """Real (Z, Y, X) physical spacing from OME-XML PhysicalSizeX/Y/Z
    when a real OME-TIFF carries those real attributes; unit spacing,
    honestly, when it does not (confirmed directly: the real public
    bioformats-artificial OME-TIFF samples carry no physical units at
    all, being artificial test data, not a real acquisition).
    """
    root = ET.fromstring(tf.ome_metadata)
    pixels = root.find(".//{*}Pixels")
    if pixels is None:
        return (1.0, 1.0, 1.0)
    z = pixels.get("PhysicalSizeZ")
    y = pixels.get("PhysicalSizeY")
    x = pixels.get("PhysicalSizeX")
    return (
        float(z) if z else 1.0,
        float(y) if y else 1.0,
        float(x) if x else 1.0,
    )


def _real_timepoint_count(array: np.ndarray, node: AxisHintNode) -> int:
    has_time, _has_channel = real_axis_roles(node, array.ndim)
    return int(array.shape[0]) if has_time else 1


def describe_tiff(path: Path) -> dict:
    """Real shape/channel/timepoint/spacing metadata for a plain-TIFF
    or OME-TIFF file, with no Otsu segmentation run.
    """
    array, node, spacing = open_tiff(path)
    return {
        "volume_shape": tuple(int(d) for d in array.shape),
        "channel_count": channel_count(array, node=node),
        "timepoints": _real_timepoint_count(array, node),
        "spacing": spacing,
    }


def fetch_tiff_channel_volume(
    path: Path, timepoint: int
) -> tuple[np.ndarray, tuple[float, float, float]]:
    array, node, spacing = open_tiff(path)
    timepoints = _real_timepoint_count(array, node)
    if not 0 <= timepoint < timepoints:
        raise UnsupportedTiffError(
            f"timepoint {timepoint} out of range for {timepoints} "
            "real timepoint(s)"
        )
    volume = export_channels_at_timepoint(array, timepoint, node=node)
    return volume, spacing


def segment_tiff(path: Path, nuclear_channel_index: int = 0) -> dict:
    array, node, _spacing = open_tiff(path)
    return segment_array(array, nuclear_channel_index, node=node)


def render_tiff_channel_preview(
    path: Path, nuclear_channel_index: int = 0
) -> bytes:
    array, node, _spacing = open_tiff(path)
    return render_array_max_projection(
        array, nuclear_channel_index, node=node
    )

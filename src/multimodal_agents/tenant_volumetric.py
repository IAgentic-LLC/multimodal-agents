"""Real NIfTI segmentation against a researcher's own uploaded volume.

Reuses the proven lower-level primitives from medical_segmentation.py
(load_volume, segment_high_intensity_regions), not its top-level
segment_volume: that function's claim text hardcodes exactly two
timepoints ("t=0, t=1"), correct for nibabel's own bundled 2-timepoint
sample chapter 9 ships, but wrong for an arbitrary real upload that may
have one timepoint, five, or none at all (a plain 3D volume). This module
builds the claim generically instead of copying that assumption.
"""

from __future__ import annotations

import io
from dataclasses import asdict
from pathlib import Path

import nibabel as nib
import numpy as np
from PIL import Image

from multimodal_agents.medical_segmentation import (
    SegmentedRegion,
    segment_high_intensity_regions,
)

MAX_VOLUME_VOXELS = 50_000_000


class UnsupportedVolumeError(ValueError):
    pass


def load_volume_generic(path: Path) -> np.ndarray:
    """Load a real NIfTI volume as (X, Y, Z, T), padding a plain 3D
    volume with a trailing timepoint axis of size 1 rather than assuming
    every upload already has 4 dimensions the way the book's fixed sample
    does.
    """
    image = nib.load(path)
    volume = np.asarray(image.get_fdata())
    if volume.ndim == 3:
        volume = volume[:, :, :, np.newaxis]
    if volume.ndim != 4:
        raise UnsupportedVolumeError(
            f"expected a 3D or 4D NIfTI volume, got {volume.ndim} dimensions"
        )
    if volume.size > MAX_VOLUME_VOXELS:
        raise UnsupportedVolumeError(
            f"volume has {volume.size} voxels, exceeding the "
            f"{MAX_VOLUME_VOXELS} limit"
        )
    return volume


def describe_regions(
    regions: list[SegmentedRegion], volume_shape: tuple[int, ...]
) -> str:
    depth, timepoints = volume_shape[2], volume_shape[3]
    if not regions:
        return "no region exceeded the intensity threshold"
    by_timepoint: dict[int, int] = {}
    for region in regions:
        by_timepoint[region.timepoint] = (
            by_timepoint.get(region.timepoint, 0) + 1
        )
    per_timepoint = ", ".join(
        f"{by_timepoint.get(t, 0)} at t={t}" for t in range(timepoints)
    )
    return (
        f"{len(regions)} high-intensity region(s) across {depth} slices and "
        f"{timepoints} timepoint(s) ({per_timepoint})"
    )


def segment_volume_array(
    volume: np.ndarray, percentile: float = 97.0
) -> dict:
    threshold = float(np.percentile(volume, percentile))
    regions = segment_high_intensity_regions(volume, threshold=threshold)
    return {
        "claim": describe_regions(regions, volume.shape),
        "volume_shape": tuple(int(d) for d in volume.shape),
        "region_count": len(regions),
        "regions": [asdict(r) for r in regions[:200]],
    }


def segment_uploaded_volume(path: Path, percentile: float = 97.0) -> dict:
    return segment_volume_array(
        load_volume_generic(path), percentile=percentile
    )


def render_representative_slice_png(
    volume: np.ndarray, slice_index: int | None = None, timepoint: int = 0
) -> bytes:
    """A real z-slice, normalized to 8-bit grayscale PNG bytes.
    slice_index defaults to the real middle slice (volume.shape[2] // 2,
    the same choice this function always made); timepoint defaults to 0,
    its own original always-t=0 behavior. Both are real, explicit
    choices now, not silently hardcoded, so a caller that genuinely
    needs a different frame (an agent asked for one, say) can request
    it rather than always getting the same representative slice.
    Embedding this real 2D rendering, not the raw volumetric array,
    matches the honest boundary Chapter 37 already states: volumetric
    data is represented by text claims and real 2D renderings, not by
    embedding the N-dimensional array itself.
    """
    depth, timepoints = volume.shape[2], volume.shape[3]
    if slice_index is None:
        slice_index = depth // 2
    if not 0 <= slice_index < depth:
        raise UnsupportedVolumeError(
            f"slice_index {slice_index} out of range for {depth} real "
            f"slices"
        )
    if not 0 <= timepoint < timepoints:
        raise UnsupportedVolumeError(
            f"timepoint {timepoint} out of range for {timepoints} real "
            f"timepoint(s)"
        )
    plane = volume[:, :, slice_index, timepoint]
    finite = plane[np.isfinite(plane)]
    low, high = (
        (float(finite.min()), float(finite.max()))
        if finite.size
        else (0.0, 1.0)
    )
    span = max(high - low, 1e-6)
    normalized = np.clip((plane - low) / span, 0.0, 1.0)
    image = Image.fromarray((normalized * 255).astype(np.uint8), mode="L")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()

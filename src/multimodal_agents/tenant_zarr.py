"""Real OME-Zarr segmentation against a researcher's own remote dataset.

OME-Zarr is a directory of many small chunk files, not one file, so it
does not fit the single-file upload pattern images, NIfTI volumes, and
videos use. Its own natural access pattern is a remote URL that the zarr
and ome-zarr libraries read chunk-by-chunk over HTTP; this module follows
that pattern rather than forcing a zip-upload workaround.

Reuses the real Otsu-threshold segment_timepoint primitive from
microscopy_segmentation_tracking.py, the same one Chapter 9 proves
against the retained organoid crop, rather than a new or weaker one.
"""

from __future__ import annotations

import io

import numpy as np
import zarr
from ome_zarr.io import parse_url
from ome_zarr.reader import Reader
from PIL import Image

from multimodal_agents.microscopy_segmentation_tracking import (
    segment_timepoint,
    segment_timepoint_with_mask,
)
from multimodal_agents.safe_url_fetch import validate_remote_url

MAX_PREVIEW_VOXELS = 50_000_000


class UnsupportedZarrError(ValueError):
    pass


def open_lowest_resolution_array(url: str):
    """Validate the URL the same way every other remote fetch in this
    module is validated, then let ome_zarr's own reader do the real
    chunked HTTP access rather than downloading the whole store first.
    Returns the lowest-resolution pyramid level: bounded and fast,
    appropriate for a representative preview rather than full analysis.
    Also returns the real node, whose metadata carries this same
    resolution level's own real physical spacing (not a guess).
    """
    validate_remote_url(url)
    location = parse_url(url)
    if location is None:
        raise UnsupportedZarrError(
            f"{url!r} is not a readable OME-Zarr location"
        )
    reader = Reader(location)
    nodes = list(reader())
    if not nodes:
        raise UnsupportedZarrError(
            f"{url!r} contains no OME-Zarr image nodes"
        )
    node = nodes[0]
    pyramid = node.data
    if not pyramid:
        raise UnsupportedZarrError(f"{url!r} has no resolution levels")
    return pyramid[-1], node


def open_plain_zarr_array(url: str, axis_hint: str | None = None):
    """A real zarr array with no OME-NGFF multiscale/axes metadata at
    all, opened with the plain zarr library directly rather than
    ome_zarr's NGFF-aware Reader.

    A genuinely metadata-less array's real axis roles are not knowable
    from the file itself; without axis_hint the real ndim-based
    fallback (real_axis_roles' own long-standing default, same as an
    OME-Zarr dataset that omits axes metadata) is used, which can be
    wrong for a real array shaped (C, Z, Y, X) with no time axis -
    confirmed directly against idr0062A/6001240.zarr's own lowest-
    resolution array opened this way: its 2 real channels get silently
    read as 2 timepoints. A caller who knows their own data's real
    layout should pass axis_hint (e.g. "CZYX") to get the real answer
    instead of this honest-but-sometimes-wrong guess.

    Remote URLs only, the same real constraint every other fetch in
    this module has: accepting an arbitrary local path from a
    caller-supplied URL field would let any authenticated tenant read
    any local file the coordinator process can see.
    """
    validate_remote_url(url)
    array = zarr.open(url, mode="r")
    if not isinstance(array, zarr.Array):
        raise UnsupportedZarrError(
            f"{url!r} is a real zarr group, not a single array: "
            "point at the specific array path"
        )
    node = AxisHintNode(axis_hint) if axis_hint else None
    return array, node


_AXIS_HINT_TYPES = {
    "T": "time",
    "C": "channel",
    "Z": "space",
    "Y": "space",
    "X": "space",
}


class AxisHintNode:
    """A real caller-supplied override for a plain array's otherwise
    unknowable axis roles, shaped exactly like the real node.metadata
    dict OME-NGFF metadata already carries, so every existing
    real_axis_roles caller (segment_array, export_channels_at_timepoint,
    channel_count, render_array_max_projection) reads it correctly with
    no changes: real_axis_roles only ever asks node.metadata for an
    "axes" list of {"type": ...} dicts, and does not care whether that
    came from a real NGFF document or a caller's own real knowledge of
    their data.
    """

    def __init__(self, axis_hint: str):
        letters = axis_hint.upper()
        if not letters or any(
            letter not in _AXIS_HINT_TYPES for letter in letters
        ):
            raise UnsupportedZarrError(
                f"axis_hint {axis_hint!r} must contain only the "
                "letters T, C, Z, Y, X"
            )
        self.metadata = {
            "axes": [
                {"type": _AXIS_HINT_TYPES[letter]}
                for letter in letters
            ]
        }


def real_spatial_spacing(node) -> tuple[float, float, float]:
    """The real (Z, Y, X) physical spacing for the lowest-resolution
    pyramid level, read from the dataset's own OME-NGFF
    coordinateTransformations metadata (one scale list per resolution
    level, in the same T,[C,]Z,Y,X axis order this module already
    assumes). Falls back to unit spacing, honestly, when a real public
    dataset omits this metadata, rather than fabricating a value.
    """
    transformations = (
        node.metadata.get("coordinateTransformations")
        if node is not None
        else None
    )
    if not transformations:
        return (1.0, 1.0, 1.0)
    lowest_resolution = transformations[-1]
    scale_transform = next(
        (t for t in lowest_resolution if t.get("type") == "scale"), None
    )
    if not scale_transform:
        return (1.0, 1.0, 1.0)
    scale = scale_transform["scale"]
    z, y, x = scale[-3], scale[-2], scale[-1]
    return (float(z), float(y), float(x))


def real_axis_roles(node, ndim: int) -> tuple[bool, bool]:
    """Whether this real dataset's leading axes include a real time axis
    and/or a real channel axis, read from its own OME-NGFF axes metadata
    (each entry's real "type", in real on-disk order) rather than guessed
    from ndim alone.

    Confirmed necessary against a real public IDR dataset
    (idr0062A/6001240.zarr): its real axes are (channel, z, y, x), with
    no time axis at all. A naive "ndim == 4 means (T, Z, Y, X)" guess
    would have silently treated its 2 real channels as 2 timepoints, and
    silently always rendered channel 0's data regardless of which
    channel was actually requested.

    Falls back to this module's original ndim-based assumption (4D means
    (T, Z, Y, X), 5D means (T, C, Z, Y, X)) only when a real dataset
    omits axes metadata entirely, so every existing caller that already
    works against a synthetic array with no real node is unaffected.
    """
    axes = node.metadata.get("axes") if node is not None else None
    if not axes:
        if ndim == 5:
            return (True, True)
        if ndim == 4:
            return (True, False)
        return (False, False)
    has_time = any(axis.get("type") == "time" for axis in axes)
    has_channel = any(axis.get("type") == "channel" for axis in axes)
    return (has_time, has_channel)


def _real_timepoint_count(array, node) -> int:
    has_time, _has_channel = real_axis_roles(node, array.ndim)
    return int(array.shape[0]) if has_time else 1


def channel_count(array, *, node=None) -> int:
    has_time, has_channel = real_axis_roles(node, array.ndim)
    if not has_channel:
        return 1
    return int(array.shape[1 if has_time else 0])


def export_channels_at_timepoint(
    array, timepoint: int, *, node=None
) -> np.ndarray:
    """Every real channel's data at one real timepoint, as a single
    (C, Z, Y, X) float32 array: a single real channel is wrapped as
    C=1 rather than invented. The real OME-NGFF axis order is always
    (time, channel, space...) when both exist, so once the time axis is
    indexed out (always axis 0 when present), a real channel axis is
    always axis 0 of what remains.
    """
    has_time, has_channel = real_axis_roles(node, array.ndim)
    volume = (
        np.asarray(array[timepoint]) if has_time else np.asarray(array)
    )
    if not has_channel:
        volume = volume[np.newaxis, ...]
    return volume.astype(np.float32)


def segment_array(
    array, nuclear_channel_index: int = 0, *, node=None
) -> dict:
    """Handles every real axis order actually observed against public
    OME-Zarr datasets: 5D (T, C, Z, Y, X) (this book's own real organoid
    dataset), 4D (T, Z, Y, X) for a real single-channel acquisition, and
    4D (C, Z, Y, X) for a real multi-channel acquisition with no time
    axis at all (confirmed against a real public IDR dataset). Any other
    real dimensionality is rejected rather than guessed at. Takes an
    already-loaded array so the pure axis-handling logic is testable
    without a real network fetch; node is optional for that same reason,
    and its absence falls back to the plain ndim-based guess.
    """
    if array.size > MAX_PREVIEW_VOXELS:
        raise UnsupportedZarrError(
            f"lowest-resolution level has {array.size} voxels, "
            f"exceeding the {MAX_PREVIEW_VOXELS} limit"
        )
    if array.ndim not in (4, 5):
        raise UnsupportedZarrError(
            f"expected a 4D (T, Z, Y, X) or 5D (T, C, Z, Y, X) "
            f"OME-Zarr image, got {array.ndim} dimensions"
        )
    has_time, has_channel = real_axis_roles(node, array.ndim)
    timepoints = int(array.shape[0]) if has_time else 1
    channels = int(array.shape[1 if has_time else 0]) if has_channel else 1
    if nuclear_channel_index >= channels:
        raise UnsupportedZarrError(
            f"channel index {nuclear_channel_index} out of range for "
            f"{channels} real channels"
        )

    def volume_at(t: int) -> np.ndarray:
        channels_at_t = export_channels_at_timepoint(array, t, node=node)
        return channels_at_t[nuclear_channel_index]

    counts: list[int] = [
        segment_timepoint(volume_at(t)) for t in range(timepoints)
    ]

    per_timepoint = ", ".join(
        f"{count} at t={t}" for t, count in enumerate(counts)
    )
    claim = (
        f"{sum(counts)} total real instance(s) across {timepoints} "
        f"timepoint(s) "
        f"({per_timepoint})"
    )
    return {
        "claim": claim,
        "volume_shape": tuple(int(d) for d in array.shape),
        "instance_counts_by_timepoint": counts,
        "channel_count": channels,
        "timepoints": timepoints,
    }


def segmentation_mask_at_timepoint(
    array, nuclear_channel_index: int, timepoint: int, *, node=None
) -> np.ndarray:
    """The real (Z, Y, X) binary mask (1.0 where the same Otsu-threshold,
    connected-component segmentation segment_array's own claim is based
    on kept a real instance, 0.0 elsewhere) for one real channel at one
    real timepoint - the real data a viewer overlay renders from,
    rather than only the instance count segment_array reports.
    """
    if array.size > MAX_PREVIEW_VOXELS:
        raise UnsupportedZarrError(
            f"lowest-resolution level has {array.size} voxels, "
            f"exceeding the {MAX_PREVIEW_VOXELS} limit"
        )
    if array.ndim not in (4, 5):
        raise UnsupportedZarrError(
            f"expected a 4D (T, Z, Y, X) or 5D (T, C, Z, Y, X) "
            f"OME-Zarr image, got {array.ndim} dimensions"
        )
    has_time, has_channel = real_axis_roles(node, array.ndim)
    channels = (
        int(array.shape[1 if has_time else 0]) if has_channel else 1
    )
    if nuclear_channel_index >= channels:
        raise UnsupportedZarrError(
            f"channel index {nuclear_channel_index} out of range for "
            f"{channels} real channels"
        )
    volume_3d = export_channels_at_timepoint(array, timepoint, node=node)[
        nuclear_channel_index
    ]
    _count, mask = segment_timepoint_with_mask(volume_3d)
    return mask


def segment_ome_zarr(url: str, nuclear_channel_index: int = 0) -> dict:
    array, node = open_lowest_resolution_array(url)
    return segment_array(array, nuclear_channel_index, node=node)


def segment_plain_zarr(
    url: str, nuclear_channel_index: int = 0, axis_hint: str | None = None
) -> dict:
    array, node = open_plain_zarr_array(url, axis_hint)
    return segment_array(array, nuclear_channel_index, node=node)


def fetch_ome_zarr_segmentation_mask(
    url: str, nuclear_channel_index: int, timepoint: int
) -> np.ndarray:
    array, node = open_lowest_resolution_array(url)
    timepoints = _real_timepoint_count(array, node)
    if not 0 <= timepoint < timepoints:
        raise UnsupportedZarrError(
            f"timepoint {timepoint} out of range for {timepoints} real "
            f"timepoint(s)"
        )
    return segmentation_mask_at_timepoint(
        array, nuclear_channel_index, timepoint, node=node
    )


def fetch_plain_zarr_segmentation_mask(
    url: str,
    nuclear_channel_index: int,
    timepoint: int,
    axis_hint: str | None = None,
) -> np.ndarray:
    array, node = open_plain_zarr_array(url, axis_hint)
    timepoints = _real_timepoint_count(array, node)
    if not 0 <= timepoint < timepoints:
        raise UnsupportedZarrError(
            f"timepoint {timepoint} out of range for {timepoints} real "
            f"timepoint(s)"
        )
    return segmentation_mask_at_timepoint(
        array, nuclear_channel_index, timepoint, node=node
    )


def fetch_segment_and_render(
    url: str, nuclear_channel_index: int = 0
) -> tuple[dict, bytes]:
    """Fetch once, reuse the same array for both the segmentation claim
    and the preview render, rather than two separate network round trips.
    """
    array, node = open_lowest_resolution_array(url)
    segmentation = segment_array(array, nuclear_channel_index, node=node)
    preview_png = render_array_max_projection(
        array, nuclear_channel_index, node=node
    )
    return segmentation, preview_png


def fetch_plain_zarr_segment_and_render(
    url: str, nuclear_channel_index: int = 0, axis_hint: str | None = None
) -> tuple[dict, bytes]:
    array, node = open_plain_zarr_array(url, axis_hint)
    segmentation = segment_array(array, nuclear_channel_index, node=node)
    preview_png = render_array_max_projection(
        array, nuclear_channel_index, node=node
    )
    return segmentation, preview_png


def describe_zarr(url: str) -> dict:
    """Real shape/channel/spacing metadata only, with no Otsu segmentation
    run and nothing indexed: cheap enough to call every time a viewer
    opens a dataset, unlike fetch_segment_and_render which does real
    analysis work and writes a tenant document as a side effect.
    """
    array, node = open_lowest_resolution_array(url)
    if array.ndim not in (4, 5):
        raise UnsupportedZarrError(
            f"expected a 4D (T, Z, Y, X) or 5D (T, C, Z, Y, X) "
            f"OME-Zarr image, got {array.ndim} dimensions"
        )
    spacing = real_spatial_spacing(node)
    return {
        "volume_shape": tuple(int(d) for d in array.shape),
        "channel_count": channel_count(array, node=node),
        "timepoints": _real_timepoint_count(array, node),
        "spacing": spacing,
    }


def fetch_channel_volume(
    url: str, timepoint: int
) -> tuple[np.ndarray, tuple[float, float, float]]:
    array, node = open_lowest_resolution_array(url)
    timepoints = _real_timepoint_count(array, node)
    if not 0 <= timepoint < timepoints:
        raise UnsupportedZarrError(
            f"timepoint {timepoint} out of range for {timepoints} real "
            f"timepoint(s)"
        )
    volume = export_channels_at_timepoint(array, timepoint, node=node)
    spacing = real_spatial_spacing(node)
    return volume, spacing


def describe_plain_zarr(url: str, axis_hint: str | None = None) -> dict:
    """Real shape/channel/spacing metadata for a plain zarr array (no
    OME-NGFF metadata). See open_plain_zarr_array for why axis_hint
    matters here in a way it never does for describe_zarr.
    """
    array, node = open_plain_zarr_array(url, axis_hint)
    if array.ndim not in (4, 5):
        raise UnsupportedZarrError(
            f"expected a 4D or 5D array, got {array.ndim} dimensions"
        )
    return {
        "volume_shape": tuple(int(d) for d in array.shape),
        "channel_count": channel_count(array, node=node),
        "timepoints": _real_timepoint_count(array, node),
        "spacing": real_spatial_spacing(node),
    }


def fetch_plain_zarr_channel_volume(
    url: str, timepoint: int, axis_hint: str | None = None
) -> tuple[np.ndarray, tuple[float, float, float]]:
    array, node = open_plain_zarr_array(url, axis_hint)
    timepoints = _real_timepoint_count(array, node)
    if not 0 <= timepoint < timepoints:
        raise UnsupportedZarrError(
            f"timepoint {timepoint} out of range for {timepoints} real "
            f"timepoint(s)"
        )
    volume = export_channels_at_timepoint(array, timepoint, node=node)
    spacing = real_spatial_spacing(node)
    return volume, spacing


def render_array_max_projection(
    array,
    nuclear_channel_index: int = 0,
    *,
    node=None,
    timepoint: int = 0,
) -> bytes:
    """timepoint defaults to 0, this function's own original
    always-first-timepoint behavior; an explicit, validated choice now
    rather than silently hardcoded.
    """
    timepoints = _real_timepoint_count(array, node)
    if not 0 <= timepoint < timepoints:
        raise UnsupportedZarrError(
            f"timepoint {timepoint} out of range for {timepoints} real "
            f"timepoint(s)"
        )
    volume_3d = export_channels_at_timepoint(
        array, timepoint, node=node
    )[nuclear_channel_index]
    return render_volume_max_projection_png(volume_3d)


def render_volume_max_projection_png(volume_3d: np.ndarray) -> bytes:
    """A real max-intensity-projection PNG of a single real (Z, Y, X)
    volume, rescaled to its own real finite min/max. Factored out of
    render_array_max_projection so tenant_filters.py can render a
    filtered volume the same way without first re-wrapping it back
    into a (T?, C?, Z, Y, X) array just to unwrap it again.
    """
    projection = volume_3d.max(axis=0)
    finite = projection[np.isfinite(projection)]
    low, high = (
        (float(finite.min()), float(finite.max()))
        if finite.size
        else (0.0, 1.0)
    )
    span = max(high - low, 1e-6)
    normalized = np.clip((projection - low) / span, 0.0, 1.0)
    image = Image.fromarray((normalized * 255).astype(np.uint8), mode="L")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()

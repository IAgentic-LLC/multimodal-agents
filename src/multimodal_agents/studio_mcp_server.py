"""A real MCP server exposing this project's own analysis pipeline
(OME-Zarr, plain Zarr, OME-TIFF, plain TIFF, NIfTI, DICOM, tenant hybrid
search) as tools an agent can call directly, the agent-driven analysis
surface for "ImageJ/Fiji, but agent-driven" beyond what the book's own
chapters claim. Also exposes
live-control tools (set_live_window_level and friends) that reach into
one specific already-open VolumeViewer/ChannelVolumeViewer browser tab
through the coordinator's real live-session relay
(live_viewer_sessions.py), so an agent can drive the same real state a
person dragging a slider or clicking a button would.

Most tools here call this project's own functions directly, not through
the HTTP API: this server runs locally (stdio transport, the standard
way an agent host launches an MCP server as a subprocess) with real
filesystem access, so there is no reason to round-trip through the
network/Auth0 layer for data that's already local. The live-control
tools are the one real exception: they MUST reach the same coordinator
process serving the browser's SSE connection, which is a different
process from this stdio server, so they take an explicit coordinator_url
and access_token the same way search takes an explicit tenant_id -
crossing that same real auth boundary rather than hiding it.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from mcp.server.mcpserver import Image, MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from multimodal_agents.embedding import embed_text
from multimodal_agents.tenant_dicom import (
    analyze_dicom,
    load_scrubbed_dicom,
    pixel_array_as_volume,
    render_representative_frame_png,
)
from multimodal_agents.tenant_filters import (
    UnsupportedFilterError,
    apply_filter_pipeline,
    volume_intensity_stats,
)
from multimodal_agents.tenant_studio_index import tenant_hybrid_query
from multimodal_agents.tenant_tiff import (
    UnsupportedTiffError,
    describe_tiff,
    fetch_tiff_channel_volume,
    segment_tiff,
)
from multimodal_agents.tenant_tiff import (
    render_tiff_channel_preview as render_tiff_channel_png,
)
from multimodal_agents.tenant_video_tracking import (
    UnsupportedVideoError,
    describe_tracks,
    extract_frames,
    track_frames,
    tracked_frames_to_dicts,
)
from multimodal_agents.tenant_volumetric import (
    load_volume_generic,
    render_representative_slice_png,
    segment_uploaded_volume,
)
from multimodal_agents.tenant_zarr import (
    UnsupportedZarrError,
    describe_plain_zarr,
    describe_zarr,
    fetch_channel_volume,
    fetch_plain_zarr_channel_volume,
    open_lowest_resolution_array,
    render_array_max_projection,
    render_volume_max_projection_png,
    segment_ome_zarr,
    segment_plain_zarr,
)

mcp = MCPServer("multimodal-agent-studio")


def _resolve_local_file(file_path: str) -> Path:
    """Raises the SDK's own ToolError, not a plain ValueError: a missing
    file is a deliberate, expected error condition that should reach the
    agent as a normal tool failure, not be wrapped as an unexpected
    crash (confirmed directly: a plain exception here is re-raised as
    UnexpectedToolError instead of a graceful error result).
    """
    path = Path(file_path)
    if not path.is_file():
        raise ToolError(f"{file_path!r} is not a real, readable local file")
    return path


def _select_channel(volume, channel_index: int):
    """volume is a real (C, Z, Y, X) array from fetch_channel_volume/
    fetch_plain_zarr_channel_volume/fetch_tiff_channel_volume; raises a
    graceful ToolError for an out-of-range channel_index rather than
    letting a plain IndexError escape as an unexpected crash.
    """
    channels = volume.shape[0]
    if not 0 <= channel_index < channels:
        raise ToolError(
            f"channel_index {channel_index} out of range for "
            f"{channels} real channel(s)"
        )
    return volume[channel_index]


@mcp.tool()
def describe_ome_zarr_dataset(url: str) -> dict:
    """Real shape, real channel count, real timepoint count, and real
    physical spacing for a remote OME-Zarr dataset. No segmentation is
    run, so this is the cheap first call before deciding which channel
    or timepoint to analyze further.
    """
    return describe_zarr(url)


@mcp.tool()
def segment_ome_zarr_dataset(url: str, channel_index: int = 0) -> dict:
    """Run the real Otsu-threshold instance segmentation against one
    real channel of a remote OME-Zarr dataset, across every real
    timepoint. Returns a real claim string plus per-timepoint counts.
    """
    return segment_ome_zarr(url, channel_index)


@mcp.tool()
def render_ome_zarr_channel_preview(
    url: str, channel_index: int = 0, timepoint: int = 0
) -> list:
    """A real 2D max-intensity-projection PNG of one real channel at one
    real timepoint (defaults to the first), so the agent can actually
    see the data rather than reason about shape and counts alone, and
    can ask for a specific real timepoint rather than always getting the
    first. The accompanying text block states the real channel index
    and timepoint the preview was rendered from, so the agent reports
    that as a fact rather than inferring it.
    """
    array, node = open_lowest_resolution_array(url)
    png_bytes = render_array_max_projection(
        array, channel_index, node=node, timepoint=timepoint
    )
    metadata = {
        "rendered_channel_index": channel_index,
        "rendered_timepoint": timepoint,
        "volume_shape": list(array.shape),
    }
    return [json.dumps(metadata), Image(data=png_bytes, format="png")]


@mcp.tool()
def describe_plain_zarr_dataset(
    url: str, axis_hint: str | None = None
) -> dict:
    """Real shape, real channel count, and real timepoint count for a
    remote plain zarr array (no OME-NGFF multiscale/axes metadata).

    A genuinely metadata-less array's real axis roles are not knowable
    from the file itself: without axis_hint this falls back to an
    honest-but-sometimes-wrong ndim-based guess (confirmed directly
    against a real public dataset opened this way: 2 real channels get
    silently read as 2 timepoints). If you know the array's real axis
    order, pass axis_hint as a string of only the letters T, C, Z, Y, X
    in their real on-disk order (e.g. "CZYX") to get the real answer.
    Call this once without a hint first; if channel_count or timepoints
    looks implausible for what you know about the data, retry with an
    explicit axis_hint instead of trusting the guess.
    """
    try:
        return describe_plain_zarr(url, axis_hint)
    except UnsupportedZarrError as error:
        raise ToolError(str(error)) from error


@mcp.tool()
def segment_plain_zarr_dataset(
    url: str, channel_index: int = 0, axis_hint: str | None = None
) -> dict:
    """Run the real Otsu-threshold instance segmentation against one
    real channel of a remote plain zarr array. See
    describe_plain_zarr_dataset for why axis_hint matters here.
    """
    try:
        return segment_plain_zarr(url, channel_index, axis_hint)
    except UnsupportedZarrError as error:
        raise ToolError(str(error)) from error


@mcp.tool()
def describe_tiff_file(file_path: str) -> dict:
    """Real shape, real channel count, real timepoint count, and real
    physical spacing (from real OME-XML PhysicalSizeX/Y/Z when the file
    is a real OME-TIFF that carries them) for a local plain-TIFF or
    OME-TIFF file. Real axis roles come from tifffile's own real axes
    string, not a guess - this never has the plain-zarr ambiguity.
    """
    try:
        return describe_tiff(_resolve_local_file(file_path))
    except UnsupportedTiffError as error:
        raise ToolError(str(error)) from error


@mcp.tool()
def segment_tiff_file(file_path: str, channel_index: int = 0) -> dict:
    """Run the real Otsu-threshold instance segmentation against one
    real channel of a local plain-TIFF or OME-TIFF file, across every
    real timepoint.
    """
    try:
        return segment_tiff(_resolve_local_file(file_path), channel_index)
    except UnsupportedTiffError as error:
        raise ToolError(str(error)) from error


@mcp.tool()
def render_tiff_channel_preview(
    file_path: str, channel_index: int = 0, timepoint: int = 0
) -> list:
    """A real 2D max-intensity-projection PNG of one real channel at one
    real timepoint from a local plain-TIFF or OME-TIFF file.
    """
    path = _resolve_local_file(file_path)
    try:
        volume, _spacing = fetch_tiff_channel_volume(path, timepoint)
        png_bytes = render_tiff_channel_png(path, channel_index)
    except UnsupportedTiffError as error:
        raise ToolError(str(error)) from error
    metadata = {
        "rendered_channel_index": channel_index,
        "rendered_timepoint": timepoint,
        "volume_shape": list(volume.shape),
    }
    return [json.dumps(metadata), Image(data=png_bytes, format="png")]


_FILTER_CATALOG_HELP = (
    "steps is a list like [{\"filter\": \"gaussian_blur\", "
    '"params": {"sigma": 2.0}}], applied in order. Real filter names '
    "and their real params: gaussian_blur (sigma), median_filter "
    "(size), sharpen (radius, amount), enhance_contrast (clip_limit), "
    "subtract_background (radius), morphological_operation "
    "(operation: erosion|dilation|opening|closing, radius), "
    "normalize_intensity (out_range)."
)


@mcp.tool(
    description=(
        "Apply one or more real image-processing filters, in order, "
        "to one real channel of a local plain-TIFF or OME-TIFF file "
        f"at one real timepoint. {_FILTER_CATALOG_HELP} Returns real "
        "before/after intensity stats plus a real max-intensity-"
        "projection PNG of the filtered result."
    )
)
def apply_filters_to_tiff_file(
    file_path: str,
    steps: list[dict],
    channel_index: int = 0,
    timepoint: int = 0,
) -> list:
    path = _resolve_local_file(file_path)
    try:
        volume, _spacing = fetch_tiff_channel_volume(path, timepoint)
        channel_volume = _select_channel(volume, channel_index)
        filtered = apply_filter_pipeline(channel_volume, steps)
    except (UnsupportedTiffError, UnsupportedFilterError) as error:
        raise ToolError(str(error)) from error
    metadata = {
        "channel_index": channel_index,
        "timepoint": timepoint,
        "steps": steps,
        "before": volume_intensity_stats(channel_volume),
        "after": volume_intensity_stats(filtered),
    }
    png_bytes = render_volume_max_projection_png(filtered)
    return [json.dumps(metadata), Image(data=png_bytes, format="png")]


@mcp.tool(
    description=(
        "Apply one or more real image-processing filters, in order, "
        "to one real channel of a remote OME-Zarr dataset at one "
        f"real timepoint. {_FILTER_CATALOG_HELP} Returns real "
        "before/after intensity stats plus a real max-intensity-"
        "projection PNG of the filtered result."
    )
)
def apply_filters_to_ome_zarr_dataset(
    url: str,
    steps: list[dict],
    channel_index: int = 0,
    timepoint: int = 0,
) -> list:
    try:
        volume, _spacing = fetch_channel_volume(url, timepoint)
        channel_volume = _select_channel(volume, channel_index)
        filtered = apply_filter_pipeline(channel_volume, steps)
    except (UnsupportedZarrError, UnsupportedFilterError) as error:
        raise ToolError(str(error)) from error
    metadata = {
        "channel_index": channel_index,
        "timepoint": timepoint,
        "steps": steps,
        "before": volume_intensity_stats(channel_volume),
        "after": volume_intensity_stats(filtered),
    }
    png_bytes = render_volume_max_projection_png(filtered)
    return [json.dumps(metadata), Image(data=png_bytes, format="png")]


@mcp.tool(
    description=(
        "Apply one or more real image-processing filters, in order, "
        "to one real channel of a remote plain zarr array (no "
        "OME-NGFF metadata) at one real timepoint. See "
        "describe_plain_zarr_dataset for why axis_hint matters here. "
        f"{_FILTER_CATALOG_HELP} Returns real before/after intensity "
        "stats plus a real max-intensity-projection PNG of the "
        "filtered result."
    )
)
def apply_filters_to_plain_zarr_dataset(
    url: str,
    steps: list[dict],
    channel_index: int = 0,
    timepoint: int = 0,
    axis_hint: str | None = None,
) -> list:
    try:
        volume, _spacing = fetch_plain_zarr_channel_volume(
            url, timepoint, axis_hint
        )
        channel_volume = _select_channel(volume, channel_index)
        filtered = apply_filter_pipeline(channel_volume, steps)
    except (UnsupportedZarrError, UnsupportedFilterError) as error:
        raise ToolError(str(error)) from error
    metadata = {
        "channel_index": channel_index,
        "timepoint": timepoint,
        "steps": steps,
        "before": volume_intensity_stats(channel_volume),
        "after": volume_intensity_stats(filtered),
    }
    png_bytes = render_volume_max_projection_png(filtered)
    return [json.dumps(metadata), Image(data=png_bytes, format="png")]


@mcp.tool()
def analyze_video_tracking(file_path: str, max_frames: int = 30) -> dict:
    """Real multi-frame object tracking against a local video file,
    via the exact same real yolo11n + ByteTrack pipeline the studio's
    own upload path runs. Returns the real claim plus every real
    frame's own tracked detections (frame_index, track_id, class_name,
    confidence, bbox_xyxy) - the same real track_id persists across
    frames for the same real tracked object.
    """
    path = _resolve_local_file(file_path)
    try:
        frames = extract_frames(path.read_bytes(), max_frames=max_frames)
        tracked = track_frames(frames)
    except UnsupportedVideoError as error:
        raise ToolError(str(error)) from error
    return {
        "claim": describe_tracks(tracked),
        "frame_count": len(frames),
        "tracks": tracked_frames_to_dicts(tracked),
    }


@mcp.tool()
def analyze_nifti_volume(file_path: str, percentile: float = 97.0) -> dict:
    """Real high-intensity-region detection against a local NIfTI file
    (.nii or .nii.gz), the same real segmentation the studio's own
    upload path runs. percentile sets the real intensity threshold: a
    higher percentile finds fewer, brighter regions.
    """
    return segment_uploaded_volume(
        _resolve_local_file(file_path), percentile=percentile
    )


@mcp.tool()
def render_nifti_slice_preview(
    file_path: str, slice_index: int | None = None, timepoint: int = 0
) -> list:
    """A real z-slice, normalized to an 8-bit grayscale PNG, from a
    local NIfTI file. slice_index defaults to the real middle slice
    when omitted; timepoint defaults to the first. The accompanying
    text block states the real z-slice index and timepoint actually
    rendered, so the agent reports that as a fact rather than inferring
    it.
    """
    volume = load_volume_generic(_resolve_local_file(file_path))
    resolved_slice_index = (
        volume.shape[2] // 2 if slice_index is None else slice_index
    )
    png_bytes = render_representative_slice_png(
        volume, resolved_slice_index, timepoint
    )
    metadata = {
        "rendered_slice_index": resolved_slice_index,
        "rendered_timepoint": timepoint,
        "volume_shape": list(volume.shape),
    }
    return [json.dumps(metadata), Image(data=png_bytes, format="png")]


@mcp.tool()
def analyze_dicom_volume(file_path: str, percentile: float = 97.0) -> dict:
    """Real high-intensity-region detection against a local DICOM file,
    after stripping identifying tags the same way the studio's own
    upload path does before any analysis runs.
    """
    return analyze_dicom(
        _resolve_local_file(file_path), percentile=percentile
    )


@mcp.tool()
def render_dicom_frame_preview(
    file_path: str, frame_index: int | None = None, timepoint: int = 0
) -> list:
    """A real frame, normalized to an 8-bit grayscale PNG, from a local
    DICOM file, after the same tag-stripping step analyze_dicom_volume
    uses. frame_index defaults to the real middle frame when omitted;
    timepoint defaults to the first. The accompanying text block states
    the real frame index and timepoint actually rendered, so the agent
    reports that as a fact rather than inferring it.
    """
    path = _resolve_local_file(file_path)
    volume = pixel_array_as_volume(load_scrubbed_dicom(path))
    resolved_frame_index = (
        volume.shape[2] // 2 if frame_index is None else frame_index
    )
    png_bytes = render_representative_frame_png(
        path, resolved_frame_index, timepoint
    )
    metadata = {
        "rendered_frame_index": resolved_frame_index,
        "rendered_timepoint": timepoint,
        "volume_shape": list(volume.shape),
    }
    return [json.dumps(metadata), Image(data=png_bytes, format="png")]


@mcp.tool()
async def search_tenant_evidence(
    tenant_id: str, query: str, size: int = 5
) -> dict:
    """Real hybrid (keyword + vector) search against one tenant's own
    already-indexed studio evidence. tenant_id is explicit here, unlike
    every other tool: this is the one capability that touches the
    shared, multi-tenant OpenSearch index rather than a caller-supplied
    local file or remote URL, so the caller must say whose evidence to
    search. Requires a real GEMINI_API_KEY to embed the query text.
    """
    vector = await embed_text(query)
    result = tenant_hybrid_query(tenant_id, query, vector, size)
    return {
        "hits": [
            hit["_source"] for hit in result.get("hits", {}).get("hits", [])
        ]
    }


def _resolve_access_token(access_token: str | None) -> str:
    """Prefers a real token from the STUDIO_ACCESS_TOKEN environment
    variable over one passed as a tool argument, and only falls back
    to the argument when that variable is unset.

    Confirmed directly against a real deployed coordinator: a real
    LLM (Gemini 2.5 Flash) asked to reproduce a long, high-entropy
    bearer token verbatim as a tool-call argument silently corrupted
    a handful of characters in the middle of the string, producing a
    token that still looked plausible but failed real signature
    verification. An LLM predicts tokens; it does not byte-copy. A
    long opaque secret should never be something an agent has to type
    out again, so the real, recommended setup exports
    STUDIO_ACCESS_TOKEN once in the environment the MCP server itself
    runs in (e.g. a small wrapper script that extracts it from the
    browser session), and every live-control tool below takes
    access_token as optional, falling back to that real environment
    value rather than asking the model to retype it.
    """
    # The environment variable wins even when an explicit access_token
    # is also given: that argument is exactly the real, high-entropy
    # string an agent is unreliable at reproducing, so once a trusted
    # STUDIO_ACCESS_TOKEN exists there is no real reason to trust a
    # caller-supplied copy of it over the source of truth.
    token = os.environ.get("STUDIO_ACCESS_TOKEN") or access_token
    if not token:
        raise ToolError(
            "no access_token given and STUDIO_ACCESS_TOKEN is not set "
            "in this server's own environment"
        )
    return token


def _live_session_request(
    coordinator_url: str,
    access_token: str | None,
    method: str,
    path: str,
    payload: dict | None = None,
) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        coordinator_url.rstrip("/") + path,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_resolve_access_token(access_token)}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise ToolError(
            f"live viewer request failed ({error.code}): {detail}"
        ) from error


def _send_live_command(
    coordinator_url: str,
    access_token: str | None,
    session_id: str,
    action: str,
    params: dict,
) -> dict:
    return _live_session_request(
        coordinator_url,
        access_token,
        "POST",
        f"/api/studio/live-sessions/{session_id}/commands",
        {"action": action, "params": params},
    )


@mcp.tool()
def list_live_viewer_sessions(
    coordinator_url: str, access_token: str | None = None
) -> dict:
    """Every one of this caller's own real currently-open live viewer
    sessions (a VolumeViewer or ChannelVolumeViewer tab that has
    registered itself), so an agent can discover which session_id to
    target instead of a person having to copy/paste one manually.
    """
    return _live_session_request(
        coordinator_url, access_token, "GET", "/api/studio/live-sessions"
    )


@mcp.tool()
def get_live_viewer_state(
    coordinator_url: str, session_id: str, access_token: str | None = None
) -> dict:
    """The real last-known state an already-open VolumeViewer or
    ChannelVolumeViewer tab reported for itself after its most recent
    real change. Call this after a set_live_* command to confirm it
    actually took effect, rather than trusting that a "sent" response
    meant "applied": that response only confirms the coordinator
    queued the command, not that the browser tab ever received or
    rendered it. If the real reported state does not match what was
    requested, self-correct by sending the command again or adjusting
    it, instead of assuming it worked.
    """
    return _live_session_request(
        coordinator_url,
        access_token,
        "GET",
        f"/api/studio/live-sessions/{session_id}/state",
    )


@mcp.tool()
def set_live_window_level(
    coordinator_url: str,
    session_id: str,
    window: float,
    level: float,
    access_token: str | None = None,
) -> dict:
    """Changes the real window/level of an already-open VolumeViewer or
    ChannelVolumeViewer tab live, exactly as if a person had dragged
    those sliders themselves.
    """
    return _send_live_command(
        coordinator_url,
        access_token,
        session_id,
        "set_window_level",
        {"window": window, "level": level},
    )


@mcp.tool()
def set_live_colormap(
    coordinator_url: str,
    session_id: str,
    colormap_name: str,
    access_token: str | None = None,
) -> dict:
    """Changes an already-open VolumeViewer tab's real colormap live.
    Real valid names: Grayscale, X Ray, Black-Body Radiation, Cool to
    Warm, Cold and Hot, rainbow (the same presets the human UI offers;
    an unrecognized name is silently ignored by the viewer, the same
    way selecting an invalid option would be).
    """
    return _send_live_command(
        coordinator_url,
        access_token,
        session_id,
        "set_colormap",
        {"name": colormap_name},
    )


@mcp.tool()
def set_live_timepoint(
    coordinator_url: str,
    session_id: str,
    timepoint: int,
    access_token: str | None = None,
) -> dict:
    """Scrubs an already-open VolumeViewer or ChannelVolumeViewer tab to
    a real timepoint live.
    """
    return _send_live_command(
        coordinator_url,
        access_token,
        session_id,
        "set_timepoint",
        {"timepoint": timepoint},
    )


@mcp.tool()
def snap_live_camera_axis(
    coordinator_url: str,
    session_id: str,
    axis: str,
    access_token: str | None = None,
) -> dict:
    """Snaps an already-open VolumeViewer or ChannelVolumeViewer tab's
    real camera to one of the six real axis-aligned views: "+X", "-X",
    "+Y", "-Y", "+Z", "-Z".
    """
    return _send_live_command(
        coordinator_url, access_token, session_id, "snap_axis", {"axis": axis}
    )


@mcp.tool()
def set_live_segmentation_visible(
    coordinator_url: str,
    session_id: str,
    visible: bool,
    access_token: str | None = None,
) -> dict:
    """Toggles an already-open VolumeViewer tab's real detected-region
    overlay live.
    """
    return _send_live_command(
        coordinator_url,
        access_token,
        session_id,
        "set_segmentation_visible",
        {"visible": visible},
    )


@mcp.tool()
def set_live_grid_visible(
    coordinator_url: str,
    session_id: str,
    visible: bool,
    access_token: str | None = None,
) -> dict:
    """Toggles an already-open VolumeViewer or ChannelVolumeViewer tab's
    real Cartesian grid live.
    """
    return _send_live_command(
        coordinator_url,
        access_token,
        session_id,
        "set_grid_visible",
        {"visible": visible},
    )


@mcp.tool()
def set_live_auto_rotate(
    coordinator_url: str,
    session_id: str,
    enabled: bool,
    direction: int = 1,
    access_token: str | None = None,
) -> dict:
    """Starts or stops an already-open VolumeViewer or
    ChannelVolumeViewer tab's real auto-rotate live. direction is 1 for
    clockwise, -1 for counter-clockwise (the same two real options the
    human UI's own dropdown offers).
    """
    return _send_live_command(
        coordinator_url,
        access_token,
        session_id,
        "set_auto_rotate",
        {"enabled": enabled, "direction": direction},
    )


@mcp.tool()
def set_live_channel_state(
    coordinator_url: str,
    session_id: str,
    channel_index: int,
    visible: bool | None = None,
    color_hex: str | None = None,
    window: float | None = None,
    level: float | None = None,
    access_token: str | None = None,
) -> dict:
    """Changes one real channel's visibility, color, and/or window/level
    in an already-open ChannelVolumeViewer tab live. Only the real
    parameters actually given are changed; any left as None keep their
    current real value, the same way leaving a control untouched would.
    """
    params: dict = {"channel_index": channel_index}
    if visible is not None:
        params["visible"] = visible
    if color_hex is not None:
        params["color_hex"] = color_hex
    if window is not None:
        params["window"] = window
    if level is not None:
        params["level"] = level
    return _send_live_command(
        coordinator_url, access_token, session_id, "set_channel_state", params
    )


@mcp.tool(
    description=(
        "Applies one or more real image-processing filters, in order, "
        "to one real channel of whatever dataset an already-open "
        "ChannelVolumeViewer tab currently has loaded (OME-Zarr or "
        f"plain zarr - the browser's own already-open source). "
        f"{_FILTER_CATALOG_HELP} The browser applies this the same way "
        "a person clicking 'Apply pipeline' in the real Filter panel "
        "would, and reports its own real before/after stats back - "
        "call get_live_viewer_state afterward to read the real result "
        "under state.lastFilterResult rather than assuming it worked."
    )
)
def apply_live_filter_pipeline(
    coordinator_url: str,
    session_id: str,
    steps: list[dict],
    channel_index: int = 0,
    timepoint: int = 0,
    access_token: str | None = None,
) -> dict:
    return _send_live_command(
        coordinator_url,
        access_token,
        session_id,
        "apply_filter_pipeline",
        {
            "steps": steps,
            "channel_index": channel_index,
            "timepoint": timepoint,
        },
    )


@mcp.tool()
def set_live_detection_display(
    coordinator_url: str,
    session_id: str,
    confidence_threshold: float | None = None,
    boxes_visible: bool | None = None,
    highlighted_index: int | None = None,
    access_token: str | None = None,
) -> dict:
    """Changes which real detected-object boxes an already-open
    detection tab shows live, exactly as if a person had moved the
    confidence slider, toggled the boxes checkbox, or clicked one real
    detection to highlight it themselves. confidence_threshold (0.0 to
    1.0) hides every real detection below it; boxes_visible toggles all
    boxes at once; highlighted_index (the real 0-based index into the
    tab's own last-known detections list) outlines one specific real
    detection. Only the real parameters actually given are changed; any
    left as None keep their current real value.
    """
    params: dict = {}
    if confidence_threshold is not None:
        params["confidence_threshold"] = confidence_threshold
    if boxes_visible is not None:
        params["boxes_visible"] = boxes_visible
    if highlighted_index is not None:
        params["highlighted_index"] = highlighted_index
    return _send_live_command(
        coordinator_url,
        access_token,
        session_id,
        "set_detection_display",
        params,
    )


@mcp.tool()
def set_live_segmentation_mask_visible(
    coordinator_url: str,
    session_id: str,
    visible: bool,
    nuclear_channel_index: int = 0,
    access_token: str | None = None,
) -> dict:
    """Toggles an already-open ChannelVolumeViewer tab's real Otsu-
    threshold segmentation mask overlay live, for one real channel
    (nuclear_channel_index). The browser fetches the real mask the
    first time this turns it on and appends it as one more real
    independent-components channel, exactly as if a person had ticked
    the "Show segmentation mask" checkbox themselves.
    """
    return _send_live_command(
        coordinator_url,
        access_token,
        session_id,
        "set_segmentation_mask_visible",
        {"visible": visible, "nuclear_channel_index": nuclear_channel_index},
    )


@mcp.tool()
def set_live_track_display(
    coordinator_url: str,
    session_id: str,
    confidence_threshold: float | None = None,
    boxes_visible: bool | None = None,
    highlighted_track_id: int | None = None,
    frame_index: int | None = None,
    access_token: str | None = None,
) -> dict:
    """Changes what an already-open tracking tab shows live, exactly
    as if a person had moved the confidence slider, toggled the boxes
    checkbox, scrubbed the frame slider, or clicked one real track to
    highlight it themselves. highlighted_track_id is the real
    persistent track_id (the same one analyze_video_tracking reports),
    not a frame-local index, so it stays meaningful as frame_index
    changes. Only the real parameters actually given are changed; any
    left as None keep their current real value.
    """
    params: dict = {}
    if confidence_threshold is not None:
        params["confidence_threshold"] = confidence_threshold
    if boxes_visible is not None:
        params["boxes_visible"] = boxes_visible
    if highlighted_track_id is not None:
        params["highlighted_track_id"] = highlighted_track_id
    if frame_index is not None:
        params["frame_index"] = frame_index
    return _send_live_command(
        coordinator_url, access_token, session_id, "set_track_display", params
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()

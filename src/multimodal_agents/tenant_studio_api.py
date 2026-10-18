"""Bring-your-own-data studio API. tenant_id always comes from the
caller's verified Auth0 organization claim, the same org-per-tenant
identity chapter 35 already proved, never from a request parameter. No
endpoint here may accept a tenant_id from the caller: that would let any
authenticated user simply claim to be a different tenant.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, Field

from multimodal_agents.embedding import embed_image_bytes, embed_text
from multimodal_agents.identity import (
    Identity,
    decode_auth0_token,
    identity_from_claims,
)
from multimodal_agents.live_viewer_sessions import (
    InvalidLiveCommandError,
    RateLimitExceededError,
    UnknownLiveSessionError,
)
from multimodal_agents.live_viewer_sessions import (
    get_screenshot as get_live_session_screenshot,
)
from multimodal_agents.live_viewer_sessions import (
    get_state as get_live_session_state,
)
from multimodal_agents.live_viewer_sessions import (
    list_sessions as list_live_sessions,
)
from multimodal_agents.live_viewer_sessions import (
    push_command as push_live_command,
)
from multimodal_agents.live_viewer_sessions import (
    register_session as register_live_session,
)
from multimodal_agents.live_viewer_sessions import (
    report_screenshot as report_live_session_screenshot,
)
from multimodal_agents.live_viewer_sessions import (
    report_state as report_live_session_state,
)
from multimodal_agents.live_viewer_sessions import (
    session_queue as live_session_queue,
)
from multimodal_agents.live_viewer_sessions import (
    unregister_session as unregister_live_session,
)
from multimodal_agents.safe_url_fetch import UnsafeURLError, fetch_remote_file
from multimodal_agents.tenant_detection import (
    describe_detections,
    detect_objects,
    detections_to_dicts,
)
from multimodal_agents.tenant_dicom import (
    UnsupportedDicomError,
    analyze_dicom,
    save_scrubbed_dicom,
)
from multimodal_agents.tenant_dicom import (
    render_representative_frame_png as render_dicom_frame_png,
)
from multimodal_agents.tenant_filters import (
    UnsupportedFilterError,
    apply_filter_pipeline,
    volume_intensity_stats,
)
from multimodal_agents.tenant_studio_index import (
    ensure_tenant_index,
    get_tenant_document,
    index_tenant_document,
    tenant_hybrid_query,
)
from multimodal_agents.tenant_tiff import (
    UnsupportedTiffError,
    render_tiff_channel_preview,
    segment_tiff,
)
from multimodal_agents.tenant_video_tracking import (
    UnsupportedVideoError,
    describe_tracks,
    extract_frames,
    track_frames,
    tracked_frames_to_dicts,
)
from multimodal_agents.tenant_volumetric import (
    UnsupportedVolumeError,
    load_volume_generic,
    render_representative_slice_png,
    segment_volume_array,
)
from multimodal_agents.tenant_zarr import (
    UnsupportedZarrError,
    describe_plain_zarr,
    describe_zarr,
    fetch_channel_volume,
    fetch_ome_zarr_segmentation_mask,
    fetch_plain_zarr_channel_volume,
    fetch_plain_zarr_segment_and_render,
    fetch_plain_zarr_segmentation_mask,
    fetch_segment_and_render,
)

REQUIRED_PERMISSION = "write:studio_evidence"
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_VOLUME_UPLOAD_BYTES = 200 * 1024 * 1024
MAX_DICOM_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_TIFF_UPLOAD_BYTES = 200 * 1024 * 1024
MAX_VIDEO_UPLOAD_BYTES = 100 * 1024 * 1024
UPLOAD_CHUNK_BYTES = 256 * 1024
ALLOWED_IMAGE_FORMATS = frozenset({"PNG", "JPEG"})
ALLOWED_VOLUME_EXTENSIONS = frozenset({".nii", ".nii.gz"})
ALLOWED_DICOM_EXTENSIONS = frozenset({".dcm"})
ALLOWED_TIFF_EXTENSIONS = frozenset(
    {".tif", ".tiff", ".ome.tif", ".ome.tiff"}
)
ALLOWED_VIDEO_EXTENSIONS = frozenset({".mp4", ".avi", ".mov", ".webm"})
UPLOAD_STORAGE_DIR = Path(os.getenv("TENANT_UPLOAD_DIR", "uploads"))


async def current_identity(request: Request) -> Identity:
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "bearer access token is required")
    claims = decode_auth0_token(authorization.removeprefix("Bearer "))
    return identity_from_claims(claims, REQUIRED_PERMISSION)


class TenantSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    size: int = Field(default=5, ge=1, le=50)


class TenantIngestURLRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)


class TenantIngestZarrRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    nuclear_channel_index: int = Field(default=0, ge=0, le=16)


class TenantIngestPlainZarrRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    nuclear_channel_index: int = Field(default=0, ge=0, le=16)
    axis_hint: str | None = Field(default=None, max_length=5)


class TenantZarrChannelVolumeRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    timepoint: int = Field(default=0, ge=0, le=10_000)


class TenantZarrMetadataRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)


class TenantPlainZarrMetadataRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    axis_hint: str | None = Field(default=None, max_length=5)


class TenantPlainZarrChannelVolumeRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    timepoint: int = Field(default=0, ge=0, le=10_000)
    axis_hint: str | None = Field(default=None, max_length=5)


class FilterStep(BaseModel):
    filter: str = Field(min_length=1, max_length=64)
    params: dict = Field(default_factory=dict)


class TenantFilterOmeZarrRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    steps: list[FilterStep] = Field(min_length=1, max_length=20)
    channel_index: int = Field(default=0, ge=0, le=64)
    timepoint: int = Field(default=0, ge=0, le=10_000)


class TenantFilterPlainZarrRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    steps: list[FilterStep] = Field(min_length=1, max_length=20)
    channel_index: int = Field(default=0, ge=0, le=64)
    timepoint: int = Field(default=0, ge=0, le=10_000)
    axis_hint: str | None = Field(default=None, max_length=5)


class TenantSegmentationMaskRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    nuclear_channel_index: int = Field(default=0, ge=0, le=64)
    timepoint: int = Field(default=0, ge=0, le=10_000)


class TenantPlainZarrSegmentationMaskRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    nuclear_channel_index: int = Field(default=0, ge=0, le=64)
    timepoint: int = Field(default=0, ge=0, le=10_000)
    axis_hint: str | None = Field(default=None, max_length=5)


class RegisterLiveSessionRequest(BaseModel):
    viewer_type: Literal["volume", "channel_volume", "detection", "tracking"]


class LiveSessionCommandRequest(BaseModel):
    action: str = Field(min_length=1, max_length=64)
    params: dict = Field(default_factory=dict)


def validate_image_bytes(data: bytes) -> str:
    """Decode and verify the image actually is what it claims to be,
    rather than trusting a client-supplied content type or extension.
    Returns the real detected format.
    """
    try:
        image = Image.open(io.BytesIO(data))
        image.verify()
    except UnidentifiedImageError as error:
        raise HTTPException(400, "file is not a readable image") from error
    except OSError as error:
        raise HTTPException(400, "file is not a valid image") from error
    image_format = (image.format or "").upper()
    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise HTTPException(
            400, f"unsupported image format: {image_format or 'unknown'}"
        )
    return image_format


async def read_upload_capped(file: UploadFile, max_bytes: int) -> bytes:
    total = 0
    chunks: list[bytes] = []
    while True:
        chunk = await file.read(UPLOAD_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(413, f"upload exceeds {max_bytes} bytes")
        chunks.append(chunk)
    if not chunks:
        raise HTTPException(400, "uploaded file is empty")
    return b"".join(chunks)


def validated_volume_extension(filename: str | None) -> str:
    name = (filename or "").lower()
    for extension in sorted(
        ALLOWED_VOLUME_EXTENSIONS, key=len, reverse=True
    ):
        if name.endswith(extension):
            return extension
    raise HTTPException(
        400,
        f"filename must end with one of {sorted(ALLOWED_VOLUME_EXTENSIONS)}",
    )


async def ingest_volume(
    tenant_id: str, data: bytes, filename: str, origin: str
) -> dict:
    extension = validated_volume_extension(filename)
    doc_id = str(uuid.uuid4())
    tenant_dir = UPLOAD_STORAGE_DIR / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    stored_path = tenant_dir / f"{doc_id}{extension}"
    stored_path.write_bytes(data)

    def load_segment_and_render() -> tuple[dict, bytes]:
        volume = load_volume_generic(stored_path)
        segmentation = segment_volume_array(volume)
        preview_png = render_representative_slice_png(volume)
        return segmentation, preview_png

    try:
        segmentation, preview_png = await asyncio.to_thread(
            load_segment_and_render
        )
    except UnsupportedVolumeError as error:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(400, str(error)) from error
    except Exception as error:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(
            400, f"could not read volume: {error}"
        ) from error

    vector = await embed_image_bytes(preview_png, "image/png")
    document = {
        "modality": "volume",
        "text": f"{segmentation['claim']} (uploaded volume from {origin})",
        "evidence_ids": [str(stored_path)],
        "source_file": str(stored_path),
        "embedding": vector,
    }
    await asyncio.to_thread(
        index_tenant_document, tenant_id, doc_id, document
    )
    return {
        "doc_id": doc_id,
        "bytes": len(data),
        "stored_at": str(stored_path),
        "claim": segmentation["claim"],
        "volume_shape": segmentation["volume_shape"],
        "region_count": segmentation["region_count"],
        "regions": segmentation["regions"],
    }


def validated_tiff_extension(filename: str | None) -> str:
    name = (filename or "").lower()
    for extension in sorted(ALLOWED_TIFF_EXTENSIONS, key=len, reverse=True):
        if name.endswith(extension):
            return extension
    raise HTTPException(
        400,
        f"filename must end with one of {sorted(ALLOWED_TIFF_EXTENSIONS)}",
    )


async def ingest_tiff(
    tenant_id: str, data: bytes, filename: str, origin: str
) -> dict:
    """Plain-TIFF and OME-TIFF share one ingest path: tifffile's own
    real axes string already tells tenant_tiff.py which real file kind
    it got, so there is no need for this layer to distinguish them.
    """
    extension = validated_tiff_extension(filename)
    doc_id = str(uuid.uuid4())
    tenant_dir = UPLOAD_STORAGE_DIR / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    stored_path = tenant_dir / f"{doc_id}{extension}"
    stored_path.write_bytes(data)

    def segment_and_render() -> tuple[dict, bytes]:
        segmentation = segment_tiff(stored_path)
        preview_png = render_tiff_channel_preview(stored_path)
        return segmentation, preview_png

    try:
        segmentation, preview_png = await asyncio.to_thread(
            segment_and_render
        )
    except UnsupportedTiffError as error:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(400, str(error)) from error
    except Exception as error:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(400, f"could not read TIFF: {error}") from error

    preview_path = tenant_dir / f"{doc_id}-preview.png"
    preview_path.write_bytes(preview_png)
    vector = await embed_image_bytes(preview_png, "image/png")
    document = {
        "modality": "volume",
        "text": f"{segmentation['claim']} (uploaded TIFF from {origin})",
        "evidence_ids": [str(stored_path)],
        "source_file": str(stored_path),
        "embedding": vector,
    }
    await asyncio.to_thread(
        index_tenant_document, tenant_id, doc_id, document
    )
    counts_by_timepoint = segmentation["instance_counts_by_timepoint"]
    return {
        "doc_id": doc_id,
        "bytes": len(data),
        "stored_at": str(stored_path),
        "claim": segmentation["claim"],
        "volume_shape": segmentation["volume_shape"],
        "channel_count": segmentation["channel_count"],
        "instance_counts_by_timepoint": counts_by_timepoint,
    }


def validated_video_extension(filename: str | None) -> str:
    name = (filename or "").lower()
    for extension in sorted(ALLOWED_VIDEO_EXTENSIONS, key=len, reverse=True):
        if name.endswith(extension):
            return extension
    raise HTTPException(
        400,
        f"filename must end with one of {sorted(ALLOWED_VIDEO_EXTENSIONS)}",
    )


async def ingest_video(
    tenant_id: str, data: bytes, filename: str, origin: str
) -> dict:
    """Real multi-frame tracking against a researcher's own uploaded
    video: every real extracted frame is also saved as its own real
    PNG so the frontend can show a real frame-by-frame player with
    real bounding boxes overlaid, the same way ingest_tiff's preview
    lets the browser show something visual rather than only numbers.
    """
    extension = validated_video_extension(filename)
    doc_id = str(uuid.uuid4())
    tenant_dir = UPLOAD_STORAGE_DIR / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    stored_path = tenant_dir / f"{doc_id}{extension}"
    stored_path.write_bytes(data)

    def extract_and_track() -> tuple[list, list, list[bytes]]:
        frames = extract_frames(data)
        tracked = track_frames(frames)
        frame_pngs = []
        for frame in frames:
            buffer = io.BytesIO()
            Image.fromarray(frame).save(buffer, format="PNG")
            frame_pngs.append(buffer.getvalue())
        return frames, tracked, frame_pngs

    try:
        frames, tracked, frame_pngs = await asyncio.to_thread(
            extract_and_track
        )
    except UnsupportedVideoError as error:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(400, str(error)) from error
    except Exception as error:
        stored_path.unlink(missing_ok=True)
        raise HTTPException(400, f"could not read video: {error}") from error

    for index, frame_png in enumerate(frame_pngs):
        (tenant_dir / f"{doc_id}-frame-{index}.png").write_bytes(frame_png)

    claim = describe_tracks(tracked)
    vector = await embed_image_bytes(frame_pngs[0], "image/png")
    document = {
        "modality": "video",
        "text": f"{claim} (uploaded video from {origin})",
        "evidence_ids": [str(stored_path)],
        "source_file": str(stored_path),
        "embedding": vector,
    }
    await asyncio.to_thread(
        index_tenant_document, tenant_id, doc_id, document
    )
    return {
        "doc_id": doc_id,
        "bytes": len(data),
        "stored_at": str(stored_path),
        "claim": claim,
        "frame_count": len(frames),
        "tracks": tracked_frames_to_dicts(tracked),
    }


async def ingest_ome_zarr(
    tenant_id: str, url: str, nuclear_channel_index: int
) -> dict:
    """OME-Zarr is a remote reference, not a downloaded file: the real
    evidence is the URL itself, plus a real locally-saved preview
    rendering so a researcher can see the projection without re-fetching.
    """
    doc_id = str(uuid.uuid4())
    tenant_dir = UPLOAD_STORAGE_DIR / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    preview_path = tenant_dir / f"{doc_id}-preview.png"

    try:
        segmentation, preview_png = await asyncio.to_thread(
            fetch_segment_and_render, url, nuclear_channel_index
        )
    except UnsafeURLError as error:
        raise HTTPException(400, str(error)) from error
    except UnsupportedZarrError as error:
        raise HTTPException(400, str(error)) from error

    preview_path.write_bytes(preview_png)
    vector = await embed_image_bytes(preview_png, "image/png")
    document = {
        "modality": "volume",
        "text": f"{segmentation['claim']} (remote OME-Zarr dataset at {url})",
        "evidence_ids": [url, str(preview_path)],
        "source_file": str(preview_path),
        "embedding": vector,
    }
    await asyncio.to_thread(
        index_tenant_document, tenant_id, doc_id, document
    )
    return {
        "doc_id": doc_id,
        "source_url": url,
        "preview_at": str(preview_path),
        "claim": segmentation["claim"],
        "volume_shape": segmentation["volume_shape"],
        "instance_counts_by_timepoint": segmentation[
            "instance_counts_by_timepoint"
        ],
    }


async def ingest_plain_zarr(
    tenant_id: str,
    url: str,
    nuclear_channel_index: int,
    axis_hint: str | None,
) -> dict:
    """A plain zarr array (no OME-NGFF metadata) is still a remote
    reference like OME-Zarr, so this mirrors ingest_ome_zarr exactly
    except for the real axis_hint it passes through: see
    tenant_zarr.open_plain_zarr_array for why that matters here.
    """
    doc_id = str(uuid.uuid4())
    tenant_dir = UPLOAD_STORAGE_DIR / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    preview_path = tenant_dir / f"{doc_id}-preview.png"

    try:
        segmentation, preview_png = await asyncio.to_thread(
            fetch_plain_zarr_segment_and_render,
            url,
            nuclear_channel_index,
            axis_hint,
        )
    except UnsafeURLError as error:
        raise HTTPException(400, str(error)) from error
    except UnsupportedZarrError as error:
        raise HTTPException(400, str(error)) from error

    preview_path.write_bytes(preview_png)
    vector = await embed_image_bytes(preview_png, "image/png")
    document = {
        "modality": "volume",
        "text": f"{segmentation['claim']} (remote plain zarr dataset "
        f"at {url})",
        "evidence_ids": [url, str(preview_path)],
        "source_file": str(preview_path),
        "embedding": vector,
    }
    await asyncio.to_thread(
        index_tenant_document, tenant_id, doc_id, document
    )
    return {
        "doc_id": doc_id,
        "source_url": url,
        "preview_at": str(preview_path),
        "claim": segmentation["claim"],
        "volume_shape": segmentation["volume_shape"],
        "instance_counts_by_timepoint": segmentation[
            "instance_counts_by_timepoint"
        ],
    }


def validated_dicom_extension(filename: str | None) -> None:
    name = (filename or "").lower()
    if not any(
        name.endswith(extension) for extension in ALLOWED_DICOM_EXTENSIONS
    ):
        raise HTTPException(
            400,
            f"filename must end with one of "
            f"{sorted(ALLOWED_DICOM_EXTENSIONS)}",
        )


async def ingest_dicom(
    tenant_id: str, data: bytes, filename: str, origin: str
) -> dict:
    """The raw uploaded bytes exist only in memory, in this function's
    own `data` and `raw_stream` locals: only the scrubbed dataset, with
    every real identifying tag already removed, is ever written to disk.
    """
    validated_dicom_extension(filename)
    doc_id = str(uuid.uuid4())
    tenant_dir = UPLOAD_STORAGE_DIR / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    stored_path = tenant_dir / f"{doc_id}.dcm"

    raw_stream = io.BytesIO(data)
    try:
        analysis = await asyncio.to_thread(analyze_dicom, raw_stream)
        raw_stream.seek(0)
        preview_png = await asyncio.to_thread(
            render_dicom_frame_png, raw_stream
        )
        raw_stream.seek(0)
        await asyncio.to_thread(save_scrubbed_dicom, raw_stream, stored_path)
    except UnsupportedDicomError as error:
        raise HTTPException(400, str(error)) from error

    vector = await embed_image_bytes(preview_png, "image/png")
    document = {
        "modality": "volume",
        "text": (
            f"{analysis['claim']} (uploaded {analysis['modality']} "
            f"DICOM from {origin}, identifying tags removed)"
        ),
        "evidence_ids": [str(stored_path)],
        "source_file": str(stored_path),
        "embedding": vector,
    }
    await asyncio.to_thread(
        index_tenant_document, tenant_id, doc_id, document
    )
    return {
        "doc_id": doc_id,
        "bytes": len(data),
        "stored_at": str(stored_path),
        "modality": analysis["modality"],
        "claim": analysis["claim"],
        "volume_shape": analysis["volume_shape"],
        "region_count": analysis["region_count"],
    }


async def ingest_image(tenant_id: str, data: bytes, origin: str) -> dict:
    image_format = validate_image_bytes(data)
    doc_id = str(uuid.uuid4())
    tenant_dir = UPLOAD_STORAGE_DIR / tenant_id
    tenant_dir.mkdir(parents=True, exist_ok=True)
    extension = "png" if image_format == "PNG" else "jpg"
    stored_path = tenant_dir / f"{doc_id}.{extension}"
    stored_path.write_bytes(data)

    media_type = "image/png" if image_format == "PNG" else "image/jpeg"
    vector, detections = await asyncio.gather(
        embed_image_bytes(data, media_type),
        asyncio.to_thread(detect_objects, data),
    )
    claim = describe_detections(detections)
    document = {
        "modality": "image",
        "text": (
            f"{claim} (uploaded {image_format.lower()} image from "
            f"{origin})"
        ),
        "evidence_ids": [str(stored_path)],
        "source_file": str(stored_path),
        "embedding": vector,
    }
    await asyncio.to_thread(
        index_tenant_document, tenant_id, doc_id, document
    )
    return {
        "doc_id": doc_id,
        "format": image_format,
        "bytes": len(data),
        "stored_at": str(stored_path),
        "claim": claim,
        "detections": detections_to_dicts(detections),
    }


router = APIRouter()


@router.on_event("startup")
async def _ensure_tenant_index_exists() -> None:
    """Idempotent: checks for the real base index before creating it, so
    this is safe to run on every boot rather than needing a separate,
    easy-to-forget migration step the first time this deploys anywhere.
    """
    await asyncio.to_thread(ensure_tenant_index)


@router.post("/api/studio/search")
async def tenant_search(
    body: TenantSearchRequest, identity: Identity = Depends(current_identity)
) -> dict:
    vector = await embed_text(body.query)
    result = tenant_hybrid_query(
        identity.tenant_id, body.query, vector, body.size
    )
    return {
        "tenant_id": identity.tenant_id,
        "hits": [
            hit["_source"] for hit in result.get("hits", {}).get("hits", [])
        ],
    }


@router.post("/api/studio/upload")
async def upload_image(
    file: UploadFile, identity: Identity = Depends(current_identity)
) -> dict:
    data = await read_upload_capped(file, MAX_UPLOAD_BYTES)
    result = await ingest_image(
        identity.tenant_id, data, origin="direct upload"
    )
    return {"tenant_id": identity.tenant_id, **result}


@router.post("/api/studio/upload-volume")
async def upload_volume(
    file: UploadFile, identity: Identity = Depends(current_identity)
) -> dict:
    data = await read_upload_capped(file, MAX_VOLUME_UPLOAD_BYTES)
    result = await ingest_volume(
        identity.tenant_id, data, file.filename or "", origin="direct upload"
    )
    return {"tenant_id": identity.tenant_id, **result}


@router.post("/api/studio/upload-dicom")
async def upload_dicom(
    file: UploadFile, identity: Identity = Depends(current_identity)
) -> dict:
    data = await read_upload_capped(file, MAX_DICOM_UPLOAD_BYTES)
    result = await ingest_dicom(
        identity.tenant_id, data, file.filename or "", origin="direct upload"
    )
    return {"tenant_id": identity.tenant_id, **result}


@router.post("/api/studio/upload-tiff")
async def upload_tiff(
    file: UploadFile, identity: Identity = Depends(current_identity)
) -> dict:
    data = await read_upload_capped(file, MAX_TIFF_UPLOAD_BYTES)
    result = await ingest_tiff(
        identity.tenant_id, data, file.filename or "", origin="direct upload"
    )
    return {"tenant_id": identity.tenant_id, **result}


@router.get("/api/studio/tiff-preview/{doc_id}")
async def get_tiff_preview(
    doc_id: str, identity: Identity = Depends(current_identity)
) -> FileResponse:
    """Serves the real max-intensity-projection PNG ingest_tiff wrote
    alongside the uploaded file, so the browser can show something
    visual: browsers do not reliably render raw TIFF bytes inline the
    way they do PNG/JPEG. Checks the same tenant-scoped directory
    get_volume_file already trusts, by direct path rather than through
    get_tenant_document, since this preview file is not itself an
    indexed document.
    """
    tenant_dir = (UPLOAD_STORAGE_DIR / identity.tenant_id).resolve()
    preview_path = (tenant_dir / f"{doc_id}-preview.png").resolve()
    if preview_path.parent != tenant_dir or not preview_path.is_file():
        raise HTTPException(404, "no such preview for this tenant")
    return FileResponse(preview_path, media_type="image/png")


@router.post("/api/studio/upload-video")
async def upload_video(
    file: UploadFile, identity: Identity = Depends(current_identity)
) -> dict:
    data = await read_upload_capped(file, MAX_VIDEO_UPLOAD_BYTES)
    result = await ingest_video(
        identity.tenant_id, data, file.filename or "", origin="direct upload"
    )
    return {"tenant_id": identity.tenant_id, **result}


@router.get("/api/studio/video-frame/{doc_id}/{frame_index}")
async def get_video_frame(
    doc_id: str,
    frame_index: int,
    identity: Identity = Depends(current_identity),
) -> FileResponse:
    """Serves one real extracted frame ingest_video wrote alongside the
    uploaded video, the same tenant-scoped direct-path pattern
    get_tiff_preview already uses. frame_index being a real int path
    param (FastAPI's own real type coercion) rules out a path-
    traversal string before this ever touches the filesystem.
    """
    tenant_dir = (UPLOAD_STORAGE_DIR / identity.tenant_id).resolve()
    frame_path = (
        tenant_dir / f"{doc_id}-frame-{frame_index}.png"
    ).resolve()
    if frame_path.parent != tenant_dir or not frame_path.is_file():
        raise HTTPException(404, "no such video frame for this tenant")
    return FileResponse(frame_path, media_type="image/png")


@router.post("/api/studio/ingest-url")
async def ingest_from_url(
    body: TenantIngestURLRequest,
    identity: Identity = Depends(current_identity),
) -> dict:
    try:
        data = await asyncio.to_thread(
            fetch_remote_file, body.url, MAX_UPLOAD_BYTES
        )
    except UnsafeURLError as error:
        raise HTTPException(400, str(error)) from error
    result = await ingest_image(identity.tenant_id, data, origin=body.url)
    return {"tenant_id": identity.tenant_id, "source_url": body.url, **result}


@router.post("/api/studio/zarr-metadata")
async def get_zarr_metadata(
    body: TenantZarrMetadataRequest,
    identity: Identity = Depends(current_identity),
) -> dict:
    """Real shape/channel/spacing metadata only: no segmentation run, no
    tenant document indexed. Cheap enough for a viewer to call on every
    open, unlike /api/studio/ingest-ome-zarr which does real analysis
    work and writes to the tenant's index as a side effect.
    """
    del identity
    try:
        return await asyncio.to_thread(describe_zarr, body.url)
    except UnsafeURLError as error:
        raise HTTPException(400, str(error)) from error
    except UnsupportedZarrError as error:
        raise HTTPException(400, str(error)) from error


@router.post("/api/studio/ingest-ome-zarr")
async def ingest_ome_zarr_endpoint(
    body: TenantIngestZarrRequest,
    identity: Identity = Depends(current_identity),
) -> dict:
    result = await ingest_ome_zarr(
        identity.tenant_id, body.url, body.nuclear_channel_index
    )
    return {"tenant_id": identity.tenant_id, **result}


@router.post("/api/studio/zarr-channel-volume")
async def get_zarr_channel_volume(
    body: TenantZarrChannelVolumeRequest,
    identity: Identity = Depends(current_identity),
) -> Response:
    """Every real channel's data at one real timepoint, as raw float32
    bytes with every channel interleaved per voxel (Z, Y, X, C), the real
    tuple layout vtk.js's own DataArray expects for a multi-component
    vtkImageData (confirmed against its own getTuple/numberOfComponents
    contract: component values for one voxel are contiguous, not planar
    per channel). identity.tenant_id is verified but not otherwise used:
    OME-Zarr access is by URL, never by a locally stored per-tenant file,
    so there is no tenant-scoped doc_id to check here. Shape and real
    physical spacing travel as response headers rather than a JSON
    envelope, matching how /api/studio/volumes/{doc_id} already serves
    raw bytes for the NIfTI pipeline.
    """
    del identity
    try:
        volume, spacing = await asyncio.to_thread(
            fetch_channel_volume, body.url, body.timepoint
        )
    except UnsafeURLError as error:
        raise HTTPException(400, str(error)) from error
    except UnsupportedZarrError as error:
        raise HTTPException(400, str(error)) from error
    channels, depth, height, width = volume.shape
    interleaved = volume.transpose(1, 2, 3, 0)
    return Response(
        content=interleaved.tobytes(),
        media_type="application/octet-stream",
        headers={
            "X-Channel-Count": str(channels),
            "X-Shape-Z": str(depth),
            "X-Shape-Y": str(height),
            "X-Shape-X": str(width),
            "X-Spacing-Z": repr(spacing[0]),
            "X-Spacing-Y": repr(spacing[1]),
            "X-Spacing-X": repr(spacing[2]),
        },
    )


@router.post("/api/studio/plain-zarr-metadata")
async def get_plain_zarr_metadata(
    body: TenantPlainZarrMetadataRequest,
    identity: Identity = Depends(current_identity),
) -> dict:
    """Mirrors /api/studio/zarr-metadata for a plain zarr array with no
    OME-NGFF metadata. See tenant_zarr.open_plain_zarr_array for why
    axis_hint matters: without it, channel_count/timepoints may be a
    real but wrong ndim-based guess.
    """
    del identity
    try:
        return await asyncio.to_thread(
            describe_plain_zarr, body.url, body.axis_hint
        )
    except UnsafeURLError as error:
        raise HTTPException(400, str(error)) from error
    except UnsupportedZarrError as error:
        raise HTTPException(400, str(error)) from error


@router.post("/api/studio/ingest-plain-zarr")
async def ingest_plain_zarr_endpoint(
    body: TenantIngestPlainZarrRequest,
    identity: Identity = Depends(current_identity),
) -> dict:
    result = await ingest_plain_zarr(
        identity.tenant_id,
        body.url,
        body.nuclear_channel_index,
        body.axis_hint,
    )
    return {"tenant_id": identity.tenant_id, **result}


@router.post("/api/studio/plain-zarr-channel-volume")
async def get_plain_zarr_channel_volume(
    body: TenantPlainZarrChannelVolumeRequest,
    identity: Identity = Depends(current_identity),
) -> Response:
    """Mirrors /api/studio/zarr-channel-volume for a plain zarr array."""
    del identity
    try:
        volume, spacing = await asyncio.to_thread(
            fetch_plain_zarr_channel_volume,
            body.url,
            body.timepoint,
            body.axis_hint,
        )
    except UnsafeURLError as error:
        raise HTTPException(400, str(error)) from error
    except UnsupportedZarrError as error:
        raise HTTPException(400, str(error)) from error
    channels, depth, height, width = volume.shape
    interleaved = volume.transpose(1, 2, 3, 0)
    return Response(
        content=interleaved.tobytes(),
        media_type="application/octet-stream",
        headers={
            "X-Channel-Count": str(channels),
            "X-Shape-Z": str(depth),
            "X-Shape-Y": str(height),
            "X-Shape-X": str(width),
            "X-Spacing-Z": repr(spacing[0]),
            "X-Spacing-Y": repr(spacing[1]),
            "X-Spacing-X": repr(spacing[2]),
        },
    )


@router.post("/api/studio/zarr-segmentation-mask")
async def get_zarr_segmentation_mask(
    body: TenantSegmentationMaskRequest,
    identity: Identity = Depends(current_identity),
) -> Response:
    """Raw float32 (Z, Y, X) bytes of the real Otsu-threshold
    segmentation mask (1.0 where a kept real instance is, 0.0
    elsewhere) for one real channel of a remote OME-Zarr dataset at one
    real timepoint. The same raw-bytes convention
    /api/studio/zarr-channel-volume already uses, one real channel's
    worth: a viewer appends this as one more real independent-
    components channel rather than needing a separate overlay
    mechanism.
    """
    del identity
    try:
        mask = await asyncio.to_thread(
            fetch_ome_zarr_segmentation_mask,
            body.url,
            body.nuclear_channel_index,
            body.timepoint,
        )
    except UnsafeURLError as error:
        raise HTTPException(400, str(error)) from error
    except UnsupportedZarrError as error:
        raise HTTPException(400, str(error)) from error
    depth, height, width = mask.shape
    return Response(
        content=mask.astype("float32").tobytes(),
        media_type="application/octet-stream",
        headers={
            "X-Shape-Z": str(depth),
            "X-Shape-Y": str(height),
            "X-Shape-X": str(width),
        },
    )


@router.post("/api/studio/plain-zarr-segmentation-mask")
async def get_plain_zarr_segmentation_mask(
    body: TenantPlainZarrSegmentationMaskRequest,
    identity: Identity = Depends(current_identity),
) -> Response:
    """Mirrors /api/studio/zarr-segmentation-mask for a plain zarr
    array. See tenant_zarr.open_plain_zarr_array for why axis_hint
    matters here.
    """
    del identity
    try:
        mask = await asyncio.to_thread(
            fetch_plain_zarr_segmentation_mask,
            body.url,
            body.nuclear_channel_index,
            body.timepoint,
            body.axis_hint,
        )
    except UnsafeURLError as error:
        raise HTTPException(400, str(error)) from error
    except UnsupportedZarrError as error:
        raise HTTPException(400, str(error)) from error
    depth, height, width = mask.shape
    return Response(
        content=mask.astype("float32").tobytes(),
        media_type="application/octet-stream",
        headers={
            "X-Shape-Z": str(depth),
            "X-Shape-Y": str(height),
            "X-Shape-X": str(width),
        },
    )


def _filtered_volume_response(
    channel_volume, filtered
) -> Response:
    """Raw float32 (Z, Y, X) bytes of the real filtered result, the
    same raw-bytes convention /api/studio/zarr-channel-volume already
    uses, plus real before/after intensity stats as headers so a
    caller can report what the filter actually did without a second
    round trip.
    """
    depth, height, width = filtered.shape
    before = volume_intensity_stats(channel_volume)
    after = volume_intensity_stats(filtered)
    return Response(
        content=filtered.astype("float32").tobytes(),
        media_type="application/octet-stream",
        headers={
            "X-Shape-Z": str(depth),
            "X-Shape-Y": str(height),
            "X-Shape-X": str(width),
            "X-Before-Min": repr(before["min"]),
            "X-Before-Max": repr(before["max"]),
            "X-Before-Mean": repr(before["mean"]),
            "X-After-Min": repr(after["min"]),
            "X-After-Max": repr(after["max"]),
            "X-After-Mean": repr(after["mean"]),
        },
    )


@router.post("/api/studio/filter-ome-zarr")
async def filter_ome_zarr(
    body: TenantFilterOmeZarrRequest,
    identity: Identity = Depends(current_identity),
) -> Response:
    """Apply one or more real filters, in order, to one real channel
    of a remote OME-Zarr dataset at one real timepoint. No tenant
    document is indexed: this is an exploratory processing step, not a
    final analysis result (mirrors /api/studio/zarr-channel-volume's
    own no-side-effect design).
    """
    del identity
    steps = [step.model_dump() for step in body.steps]
    try:
        volume, _spacing = await asyncio.to_thread(
            fetch_channel_volume, body.url, body.timepoint
        )
        if not 0 <= body.channel_index < volume.shape[0]:
            raise HTTPException(
                400,
                f"channel_index {body.channel_index} out of range for "
                f"{volume.shape[0]} real channel(s)",
            )
        channel_volume = volume[body.channel_index]
        filtered = await asyncio.to_thread(
            apply_filter_pipeline, channel_volume, steps
        )
    except UnsafeURLError as error:
        raise HTTPException(400, str(error)) from error
    except UnsupportedZarrError as error:
        raise HTTPException(400, str(error)) from error
    except UnsupportedFilterError as error:
        raise HTTPException(400, str(error)) from error
    return _filtered_volume_response(channel_volume, filtered)


@router.post("/api/studio/filter-plain-zarr")
async def filter_plain_zarr(
    body: TenantFilterPlainZarrRequest,
    identity: Identity = Depends(current_identity),
) -> Response:
    """Mirrors /api/studio/filter-ome-zarr for a plain zarr array with
    no OME-NGFF metadata. See tenant_zarr.open_plain_zarr_array for why
    axis_hint matters here.
    """
    del identity
    steps = [step.model_dump() for step in body.steps]
    try:
        volume, _spacing = await asyncio.to_thread(
            fetch_plain_zarr_channel_volume,
            body.url,
            body.timepoint,
            body.axis_hint,
        )
        if not 0 <= body.channel_index < volume.shape[0]:
            raise HTTPException(
                400,
                f"channel_index {body.channel_index} out of range for "
                f"{volume.shape[0]} real channel(s)",
            )
        channel_volume = volume[body.channel_index]
        filtered = await asyncio.to_thread(
            apply_filter_pipeline, channel_volume, steps
        )
    except UnsafeURLError as error:
        raise HTTPException(400, str(error)) from error
    except UnsupportedZarrError as error:
        raise HTTPException(400, str(error)) from error
    except UnsupportedFilterError as error:
        raise HTTPException(400, str(error)) from error
    return _filtered_volume_response(channel_volume, filtered)


@router.get("/api/studio/volumes/{doc_id}")
async def get_volume_file(
    doc_id: str, identity: Identity = Depends(current_identity)
) -> FileResponse:
    """Serve a tenant's own real uploaded file for in-browser rendering.
    Ownership is resolved through the same tenant-scoped alias lookup
    every other tenant read already goes through: a doc_id that exists
    but belongs to a different tenant resolves to 404 here, never to
    that other tenant's file.
    """
    document = await asyncio.to_thread(
        get_tenant_document, identity.tenant_id, doc_id
    )
    if document is None:
        raise HTTPException(404, "no such document for this tenant")
    source_file = Path(document["source_file"])
    tenant_dir = (UPLOAD_STORAGE_DIR / identity.tenant_id).resolve()
    resolved = source_file.resolve()
    if resolved.parent != tenant_dir or not resolved.is_file():
        raise HTTPException(404, "stored file not found")
    return FileResponse(resolved, media_type="application/octet-stream")


@router.post("/api/studio/live-sessions")
async def open_live_session(
    body: RegisterLiveSessionRequest,
    identity: Identity = Depends(current_identity),
) -> dict:
    """Registers one real, currently-open VolumeViewer or
    ChannelVolumeViewer tab so an MCP tool call can target it by
    session_id. Called once when that viewer mounts.
    """
    session = register_live_session(identity.tenant_id, body.viewer_type)
    return {"session_id": session.session_id}


@router.get("/api/studio/live-sessions")
async def get_live_sessions(
    identity: Identity = Depends(current_identity),
) -> dict:
    """Every one of this tenant's own real currently-open live
    sessions, so an agent can discover which session_id to target
    without the person having to copy/paste one manually.
    """
    return {"sessions": list_live_sessions(identity.tenant_id)}


@router.get("/api/studio/live-sessions/{session_id}/events")
async def live_session_events(
    session_id: str, identity: Identity = Depends(current_identity)
) -> StreamingResponse:
    """A real Server-Sent-Events stream of every command pushed to this
    one session, consumed by that same browser tab via fetch + a manual
    SSE parser (not the native EventSource API, which cannot send the
    real Authorization header this endpoint requires).
    """
    try:
        queue = live_session_queue(session_id, identity.tenant_id)
    except UnknownLiveSessionError as error:
        raise HTTPException(404, str(error)) from error

    async def event_stream():
        try:
            while True:
                try:
                    command = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {json.dumps(command)}\n\n"
                except TimeoutError:
                    # A comment line, not a real event: keeps the real
                    # connection alive through proxies that would
                    # otherwise time out an idle stream.
                    yield ": heartbeat\n\n"
        finally:
            unregister_live_session(session_id)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/studio/live-sessions/{session_id}/commands")
async def send_live_session_command(
    session_id: str,
    body: LiveSessionCommandRequest,
    identity: Identity = Depends(current_identity),
) -> dict:
    """The real delivery point an MCP tool call reaches to make an
    already-open browser tab actually change what it is showing. Every
    real command is validated, rate-limited, and appended to a real
    audit log (tagged with the caller's own real identity) before it is
    ever queued for delivery.
    """
    try:
        await push_live_command(
            session_id,
            identity.tenant_id,
            body.action,
            body.params,
            subject=identity.subject,
        )
    except UnknownLiveSessionError as error:
        raise HTTPException(404, str(error)) from error
    except InvalidLiveCommandError as error:
        raise HTTPException(400, str(error)) from error
    except RateLimitExceededError as error:
        raise HTTPException(429, str(error)) from error
    return {"status": "sent"}


@router.post("/api/studio/live-sessions/{session_id}/state")
async def report_live_session_state_endpoint(
    session_id: str,
    body: dict,
    identity: Identity = Depends(current_identity),
) -> dict:
    """The browser's own real current state, reported after applying
    any change, so get_live_session_state_endpoint always reflects what
    is genuinely on screen right now rather than merely what was
    requested.
    """
    try:
        report_live_session_state(session_id, identity.tenant_id, body)
    except UnknownLiveSessionError as error:
        raise HTTPException(404, str(error)) from error
    return {"status": "recorded"}


@router.get("/api/studio/live-sessions/{session_id}/state")
async def get_live_session_state_endpoint(
    session_id: str, identity: Identity = Depends(current_identity)
) -> dict:
    """The real last-known state an already-open browser tab reported
    for itself, so an agent can confirm a command actually took effect
    rather than trusting that "sent" meant "applied".
    """
    try:
        return get_live_session_state(session_id, identity.tenant_id)
    except UnknownLiveSessionError as error:
        raise HTTPException(404, str(error)) from error


@router.post("/api/studio/live-sessions/{session_id}/screenshot")
async def report_live_session_screenshot_endpoint(
    session_id: str,
    body: dict,
    identity: Identity = Depends(current_identity),
) -> dict:
    """The browser's own real screenshot of its current canvas, taken
    and reported after a capture_screenshot command, the same way
    report_live_session_state_endpoint reports state. body must contain
    a real base64-encoded PNG under "image_base64".
    """
    image_base64 = body.get("image_base64")
    if not isinstance(image_base64, str) or not image_base64:
        raise HTTPException(400, "image_base64 must be a real, non-empty string")
    try:
        report_live_session_screenshot(
            session_id, identity.tenant_id, image_base64
        )
    except UnknownLiveSessionError as error:
        raise HTTPException(404, str(error)) from error
    return {"status": "recorded"}


@router.get("/api/studio/live-sessions/{session_id}/screenshot")
async def get_live_session_screenshot_endpoint(
    session_id: str, identity: Identity = Depends(current_identity)
) -> dict:
    """The real last screenshot an already-open browser tab reported
    for itself, so an agent calling capture_live_viewer_screenshot can
    poll for a real, freshly-captured image rather than one the backend
    fabricated.
    """
    try:
        return get_live_session_screenshot(session_id, identity.tenant_id)
    except UnknownLiveSessionError as error:
        raise HTTPException(404, str(error)) from error

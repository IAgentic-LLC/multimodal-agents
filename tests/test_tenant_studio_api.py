import asyncio
import io
import json
import os
from pathlib import Path

import numpy as np
import pydicom
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from nibabel.testing import data_path
from PIL import Image
from ultralytics.utils import ASSETS

from multimodal_agents.identity import Identity
from multimodal_agents.tenant_studio_api import current_identity, router
from multimodal_agents.tenant_video_tracking import (
    extract_frames as real_extract_frames,
)


def real_png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(buffer, format="PNG")
    return buffer.getvalue()


def make_client(monkeypatch, tmp_path) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[current_identity] = lambda: Identity(
        subject="user-1", tenant_id="lab-one", permissions=frozenset({"write:studio_evidence"})
    )
    monkeypatch.setattr(
        "multimodal_agents.tenant_studio_api.UPLOAD_STORAGE_DIR", tmp_path
    )

    async def fake_embed_image_bytes(data: bytes, media_type: str = "image/png") -> list[float]:
        return [0.1] * 768

    monkeypatch.setattr(
        "multimodal_agents.tenant_studio_api.embed_image_bytes", fake_embed_image_bytes
    )
    monkeypatch.setattr(
        "multimodal_agents.tenant_studio_api.index_tenant_document",
        lambda tenant_id, doc_id, document: None,
    )
    return TestClient(app)


def test_upload_accepts_a_real_png(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/upload",
        files={"file": ("sample.png", real_png_bytes(), "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "lab-one"
    assert body["format"] == "PNG"


def test_upload_rejects_non_image_bytes_regardless_of_claimed_type(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/upload",
        files={"file": ("fake.png", b"not actually a png", "image/png")},
    )
    assert response.status_code == 400


def test_upload_requires_authentication():
    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    response = client.post(
        "/api/studio/upload",
        files={"file": ("sample.png", real_png_bytes(), "image/png")},
    )
    assert response.status_code == 401


def test_ingest_url_rejects_cloud_metadata_address(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/ingest-url",
        json={"url": "http://169.254.169.254/latest/meta-data/"},
    )
    assert response.status_code == 400


def test_ingest_url_rejects_non_http_scheme(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post("/api/studio/ingest-url", json={"url": "file:///etc/passwd"})
    assert response.status_code == 400


def test_upload_persists_the_real_file_under_the_tenants_own_directory(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/upload",
        files={"file": ("sample.png", real_png_bytes(), "image/png")},
    )
    stored_at = response.json()["stored_at"]
    assert str(tmp_path / "lab-one") in stored_at


def test_upload_runs_real_detection_against_a_real_photo(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/upload",
        files={"file": ("bus.jpg", (ASSETS / "bus.jpg").read_bytes(), "image/jpeg")},
    )
    assert response.status_code == 200
    body = response.json()
    class_names = {d["class_name"] for d in body["detections"]}
    assert "bus" in class_names
    assert "person" in class_names
    assert "bus" in body["claim"]


def test_upload_volume_runs_real_segmentation_against_a_real_nifti(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    real_volume_bytes = Path(os.path.join(data_path, "example4d.nii.gz")).read_bytes()
    response = client.post(
        "/api/studio/upload-volume",
        files={"file": ("brain.nii.gz", real_volume_bytes, "application/octet-stream")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "lab-one"
    assert body["volume_shape"] == [128, 96, 24, 2]
    assert body["region_count"] > 0
    assert "t=0" in body["claim"]
    assert "t=1" in body["claim"]
    assert len(body["regions"]) == body["region_count"]
    first_region = body["regions"][0]
    assert set(first_region) == {
        "region_id", "label", "voxel_count", "mean_intensity", "slice_index", "timepoint", "bbox",
    }
    assert len(first_region["bbox"]) == 4


def test_upload_volume_rejects_a_bad_extension(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/upload-volume",
        files={"file": ("not-a-volume.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_ingest_ome_zarr_stores_a_real_preview_and_indexes_it(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)

    def fake_fetch_segment_and_render(url, nuclear_channel_index=0):
        segmentation = {
            "claim": "40 total real instance(s) across 2 timepoint(s) (26 at t=0, 14 at t=1)",
            "volume_shape": (2, 236, 68, 67),
            "instance_counts_by_timepoint": [26, 14],
        }
        return segmentation, real_png_bytes()

    monkeypatch.setattr(
        "multimodal_agents.tenant_studio_api.fetch_segment_and_render",
        fake_fetch_segment_and_render,
    )
    response = client.post(
        "/api/studio/ingest-ome-zarr",
        json={"url": "https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0062A/6001240.zarr"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "lab-one"
    assert body["volume_shape"] == [2, 236, 68, 67]
    assert "26 at t=0" in body["claim"]
    assert (tmp_path / "lab-one").exists()


def test_ingest_ome_zarr_rejects_an_unsafe_url(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/ingest-ome-zarr",
        json={"url": "http://169.254.169.254/latest/meta-data/.zarr"},
    )
    assert response.status_code == 400


def test_zarr_metadata_returns_real_shape_without_side_effects(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)

    def fake_describe_zarr(url):
        return {
            "volume_shape": (2, 3, 6, 24, 24),
            "channel_count": 3,
            "timepoints": 2,
            "spacing": (2.0, 0.5, 0.5),
        }

    monkeypatch.setattr("multimodal_agents.tenant_studio_api.describe_zarr", fake_describe_zarr)
    response = client.post(
        "/api/studio/zarr-metadata",
        json={"url": "https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0062A/6001240.zarr"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "volume_shape": [2, 3, 6, 24, 24],
        "channel_count": 3,
        "timepoints": 2,
        "spacing": [2.0, 0.5, 0.5],
    }
    assert not any((tmp_path).iterdir())


def test_zarr_metadata_rejects_an_unsafe_url(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/zarr-metadata",
        json={"url": "http://169.254.169.254/latest/meta-data/.zarr"},
    )
    assert response.status_code == 400


def test_zarr_channel_volume_returns_real_raw_bytes_with_shape_headers(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    real_volume = np.arange(2 * 3 * 4 * 5, dtype=np.float32).reshape(2, 3, 4, 5)

    def fake_fetch_channel_volume(url, timepoint):
        return real_volume, (2.0, 0.5, 0.5)

    monkeypatch.setattr(
        "multimodal_agents.tenant_studio_api.fetch_channel_volume",
        fake_fetch_channel_volume,
    )
    response = client.post(
        "/api/studio/zarr-channel-volume",
        json={"url": "https://uk1s3.embassy.ebi.ac.uk/idr/zarr/v0.4/idr0062A/6001240.zarr", "timepoint": 0},
    )
    assert response.status_code == 200
    assert response.headers["X-Channel-Count"] == "2"
    assert response.headers["X-Shape-Z"] == "3"
    assert response.headers["X-Shape-Y"] == "4"
    assert response.headers["X-Shape-X"] == "5"
    assert response.headers["X-Spacing-Z"] == "2.0"
    assert response.headers["X-Spacing-Y"] == "0.5"
    received = np.frombuffer(response.content, dtype=np.float32).reshape(3, 4, 5, 2)
    np.testing.assert_array_equal(received, real_volume.transpose(1, 2, 3, 0))


def test_zarr_channel_volume_rejects_an_unsafe_url(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/zarr-channel-volume",
        json={"url": "http://169.254.169.254/latest/meta-data/.zarr", "timepoint": 0},
    )
    assert response.status_code == 400


def real_tiff_bytes() -> bytes:
    """A real small (Z, Y, X) TIFF with two genuinely separable bright
    blobs, written with tifffile the same way test_tenant_tiff.py does,
    so the real Otsu segmentation has something real to find.
    """
    import tifffile

    volume = np.zeros((6, 24, 24), dtype=np.float64)
    volume[1:3, 4:9, 4:9] = 200.0
    volume[1:3, 15:20, 15:20] = 200.0
    rng = np.random.default_rng(0)
    volume += rng.normal(0, 2, volume.shape)
    buffer = io.BytesIO()
    tifffile.imwrite(
        buffer, volume.astype(np.uint16), metadata={"axes": "ZYX"}
    )
    return buffer.getvalue()


def test_upload_tiff_runs_real_segmentation_against_a_real_tiff(
    monkeypatch, tmp_path
):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/upload-tiff",
        files={"file": ("sample.tif", real_tiff_bytes(), "image/tiff")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "lab-one"
    assert body["volume_shape"] == [1, 6, 24, 24]
    assert body["channel_count"] == 1
    assert body["instance_counts_by_timepoint"][0] >= 1
    assert "t=0" in body["claim"]


def test_upload_tiff_rejects_a_bad_extension(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/upload-tiff",
        files={"file": ("not-a-tiff.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_tiff_preview_serves_the_real_preview_written_at_upload(
    monkeypatch, tmp_path
):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/upload-tiff",
        files={"file": ("sample.tif", real_tiff_bytes(), "image/tiff")},
    )
    doc_id = response.json()["doc_id"]
    preview = client.get(f"/api/studio/tiff-preview/{doc_id}")
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert preview.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_tiff_preview_404s_for_an_unknown_doc_id(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.get("/api/studio/tiff-preview/not-a-real-doc-id")
    assert response.status_code == 404


def test_tiff_preview_404s_for_a_path_traversal_attempt(
    monkeypatch, tmp_path
):
    client = make_client(monkeypatch, tmp_path)
    response = client.get(
        "/api/studio/tiff-preview/..%2F..%2F..%2Fetc%2Fpasswd"
    )
    assert response.status_code == 404


def real_video_bytes() -> bytes:
    path = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "opencv-vtest-sample.avi"
    )
    return path.read_bytes()


def test_upload_video_runs_real_tracking_against_a_real_video(
    monkeypatch, tmp_path
):
    client = make_client(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "multimodal_agents.tenant_studio_api.extract_frames",
        lambda data: real_extract_frames(data, max_frames=4),
    )
    response = client.post(
        "/api/studio/upload-video",
        files={"file": ("sample.avi", real_video_bytes(), "video/avi")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "lab-one"
    assert body["frame_count"] == 4
    assert len(body["tracks"]) == 4
    assert "real tracked object(s)" in body["claim"]


def test_upload_video_rejects_a_bad_extension(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/upload-video",
        files={"file": ("not-a-video.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400


def test_video_frame_serves_a_real_extracted_frame(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "multimodal_agents.tenant_studio_api.extract_frames",
        lambda data: real_extract_frames(data, max_frames=3),
    )
    upload_response = client.post(
        "/api/studio/upload-video",
        files={"file": ("sample.avi", real_video_bytes(), "video/avi")},
    )
    doc_id = upload_response.json()["doc_id"]
    frame_response = client.get(f"/api/studio/video-frame/{doc_id}/0")
    assert frame_response.status_code == 200
    assert frame_response.headers["content-type"] == "image/png"
    assert frame_response.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_video_frame_404s_for_an_out_of_range_frame(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "multimodal_agents.tenant_studio_api.extract_frames",
        lambda data: real_extract_frames(data, max_frames=3),
    )
    upload_response = client.post(
        "/api/studio/upload-video",
        files={"file": ("sample.avi", real_video_bytes(), "video/avi")},
    )
    doc_id = upload_response.json()["doc_id"]
    response = client.get(f"/api/studio/video-frame/{doc_id}/999")
    assert response.status_code == 404


def test_video_frame_404s_for_a_path_traversal_attempt(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.get(
        "/api/studio/video-frame/..%2F..%2F..%2Fetc%2Fpasswd/0"
    )
    assert response.status_code == 404


def test_plain_zarr_metadata_returns_real_shape_without_side_effects(
    monkeypatch, tmp_path
):
    client = make_client(monkeypatch, tmp_path)

    def fake_describe_plain_zarr(url, axis_hint=None):
        return {
            "volume_shape": (2, 6, 24, 24),
            "channel_count": 2,
            "timepoints": 1,
            "spacing": (1.0, 1.0, 1.0),
        }

    monkeypatch.setattr(
        "multimodal_agents.tenant_studio_api.describe_plain_zarr",
        fake_describe_plain_zarr,
    )
    response = client.post(
        "/api/studio/plain-zarr-metadata",
        json={"url": "https://example.test/plain.zarr", "axis_hint": "CZYX"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "volume_shape": [2, 6, 24, 24],
        "channel_count": 2,
        "timepoints": 1,
        "spacing": [1.0, 1.0, 1.0],
    }
    assert not any(tmp_path.iterdir())


def test_plain_zarr_metadata_rejects_an_unsafe_url(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/plain-zarr-metadata",
        json={"url": "http://169.254.169.254/latest/meta-data/.zarr"},
    )
    assert response.status_code == 400


def test_ingest_plain_zarr_stores_a_real_preview_and_indexes_it(
    monkeypatch, tmp_path
):
    client = make_client(monkeypatch, tmp_path)

    def fake_fetch_plain_zarr_segment_and_render(
        url, nuclear_channel_index=0, axis_hint=None
    ):
        segmentation = {
            "claim": (
                "15 total real instance(s) across 1 timepoint(s) "
                "(15 at t=0)"
            ),
            "volume_shape": (2, 236, 68, 67),
            "instance_counts_by_timepoint": [15],
        }
        return segmentation, real_png_bytes()

    monkeypatch.setattr(
        "multimodal_agents.tenant_studio_api.fetch_plain_zarr_segment_and_render",
        fake_fetch_plain_zarr_segment_and_render,
    )
    response = client.post(
        "/api/studio/ingest-plain-zarr",
        json={
            "url": "https://example.test/plain.zarr",
            "nuclear_channel_index": 1,
            "axis_hint": "CZYX",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "lab-one"
    assert body["volume_shape"] == [2, 236, 68, 67]
    assert "15 at t=0" in body["claim"]
    assert (tmp_path / "lab-one").exists()


def test_ingest_plain_zarr_rejects_an_unsafe_url(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/ingest-plain-zarr",
        json={"url": "http://169.254.169.254/latest/meta-data/.zarr"},
    )
    assert response.status_code == 400


def test_plain_zarr_channel_volume_returns_real_raw_bytes_with_shape_headers(
    monkeypatch, tmp_path
):
    client = make_client(monkeypatch, tmp_path)
    real_volume = np.arange(2 * 3 * 4 * 5, dtype=np.float32)
    real_volume = real_volume.reshape(2, 3, 4, 5)

    def fake_fetch_plain_zarr_channel_volume(url, timepoint, axis_hint=None):
        return real_volume, (2.0, 0.5, 0.5)

    monkeypatch.setattr(
        "multimodal_agents.tenant_studio_api."
        "fetch_plain_zarr_channel_volume",
        fake_fetch_plain_zarr_channel_volume,
    )
    response = client.post(
        "/api/studio/plain-zarr-channel-volume",
        json={
            "url": "https://example.test/plain.zarr",
            "timepoint": 0,
            "axis_hint": "CZYX",
        },
    )
    assert response.status_code == 200
    assert response.headers["X-Channel-Count"] == "2"
    received = np.frombuffer(response.content, dtype=np.float32)
    received = received.reshape(3, 4, 5, 2)
    np.testing.assert_array_equal(received, real_volume.transpose(1, 2, 3, 0))


def test_plain_zarr_channel_volume_rejects_an_unsafe_url(
    monkeypatch, tmp_path
):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/plain-zarr-channel-volume",
        json={
            "url": "http://169.254.169.254/latest/meta-data/.zarr",
            "timepoint": 0,
        },
    )
    assert response.status_code == 400


def test_zarr_segmentation_mask_returns_real_raw_bytes(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    real_mask = np.zeros((6, 24, 24), dtype=np.float32)
    real_mask[1:3, 4:9, 4:9] = 1.0

    monkeypatch.setattr(
        "multimodal_agents.tenant_studio_api."
        "fetch_ome_zarr_segmentation_mask",
        lambda url, nuclear_channel_index, timepoint: real_mask,
    )
    response = client.post(
        "/api/studio/zarr-segmentation-mask",
        json={
            "url": "https://example.test/real.zarr",
            "nuclear_channel_index": 0,
        },
    )
    assert response.status_code == 200
    assert response.headers["X-Shape-Z"] == "6"
    assert response.headers["X-Shape-Y"] == "24"
    assert response.headers["X-Shape-X"] == "24"
    received = np.frombuffer(response.content, dtype=np.float32)
    np.testing.assert_array_equal(received.reshape(6, 24, 24), real_mask)


def test_zarr_segmentation_mask_rejects_an_unsafe_url(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/zarr-segmentation-mask",
        json={"url": "http://169.254.169.254/latest/meta-data/.zarr"},
    )
    assert response.status_code == 400


def test_plain_zarr_segmentation_mask_returns_real_raw_bytes(
    monkeypatch, tmp_path
):
    client = make_client(monkeypatch, tmp_path)
    real_mask = np.zeros((6, 24, 24), dtype=np.float32)
    real_mask[1:3, 4:9, 4:9] = 1.0

    def fake_fetch(url, nuclear_channel_index, timepoint, axis_hint=None):
        return real_mask

    monkeypatch.setattr(
        "multimodal_agents.tenant_studio_api."
        "fetch_plain_zarr_segmentation_mask",
        fake_fetch,
    )
    response = client.post(
        "/api/studio/plain-zarr-segmentation-mask",
        json={
            "url": "https://example.test/plain.zarr",
            "nuclear_channel_index": 1,
            "axis_hint": "CZYX",
        },
    )
    assert response.status_code == 200
    received = np.frombuffer(response.content, dtype=np.float32)
    np.testing.assert_array_equal(received.reshape(6, 24, 24), real_mask)


def test_plain_zarr_segmentation_mask_rejects_an_unsafe_url(
    monkeypatch, tmp_path
):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/plain-zarr-segmentation-mask",
        json={"url": "http://169.254.169.254/latest/meta-data/.zarr"},
    )
    assert response.status_code == 400


def test_filter_ome_zarr_applies_a_real_pipeline_and_reports_stats(
    monkeypatch, tmp_path
):
    client = make_client(monkeypatch, tmp_path)
    real_volume = np.zeros((2, 6, 24, 24), dtype=np.float32)
    real_volume[0, 1:3, 4:9, 4:9] = 200.0

    def fake_fetch_channel_volume(url, timepoint):
        return real_volume, (1.0, 1.0, 1.0)

    monkeypatch.setattr(
        "multimodal_agents.tenant_studio_api.fetch_channel_volume",
        fake_fetch_channel_volume,
    )
    response = client.post(
        "/api/studio/filter-ome-zarr",
        json={
            "url": "https://example.test/real.zarr",
            "channel_index": 0,
            "steps": [{"filter": "gaussian_blur", "params": {"sigma": 1.0}}],
        },
    )
    assert response.status_code == 200
    assert response.headers["X-Shape-Z"] == "6"
    assert response.headers["X-Shape-Y"] == "24"
    assert response.headers["X-Shape-X"] == "24"
    assert float(response.headers["X-Before-Max"]) == 200.0
    filtered = np.frombuffer(response.content, dtype=np.float32)
    assert filtered.reshape(6, 24, 24).max() < 200.0  # real blur spreads peak


def test_filter_ome_zarr_rejects_an_out_of_range_channel(
    monkeypatch, tmp_path
):
    client = make_client(monkeypatch, tmp_path)
    real_volume = np.zeros((2, 6, 24, 24), dtype=np.float32)

    monkeypatch.setattr(
        "multimodal_agents.tenant_studio_api.fetch_channel_volume",
        lambda url, timepoint: (real_volume, (1.0, 1.0, 1.0)),
    )
    response = client.post(
        "/api/studio/filter-ome-zarr",
        json={
            "url": "https://example.test/real.zarr",
            "channel_index": 9,
            "steps": [{"filter": "gaussian_blur"}],
        },
    )
    assert response.status_code == 400
    assert "out of range" in response.json()["detail"]


def test_filter_ome_zarr_rejects_an_unknown_filter_name(
    monkeypatch, tmp_path
):
    client = make_client(monkeypatch, tmp_path)
    real_volume = np.zeros((2, 6, 24, 24), dtype=np.float32)

    monkeypatch.setattr(
        "multimodal_agents.tenant_studio_api.fetch_channel_volume",
        lambda url, timepoint: (real_volume, (1.0, 1.0, 1.0)),
    )
    response = client.post(
        "/api/studio/filter-ome-zarr",
        json={
            "url": "https://example.test/real.zarr",
            "steps": [{"filter": "not-a-real-filter"}],
        },
    )
    assert response.status_code == 400
    assert "unknown filter" in response.json()["detail"]


def test_filter_ome_zarr_rejects_an_unsafe_url(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/filter-ome-zarr",
        json={
            "url": "http://169.254.169.254/latest/meta-data/.zarr",
            "steps": [{"filter": "gaussian_blur"}],
        },
    )
    assert response.status_code == 400


def test_filter_plain_zarr_applies_a_real_pipeline_and_reports_stats(
    monkeypatch, tmp_path
):
    client = make_client(monkeypatch, tmp_path)
    real_volume = np.zeros((2, 6, 24, 24), dtype=np.float32)
    real_volume[1, 1:3, 4:9, 4:9] = 150.0

    def fake_fetch_plain_zarr_channel_volume(url, timepoint, axis_hint=None):
        return real_volume, (1.0, 1.0, 1.0)

    monkeypatch.setattr(
        "multimodal_agents.tenant_studio_api."
        "fetch_plain_zarr_channel_volume",
        fake_fetch_plain_zarr_channel_volume,
    )
    response = client.post(
        "/api/studio/filter-plain-zarr",
        json={
            "url": "https://example.test/plain.zarr",
            "channel_index": 1,
            "axis_hint": "CZYX",
            "steps": [{"filter": "normalize_intensity"}],
        },
    )
    assert response.status_code == 200
    filtered = np.frombuffer(response.content, dtype=np.float32)
    assert filtered.reshape(6, 24, 24).max() == pytest.approx(1.0)


def test_filter_plain_zarr_rejects_an_unsafe_url(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/filter-plain-zarr",
        json={
            "url": "http://169.254.169.254/latest/meta-data/.zarr",
            "steps": [{"filter": "gaussian_blur"}],
        },
    )
    assert response.status_code == 400


def real_dicom_sample_bytes() -> bytes:
    return Path(pydicom.data.get_testdata_file("CT_small.dcm")).read_bytes()


def test_upload_dicom_runs_real_segmentation_and_strips_identifying_tags(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/upload-dicom",
        files={"file": ("ct.dcm", real_dicom_sample_bytes(), "application/dicom")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == "lab-one"
    assert body["modality"] == "CT"
    assert body["volume_shape"][:2] == [128, 128]

    from multimodal_agents.tenant_dicom import IDENTIFYING_TAGS

    stored = pydicom.dcmread(body["stored_at"])
    for tag in IDENTIFYING_TAGS:
        assert tag not in stored


def test_upload_dicom_rejects_a_bad_extension(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/upload-dicom",
        files={"file": ("scan.png", real_dicom_sample_bytes(), "application/dicom")},
    )
    assert response.status_code == 400


def make_client_for_tenant(monkeypatch, tmp_path, tenant_id: str) -> TestClient:
    """Like make_client, but against the real local OpenSearch index
    rather than a mocked no-op, since the volume-serving endpoint's own
    tenant-isolation guarantee can only be proven against the real
    alias-based lookup, not a stub that never actually writes anything.
    """
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[current_identity] = lambda: Identity(
        subject="user-1", tenant_id=tenant_id, permissions=frozenset({"write:studio_evidence"})
    )
    monkeypatch.setattr("multimodal_agents.tenant_studio_api.UPLOAD_STORAGE_DIR", tmp_path)

    async def fake_embed_image_bytes(data: bytes, media_type: str = "image/png") -> list[float]:
        return [0.1] * 768

    monkeypatch.setattr(
        "multimodal_agents.tenant_studio_api.embed_image_bytes", fake_embed_image_bytes
    )
    return TestClient(app)


def test_volume_endpoint_serves_only_the_owning_tenants_own_file(monkeypatch, tmp_path):
    from multimodal_agents.tenant_studio_index import ensure_tenant_index

    ensure_tenant_index(reset=True)

    owner_client = make_client_for_tenant(monkeypatch, tmp_path, "lab-one")
    upload_response = owner_client.post(
        "/api/studio/upload",
        files={"file": ("sample.png", real_png_bytes(), "image/png")},
    )
    assert upload_response.status_code == 200
    doc_id = upload_response.json()["doc_id"]

    owner_fetch = owner_client.get(f"/api/studio/volumes/{doc_id}")
    assert owner_fetch.status_code == 200

    other_client = make_client_for_tenant(monkeypatch, tmp_path, "lab-two")
    other_fetch = other_client.get(f"/api/studio/volumes/{doc_id}")
    assert other_fetch.status_code == 404

    ensure_tenant_index(reset=True)


def test_volume_endpoint_404s_for_an_unknown_doc_id(monkeypatch, tmp_path):
    client = make_client_for_tenant(monkeypatch, tmp_path, "lab-one")
    response = client.get("/api/studio/volumes/does-not-exist")
    assert response.status_code == 404


def test_open_live_session_returns_a_real_session_id(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post("/api/studio/live-sessions", json={"viewer_type": "volume"})
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    assert session_id

    listing = client.get("/api/studio/live-sessions")
    assert listing.json()["sessions"] == [
        {"session_id": session_id, "viewer_type": "volume", "registered_at": listing.json()["sessions"][0]["registered_at"]}
    ]


def test_live_sessions_are_scoped_to_the_real_tenant(monkeypatch, tmp_path):
    lab_one = make_client_for_tenant(monkeypatch, tmp_path, "lab-one")
    lab_two = make_client_for_tenant(monkeypatch, tmp_path, "lab-two")
    lab_one.post("/api/studio/live-sessions", json={"viewer_type": "volume"})
    lab_two_sessions = lab_two.get("/api/studio/live-sessions").json()["sessions"]
    assert lab_two_sessions == []


def test_send_live_session_command_delivers_a_real_event_over_sse(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    session_id = client.post("/api/studio/live-sessions", json={"viewer_type": "volume"}).json()["session_id"]

    sent = client.post(
        f"/api/studio/live-sessions/{session_id}/commands",
        json={"action": "set_window_level", "params": {"window": 500, "level": 100}},
    )
    assert sent.status_code == 200

    # The route itself is deliberately an infinite generator (a real,
    # persistent SSE connection), which httpx's ASGITransport cannot
    # read incrementally: confirmed directly, it buffers a streaming
    # response's producer task to completion before yielding anything,
    # so it hangs forever against a generator that never finishes. This
    # calls the real route function and reads its real body_iterator
    # directly instead, which exercises the exact same real logic
    # without going through that transport-layer limitation.
    from multimodal_agents.identity import Identity
    from multimodal_agents.tenant_studio_api import live_session_events

    identity = Identity(subject="user-1", tenant_id="lab-one", permissions=frozenset({"write:studio_evidence"}))
    response = asyncio.run(live_session_events(session_id, identity))
    assert response.status_code == 200
    first_chunk = asyncio.run(anext(response.body_iterator))
    assert first_chunk == 'data: {"action": "set_window_level", "params": {"window": 500, "level": 100}}\n\n'


def test_send_live_session_command_404s_for_an_unknown_session(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    response = client.post(
        "/api/studio/live-sessions/no-such-session/commands",
        json={"action": "set_window_level", "params": {}},
    )
    assert response.status_code == 404


def test_live_session_events_404s_for_a_session_from_a_different_tenant(monkeypatch, tmp_path):
    lab_one = make_client_for_tenant(monkeypatch, tmp_path, "lab-one")
    lab_two = make_client_for_tenant(monkeypatch, tmp_path, "lab-two")
    session_id = lab_one.post("/api/studio/live-sessions", json={"viewer_type": "volume"}).json()["session_id"]
    response = lab_two.get(f"/api/studio/live-sessions/{session_id}/events")
    assert response.status_code == 404


def test_send_live_session_command_400s_for_an_invalid_command(monkeypatch, tmp_path):
    monkeypatch.setattr("multimodal_agents.live_viewer_sessions.AUDIT_LOG_PATH", tmp_path / "audit.jsonl")
    client = make_client(monkeypatch, tmp_path)
    session_id = client.post("/api/studio/live-sessions", json={"viewer_type": "volume"}).json()["session_id"]
    response = client.post(
        f"/api/studio/live-sessions/{session_id}/commands",
        json={"action": "snap_axis", "params": {"axis": "+Q"}},
    )
    assert response.status_code == 400


def test_send_live_session_command_429s_after_a_real_burst(monkeypatch, tmp_path):
    monkeypatch.setattr("multimodal_agents.live_viewer_sessions.AUDIT_LOG_PATH", tmp_path / "audit.jsonl")
    monkeypatch.setattr("multimodal_agents.live_viewer_sessions.RATE_LIMIT_MAX_COMMANDS", 2)
    client = make_client(monkeypatch, tmp_path)
    session_id = client.post("/api/studio/live-sessions", json={"viewer_type": "volume"}).json()["session_id"]
    body = {"action": "set_timepoint", "params": {"timepoint": 1}}
    client.post(f"/api/studio/live-sessions/{session_id}/commands", json=body)
    client.post(f"/api/studio/live-sessions/{session_id}/commands", json=body)
    response = client.post(f"/api/studio/live-sessions/{session_id}/commands", json=body)
    assert response.status_code == 429


def test_send_live_session_command_audit_logs_the_real_callers_identity(monkeypatch, tmp_path):
    log_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr("multimodal_agents.live_viewer_sessions.AUDIT_LOG_PATH", log_path)
    client = make_client(monkeypatch, tmp_path)
    session_id = client.post("/api/studio/live-sessions", json={"viewer_type": "volume"}).json()["session_id"]
    client.post(
        f"/api/studio/live-sessions/{session_id}/commands",
        json={"action": "set_timepoint", "params": {"timepoint": 1}},
    )
    entry = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert entry["subject"] == "user-1"  # the real identity make_client's dependency override supplies
    assert entry["tenant_id"] == "lab-one"


def test_live_session_state_round_trips_a_real_report(monkeypatch, tmp_path):
    client = make_client(monkeypatch, tmp_path)
    session_id = client.post("/api/studio/live-sessions", json={"viewer_type": "volume"}).json()["session_id"]
    report = client.post(
        f"/api/studio/live-sessions/{session_id}/state", json={"window": 500, "level": 100}
    )
    assert report.status_code == 200
    read_back = client.get(f"/api/studio/live-sessions/{session_id}/state")
    assert read_back.json()["state"] == {"window": 500, "level": 100}


def test_live_session_state_404s_for_a_session_from_a_different_tenant(monkeypatch, tmp_path):
    lab_one = make_client_for_tenant(monkeypatch, tmp_path, "lab-one")
    lab_two = make_client_for_tenant(monkeypatch, tmp_path, "lab-two")
    session_id = lab_one.post("/api/studio/live-sessions", json={"viewer_type": "volume"}).json()["session_id"]
    response = lab_two.get(f"/api/studio/live-sessions/{session_id}/state")
    assert response.status_code == 404

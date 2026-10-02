import asyncio
import base64
import json
from pathlib import Path

import pytest
from mcp.server.mcpserver.exceptions import ToolError

from multimodal_agents import studio_mcp_server as server


def call(name: str, **arguments) -> dict:
    """Every tool here returns a dict (JSON-serialized into a text
    content block by the real MCP SDK, confirmed directly: a plain dict
    return is not auto-promoted to structured_content unless a tool
    explicitly opts in), an Image (a real base64-encoded image content
    block), or a [text, Image] list for the preview tools that report
    real ground-truth metadata alongside the image. This helper decodes
    whatever combination came back into one flat dict, and runs the
    real async call_tool path synchronously for tests.
    """
    result = asyncio.run(server.mcp.call_tool(name, arguments))
    assert not result.is_error, result.content
    merged: dict = {}
    for block in result.content:
        if block.type == "text":
            merged.update(json.loads(block.text))
        else:
            assert block.type == "image"
            merged["mime_type"] = block.mime_type
            merged["data"] = base64.b64decode(block.data)
    return merged


def test_describe_ome_zarr_dataset_wires_through(monkeypatch):
    monkeypatch.setattr(
        server,
        "describe_zarr",
        lambda url: {"volume_shape": [2, 236, 68, 67], "channel_count": 2},
    )
    result = call(
        "describe_ome_zarr_dataset", url="https://example.test/dataset.zarr"
    )
    assert result == {"volume_shape": [2, 236, 68, 67], "channel_count": 2}


def test_segment_ome_zarr_dataset_passes_through_the_channel_index(
    monkeypatch,
):
    captured = {}

    def fake_segment(url, channel_index):
        captured["url"] = url
        captured["channel_index"] = channel_index
        return {"claim": "3 total real instance(s)"}

    monkeypatch.setattr(server, "segment_ome_zarr", fake_segment)
    result = call(
        "segment_ome_zarr_dataset",
        url="https://example.test/dataset.zarr",
        channel_index=1,
    )
    assert result == {"claim": "3 total real instance(s)"}
    assert captured == {
        "url": "https://example.test/dataset.zarr",
        "channel_index": 1,
    }


def test_render_ome_zarr_channel_preview_returns_bytes_and_ground_truth(
    monkeypatch,
):
    fake_array = type("FakeArray", (), {"shape": (2, 236, 68, 67)})()
    fake_node = object()
    monkeypatch.setattr(
        server,
        "open_lowest_resolution_array",
        lambda url: (fake_array, fake_node),
    )

    def fake_render(array, channel_index, *, node, timepoint):
        assert array is fake_array
        assert node is fake_node
        assert channel_index == 1
        assert timepoint == 0
        return b"\x89PNG\r\n\x1a\nreal-bytes"

    monkeypatch.setattr(server, "render_array_max_projection", fake_render)
    result = call(
        "render_ome_zarr_channel_preview",
        url="https://example.test/dataset.zarr",
        channel_index=1,
    )
    assert result["mime_type"] == "image/png"
    assert result["data"] == b"\x89PNG\r\n\x1a\nreal-bytes"
    assert result["rendered_channel_index"] == 1
    assert result["rendered_timepoint"] == 0
    assert result["volume_shape"] == [2, 236, 68, 67]


def test_render_ome_zarr_channel_preview_passes_through_a_timepoint(
    monkeypatch,
):
    fake_array = type("FakeArray", (), {"shape": (2, 236, 68, 67)})()
    fake_node = object()
    monkeypatch.setattr(
        server,
        "open_lowest_resolution_array",
        lambda url: (fake_array, fake_node),
    )

    def fake_render(array, channel_index, *, node, timepoint):
        assert timepoint == 3
        return b"\x89PNG\r\n\x1a\nreal-bytes"

    monkeypatch.setattr(server, "render_array_max_projection", fake_render)
    result = call(
        "render_ome_zarr_channel_preview",
        url="https://example.test/dataset.zarr",
        channel_index=1,
        timepoint=3,
    )
    assert result["rendered_timepoint"] == 3


def test_analyze_video_tracking_runs_real_tracking_against_a_real_video():
    fixture = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "opencv-vtest-sample.avi"
    )
    result = call(
        "analyze_video_tracking",
        file_path=str(fixture),
        max_frames=4,
    )
    assert result["frame_count"] == 4
    assert len(result["tracks"]) == 4
    assert "real tracked object(s)" in result["claim"]


def test_analyze_video_tracking_rejects_a_missing_file():
    with pytest.raises(ToolError, match="not a real, readable local file"):
        asyncio.run(
            server.mcp.call_tool(
                "analyze_video_tracking", {"file_path": "/no/such/file.mp4"}
            )
        )


def test_set_live_track_display_omits_real_unset_parameters(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        server.urllib.request,
        "urlopen",
        fake_urlopen_capturing(captured, {"status": "sent"}),
    )
    call(
        "set_live_track_display",
        coordinator_url="http://127.0.0.1:8092",
        access_token="real-token",
        session_id="session-1",
        highlighted_track_id=4,
        frame_index=2,
    )
    assert captured["body"] == {
        "action": "set_track_display",
        "params": {"highlighted_track_id": 4, "frame_index": 2},
    }


def test_analyze_nifti_volume_rejects_a_missing_file():
    """call_tool, called directly rather than through the full JSON-RPC
    request pipeline, re-raises a deliberate ToolError rather than
    returning a graceful CallToolResult(is_error=True): confirmed
    directly against the real SDK, not assumed.
    """
    with pytest.raises(ToolError, match="not a real, readable local file"):
        asyncio.run(
            server.mcp.call_tool(
                "analyze_nifti_volume", {"file_path": "/no/such/file.nii.gz"}
            )
        )


def test_analyze_nifti_volume_wires_through_to_a_real_local_file(
    monkeypatch, tmp_path
):
    fixture = tmp_path / "volume.nii.gz"
    fixture.write_bytes(b"not a real nifti file, just needs to exist")
    captured = {}

    def fake_segment_uploaded_volume(path, percentile):
        captured["path"] = path
        captured["percentile"] = percentile
        return {"claim": "1 high-intensity region(s)"}

    monkeypatch.setattr(
        server, "segment_uploaded_volume", fake_segment_uploaded_volume
    )
    result = call(
        "analyze_nifti_volume", file_path=str(fixture), percentile=90.0
    )
    assert result == {"claim": "1 high-intensity region(s)"}
    assert captured["path"] == Path(fixture)
    assert captured["percentile"] == 90.0


def test_render_nifti_slice_preview_wires_through_and_reports_the_index(
    monkeypatch, tmp_path
):
    fixture = tmp_path / "volume.nii.gz"
    fixture.write_bytes(b"placeholder")
    fake_volume = type("FakeVolume", (), {"shape": (128, 96, 24, 2)})()
    monkeypatch.setattr(
        server, "load_volume_generic", lambda path: fake_volume
    )

    def fake_render(volume, slice_index, timepoint):
        assert volume is fake_volume
        assert slice_index == 12
        assert timepoint == 0
        return b"\x89PNG\r\n\x1a\nslice-bytes"

    monkeypatch.setattr(
        server, "render_representative_slice_png", fake_render
    )
    result = call("render_nifti_slice_preview", file_path=str(fixture))
    assert result["data"] == b"\x89PNG\r\n\x1a\nslice-bytes"
    assert result["rendered_slice_index"] == 12
    assert result["rendered_timepoint"] == 0
    assert result["volume_shape"] == [128, 96, 24, 2]


def test_render_nifti_slice_preview_passes_through_a_slice_and_timepoint(
    monkeypatch, tmp_path
):
    fixture = tmp_path / "volume.nii.gz"
    fixture.write_bytes(b"placeholder")
    fake_volume = type("FakeVolume", (), {"shape": (128, 96, 24, 2)})()
    monkeypatch.setattr(
        server, "load_volume_generic", lambda path: fake_volume
    )

    def fake_render(volume, slice_index, timepoint):
        assert slice_index == 5
        assert timepoint == 1
        return b"\x89PNG\r\n\x1a\nslice-bytes"

    monkeypatch.setattr(
        server, "render_representative_slice_png", fake_render
    )
    result = call(
        "render_nifti_slice_preview",
        file_path=str(fixture),
        slice_index=5,
        timepoint=1,
    )
    assert result["rendered_slice_index"] == 5
    assert result["rendered_timepoint"] == 1


def test_analyze_dicom_volume_wires_through(monkeypatch, tmp_path):
    fixture = tmp_path / "scan.dcm"
    fixture.write_bytes(b"placeholder")
    captured = {}

    def fake_analyze_dicom(path, percentile):
        captured["path"] = path
        captured["percentile"] = percentile
        return {"claim": "real dicom claim"}

    monkeypatch.setattr(server, "analyze_dicom", fake_analyze_dicom)
    result = call("analyze_dicom_volume", file_path=str(fixture))
    assert result == {"claim": "real dicom claim"}
    assert captured["path"] == Path(fixture)
    assert captured["percentile"] == 97.0


def test_render_dicom_frame_preview_wires_through_and_reports_the_index(
    monkeypatch, tmp_path
):
    fixture = tmp_path / "scan.dcm"
    fixture.write_bytes(b"placeholder")
    fake_dataset = object()
    fake_volume = type("FakeVolume", (), {"shape": (128, 128, 5, 1)})()

    monkeypatch.setattr(
        server, "load_scrubbed_dicom", lambda path: fake_dataset
    )
    monkeypatch.setattr(
        server, "pixel_array_as_volume", lambda dataset: fake_volume
    )

    def fake_render(path, frame_index, timepoint):
        assert path == Path(fixture)
        assert frame_index == 2
        assert timepoint == 0
        return b"\x89PNG\r\n\x1a\nframe-bytes"

    monkeypatch.setattr(
        server, "render_representative_frame_png", fake_render
    )
    result = call("render_dicom_frame_preview", file_path=str(fixture))
    assert result["data"] == b"\x89PNG\r\n\x1a\nframe-bytes"
    assert result["rendered_frame_index"] == 2
    assert result["rendered_timepoint"] == 0
    assert result["volume_shape"] == [128, 128, 5, 1]


def test_render_dicom_frame_preview_passes_through_a_frame_and_timepoint(
    monkeypatch, tmp_path
):
    fixture = tmp_path / "scan.dcm"
    fixture.write_bytes(b"placeholder")
    fake_dataset = object()
    fake_volume = type("FakeVolume", (), {"shape": (128, 128, 5, 2)})()

    monkeypatch.setattr(
        server, "load_scrubbed_dicom", lambda path: fake_dataset
    )
    monkeypatch.setattr(
        server, "pixel_array_as_volume", lambda dataset: fake_volume
    )

    def fake_render(path, frame_index, timepoint):
        assert frame_index == 4
        assert timepoint == 1
        return b"\x89PNG\r\n\x1a\nframe-bytes"

    monkeypatch.setattr(
        server, "render_representative_frame_png", fake_render
    )
    result = call(
        "render_dicom_frame_preview",
        file_path=str(fixture),
        frame_index=4,
        timepoint=1,
    )
    assert result["rendered_frame_index"] == 4
    assert result["rendered_timepoint"] == 1


def test_search_tenant_evidence_embeds_and_queries(monkeypatch):
    captured = {}

    async def fake_embed_text(query):
        captured["query"] = query
        return [0.1, 0.2]

    def fake_hybrid_query(tenant_id, text_query, vector, size):
        captured["tenant_id"] = tenant_id
        captured["text_query"] = text_query
        captured["vector"] = vector
        captured["size"] = size
        return {"hits": {"hits": [{"_source": {"text": "real evidence"}}]}}

    monkeypatch.setattr(server, "embed_text", fake_embed_text)
    monkeypatch.setattr(server, "tenant_hybrid_query", fake_hybrid_query)
    result = call(
        "search_tenant_evidence",
        tenant_id="lab-one",
        query="organoid",
        size=3,
    )
    assert result == {"hits": [{"text": "real evidence"}]}
    assert captured == {
        "query": "organoid",
        "tenant_id": "lab-one",
        "text_query": "organoid",
        "vector": [0.1, 0.2],
        "size": 3,
    }


class FakeHTTPResponse:
    def __init__(self, body: dict):
        self._body = json.dumps(body).encode()

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def fake_urlopen_capturing(captured: dict, response_body: dict):
    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["body"] = json.loads(req.data) if req.data else None
        captured["headers"] = dict(req.header_items())
        return FakeHTTPResponse(response_body)

    return fake_urlopen


def test_list_live_viewer_sessions_sends_a_real_authenticated_get(
    monkeypatch,
):
    captured: dict = {}
    monkeypatch.setattr(
        server.urllib.request,
        "urlopen",
        fake_urlopen_capturing(captured, {"sessions": []}),
    )
    result = call(
        "list_live_viewer_sessions",
        coordinator_url="http://127.0.0.1:8092",
        access_token="real-token",
    )
    assert result == {"sessions": []}
    assert (
        captured["url"] == "http://127.0.0.1:8092/api/studio/live-sessions"
    )
    assert captured["method"] == "GET"
    assert captured["headers"]["Authorization"] == "Bearer real-token"


def test_live_tool_falls_back_to_the_real_env_token_when_omitted(
    monkeypatch,
):
    """Confirmed directly against a real deployed coordinator: an LLM
    asked to retype a long bearer token as a tool argument can silently
    corrupt it. The real fix is never asking it to - this falls back to
    STUDIO_ACCESS_TOKEN so the agent only ever has to pass a short
    session_id and coordinator_url.
    """
    captured: dict = {}
    monkeypatch.setattr(
        server.urllib.request,
        "urlopen",
        fake_urlopen_capturing(captured, {"sessions": []}),
    )
    monkeypatch.setenv("STUDIO_ACCESS_TOKEN", "real-env-token")
    result = call(
        "list_live_viewer_sessions", coordinator_url="http://127.0.0.1:8092"
    )
    assert result == {"sessions": []}
    assert captured["headers"]["Authorization"] == "Bearer real-env-token"


def test_live_tool_prefers_the_real_env_token_over_an_explicit_one(
    monkeypatch,
):
    captured: dict = {}
    monkeypatch.setattr(
        server.urllib.request,
        "urlopen",
        fake_urlopen_capturing(captured, {"sessions": []}),
    )
    monkeypatch.setenv("STUDIO_ACCESS_TOKEN", "real-env-token")
    call(
        "list_live_viewer_sessions",
        coordinator_url="http://127.0.0.1:8092",
        access_token="a-possibly-corrupted-token",
    )
    assert captured["headers"]["Authorization"] == "Bearer real-env-token"


def test_live_tool_raises_a_graceful_error_with_no_token_available(
    monkeypatch,
):
    monkeypatch.delenv("STUDIO_ACCESS_TOKEN", raising=False)
    with pytest.raises(ToolError, match="STUDIO_ACCESS_TOKEN is not set"):
        call(
            "list_live_viewer_sessions",
            coordinator_url="http://127.0.0.1:8092",
        )


def test_get_live_viewer_state_sends_a_real_authenticated_get(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        server.urllib.request,
        "urlopen",
        fake_urlopen_capturing(
            captured,
            {"state": {"window": 500, "level": 100}, "reported_at": 123.0},
        ),
    )
    result = call(
        "get_live_viewer_state",
        coordinator_url="http://127.0.0.1:8092",
        access_token="real-token",
        session_id="session-1",
    )
    assert result == {
        "state": {"window": 500, "level": 100},
        "reported_at": 123.0,
    }
    assert captured["url"] == (
        "http://127.0.0.1:8092/api/studio/live-sessions/session-1/state"
    )
    assert captured["method"] == "GET"


def test_set_live_window_level_sends_the_real_action_and_params(
    monkeypatch,
):
    captured: dict = {}
    monkeypatch.setattr(
        server.urllib.request,
        "urlopen",
        fake_urlopen_capturing(captured, {"status": "sent"}),
    )
    result = call(
        "set_live_window_level",
        coordinator_url="http://127.0.0.1:8092",
        access_token="real-token",
        session_id="session-1",
        window=500,
        level=100,
    )
    assert result == {"status": "sent"}
    assert captured["url"] == (
        "http://127.0.0.1:8092/api/studio/live-sessions/session-1/commands"
    )
    assert captured["method"] == "POST"
    assert captured["body"] == {
        "action": "set_window_level",
        "params": {"window": 500, "level": 100},
    }


def test_set_live_channel_state_omits_real_unset_parameters(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        server.urllib.request,
        "urlopen",
        fake_urlopen_capturing(captured, {"status": "sent"}),
    )
    call(
        "set_live_channel_state",
        coordinator_url="http://127.0.0.1:8092",
        access_token="real-token",
        session_id="session-1",
        channel_index=1,
        visible=False,
    )
    assert captured["body"] == {
        "action": "set_channel_state",
        "params": {"channel_index": 1, "visible": False},
    }


def test_set_live_detection_display_omits_real_unset_parameters(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        server.urllib.request,
        "urlopen",
        fake_urlopen_capturing(captured, {"status": "sent"}),
    )
    call(
        "set_live_detection_display",
        coordinator_url="http://127.0.0.1:8092",
        access_token="real-token",
        session_id="session-1",
        confidence_threshold=0.5,
    )
    assert captured["body"] == {
        "action": "set_detection_display",
        "params": {"confidence_threshold": 0.5},
    }


def test_set_live_segmentation_mask_visible_sends_the_real_action(
    monkeypatch,
):
    captured: dict = {}
    monkeypatch.setattr(
        server.urllib.request,
        "urlopen",
        fake_urlopen_capturing(captured, {"status": "sent"}),
    )
    call(
        "set_live_segmentation_mask_visible",
        coordinator_url="http://127.0.0.1:8092",
        access_token="real-token",
        session_id="session-1",
        visible=True,
        nuclear_channel_index=1,
    )
    assert captured["body"] == {
        "action": "set_segmentation_mask_visible",
        "params": {"visible": True, "nuclear_channel_index": 1},
    }


def test_live_session_request_converts_a_real_http_error_to_a_tool_error(
    monkeypatch,
):
    import urllib.error

    def fake_urlopen(req, timeout=None):
        raise urllib.error.HTTPError(
            req.full_url,
            404,
            "not found",
            {},
            __import__("io").BytesIO(b'{"detail": "no such session"}'),
        )

    monkeypatch.setattr(server.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ToolError, match="live viewer request failed"):
        asyncio.run(
            server.mcp.call_tool(
                "snap_live_camera_axis",
                {
                    "coordinator_url": "http://127.0.0.1:8092",
                    "access_token": "real-token",
                    "session_id": "no-such-session",
                    "axis": "+X",
                },
            )
        )

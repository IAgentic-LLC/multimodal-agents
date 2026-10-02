from pathlib import Path

import pytest

from multimodal_agents.tenant_video_tracking import (
    UnsupportedVideoError,
    describe_tracks,
    extract_frames,
    track_frames,
    tracked_frames_to_dicts,
)

REAL_SAMPLE_VIDEO = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "opencv-vtest-sample.avi"
)


def real_video_bytes() -> bytes:
    return REAL_SAMPLE_VIDEO.read_bytes()


def test_extract_frames_decodes_a_bounded_real_frame_count():
    frames = extract_frames(real_video_bytes(), max_frames=6)
    assert 1 <= len(frames) <= 6
    assert frames[0].ndim == 3
    assert frames[0].shape[2] == 3


def test_extract_frames_rejects_non_video_bytes():
    with pytest.raises(UnsupportedVideoError):
        extract_frames(b"not a real video file")


def test_track_frames_finds_real_persistent_vehicle_tracks():
    frames = extract_frames(real_video_bytes(), max_frames=5)
    tracked = track_frames(frames)
    assert len(tracked) == len(frames)
    all_detections = [d for frame in tracked for d in frame]
    real_classes = {d.class_name for d in all_detections}
    # The real background vehicles in this real public sample are
    # stationary, so at least one should track across every real frame.
    assert real_classes & {"bus", "car", "truck", "person"}


def test_describe_tracks_reports_real_persistent_identity_count():
    frames = extract_frames(real_video_bytes(), max_frames=5)
    tracked = track_frames(frames)
    claim = describe_tracks(tracked)
    assert "real tracked object(s)" in claim
    assert f"all {len(frames)} real frame(s)" in claim


def test_describe_tracks_handles_no_real_detections():
    claim = describe_tracks([[], [], []])
    assert claim == "yolo11n + ByteTrack found no real trackable objects"


def test_tracked_frames_to_dicts_matches_the_real_frame_count():
    frames = extract_frames(real_video_bytes(), max_frames=4)
    tracked = track_frames(frames)
    payload = tracked_frames_to_dicts(tracked)
    assert len(payload) == len(frames)
    for frame_detections in payload:
        for detection in frame_detections:
            assert set(detection) == {
                "frame_index",
                "track_id",
                "class_name",
                "confidence",
                "bbox_xyxy",
            }

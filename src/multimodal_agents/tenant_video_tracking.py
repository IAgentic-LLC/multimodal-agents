"""Real multi-frame object tracking against a researcher's own uploaded
video file, reusing the exact same real yolo11n + ByteTrack pipeline
chapter 9's video_detection_tracking.py already proves
(model.track(..., persist=True, tracker="bytetrack.yaml")), extended to
a real decoded video file's own real frames instead of only a
synthetic pan of one bundled photo.

A fresh YOLO model instance per real tracking call, not the shared
singleton tenant_detection.py uses for plain per-image detection:
persist=True keeps real internal track-identity state on the model
instance itself between calls, which must never leak between two
different real uploads sharing one process-wide model. chapter 9's own
run_video_tracking() makes the same real choice for the same real
reason.
"""

from __future__ import annotations

import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

MAX_FRAMES = 30


class UnsupportedVideoError(ValueError):
    pass


@dataclass(frozen=True)
class TrackedDetection:
    frame_index: int
    track_id: int
    class_name: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]


def extract_frames(
    video_bytes: bytes, max_frames: int = MAX_FRAMES
) -> list[np.ndarray]:
    """Decodes a real uploaded video file's real frames via cv2's own
    VideoCapture, bounded to max_frames real, evenly-spaced frames
    rather than every frame, so a real upload's analysis time stays
    bounded regardless of the real video's own length.
    """
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as handle:
        handle.write(video_bytes)
        temp_path = handle.name
    try:
        capture = cv2.VideoCapture(temp_path)
        if not capture.isOpened():
            raise UnsupportedVideoError(
                "could not open this as a real video file"
            )
        total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if total <= 0:
            capture.release()
            raise UnsupportedVideoError(
                "real video file reports zero real frames"
            )
        frames: list[np.ndarray] = []
        step = max(total // max_frames, 1)
        for frame_index in range(0, total, step):
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame_bgr = capture.read()
            if not ok:
                continue
            frames.append(cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
            if len(frames) >= max_frames:
                break
        capture.release()
    finally:
        Path(temp_path).unlink(missing_ok=True)
    if not frames:
        raise UnsupportedVideoError(
            "could not decode any real frames from this video"
        )
    return frames


def track_frames(frames: list[np.ndarray]) -> list[list[TrackedDetection]]:
    """Real per-frame tracked detections via model.track(...,
    persist=True), the exact same real tracking call
    run_video_tracking() already proves against a synthetic pan;
    this runs it against real decoded video frames instead.
    """
    model = YOLO("yolo11n.pt")
    tracked_frames: list[list[TrackedDetection]] = []
    for frame_index, frame in enumerate(frames):
        result = model.track(
            frame, persist=True, verbose=False, tracker="bytetrack.yaml"
        )[0]
        frame_detections: list[TrackedDetection] = []
        if result.boxes.id is not None:
            for box, track_id in zip(
                result.boxes, result.boxes.id, strict=True
            ):
                class_id = int(box.cls)
                xyxy = tuple(
                    round(float(v), 1) for v in box.xyxy[0].tolist()
                )
                frame_detections.append(
                    TrackedDetection(
                        frame_index=frame_index,
                        track_id=int(track_id),
                        class_name=model.names[class_id],
                        confidence=round(float(box.conf), 3),
                        bbox_xyxy=xyxy,  # type: ignore[arg-type]
                    )
                )
        tracked_frames.append(frame_detections)
    return tracked_frames


def describe_tracks(tracked_frames: list[list[TrackedDetection]]) -> str:
    all_detections = [d for frame in tracked_frames for d in frame]
    track_ids = {d.track_id for d in all_detections}
    if not track_ids:
        return "yolo11n + ByteTrack found no real trackable objects"
    persistent = {
        tid
        for tid in track_ids
        if len(
            {d.frame_index for d in all_detections if d.track_id == tid}
        )
        == len(tracked_frames)
    }
    return (
        f"{len(persistent)} of {len(track_ids)} real tracked object(s) "
        f"hold the same identity across all {len(tracked_frames)} "
        f"real frame(s)"
    )


def tracked_frames_to_dicts(
    tracked_frames: list[list[TrackedDetection]],
) -> list[list[dict[str, object]]]:
    return [[asdict(d) for d in frame] for frame in tracked_frames]

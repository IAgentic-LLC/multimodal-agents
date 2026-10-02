"""Evidence-first detection and multi-frame tracking over real video frames.

YOLO proposes a bounded claim (object class, confidence, pixel region) per
frame. ByteTrack, bundled with ultralytics, links those claims into a
persistent identity across frames using motion and appearance continuity,
not a fresh guess every frame. The retained sequence here is a real panning
crop of one bundled sample photograph, which keeps the demonstration small
while still exercising the real detector and the real tracker end to end.
Production use points the same call at an actual video file or stream.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from ultralytics import YOLO
from ultralytics.utils import ASSETS


@dataclass(frozen=True)
class TrackedDetection:
    frame_index: int
    track_id: int
    class_name: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]


@dataclass(frozen=True)
class TrackingEvidence:
    capability: str
    status: str
    claim: str
    evidence_ids: tuple[str, ...]
    source: str
    model: str
    detections: tuple[TrackedDetection, ...]


def pan_frames(image: np.ndarray, num_frames: int, step: int, crop_margin: int = 40) -> list[np.ndarray]:
    height, width = image.shape[:2]
    frames = []
    for index in range(num_frames):
        shift = min(index * step, width - crop_margin)
        frame = image[:, shift : shift + width - crop_margin, :]
        frames.append(frame)
    return frames


def run_video_tracking(num_frames: int = 5, step: int = 8) -> TrackingEvidence:
    source_path = ASSETS / "bus.jpg"
    image = np.array(Image.open(source_path))
    frames = pan_frames(image, num_frames=num_frames, step=step)

    model = YOLO("yolo11n.pt")
    detections: list[TrackedDetection] = []
    track_ids: set[int] = set()
    for frame_index, frame in enumerate(frames):
        result = model.track(frame, persist=True, verbose=False, tracker="bytetrack.yaml")[0]
        if result.boxes.id is None:
            continue
        for box, track_id in zip(result.boxes, result.boxes.id, strict=True):
            class_id = int(box.cls)
            tid = int(track_id)
            track_ids.add(tid)
            xyxy = tuple(round(float(v), 1) for v in box.xyxy[0].tolist())
            detections.append(
                TrackedDetection(
                    frame_index=frame_index,
                    track_id=tid,
                    class_name=model.names[class_id],
                    confidence=round(float(box.conf), 3),
                    bbox_xyxy=xyxy,  # type: ignore[arg-type]
                )
            )

    persistent = {
        tid
        for tid in track_ids
        if len({d.frame_index for d in detections if d.track_id == tid}) == len(frames)
    }
    claim = (
        f"{len(persistent)} of {len(track_ids)} tracked objects hold the same identity "
        f"across all {len(frames)} frames"
    )
    return TrackingEvidence(
        capability="video-detection-tracking",
        status="completed",
        claim=claim,
        evidence_ids=tuple(f"track-{tid}" for tid in sorted(persistent)),
        source=f"ultralytics bundled sample asset: {source_path.name}",
        model="yolo11n + bytetrack",
        detections=tuple(detections),
    )


def evidence_to_dict(evidence: TrackingEvidence) -> dict[str, object]:
    payload = asdict(evidence)
    payload["detections"] = [asdict(d) for d in evidence.detections]
    return payload

"""Real object detection against a researcher's own uploaded image,
reusing the same real yolo11n model chapter 9's video-tracking path
already proves, not a new or weaker one. Detection only, since a single
uploaded image has no second frame to track identity across; a real
multi-frame or volumetric upload would extend this, not replace it.
"""

from __future__ import annotations

import io
import threading
from dataclasses import asdict, dataclass

import numpy as np
from PIL import Image
from ultralytics import YOLO

_model: YOLO | None = None
_model_lock = threading.Lock()


def _load_model() -> YOLO:
    global _model
    with _model_lock:
        if _model is None:
            _model = YOLO("yolo11n.pt")
        return _model


@dataclass(frozen=True)
class DetectedObject:
    class_name: str
    confidence: float
    bbox_xyxy: tuple[float, float, float, float]


def detect_objects(image_bytes: bytes) -> list[DetectedObject]:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    array = np.array(image)
    model = _load_model()
    result = model.predict(array, verbose=False)[0]
    detections: list[DetectedObject] = []
    for box in result.boxes:
        class_id = int(box.cls)
        xyxy = tuple(round(float(v), 1) for v in box.xyxy[0].tolist())
        detections.append(
            DetectedObject(
                class_name=model.names[class_id],
                confidence=round(float(box.conf), 3),
                bbox_xyxy=xyxy,  # type: ignore[arg-type]
            )
        )
    return detections


def describe_detections(detections: list[DetectedObject]) -> str:
    if not detections:
        return "yolo11n found no objects above its default confidence threshold"
    counts: dict[str, int] = {}
    for detection in detections:
        counts[detection.class_name] = counts.get(detection.class_name, 0) + 1
    parts = [f"{count} {name}" for name, count in sorted(counts.items())]
    return f"yolo11n detected {', '.join(parts)}"


def detections_to_dicts(detections: list[DetectedObject]) -> list[dict[str, object]]:
    return [asdict(detection) for detection in detections]

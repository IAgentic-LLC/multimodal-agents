"""Validation and persistence for consented browser capture sessions."""

from __future__ import annotations

import base64
import binascii
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")
JPEG_PREFIX = "data:image/jpeg;base64,"


@dataclass(frozen=True)
class CapturePaths:
    session: Path
    frame: Path
    audio: Path
    manifest: Path


def safe_id(value: str, field: str) -> str:
    if not SAFE_ID.fullmatch(value):
        raise ValueError(f"{field} contains unsupported characters")
    return value


def decode_jpeg(data_url: str) -> bytes:
    if not data_url.startswith(JPEG_PREFIX):
        raise ValueError("frame must be a JPEG data URL")
    try:
        payload = base64.b64decode(
            data_url.removeprefix(JPEG_PREFIX),
            validate=True,
        )
    except (binascii.Error, ValueError) as error:
        raise ValueError("frame contains invalid base64") from error
    if not payload.startswith(b"\xff\xd8"):
        raise ValueError("frame is not a JPEG")
    return payload


def capture_paths(root: Path, session_id: str, capture_id: str) -> CapturePaths:
    session = root / safe_id(session_id, "session_id")
    stem = safe_id(capture_id, "capture_id")
    return CapturePaths(
        session=session,
        frame=session / "frames" / f"{stem}.jpg",
        audio=session / "audio" / f"{stem}.webm",
        manifest=session / "events.jsonl",
    )


def persist_capture(
    root: Path,
    metadata: dict[str, Any],
    frame_data_url: str,
    audio: bytes,
) -> CapturePaths:
    paths = capture_paths(
        root,
        str(metadata["session_id"]),
        str(metadata["capture_id"]),
    )
    frame = decode_jpeg(frame_data_url)
    if not audio:
        raise ValueError("audio must not be empty")
    if len(frame) > 10_000_000 or len(audio) > 20_000_000:
        raise ValueError("capture exceeds the local size limit")

    paths.frame.parent.mkdir(parents=True, exist_ok=True)
    paths.audio.parent.mkdir(parents=True, exist_ok=True)
    paths.frame.write_bytes(frame)
    paths.audio.write_bytes(audio)

    event = {
        **metadata,
        "frame_asset": paths.frame.relative_to(root).as_posix(),
        "audio_asset": paths.audio.relative_to(root).as_posix(),
    }
    with paths.manifest.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
    return paths

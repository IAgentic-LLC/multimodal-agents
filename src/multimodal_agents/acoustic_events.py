import math
import struct
import wave
from pathlib import Path


def make_fixture(path: Path, rate: int = 16000) -> dict:
    duration = 3.0
    samples = []
    for index in range(int(rate * duration)):
        time = index / rate
        value = 0.0
        if 0.8 <= time < 1.4:
            value += 0.55 * math.sin(2 * math.pi * 1000 * time)
        if 2.0 <= time < 2.03:
            value += 0.85 * math.exp(-90 * (time - 2.0))
        samples.append(max(-1.0, min(1.0, value)))
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(b"".join(
            struct.pack("<h", round(sample * 32767)) for sample in samples
        ))
    return {
        "rate_hz": rate,
        "duration_s": duration,
        "events": [
            {"label": "alarm_tone", "onset_s": 0.8, "offset_s": 1.4},
            {"label": "knock", "onset_s": 2.0, "offset_s": 2.03},
        ],
    }


def frame_rms(samples: list[float]) -> float:
    return math.sqrt(sum(value * value for value in samples) / len(samples))


def detect_energy(
    samples: list[float],
    rate: int,
    frame_ms: int = 20,
    threshold: float = 0.08,
) -> list[tuple[float, float]]:
    size = rate * frame_ms // 1000
    active = [
        frame_rms(samples[start:start + size]) >= threshold
        for start in range(0, len(samples), size)
        if len(samples[start:start + size]) == size
    ]
    intervals = []
    start = None
    for index, value in enumerate(active + [False]):
        if value and start is None:
            start = index
        elif not value and start is not None:
            intervals.append((start * frame_ms / 1000, index * frame_ms / 1000))
            start = None
    return intervals


def read_wav(path: Path) -> tuple[int, list[float]]:
    with wave.open(str(path), "rb") as source:
        rate = source.getframerate()
        frames = source.readframes(source.getnframes())
    values = struct.unpack(f"<{len(frames) // 2}h", frames)
    return rate, [value / 32768 for value in values]

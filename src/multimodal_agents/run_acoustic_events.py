import json
from pathlib import Path

from multimodal_agents.acoustic_events import detect_energy, make_fixture, read_wav


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    audio_path = root / "fixtures" / "acoustic-events.wav"
    artifact_path = root / "runs" / "gate-23" / "acoustic-event-results.json"
    truth = make_fixture(audio_path)
    rate, samples = read_wav(audio_path)
    detected = detect_energy(samples, rate)
    rows = []
    for expected, actual in zip(truth["events"], detected, strict=True):
        rows.append({
            "label": expected["label"],
            "truth": {
                "onset_s": expected["onset_s"],
                "offset_s": expected["offset_s"],
            },
            "detected": {"onset_s": actual[0], "offset_s": actual[1]},
            "onset_error_ms": round(
                (actual[0] - expected["onset_s"]) * 1000,
            ),
            "offset_error_ms": round(
                (actual[1] - expected["offset_s"]) * 1000,
            ),
        })
    result = {
        "fixture": str(audio_path.relative_to(root)).replace("\\", "/"),
        "sample_rate_hz": rate,
        "frame_ms": 20,
        "threshold_rms": 0.08,
        "events": rows,
        "false_positives": max(0, len(detected) - len(rows)),
        "missed_events": max(0, len(truth["events"]) - len(rows)),
    }
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

from multimodal_agents.acoustic_events import detect_energy, make_fixture, read_wav


def test_fixture_and_detector_localize_two_non_speech_events(tmp_path):
    path = tmp_path / "events.wav"
    truth = make_fixture(path)
    rate, samples = read_wav(path)
    detected = detect_energy(samples, rate)
    assert truth["events"][0]["label"] == "alarm_tone"
    assert detected == [(0.8, 1.4), (2.0, 2.02)]


def test_silence_produces_no_events():
    assert detect_energy([0.0] * 16000, 16000) == []

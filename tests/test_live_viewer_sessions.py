import asyncio
import json

import pytest

import multimodal_agents.live_viewer_sessions as live_viewer_sessions
from multimodal_agents.live_viewer_sessions import (
    InvalidLiveCommandError,
    RateLimitExceededError,
    UnknownLiveSessionError,
    get_state,
    list_sessions,
    push_command,
    register_session,
    report_state,
    session_queue,
    unregister_session,
    validate_command,
)


@pytest.fixture(autouse=True)
def _clear_global_session_registry():
    """Other test modules register real sessions in the same process-wide
    registry and do not all clean up; this file's own assertions assume a
    registry scoped to just what each test registers.
    """
    live_viewer_sessions._sessions.clear()
    yield
    live_viewer_sessions._sessions.clear()


def test_register_session_returns_a_real_unique_session_id():
    first = register_session("lab-one", "volume")
    second = register_session("lab-one", "volume")
    assert first.session_id != second.session_id
    unregister_session(first.session_id)
    unregister_session(second.session_id)


def test_list_sessions_is_scoped_to_the_real_tenant():
    one = register_session("lab-one", "volume")
    two = register_session("lab-two", "channel_volume")
    try:
        lab_one_sessions = list_sessions("lab-one")
        assert [s["session_id"] for s in lab_one_sessions] == [one.session_id]
        assert lab_one_sessions[0]["viewer_type"] == "volume"
        lab_two_sessions = list_sessions("lab-two")
        assert [s["session_id"] for s in lab_two_sessions] == [two.session_id]
    finally:
        unregister_session(one.session_id)
        unregister_session(two.session_id)


def test_push_command_delivers_to_the_real_sessions_own_queue():
    session = register_session("lab-one", "volume")
    try:
        asyncio.run(
            push_command(
                session.session_id,
                "lab-one",
                "set_window_level",
                {"window": 10, "level": 5},
            )
        )
        queue = session_queue(session.session_id, "lab-one")
        delivered = queue.get_nowait()
        assert delivered == {
            "action": "set_window_level",
            "params": {"window": 10, "level": 5},
        }
    finally:
        unregister_session(session.session_id)


def test_push_command_rejects_a_caller_from_a_different_tenant():
    session = register_session("lab-one", "volume")
    try:
        with pytest.raises(UnknownLiveSessionError):
            asyncio.run(
                push_command(
                    session.session_id, "lab-two", "set_window_level", {}
                )
            )
    finally:
        unregister_session(session.session_id)


def test_push_command_rejects_an_unknown_session_id():
    with pytest.raises(UnknownLiveSessionError):
        asyncio.run(
            push_command(
                "no-such-session", "lab-one", "set_window_level", {}
            )
        )


def test_session_queue_rejects_a_caller_from_a_different_tenant():
    session = register_session("lab-one", "volume")
    try:
        with pytest.raises(UnknownLiveSessionError):
            session_queue(session.session_id, "lab-two")
    finally:
        unregister_session(session.session_id)


def test_unregister_session_is_idempotent_and_makes_the_session_disappear():
    session = register_session("lab-one", "volume")
    unregister_session(session.session_id)
    unregister_session(session.session_id)  # must not raise
    assert list_sessions("lab-one") == []


# --- Validation ---------------------------------------------------------


def test_validate_command_rejects_an_unknown_action():
    with pytest.raises(
        InvalidLiveCommandError, match="unknown live command action"
    ):
        validate_command("delete_everything", {})


def test_validate_command_rejects_a_missing_required_parameter():
    with pytest.raises(
        InvalidLiveCommandError, match="missing required parameter"
    ):
        validate_command("set_window_level", {"window": 10})


def test_validate_command_rejects_an_unknown_parameter():
    with pytest.raises(InvalidLiveCommandError, match="unknown parameter"):
        validate_command("set_timepoint", {"timepoint": 1, "extra": "nope"})


def test_validate_command_rejects_the_wrong_type():
    with pytest.raises(InvalidLiveCommandError, match="must be"):
        validate_command("set_timepoint", {"timepoint": "not a real int"})


def test_validate_command_rejects_a_bool_where_a_real_number_is_required():
    """bool is a real subclass of int in Python: True would otherwise
    silently pass a naive isinstance(value, (int, float)) check.
    """
    with pytest.raises(
        InvalidLiveCommandError, match="must be a real number"
    ):
        validate_command("set_window_level", {"window": True, "level": 5})


def test_validate_command_rejects_a_real_unrecognized_axis():
    with pytest.raises(InvalidLiveCommandError, match="not a real axis"):
        validate_command("snap_axis", {"axis": "+Q"})


def test_validate_command_accepts_every_real_axis():
    for axis in ["+X", "-X", "+Y", "-Y", "+Z", "-Z"]:
        validate_command("snap_axis", {"axis": axis})  # must not raise


def test_validate_command_rejects_a_real_unrecognized_colormap():
    with pytest.raises(InvalidLiveCommandError, match="not a real colormap"):
        validate_command("set_colormap", {"name": "Not A Real Colormap"})


def test_validate_command_rejects_an_invalid_auto_rotate_direction():
    with pytest.raises(InvalidLiveCommandError, match="direction must be"):
        validate_command("set_auto_rotate", {"enabled": True, "direction": 7})


def test_validate_command_accepts_optional_params_being_omitted():
    # direction omitted: fine
    validate_command("set_auto_rotate", {"enabled": True})
    # all else omitted: fine
    validate_command("set_channel_state", {"channel_index": 0})


def test_validate_command_accepts_a_real_filter_pipeline():
    validate_command(
        "apply_filter_pipeline",
        {
            "steps": [{"filter": "gaussian_blur", "params": {"sigma": 1.0}}],
            "channel_index": 1,
            "timepoint": 0,
        },
    )


def test_validate_command_rejects_an_empty_filter_pipeline():
    with pytest.raises(InvalidLiveCommandError, match="must not be empty"):
        validate_command("apply_filter_pipeline", {"steps": []})


def test_validate_command_rejects_a_filter_step_missing_a_filter_name():
    with pytest.raises(InvalidLiveCommandError, match="real string 'filter'"):
        validate_command(
            "apply_filter_pipeline", {"steps": [{"params": {"sigma": 1.0}}]}
        )


def test_validate_command_rejects_a_non_dict_filter_step():
    with pytest.raises(InvalidLiveCommandError, match="real string 'filter'"):
        validate_command(
            "apply_filter_pipeline", {"steps": ["gaussian_blur"]}
        )


def test_validate_command_accepts_a_real_detection_display_update():
    validate_command(
        "set_detection_display",
        {"confidence_threshold": 0.5, "boxes_visible": True},
    )


def test_validate_command_accepts_an_empty_detection_display_update():
    validate_command("set_detection_display", {})


def test_validate_command_rejects_an_out_of_range_confidence_threshold():
    with pytest.raises(InvalidLiveCommandError, match="between 0.0 and 1.0"):
        validate_command(
            "set_detection_display", {"confidence_threshold": 1.5}
        )


def test_validate_command_accepts_a_real_segmentation_mask_toggle():
    validate_command(
        "set_segmentation_mask_visible",
        {"visible": True, "nuclear_channel_index": 1},
    )


def test_validate_command_rejects_a_missing_visible_for_mask_toggle():
    with pytest.raises(InvalidLiveCommandError, match="missing required"):
        validate_command(
            "set_segmentation_mask_visible", {"nuclear_channel_index": 1}
        )


def test_validate_command_accepts_a_real_track_display_update():
    validate_command(
        "set_track_display",
        {
            "confidence_threshold": 0.4,
            "highlighted_track_id": 4,
            "frame_index": 2,
        },
    )


def test_validate_command_accepts_an_empty_track_display_update():
    validate_command("set_track_display", {})


def test_validate_command_rejects_an_out_of_range_track_confidence():
    with pytest.raises(InvalidLiveCommandError, match="between 0.0 and 1.0"):
        validate_command("set_track_display", {"confidence_threshold": -0.1})


def test_push_command_rejects_an_invalid_command_before_queuing(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        live_viewer_sessions, "AUDIT_LOG_PATH", tmp_path / "audit.jsonl"
    )
    session = register_session("lab-one", "volume")
    try:
        with pytest.raises(InvalidLiveCommandError):
            asyncio.run(
                push_command(
                    session.session_id,
                    "lab-one",
                    "set_timepoint",
                    {"timepoint": "nope"},
                )
            )
        queue = session_queue(session.session_id, "lab-one")
        assert queue.empty()
        # a rejected command is never logged as sent
        assert not (tmp_path / "audit.jsonl").exists()
    finally:
        unregister_session(session.session_id)


# --- Rate limiting -------------------------------------------------------


def test_push_command_enforces_a_real_per_session_rate_limit(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        live_viewer_sessions, "AUDIT_LOG_PATH", tmp_path / "audit.jsonl"
    )
    monkeypatch.setattr(live_viewer_sessions, "RATE_LIMIT_MAX_COMMANDS", 3)
    session = register_session("lab-one", "volume")
    try:
        for _ in range(3):
            asyncio.run(
                push_command(
                    session.session_id,
                    "lab-one",
                    "set_timepoint",
                    {"timepoint": 1},
                )
            )
        with pytest.raises(RateLimitExceededError):
            asyncio.run(
                push_command(
                    session.session_id,
                    "lab-one",
                    "set_timepoint",
                    {"timepoint": 1},
                )
            )
    finally:
        unregister_session(session.session_id)


def test_rate_limit_window_is_scoped_to_its_own_real_session(
    monkeypatch, tmp_path
):
    """A burst against one session must not throttle a different real
    session, even for the same tenant.
    """
    monkeypatch.setattr(
        live_viewer_sessions, "AUDIT_LOG_PATH", tmp_path / "audit.jsonl"
    )
    monkeypatch.setattr(live_viewer_sessions, "RATE_LIMIT_MAX_COMMANDS", 1)
    busy = register_session("lab-one", "volume")
    quiet = register_session("lab-one", "volume")
    try:
        asyncio.run(
            push_command(
                busy.session_id, "lab-one", "set_timepoint", {"timepoint": 1}
            )
        )
        with pytest.raises(RateLimitExceededError):
            asyncio.run(
                push_command(
                    busy.session_id,
                    "lab-one",
                    "set_timepoint",
                    {"timepoint": 1},
                )
            )
        # must not raise: a different session, same tenant
        asyncio.run(
            push_command(
                quiet.session_id,
                "lab-one",
                "set_timepoint",
                {"timepoint": 1},
            )
        )
    finally:
        unregister_session(busy.session_id)
        unregister_session(quiet.session_id)


# --- Audit log -------------------------------------------------------------


def test_push_command_appends_a_real_audit_entry(monkeypatch, tmp_path):
    log_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(live_viewer_sessions, "AUDIT_LOG_PATH", log_path)
    session = register_session("lab-one", "volume")
    try:
        asyncio.run(
            push_command(
                session.session_id,
                "lab-one",
                "set_timepoint",
                {"timepoint": 2},
                subject="agent-session-1",
            )
        )
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["tenant_id"] == "lab-one"
        assert entry["session_id"] == session.session_id
        assert entry["viewer_type"] == "volume"
        assert entry["action"] == "set_timepoint"
        assert entry["params"] == {"timepoint": 2}
        assert entry["subject"] == "agent-session-1"
        assert "recorded_at" in entry
    finally:
        unregister_session(session.session_id)


def test_push_command_appends_one_real_line_per_real_command(
    monkeypatch, tmp_path
):
    log_path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(live_viewer_sessions, "AUDIT_LOG_PATH", log_path)
    session = register_session("lab-one", "volume")
    try:
        asyncio.run(
            push_command(
                session.session_id,
                "lab-one",
                "set_timepoint",
                {"timepoint": 1},
            )
        )
        asyncio.run(
            push_command(
                session.session_id,
                "lab-one",
                "set_timepoint",
                {"timepoint": 2},
            )
        )
        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
    finally:
        unregister_session(session.session_id)


# --- State readback (self-correction) --------------------------------------


def test_report_state_and_get_state_round_trip_a_real_snapshot():
    session = register_session("lab-one", "volume")
    try:
        report_state(
            session.session_id, "lab-one", {"window": 500, "level": 100}
        )
        result = get_state(session.session_id, "lab-one")
        assert result["state"] == {"window": 500, "level": 100}
        assert result["reported_at"] is not None
    finally:
        unregister_session(session.session_id)


def test_get_state_before_any_report_returns_a_real_empty_state():
    session = register_session("lab-one", "volume")
    try:
        result = get_state(session.session_id, "lab-one")
        assert result == {"state": {}, "reported_at": None}
    finally:
        unregister_session(session.session_id)


def test_report_state_rejects_a_caller_from_a_different_tenant():
    session = register_session("lab-one", "volume")
    try:
        with pytest.raises(UnknownLiveSessionError):
            report_state(session.session_id, "lab-two", {"window": 1})
    finally:
        unregister_session(session.session_id)


def test_get_state_rejects_a_caller_from_a_different_tenant():
    session = register_session("lab-one", "volume")
    try:
        with pytest.raises(UnknownLiveSessionError):
            get_state(session.session_id, "lab-two")
    finally:
        unregister_session(session.session_id)

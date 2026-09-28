import pytest

from multimodal_agents.failure_injection import (
    FailureCase,
    exercise,
    run_suite,
    suite,
)


def test_all_seeded_failures_are_detected_and_safe():
    result = run_suite(suite())
    assert result["passed_count"] == 5
    assert result["protected_violations"] == 0


@pytest.mark.parametrize("case", suite())
def test_each_failure_has_explicit_expected_outcome(case):
    assert exercise(case)["passed"] is True


def test_unknown_failure_kind_is_rejected():
    with pytest.raises(ValueError):
        exercise(FailureCase("bad", "unknown", {}, "blocked"))


def test_unsafe_injection_path_is_counted_as_protected_violation():
    unsafe = FailureCase(
        "unsafe",
        "indirect_injection",
        {"content_trust": "trusted"},
        "blocked",
    )
    result = run_suite([unsafe])
    assert result["passed_count"] == 0
    assert result["protected_violations"] == 1

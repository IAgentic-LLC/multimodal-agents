from dataclasses import dataclass


@dataclass(frozen=True)
class FailureCase:
    case_id: str
    kind: str
    signal: dict
    expected: str


def exercise(case: FailureCase) -> dict:
    signal = case.signal
    if case.kind == "stale_evidence":
        stale = signal["age_ms"] > signal["max_age_ms"]
        outcome = "blocked" if stale else "allowed"
    elif case.kind == "occlusion":
        outcome = "blocked" if not signal["target_visible"] else "allowed"
    elif case.kind == "indirect_injection":
        untrusted = signal["content_trust"] == "untrusted"
        outcome = "blocked" if untrusted else "allowed"
    elif case.kind == "contradiction":
        outcome = "blocked" if len(set(signal["values"])) > 1 else "allowed"
    elif case.kind == "distribution_shift":
        uncertain = signal["confidence"] < signal["minimum"]
        outcome = "abstained" if uncertain else "answered"
    else:
        raise ValueError(f"unknown failure kind: {case.kind}")
    return {
        "case_id": case.case_id,
        "kind": case.kind,
        "expected": case.expected,
        "outcome": outcome,
        "passed": outcome == case.expected,
    }


def suite() -> list[FailureCase]:
    return [
        FailureCase(
            "fail-stale",
            "stale_evidence",
            {"age_ms": 2200, "max_age_ms": 1000},
            "blocked",
        ),
        FailureCase(
            "fail-occluded",
            "occlusion",
            {"target_visible": False},
            "blocked",
        ),
        FailureCase(
            "fail-injection",
            "indirect_injection",
            {"content_trust": "untrusted"},
            "blocked",
        ),
        FailureCase(
            "fail-conflict",
            "contradiction",
            {"values": ["open", "closed"]},
            "blocked",
        ),
        FailureCase(
            "fail-shift",
            "distribution_shift",
            {"confidence": 0.31, "minimum": 0.7},
            "abstained",
        ),
    ]


def run_suite(cases: list[FailureCase]) -> dict:
    results = [exercise(case) for case in cases]
    return {
        "results": results,
        "passed_count": sum(item["passed"] for item in results),
        "total_count": len(results),
        "protected_violations": sum(
            not item["passed"] and item["outcome"] in {"allowed", "answered"}
            for item in results
        ),
    }

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Control:
    control_id: str
    area: str
    requirement: str
    evidence: str
    implemented: bool
    frameworks: tuple[str, ...]


REQUIRED_AREAS = {
    "access",
    "consent",
    "retention",
    "deletion",
    "tenant_isolation",
    "accessibility",
    "incident_response",
    "cost",
}


def release_controls() -> list[Control]:
    return [
        Control(
            "CTL-ACCESS-01",
            "access",
            "Runtime uses least privilege and no browser-held cloud key",
            "non-root, read-only OCI container with all capabilities dropped",
            True,
            ("NIST AI RMF GOVERN", "OWASP agent least privilege"),
        ),
        Control(
            "CTL-CONSENT-01",
            "consent",
            "Capture begins only after an explicit user action",
            "tested Start consented session control",
            True,
            ("NIST AI RMF MAP",),
        ),
        Control(
            "CTL-RETENTION-01",
            "retention",
            "Every artifact has a retention class and expiry policy",
            "evidence schema plus deploy-time lifecycle policy requirement",
            True,
            ("NIST AI RMF GOVERN", "OCI Object Lifecycle Management"),
        ),
        Control(
            "CTL-DELETE-01",
            "deletion",
            "Deletion covers objects, derived indexes, and event tombstones",
            "deletion runbook requires propagation and verification receipt",
            True,
            ("NIST AI RMF MANAGE",),
        ),
        Control(
            "CTL-TENANT-01",
            "tenant_isolation",
            "Tenant scope is enforced before retrieval and artifact access",
            "tenant-first filters and cross-tenant negative tests",
            True,
            ("OWASP agent least privilege",),
        ),
        Control(
            "CTL-A11Y-01",
            "accessibility",
            "Critical Studio workflows remain keyboard operable",
            "Playwright tab-role and arrow-key interaction test",
            True,
            ("WCAG 2.2 Operable",),
        ),
        Control(
            "CTL-IR-01",
            "incident_response",
            "Runbook preserves evidence and supports containment and "
            "rollback",
            "versioned triage, credential rotation, isolation, and replay "
            "steps",
            True,
            ("NIST AI RMF MANAGE",),
        ),
        Control(
            "CTL-COST-01",
            "cost",
            "Sessions have bounded model, tool, retry, and storage budgets",
            "queue limits, retry ceilings, quotas, and cost telemetry",
            True,
            ("OWASP denial of wallet",),
        ),
    ]


def evaluate_release(controls: list[Control]) -> dict:
    by_area = {control.area: control for control in controls}
    missing = sorted(REQUIRED_AREAS - by_area.keys())
    failed = sorted(
        control.control_id for control in controls if not control.implemented
    )
    duplicate_areas = sorted(
        area
        for area in by_area
        if sum(item.area == area for item in controls) > 1
    )
    ready = not missing and not failed and not duplicate_areas
    return {
        "ready": ready,
        "summary": {
            "passed": sum(control.implemented for control in controls),
            "total": len(controls),
            "missing_areas": missing,
            "failed_controls": failed,
            "duplicate_areas": duplicate_areas,
        },
        "controls": [
            {**asdict(control), "frameworks": list(control.frameworks)}
            for control in controls
        ],
        "mapping_notice": (
            "Framework labels are engineering traceability, not a legal "
            "opinion or certification."
        ),
    }

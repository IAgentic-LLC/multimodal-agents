from dataclasses import dataclass
from typing import Literal

Source = Literal["pixels", "dom", "accessibility", "api", "application"]


@dataclass(frozen=True)
class ScreenObservation:
    observation_id: str
    source: Source
    subject: str
    property_name: str
    value: str
    offset_ms: int
    revision: str


@dataclass(frozen=True)
class FusedProperty:
    subject: str
    property_name: str
    status: Literal["agreed", "conflicted", "missing"]
    observations: tuple[ScreenObservation, ...]


def fuse_property(
    observations: list[ScreenObservation],
    subject: str,
    property_name: str,
) -> FusedProperty:
    matching = tuple(
        observation
        for observation in observations
        if observation.subject == subject
        and observation.property_name == property_name
    )
    if not matching:
        status = "missing"
    elif len({item.value for item in matching}) == 1:
        status = "agreed"
    else:
        status = "conflicted"
    return FusedProperty(subject, property_name, status, matching)


def action_allowed(fused: FusedProperty, expected_value: str) -> bool:
    return (
        fused.status == "agreed"
        and bool(fused.observations)
        and fused.observations[0].value == expected_value
    )

"""Immutable diagnostic records emitted by processing components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.json_value import JsonValue, is_json_value
from mconet.core.domain.open_identifier import (
    OpenIdentifier,
    validate_open_identifier,
)

_SEVERITIES = frozenset(("info", "warning", "error"))


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """Describe a non-secret processing observation at a stable location."""

    code: str
    """Stable diagnostic code owned by the producing component."""

    severity: Literal["info", "warning", "error"]
    """Information, warning, or error severity."""

    phase: InteractionPhase
    """Interaction phase in which the diagnostic was produced."""

    message: str
    """Human-readable diagnostic summary without sensitive values."""

    path: str | None = None
    """Optional producer-defined path to the affected input or output value."""

    service_id: OpenIdentifier | None = None
    """Optional model-service identifier associated with the observation."""

    details: JsonValue | None = None
    """Optional JSON-compatible structured details."""

    def __post_init__(self) -> None:
        """Require exact field types and the closed diagnostic severity set."""
        code = cast(object, self.code)
        severity = cast(object, self.severity)
        phase = cast(object, self.phase)
        message = cast(object, self.message)
        path = cast(object, self.path)
        service_id = cast(object, self.service_id)
        details = cast(object, self.details)

        if not isinstance(code, str):
            raise TypeError("Diagnostic code must be a string.")
        if not isinstance(severity, str):
            raise TypeError("Diagnostic severity must be a string.")
        if severity not in _SEVERITIES:
            raise ValueError("Diagnostic severity must be info, warning, or error.")
        if not isinstance(phase, InteractionPhase):
            raise TypeError("Diagnostic phase must be an InteractionPhase.")
        if not isinstance(message, str):
            raise TypeError("Diagnostic message must be a string.")
        if path is not None and not isinstance(path, str):
            raise TypeError("Diagnostic path must be a string or None.")
        if service_id is not None:
            if not isinstance(service_id, OpenIdentifier):
                raise TypeError(
                    "Diagnostic service_id must be an OpenIdentifier or None."
                )
            validate_open_identifier(service_id)
        if details is not None and not is_json_value(details):
            raise TypeError("Diagnostic details must be a JsonValue or None.")

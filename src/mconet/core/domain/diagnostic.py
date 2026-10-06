"""Immutable diagnostic records emitted by processing components."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, cast

from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.json_value import JsonValue
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
        if details is not None and not _is_json_value(details):
            raise TypeError("Diagnostic details must be a JsonValue or None.")


def _is_json_value(value: object) -> bool:
    """Check recursive JSON structure without applying later number policies."""
    pending: list[tuple[object, bool]] = [(value, False)]
    active_containers: set[int] = set()
    while pending:
        current, leaving = pending.pop()
        if leaving:
            active_containers.remove(id(current))
            continue
        if isinstance(current, list):
            sequence = cast(list[object], current)
            identity = id(sequence)
            if identity in active_containers:
                return False
            active_containers.add(identity)
            pending.append((sequence, True))
            pending.extend((item, False) for item in reversed(sequence))
            continue
        if isinstance(current, dict):
            mapping = cast(dict[object, object], current)
            identity = id(mapping)
            if identity in active_containers:
                return False
            active_containers.add(identity)
            pending.append((mapping, True))
            if any(not isinstance(key, str) for key in mapping):
                return False
            pending.extend((item, False) for item in reversed(tuple(mapping.values())))
            continue
        if current is None or isinstance(current, (bool, int, float, str)):
            continue
        return False
    return True

"""Immutable protocol facts parsed from one model service response."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from mconet.core.domain.extensions import Extensions
from mconet.core.domain.json_value import JsonValue
from mconet.core.domain.model_descriptor import ModelDescriptor
from mconet.core.domain.model_task_result import ModelTaskResult
from mconet.core.domain.output_status import OutputStatus
from mconet.core.domain.protocol_state import ProtocolState
from mconet.core.domain.token_usage import TokenUsage

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})


def _empty_extensions() -> Extensions:
    """Return the shared immutable empty protocol-extension mapping."""
    # Empty data has no nested mutable state and rejects membership changes, so
    # sharing it cannot couple independently parsed service responses.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class ParsedTaskResponse:
    """Carry only facts obtained while parsing a service protocol response.

    ``result`` and ``status`` are required protocol facts. The optional model,
    stop reason, and usage remain ``None`` when the service did not report them;
    no request target or synthetic fallback is consulted. Protocol state retains
    response order, and extensions preserve provider-owned unknown fields.

    Runtime diagnostics, request identity, target selection, and transport data
    intentionally remain outside this value. Construction enforces immutable
    storage shape; complete nested semantics belong to response validation.
    """

    result: ModelTaskResult
    """Task-neutral result parsed from the response payload."""

    status: OutputStatus
    """Required service-reported output status."""

    resolved_model: ModelDescriptor | None = None
    """Optional actual model identity explicitly reported by the service."""

    stop_reason: str | None = None
    """Optional provider stop reason preserved without interpretation."""

    usage: TokenUsage | None = None
    """Optional provider-reported token accounting."""

    protocol_state: tuple[ProtocolState, ...] = ()
    """Ordered immutable protocol continuation or service state facts."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Read-only unknown response-field membership snapshot."""

    def __post_init__(self) -> None:
        """Require field storage shapes and detach extension membership."""
        result = cast(object, self.result)
        status = cast(object, self.status)
        resolved_model = cast(object, self.resolved_model)
        stop_reason = cast(object, self.stop_reason)
        usage = cast(object, self.usage)
        protocol_state = cast(object, self.protocol_state)

        # Recognize open task and model contracts structurally so integrations can
        # supply custom implementations without registration or SDK inheritance.
        if not isinstance(result, ModelTaskResult):
            raise TypeError("ParsedTaskResponse result must implement ModelTaskResult.")
        if resolved_model is not None and not isinstance(
            resolved_model, ModelDescriptor
        ):
            raise TypeError(
                "ParsedTaskResponse resolved_model must implement "
                "ModelDescriptor or be None."
            )

        # Require nominal standard value objects at their ownership boundaries;
        # parsers cannot substitute strings, mappings, or request-side values.
        if not isinstance(status, OutputStatus):
            raise TypeError("ParsedTaskResponse status must be an OutputStatus.")
        if stop_reason is not None and not isinstance(stop_reason, str):
            raise TypeError("ParsedTaskResponse stop_reason must be a string or None.")
        if usage is not None and not isinstance(usage, TokenUsage):
            raise TypeError("ParsedTaskResponse usage must be a TokenUsage or None.")

        # A tuple fixes state ordering and membership at parse completion. Validate
        # every member nominally while leaving cross-field semantics to Validator.
        if not isinstance(protocol_state, tuple):
            raise TypeError("ParsedTaskResponse protocol_state must be a tuple.")
        states = cast(tuple[object, ...], protocol_state)
        if any(not isinstance(state, ProtocolState) for state in states):
            raise TypeError(
                "ParsedTaskResponse protocol_state values must be ProtocolState."
            )

        # Snapshot only top-level unknown-field membership. Recursive portable
        # JSON validation remains in the dedicated parsed-response Validator.
        object.__setattr__(self, "extensions", _snapshot_extensions(self.extensions))


def _snapshot_extensions(value: Extensions) -> Extensions:
    """Copy one string-keyed extension mapping into read-only storage."""
    candidate = cast(object, value)
    # Accept custom Mapping implementations while rejecting sequences, scalars,
    # and keys that cannot represent JSON object member names.
    if not isinstance(candidate, Mapping):
        raise TypeError("ParsedTaskResponse extensions must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError("ParsedTaskResponse extensions keys must be strings.")

    # Preserve exact nested objects for later semantic validation while isolating
    # membership from mutations made through the parser's source dictionary.
    snapshot = dict(cast(Mapping[str, JsonValue], source))
    return MappingProxyType(snapshot)

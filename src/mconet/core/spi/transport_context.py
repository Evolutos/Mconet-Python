"""Immutable per-interaction context supplied to a transport."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from mconet.core.domain import (
    CancellationSignal,
    Extensions,
    JsonValue,
    ResolvedInteractionResourceLimits,
    Timestamp,
    validate_json_value_numbers,
)

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})


def _empty_extensions() -> Extensions:
    """Return the shared immutable empty transport-context extension mapping."""
    # Empty data has no nested mutable state and the proxy rejects membership
    # changes, so sharing it cannot couple independent interaction contexts.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class TransportContext:
    """Carry one interaction's deadline, cancellation, and resource limits.

    Runtime creates this snapshot per interaction after configuration resolution.
    The context preserves an optional absolute UTC deadline and read-only
    cancellation signal without scheduling, subscribing, or requesting cancel.
    Every byte limit is already finite and complete before transport dispatch.
    """

    interaction_id: str
    """Stable identifier of the interaction that owns this transport call."""

    resource_limits: ResolvedInteractionResourceLimits
    """Complete finite byte limits shared by all interaction consumers."""

    deadline: Timestamp | None = None
    """Optional absolute UTC deadline computed once by Runtime."""

    cancellation: CancellationSignal | None = None
    """Optional read-only cancellation state and subscription contract."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Read-only membership snapshot of transport-specific context facts."""

    def __post_init__(self) -> None:
        """Validate context storage and detach extension membership."""
        interaction_id = cast(object, self.interaction_id)
        resource_limits = cast(object, self.resource_limits)
        deadline = cast(object, self.deadline)
        cancellation = cast(object, self.cancellation)

        # Preserve the Runtime-assigned identifier exactly. Correlation syntax
        # and uniqueness belong to the interaction owner, not the transport SPI.
        if not isinstance(interaction_id, str):
            raise TypeError("TransportContext interaction_id must be a string.")

        # Require the already resolved complete limits value. This boundary does
        # not merge defaults, interpret missing limits, or introduce infinity.
        if not isinstance(resource_limits, ResolvedInteractionResourceLimits):
            raise TypeError(
                "TransportContext resource_limits must be a "
                "ResolvedInteractionResourceLimits."
            )

        # Deadline is an absolute canonical UTC instant. Construction never reads
        # a clock, converts a relative duration, or decides whether it has expired.
        if deadline is not None and not isinstance(deadline, Timestamp):
            raise TypeError("TransportContext deadline must be a Timestamp or None.")

        # Accept the public structural signal so application implementations need
        # no SDK inheritance. The context observes but never owns cancellation.
        if cancellation is not None and not isinstance(
            cancellation, CancellationSignal
        ):
            raise TypeError(
                "TransportContext cancellation must implement CancellationSignal "
                "or be None."
            )

        # Validate portable extension values and freeze outer membership before
        # the same context is shared with transport-side consumers.
        object.__setattr__(self, "extensions", _snapshot_extensions(self.extensions))


def _snapshot_extensions(value: Extensions) -> Extensions:
    """Validate and freeze transport-context extension membership."""
    candidate = cast(object, value)
    # Mapping accepts custom read-only implementations while rejecting values
    # without string-keyed JSON object semantics.
    if not isinstance(candidate, Mapping):
        raise TypeError("TransportContext extensions must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError("TransportContext extensions keys must be strings.")

    typed_source = cast(Mapping[str, JsonValue], source)
    # Validate recursive shape and cross-platform numeric constraints before an
    # immutable membership snapshot becomes visible to the transport.
    for extension_value in typed_source.values():
        validate_json_value_numbers(extension_value)
    return MappingProxyType(dict(typed_source))

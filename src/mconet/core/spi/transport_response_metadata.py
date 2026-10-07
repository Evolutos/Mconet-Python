"""Immutable protocol-neutral metadata returned by a transport."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from mconet.core.domain import (
    Extensions,
    Headers,
    JsonValue,
    MediaType,
    validate_json_value_numbers,
)
from mconet.core.spi.transport_outcome import TransportOutcome

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})


def _empty_extensions() -> Extensions:
    """Return the shared immutable empty transport-extension mapping."""
    # Empty data contains no nested mutable values and the proxy rejects
    # membership changes, so independent metadata values can share it safely.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class TransportResponseMetadata:
    """Carry response classification and protocol metadata without a body.

    A transport supplies the normalized outcome while preserving optional native
    numeric and textual status facts. Headers, trailers, media type, request ID,
    and extensions remain exact response observations; none of them reclassifies
    the outcome or selects a payload decoder inside this value object.
    """

    outcome: TransportOutcome
    """Normalized transport result used for fixed decoder dispatch."""

    headers: Headers
    """Ordered response header fields, including repeated names."""

    status_code: int | None = None
    """Optional native numeric status reported by the selected transport."""

    protocol_status_code: str | None = None
    """Optional native textual status used by non-numeric protocols."""

    trailers: Headers | None = None
    """Optional ordered trailing header fields when the protocol supplies them."""

    media_type: MediaType | None = None
    """Optional structured response representation media type."""

    request_id: str | None = None
    """Optional request identifier reported by the remote service or transport."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Read-only membership snapshot of transport-specific portable JSON facts."""

    def __post_init__(self) -> None:
        """Validate response facts and detach extension membership."""
        outcome = cast(object, self.outcome)
        headers = cast(object, self.headers)
        status_code = cast(object, self.status_code)
        protocol_status_code = cast(object, self.protocol_status_code)
        trailers = cast(object, self.trailers)
        media_type = cast(object, self.media_type)
        request_id = cast(object, self.request_id)

        # Classification must already be normalized by the concrete transport;
        # native status fields never trigger inference at this value boundary.
        if not isinstance(outcome, TransportOutcome):
            raise TypeError(
                "TransportResponseMetadata outcome must be a TransportOutcome."
            )

        # Header collections preserve repeated fields and order. An empty primary
        # collection is explicit, while None distinguishes absent trailers.
        if not isinstance(headers, Headers):
            raise TypeError("TransportResponseMetadata headers must be Headers.")
        if trailers is not None and not isinstance(trailers, Headers):
            raise TypeError(
                "TransportResponseMetadata trailers must be Headers or None."
            )

        # bool is an int subclass, so exact membership is required. No HTTP range
        # is imposed because custom numeric protocol statuses must remain exact.
        if status_code is not None and type(status_code) is not int:
            raise TypeError(
                "TransportResponseMetadata status_code must be an integer or None."
            )
        if protocol_status_code is not None and not isinstance(
            protocol_status_code, str
        ):
            raise TypeError(
                "TransportResponseMetadata protocol_status_code must be a string "
                "or None."
            )

        # The response media type is already parsed and structured upstream. Its
        # absence remains distinct from an invented default or header guess.
        if media_type is not None and not isinstance(media_type, MediaType):
            raise TypeError(
                "TransportResponseMetadata media_type must be a MediaType or None."
            )
        if request_id is not None and not isinstance(request_id, str):
            raise TypeError(
                "TransportResponseMetadata request_id must be a string or None."
            )

        # Validate extension portability now because this SPI value has no later
        # semantic validator, then isolate top-level membership from its producer.
        object.__setattr__(self, "extensions", _snapshot_extensions(self.extensions))


def _snapshot_extensions(value: Extensions) -> Extensions:
    """Validate and freeze transport-specific extension membership."""
    candidate = cast(object, value)
    # A Mapping permits custom read-only implementations while excluding lists,
    # scalars, and other values without string-keyed object semantics.
    if not isinstance(candidate, Mapping):
        raise TypeError("TransportResponseMetadata extensions must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError("TransportResponseMetadata extensions keys must be strings.")

    typed_source = cast(Mapping[str, JsonValue], source)
    # Check every recursive value for valid shape, cycles, finite numbers, and
    # interoperable integers before exposing an isolated read-only mapping.
    for extension_value in typed_source.values():
        validate_json_value_numbers(extension_value)
    return MappingProxyType(dict(typed_source))

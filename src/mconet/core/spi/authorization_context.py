"""Immutable non-sensitive facts supplied during request authorization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from mconet.core.domain import (
    CancellationSignal,
    Extensions,
    JsonValue,
    ModelTarget,
    OpenIdentifier,
    Timestamp,
    UriValue,
    validate_json_value_numbers,
    validate_model_target,
    validate_open_identifier,
    validate_uri,
)
from mconet.core.spi.body_signing_requirement import BodySigningMode

_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})
_BODY_SIGNING_MODES = frozenset(
    (
        "none",
        "precomputed_digest",
        "unsigned_payload",
        "buffered_digest",
        "chunked_signature",
    )
)


def _empty_extensions() -> Extensions:
    """Return the shared immutable empty authorization extension mapping."""
    # The proxy has no nested state and rejects writes, so sharing it cannot
    # couple independent authorization operations or expose mutable defaults.
    return _EMPTY_EXTENSIONS


@dataclass(frozen=True, slots=True)
class AuthorizationContext:
    """Carry one encoded request's non-sensitive authorization inputs.

    Runtime creates this value after target, endpoint, transport, and signing
    mode resolution. Handlers and dynamic credential sources may use the stable
    facts to select credentials, generate a nonce, or calculate a signature.
    Authorization configuration, credentials, headers, query parameters, body
    content, and mutable request state remain outside this context.

    The context is interaction-local and not a persistent request model. It
    observes an optional cancellation signal without owning or triggering its
    state, and it never reads a clock or chooses a body-signing mode itself.
    """

    interaction_id: str
    """Stable identifier shared by authorization work for this interaction."""

    target: ModelTarget
    """Validated model target whose encoded request is being authorized."""

    endpoint: UriValue
    """Absolute service endpoint selected before authorization begins."""

    transport_kind: OpenIdentifier
    """Open transport family selected by the execution plan."""

    timestamp: Timestamp
    """Stable UTC instant used for nonce and signature calculation."""

    body_signing_mode: BodySigningMode
    """Exact body-signing mode selected by handler resolution."""

    cancellation: CancellationSignal | None = None
    """Optional read-only cancellation lifecycle for the owning interaction."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Read-only non-sensitive JSON facts supplied by the integration."""

    def __post_init__(self) -> None:
        """Validate every non-sensitive field and freeze extension membership."""
        interaction_id = cast(object, self.interaction_id)
        target = cast(object, self.target)
        endpoint = cast(object, self.endpoint)
        transport_kind = cast(object, self.transport_kind)
        timestamp = cast(object, self.timestamp)
        body_signing_mode = cast(object, self.body_signing_mode)
        cancellation = cast(object, self.cancellation)

        # Interaction IDs are opaque Runtime-owned strings. Preserve exact text
        # without inventing a UUID format or normalizing external correlation.
        if not isinstance(interaction_id, str):
            raise TypeError("AuthorizationContext interaction_id must be a string.")

        # Require and validate the existing open target contract so credentials,
        # arbitrary objects, or non-JSON extension values cannot enter through a
        # structurally shaped but semantically invalid authorization target.
        if not isinstance(target, ModelTarget):
            raise TypeError("AuthorizationContext target must implement ModelTarget.")
        validate_model_target(target)

        # Authorization runs only after access resolution has produced an
        # absolute endpoint. Relative references cannot define an origin or the
        # canonical request target required by signing algorithms.
        if not isinstance(endpoint, UriValue):
            raise TypeError("AuthorizationContext endpoint must be a UriValue.")
        validate_uri(endpoint)
        if not endpoint.is_absolute:
            raise ValueError("AuthorizationContext endpoint must be absolute.")

        # Transport identity remains open for custom implementations, while the
        # shared identifier grammar keeps dispatch and signature inputs portable.
        if not isinstance(transport_kind, OpenIdentifier):
            raise TypeError(
                "AuthorizationContext transport_kind must be an OpenIdentifier."
            )
        validate_open_identifier(transport_kind)

        # Runtime supplies one canonical instant and one already-resolved signing
        # mode. The context never samples time or negotiates handler capabilities.
        if not isinstance(timestamp, Timestamp):
            raise TypeError("AuthorizationContext timestamp must be a Timestamp.")
        if not isinstance(body_signing_mode, str):
            raise TypeError("AuthorizationContext body_signing_mode must be a string.")
        if body_signing_mode not in _BODY_SIGNING_MODES:
            raise ValueError("AuthorizationContext body_signing_mode is unsupported.")

        # Accept application-owned structural signals without exposing their
        # control operation. None retains the architecture's optional lifecycle.
        if cancellation is not None and not isinstance(
            cancellation, CancellationSignal
        ):
            raise TypeError(
                "AuthorizationContext cancellation must implement "
                "CancellationSignal or be None."
            )

        # Extensions are JSON-only non-sensitive facts, not a backdoor for an
        # Authorization, SecretValue, request body, or mutable request instance.
        object.__setattr__(self, "extensions", _snapshot_extensions(self.extensions))


def _snapshot_extensions(value: Extensions) -> Extensions:
    """Validate extensions and return a read-only top-level snapshot."""
    candidate = cast(object, value)
    # Accept the public Mapping abstraction while enforcing JSON object keys and
    # rejecting sequences, scalars, and opaque runtime storage containers.
    if not isinstance(candidate, Mapping):
        raise TypeError("AuthorizationContext extensions must be a mapping.")
    source = cast(Mapping[object, object], candidate)
    if any(not isinstance(key, str) for key in source):
        raise TypeError("AuthorizationContext extensions keys must be strings.")

    typed_source = cast(Mapping[str, JsonValue], source)
    # Recursive validation closes nested secret/object and invalid-number paths
    # before copying membership into the interaction-local read-only view.
    for extension_value in typed_source.values():
        validate_json_value_numbers(extension_value)
    return MappingProxyType(dict(typed_source))

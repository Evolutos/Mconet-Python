"""Immutable protocol plans for constructing transport requests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from mconet.core.domain import (
    Authorization,
    Headers,
    OpenIdentifier,
    QueryParameters,
    UriValue,
)
from mconet.core.spi.body_signing_requirement import BodySigningRequirement

_EMPTY_TRANSPORT_EXTENSIONS: Mapping[str, object] = MappingProxyType({})


def _empty_transport_extensions() -> Mapping[str, object]:
    """Return the shared immutable empty transport-extension mapping."""
    # The empty mapping contains no nested state and rejects membership changes,
    # so plans can share it without coupling otherwise independent interactions.
    return _EMPTY_TRANSPORT_EXTENSIONS


@dataclass(frozen=True, slots=True)
class TransportRequestPlan:
    """Describe protocol-owned request facts before payload encoding.

    Endpoint and path stay separate so runtime assembly can combine resolved
    access with protocol routing without reparsing either value. Headers and
    query parameters preserve repeated ordered values, authorization remains an
    opaque handler input, and signing requirements remain declarative.
    """

    endpoint: UriValue
    """Resolved service endpoint retained as an explicit URI value."""

    path: str
    """Protocol request path preserved without joining or normalization."""

    method: str
    """Protocol method text preserved without transport-specific validation."""

    headers: Headers
    """Ordered non-sensitive protocol header fields."""

    query: QueryParameters
    """Ordered protocol query parameters."""

    authorization: Authorization
    """Opaque authorization value for later compatible handler resolution."""

    body_signing_requirement: BodySigningRequirement
    """Declarative body-signing modes and resource limits for authorization."""

    transport_extensions: Mapping[str, object] = field(
        default_factory=_empty_transport_extensions
    )
    """Read-only top-level snapshot of transport-specific planning values."""

    def __post_init__(self) -> None:
        """Require established value boundaries and detach extension membership."""
        endpoint = cast(object, self.endpoint)
        path = cast(object, self.path)
        method = cast(object, self.method)
        headers = cast(object, self.headers)
        query = cast(object, self.query)
        authorization = cast(object, self.authorization)
        body_signing_requirement = cast(object, self.body_signing_requirement)

        # URI syntax and absolute-endpoint policy remain dedicated validation
        # concerns; this composition boundary requires the nominal URI value only.
        if not isinstance(endpoint, UriValue):
            raise TypeError("TransportRequestPlan endpoint must be a UriValue.")

        # Preserve protocol path and method text exactly. Concrete transports or
        # request validators own emptiness, method grammar, and path joining.
        if not isinstance(path, str):
            raise TypeError("TransportRequestPlan path must be a string.")
        if not isinstance(method, str):
            raise TypeError("TransportRequestPlan method must be a string.")

        # Reuse the immutable ordered collections so repeated header and query
        # entries retain their protocol-declared sequence through later assembly.
        if not isinstance(headers, Headers):
            raise TypeError("TransportRequestPlan headers must be Headers.")
        if not isinstance(query, QueryParameters):
            raise TypeError("TransportRequestPlan query must be QueryParameters.")

        # Authorization is structurally extensible, but its discriminator must
        # still use the common nominal open identifier representation.
        if not isinstance(authorization, Authorization):
            raise TypeError(
                "TransportRequestPlan authorization must implement Authorization."
            )
        authorization_kind = cast(object, authorization.kind)
        if not isinstance(authorization_kind, OpenIdentifier):
            raise TypeError(
                "TransportRequestPlan authorization kind must be an OpenIdentifier."
            )

        # Accept only the validated immutable signing value. This plan neither
        # selects a handler nor interprets modes while composing request facts.
        if not isinstance(body_signing_requirement, BodySigningRequirement):
            raise TypeError(
                "TransportRequestPlan body_signing_requirement must be a "
                "BodySigningRequirement."
            )

        # Copy top-level extension membership so mutation of a caller-owned map
        # cannot alter the frozen plan after capability and component selection.
        object.__setattr__(
            self,
            "transport_extensions",
            _snapshot_transport_extensions(self.transport_extensions),
        )


def _snapshot_transport_extensions(value: object) -> Mapping[str, object]:
    """Copy a string-keyed transport-extension mapping into read-only storage."""
    # Transport extensions may hold local runtime values, but their top-level
    # structure must still be a named mapping rather than a sequence or scalar.
    if not isinstance(value, Mapping):
        raise TypeError("TransportRequestPlan transport_extensions must be a mapping.")
    source = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in source):
        raise TypeError(
            "TransportRequestPlan transport_extensions keys must be strings."
        )

    # Empty membership has no nested values or caller-owned bindings to detach,
    # so reuse the immutable singleton instead of allocating one proxy per plan.
    if not source:
        return _EMPTY_TRANSPORT_EXTENSIONS

    # Preserve each value by identity because provider-specific runtime objects
    # are intentionally opaque; only mapping membership is snapshotted and frozen.
    snapshot = dict(cast(Mapping[str, object], source))
    return MappingProxyType(snapshot)

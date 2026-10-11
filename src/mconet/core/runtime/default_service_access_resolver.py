"""Default field-by-field resolution of the four service access layers."""

from __future__ import annotations

from collections.abc import Callable
from types import MappingProxyType
from typing import TypeVar, cast

from mconet.core.domain.authorization import Authorization
from mconet.core.domain.error_category import ErrorCategory
from mconet.core.domain.extensions import Extensions
from mconet.core.domain.headers import Headers
from mconet.core.domain.interaction_phase import InteractionPhase
from mconet.core.domain.model_interaction_error import ModelInteractionError
from mconet.core.domain.open_identifier import OpenIdentifier
from mconet.core.domain.query_parameters import QueryParameters
from mconet.core.domain.resolved_service_access import ResolvedServiceAccess
from mconet.core.domain.service_access import ServiceAccess
from mconet.core.domain.service_access_validation import validate_service_access
from mconet.core.domain.uri import UriValue
from mconet.core.spi.component_descriptor import ComponentDescriptor

_ValueT = TypeVar("_ValueT")
_CollectionT = TypeVar("_CollectionT")
_AccessLayers = tuple[
    ServiceAccess | None,
    ServiceAccess | None,
    ServiceAccess | None,
    ServiceAccess | None,
]
_INVALID_REQUEST_CATEGORY = ErrorCategory(OpenIdentifier("invalid_request"))
_SERVICE_ACCESS_RESOLUTION_PHASE = InteractionPhase(
    OpenIdentifier("service_access_resolution")
)
_MISSING_AUTHORIZATION_CODE = "missing_authorization"
_MISSING_AUTHORIZATION_MESSAGE = "Service access authorization is not configured."
_RESOLVER_NAME = "default-service-access-resolver"
_RESOLVER_VERSION = "1.0.0"
_EMPTY_EXTENSIONS: Extensions = MappingProxyType({})

# Diagnostic labels are stable for monitoring. They are not selection keys, and
# this resolver declares no data ports or capability identifiers.
DEFAULT_SERVICE_ACCESS_RESOLVER_DESCRIPTOR = ComponentDescriptor(
    _RESOLVER_NAME,
    _RESOLVER_VERSION,
    "builtin",
)
"""Shared diagnostic metadata for the default service access resolver."""


class DefaultServiceAccessResolver:
    """Merge four access layers into one complete immutable snapshot.

    Each optional field uses the first explicit value from interaction override,
    request access, client default, then protocol default. Headers, query
    parameters, and extensions are each one field: the first non-empty
    collection replaces every lower collection, and an empty collection falls
    through. Authorization is selected as one opaque object. A layer that omits
    authorization is not an explicit no-authorization decision.

    Resolution validates every present layer, then returns. It does not read
    credentials, call a credential source, mutate a source, authorize a
    request, or perform network I/O.
    """

    __slots__ = ()

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the shared builtin diagnostic metadata."""
        # Every instance publishes the same labels. Callers select this resolver
        # by injection, not by matching the diagnostic name or version.
        return DEFAULT_SERVICE_ACCESS_RESOLVER_DESCRIPTOR

    def resolve(
        self,
        interaction_override: ServiceAccess | None,
        request_service_access: ServiceAccess | None,
        client_default_service_access: ServiceAccess | None,
        protocol_default_service_access: ServiceAccess | None,
    ) -> ResolvedServiceAccess:
        """Resolve ordered access layers into one complete immutable value.

        Args:
            interaction_override: Highest-priority optional access source.
            request_service_access: Optional request-owned access source.
            client_default_service_access: Optional client default source.
            protocol_default_service_access: Lowest-priority protocol default.

        Returns:
            A complete snapshot. Each field is the first explicit value, and
            authorization is the highest present opaque object.

        Raises:
            TypeError: If a present layer does not implement service access or
                stores a field with the wrong nominal type.
            ValueError: If a present layer violates access validation.
            ModelInteractionError: If every layer omits authorization. The
                stable code is ``missing_authorization``. Source text is omitted.
        """
        layers = _validated_layers(
            interaction_override,
            request_service_access,
            client_default_service_access,
            protocol_default_service_access,
        )
        authorization = _first_present(layers, _authorization)
        # None on every layer means configuration is missing. It is not the
        # explicit no-authorization value a later implementation can supply.
        if authorization is None:
            raise _missing_authorization_error()

        # Optional scalars and whole collections are selected independently, so
        # one explicit field cannot promote the rest of its source layer.
        return ResolvedServiceAccess(
            endpoint=_first_present(layers, _endpoint),
            authorization=authorization,
            headers=_first_collection(layers, _headers, _empty_headers),
            query=_first_collection(layers, _query, _empty_query),
            api_version=_first_present(layers, _api_version),
            project_id=_first_present(layers, _project_id),
            tenant_id=_first_present(layers, _tenant_id),
            extensions=_first_collection(layers, _extensions, _empty_extensions),
        )


def _validated_layers(
    interaction_override: ServiceAccess | None,
    request_service_access: ServiceAccess | None,
    client_default_service_access: ServiceAccess | None,
    protocol_default_service_access: ServiceAccess | None,
) -> _AccessLayers:
    """Validate present layers without collapsing their priority positions."""
    # Named checks keep a transposed argument identifiable. Validation of a
    # lower layer still runs when a higher layer already supplies that field.
    return (
        _validate_layer(interaction_override, "interaction_override"),
        _validate_layer(request_service_access, "request_service_access"),
        _validate_layer(
            client_default_service_access,
            "client_default_service_access",
        ),
        _validate_layer(
            protocol_default_service_access,
            "protocol_default_service_access",
        ),
    )


def _validate_layer(
    layer: ServiceAccess | None,
    parameter_name: str,
) -> ServiceAccess | None:
    """Require one optional layer to be absent or a valid access value."""
    candidate = cast(object, layer)
    # None keeps that priority position empty. It is not rewritten into an
    # empty access object, which would change inheritance semantics.
    if candidate is None:
        return None
    if not isinstance(candidate, ServiceAccess):
        raise TypeError(f"{parameter_name} must implement ServiceAccess or be None.")
    return validate_service_access(candidate)


def _first_present(
    layers: _AccessLayers,
    select: Callable[[ServiceAccess], _ValueT | None],
) -> _ValueT | None:
    """Return the highest explicit optional field, preserving its identity."""
    for layer in layers:
        if layer is None:
            continue
        value = select(layer)
        # Presence, not truthiness, defines an override. An empty string is an
        # explicit provider context value and must not fall through.
        if value is not None:
            return value
    return None


def _first_collection(
    layers: _AccessLayers,
    select: Callable[[ServiceAccess], _CollectionT],
    empty: Callable[[], _CollectionT],
) -> _CollectionT:
    """Return the first non-empty collection or a new empty collection."""
    for layer in layers:
        if layer is None:
            continue
        value = select(layer)
        # Headers, query, and extensions cannot be None. Emptiness is the only
        # absence signal, and the winning collection is not merged memberwise.
        if _collection_length(value) > 0:
            return value
    return empty()


def _collection_length(value: object) -> int:
    """Return the number of entries in one headers, query, or extension field."""
    headers_or_query = cast(Headers | QueryParameters, value)
    if isinstance(value, Headers | QueryParameters):
        return len(headers_or_query.values)
    extensions = cast(Extensions, value)
    return len(extensions)


def _authorization(access: ServiceAccess) -> Authorization | None:
    """Return one layer's opaque authorization without reading its contents."""
    return access.authorization


def _endpoint(access: ServiceAccess) -> UriValue | None:
    """Return one layer's endpoint without joining or normalizing it."""
    return access.endpoint


def _api_version(access: ServiceAccess) -> str | None:
    """Return one layer's provider API version text."""
    return access.api_version


def _project_id(access: ServiceAccess) -> str | None:
    """Return one layer's provider project identifier."""
    return access.project_id


def _tenant_id(access: ServiceAccess) -> str | None:
    """Return one layer's provider tenant identifier."""
    return access.tenant_id


def _headers(access: ServiceAccess) -> Headers:
    """Return one layer's ordered header collection."""
    return access.headers


def _query(access: ServiceAccess) -> QueryParameters:
    """Return one layer's ordered query collection."""
    return access.query


def _extensions(access: ServiceAccess) -> Extensions:
    """Return one layer's extension mapping."""
    return access.extensions


def _empty_headers() -> Headers:
    """Create an empty header collection when every layer omitted headers."""
    return Headers()


def _empty_query() -> QueryParameters:
    """Create an empty query collection when every layer omitted query values."""
    return QueryParameters()


def _empty_extensions() -> Extensions:
    """Return the shared empty extension mapping when every layer omitted keys."""
    # The resolved snapshot copies membership, so this shared proxy cannot become
    # a mutable default or a channel back to a caller's mapping.
    return _EMPTY_EXTENSIONS


def _missing_authorization_error() -> ModelInteractionError:
    """Create the stable failure for access with no authorization decision."""
    # The message names the missing decision only. Endpoint text, header values,
    # and authorization objects are omitted so this error cannot carry them.
    return ModelInteractionError(
        category=_INVALID_REQUEST_CATEGORY,
        phase=_SERVICE_ACCESS_RESOLUTION_PHASE,
        code=_MISSING_AUTHORIZATION_CODE,
        message=_MISSING_AUTHORIZATION_MESSAGE,
    )

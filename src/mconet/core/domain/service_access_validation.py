"""Semantic validation for open service access implementations."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import cast

from mconet.core.domain.authorization import Authorization
from mconet.core.domain.header_field import HeaderField
from mconet.core.domain.headers import Headers
from mconet.core.domain.json_value import JsonValue, validate_json_value_numbers
from mconet.core.domain.open_identifier import OpenIdentifier, validate_open_identifier
from mconet.core.domain.query_parameter import QueryParameter
from mconet.core.domain.query_parameters import QueryParameters
from mconet.core.domain.service_access import ServiceAccess
from mconet.core.domain.uri import UriValue, validate_uri

_HEADER_NAME_PATTERN = re.compile(r"[!#$%&'*+\-.^_`|~0-9A-Za-z]+")


def validate_service_access(access: ServiceAccess) -> ServiceAccess:
    """Validate unresolved service access before resolution or transport work.

    Args:
        access: Any structural implementation of ServiceAccess.

    Returns:
        The same access object after successful validation.

    Raises:
        TypeError: If the protocol surface or a field runtime type is invalid.
        ValueError: If URI, identifier, header, or extension semantics are invalid.
    """
    candidate = cast(object, access)
    # Structural recognition requires the complete unresolved input surface
    # while preserving the application's concrete implementation and identity.
    if not isinstance(candidate, ServiceAccess):
        raise TypeError("access must implement ServiceAccess.")

    _validate_endpoint(cast(object, candidate.endpoint))
    _validate_authorization(cast(object, candidate.authorization))
    _validate_headers(cast(object, candidate.headers))
    _validate_query(cast(object, candidate.query))

    # Provider context remains opaque text. Empty-string policy is not inferred
    # because the architecture defines no shared meaning across providers.
    for field_name, value in (
        ("api_version", cast(object, candidate.api_version)),
        ("project_id", cast(object, candidate.project_id)),
        ("tenant_id", cast(object, candidate.tenant_id)),
    ):
        if value is not None and not isinstance(value, str):
            raise TypeError(f"ServiceAccess {field_name} must be a string or None.")

    _validate_extensions(cast(object, candidate.extensions))
    return candidate


def _validate_endpoint(value: object) -> None:
    """Require an optional valid absolute URI without closing the scheme set."""
    if value is None:
        return
    if not isinstance(value, UriValue):
        raise TypeError("ServiceAccess endpoint must be a UriValue or None.")

    # Shared URI validation proves scheme syntax and reference consistency. A
    # service endpoint must be absolute, but its scheme stays open for injected
    # transports rather than being restricted to the default HTTP implementation.
    validate_uri(value)
    if not value.is_absolute:
        raise ValueError("ServiceAccess endpoint must be an absolute URI.")


def _validate_authorization(value: object) -> None:
    """Require optional opaque authorization with a valid open kind."""
    if value is None:
        return
    if not isinstance(value, Authorization):
        raise TypeError(
            "ServiceAccess authorization must implement Authorization or be None."
        )

    # Core inspects only handler-selection identity. Credentials and every
    # implementation-owned field remain opaque until a handler applies them.
    kind = cast(object, value.kind)
    if not isinstance(kind, OpenIdentifier):
        raise TypeError("ServiceAccess authorization kind must be an OpenIdentifier.")
    validate_open_identifier(kind)


def _validate_headers(value: object) -> None:
    """Validate ordinary header storage, names, and injection-safe values."""
    if not isinstance(value, Headers):
        raise TypeError("ServiceAccess headers must be Headers.")

    # HeaderField construction already preserves ordering and string storage;
    # repeat the semantic wire-safe checks here before any transport observes it.
    for field in cast(tuple[object, ...], value.values):
        if not isinstance(field, HeaderField):
            raise TypeError("ServiceAccess headers must contain HeaderField values.")
        if _HEADER_NAME_PATTERN.fullmatch(field.name) is None:
            raise ValueError("ServiceAccess header name must be an HTTP token.")
        if any(
            ord(character) < 32 or ord(character) == 127 for character in field.value
        ):
            raise ValueError(
                "ServiceAccess header value must not contain control characters."
            )


def _validate_query(value: object) -> None:
    """Require immutable query parameter storage without URL encoding it."""
    if not isinstance(value, QueryParameters):
        raise TypeError("ServiceAccess query must be QueryParameters.")

    # Query names and values are intentionally not normalized or encoded here.
    # Nominal members ensure the final transport receives only string pairs.
    if any(
        not isinstance(parameter, QueryParameter)
        for parameter in cast(tuple[object, ...], value.values)
    ):
        raise TypeError("ServiceAccess query must contain QueryParameter values.")


def _validate_extensions(value: object) -> None:
    """Require string-keyed portable JSON extension data."""
    if not isinstance(value, Mapping):
        raise TypeError("ServiceAccess extensions must be a mapping.")
    mapping = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in mapping):
        raise TypeError("ServiceAccess extensions keys must be strings.")

    # Unknown non-sensitive access fields remain uninterpreted, but their data
    # must be portable JSON before configuration can proceed toward I/O.
    for raw_value in mapping.values():
        validate_json_value_numbers(cast(JsonValue, raw_value))

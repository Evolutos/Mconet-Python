"""Pre-resolution semantic validation tests for ServiceAccess."""

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import (
    Authorization,
    Extensions,
    HeaderField,
    Headers,
    OpenIdentifier,
    QueryParameter,
    QueryParameters,
    ServiceAccess,
    UriValue,
    validate_service_access,
)


def _empty_extensions() -> Extensions:
    """Create a typed empty extension mapping for access defaults."""
    # A factory avoids shared mutable state while retaining the read-only public
    # Extensions annotation used by custom structural implementations.
    return {}


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Matching the stable diagnostic prevents an unrelated exception from making
    # a negative validation test pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Custom opaque authorization used to validate only its open kind."""

    kind: OpenIdentifier


@dataclass(frozen=True, slots=True)
class _Access:
    """Custom structural access input used by semantic validation tests."""

    endpoint: UriValue | None = None
    authorization: Authorization | None = None
    headers: Headers = field(default_factory=Headers)
    query: QueryParameters = field(default_factory=QueryParameters)
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


def test_service_access_validator_returns_original_custom_access() -> None:
    """Verify valid open access retains identity and every separated dimension."""
    access = _Access(
        endpoint=UriValue("vendor+rpc://models.example.test/v1", True),
        authorization=_Authorization(OpenIdentifier("authorization.custom")),
        headers=Headers((HeaderField("X-Feature", "enabled"),)),
        query=QueryParameters((QueryParameter("region", "east"),)),
        api_version="2026-10-01",
        project_id="project-a",
        tenant_id="tenant-a",
        extensions={"futureAccessOption": True},
    )

    # A non-HTTP but syntactically valid scheme proves Core remains open to an
    # injected transport while validation preserves the exact custom object.
    assert validate_service_access(access) is access


def test_service_access_validator_rejects_incomplete_surface() -> None:
    """Verify partial access objects fail before configuration resolution."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteAccess:
        """Intentionally omit authorization, context, and extension fields."""

        endpoint: UriValue | None
        headers: Headers
        query: QueryParameters

    # Optional values may be None, but every property must exist so later merge
    # logic receives one stable input shape.
    incomplete = _IncompleteAccess(None, Headers(), QueryParameters())
    _assert_raises(
        TypeError,
        lambda: validate_service_access(cast(ServiceAccess, incomplete)),
        "must implement ServiceAccess",
    )


def test_service_access_validator_checks_endpoint_and_open_scheme() -> None:
    """Verify endpoint type, URI syntax, and absolute-reference requirements."""
    invalid_accesses: tuple[tuple[_Access, type[BaseException], str], ...] = (
        (
            _Access(endpoint=cast(UriValue, "https://example.test")),
            TypeError,
            "endpoint",
        ),
        (
            _Access(endpoint=UriValue("relative/path", False)),
            ValueError,
            "absolute URI",
        ),
        (
            _Access(endpoint=UriValue("missing-scheme", True)),
            ValueError,
            "valid scheme",
        ),
    )

    # Endpoint failures remain separate from transport scheme selection: valid
    # custom schemes pass, while missing or relative schemes fail here.
    for access, exception_type, message in invalid_accesses:
        _assert_raises(
            exception_type,
            lambda access=access: validate_service_access(access),
            message,
        )


def test_service_access_validator_checks_authorization_kind() -> None:
    """Verify authorization stays opaque while handler identity remains valid."""
    invalid_authorizations: tuple[
        tuple[Authorization, type[BaseException], str], ...
    ] = (
        (cast(Authorization, object()), TypeError, "authorization"),
        (
            _Authorization(cast(OpenIdentifier, "authorization.custom")),
            TypeError,
            "authorization kind",
        ),
        (
            _Authorization(OpenIdentifier("Invalid Authorization")),
            ValueError,
            "OpenIdentifier",
        ),
    )

    # The validator reads no credentials; it only verifies structural membership
    # and the portable open identifier used by a future handler resolver.
    for authorization, exception_type, message in invalid_authorizations:
        _assert_raises(
            exception_type,
            lambda authorization=authorization: validate_service_access(
                _Access(authorization=authorization)
            ),
            message,
        )


def test_service_access_validator_checks_header_context() -> None:
    """Verify ordinary headers use token names and injection-safe values."""
    invalid_headers = (
        Headers((HeaderField("Invalid Header", "value"),)),
        Headers((HeaderField("Invalid:Header", "value"),)),
        Headers((HeaderField("X-Value", "line-one\r\nline-two"),)),
    )

    # Ordinary caller headers are validated before transport; authorization
    # headers are generated later through their dedicated handler boundary.
    for headers in invalid_headers:
        _assert_raises(
            ValueError,
            lambda headers=headers: validate_service_access(_Access(headers=headers)),
            "header",
        )


def test_service_access_validator_checks_collections_and_context_types() -> None:
    """Verify nominal collections and optional provider context field types."""
    invalid_accesses = (
        _Access(headers=cast(Headers, ())),
        _Access(query=cast(QueryParameters, ())),
        _Access(api_version=cast(str, 1)),
        _Access(project_id=cast(str, 1)),
        _Access(tenant_id=cast(str, 1)),
    )

    # Each dimension fails independently so diagnostics identify the exact
    # configuration boundary rather than deferring the error to transport.
    for access in invalid_accesses:
        _assert_raises(
            TypeError,
            lambda access=access: validate_service_access(access),
            "ServiceAccess",
        )


def test_service_access_validator_checks_portable_extensions() -> None:
    """Verify extension keys and recursive JSON numbers remain portable."""
    invalid_extensions: tuple[tuple[Extensions, type[BaseException], str], ...] = (
        (cast(Extensions, {1: "value"}), TypeError, "keys must be strings"),
        ({"future": math.inf}, ValueError, "must be finite"),
    )

    # Unknown access fields remain uninterpreted, but invalid keys and non-finite
    # numbers cannot proceed into configuration snapshots or I/O.
    for extensions, exception_type, message in invalid_extensions:
        _assert_raises(
            exception_type,
            lambda extensions=extensions: validate_service_access(
                _Access(extensions=extensions)
            ),
            message,
        )

"""Structural boundary tests for the open ServiceAccess protocol."""

from dataclasses import dataclass, field

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
)


def _empty_extensions() -> Extensions:
    """Create a typed empty access extension mapping for test defaults."""
    # A factory avoids sharing a mutable dictionary between otherwise immutable
    # test records while retaining the public read-only mapping type.
    return {}


@dataclass(frozen=True, slots=True)
class _CustomAuthorization:
    """Represent an application-defined authorization mechanism."""

    kind: OpenIdentifier


@dataclass(frozen=True, slots=True)
class _CustomServiceAccess:
    """Custom access input proving no SDK concrete base type is required."""

    endpoint: UriValue | None
    authorization: Authorization | None
    headers: Headers
    query: QueryParameters
    api_version: str | None = None
    project_id: str | None = None
    tenant_id: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


def test_service_access_keeps_access_dimensions_separate() -> None:
    """Verify endpoint, authorization, headers, query, and context stay distinct."""
    authorization = _CustomAuthorization(
        OpenIdentifier("authorization.vendor_signature")
    )
    access = _CustomServiceAccess(
        endpoint=UriValue("https://models.example.test/v1", is_absolute=True),
        authorization=authorization,
        headers=Headers((HeaderField("X-Feature", "enabled"),)),
        query=QueryParameters((QueryParameter("region", "east"),)),
        api_version="2026-10-01",
        project_id="project-a",
        tenant_id="tenant-a",
        extensions={"futureAccessOption": True},
    )

    # Structural recognition retains the application-owned object while every
    # access dimension remains independently observable and unmerged.
    assert isinstance(access, ServiceAccess)
    assert access.endpoint == UriValue(
        "https://models.example.test/v1", is_absolute=True
    )
    assert access.authorization is authorization
    assert access.headers.get_all("x-feature") == ("enabled",)
    assert access.query.values == (QueryParameter("region", "east"),)
    assert access.api_version == "2026-10-01"
    assert access.project_id == "project-a"
    assert access.tenant_id == "tenant-a"
    assert access.extensions == {"futureAccessOption": True}


def test_service_access_allows_unresolved_optional_fields() -> None:
    """Verify unresolved input can omit endpoint, authorization, and context."""
    access = _CustomServiceAccess(
        endpoint=None,
        authorization=None,
        headers=Headers(),
        query=QueryParameters(),
    )

    # None is meaningful only before resolution; required collection properties
    # remain present as explicit empty immutable values.
    assert isinstance(access, ServiceAccess)
    assert access.endpoint is None
    assert access.authorization is None
    assert access.headers.values == ()
    assert access.query.values == ()
    assert access.api_version is None
    assert access.project_id is None
    assert access.tenant_id is None


def test_service_access_requires_the_complete_property_surface() -> None:
    """Verify endpoint and authorization alone cannot satisfy the protocol."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteServiceAccess:
        """Intentionally omit collections, context, and extension properties."""

        endpoint: UriValue | None
        authorization: Authorization | None

    # Optional values may be None, but all properties are required so resolvers
    # receive one stable structural shape from every custom implementation.
    incomplete = _IncompleteServiceAccess(endpoint=None, authorization=None)
    assert not isinstance(incomplete, ServiceAccess)

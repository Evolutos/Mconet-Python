"""Configured outcome tests for StubServiceAccessResolver."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import cast, get_type_hints

from mconet.core.domain import (
    Headers,
    OpenIdentifier,
    QueryParameters,
    ResolvedServiceAccess,
    ServiceAccess,
    UriValue,
)
from mconet.core.spi import ComponentDescriptor, ServiceAccessResolver
from mconet.testing import StubServiceAccessResolver


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization fixture retained by resolved access."""

    kind: OpenIdentifier
    """Non-sensitive handler-selection discriminator."""


def _resolved_access() -> ResolvedServiceAccess:
    """Build one complete immutable configured access snapshot."""
    # Every field is explicit so the Stub cannot hide unresolved inheritance or
    # an absent authorization decision behind constructor defaults.
    return ResolvedServiceAccess(
        endpoint=UriValue("https://resolved.models.example.test", True),
        authorization=_Authorization(OpenIdentifier("authorization.resolved")),
        headers=Headers(),
        query=QueryParameters(),
        api_version="version-resolved",
        project_id="project-resolved",
        tenant_id="tenant-resolved",
        extensions={"source": "resolved"},
    )


def _sources() -> tuple[
    ServiceAccess,
    ServiceAccess,
    ServiceAccess,
    ServiceAccess,
]:
    """Create four distinct typed source sentinels for Stub calls."""
    # A fixed-result Stub must not read source properties. Distinct sentinels
    # prove callers may still supply the complete ordered protocol argument set.
    return (
        cast(ServiceAccess, object()),
        cast(ServiceAccess, object()),
        cast(ServiceAccess, object()),
        cast(ServiceAccess, object()),
    )


def _resolve(stub: StubServiceAccessResolver) -> ResolvedServiceAccess:
    """Invoke one Stub with all four ordered access source positions."""
    interaction, request, client, protocol = _sources()
    # The helper keeps success and failure tests on the same exact public call
    # shape without introducing an unrelated field-merging implementation.
    return stub.resolve(interaction, request, client, protocol)


def _assert_raises_identity(
    stub: StubServiceAccessResolver,
    expected: BaseException,
) -> None:
    """Require one resolution call to raise the exact configured failure."""
    try:
        _resolve(stub)
    except BaseException as error:
        # Identity proves the Stub neither wraps the configuration failure nor
        # replaces it with authorization, endpoint, or fallback diagnostics.
        assert error is expected
        return
    raise AssertionError(f"Expected {type(expected).__name__} to be raised.")


def test_stub_structurally_implements_service_access_resolver() -> None:
    """Expose complete resolution behavior without inheritance or registration."""
    stub = StubServiceAccessResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        _resolved_access(),
    )

    accepted: ServiceAccessResolver = stub

    # Static and runtime recognition agree on the same ordinary object and its
    # descriptor, without a component ID, SDK base class, or provider subtype.
    assert accepted is stub
    assert isinstance(stub, ServiceAccessResolver)
    assert stub.descriptor.name == "Stub resolver"


def test_stub_returns_exact_resolved_access() -> None:
    """Preserve the complete configured snapshot and nested value identities."""
    expected = _resolved_access()
    stub = StubServiceAccessResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        expected,
    )

    result = _resolve(stub)

    # The prebuilt immutable snapshot crosses unchanged; no source merge,
    # endpoint normalization, or authorization reconstruction occurs.
    assert result is expected
    assert result.endpoint is expected.endpoint
    assert result.authorization is expected.authorization
    assert result.headers is expected.headers
    assert result.query is expected.query


def test_stub_accepts_all_absent_sources_for_a_configured_result() -> None:
    """Allow a fixture to model an already completed result from no sources."""
    expected = _resolved_access()
    stub = StubServiceAccessResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        expected,
    )

    result = stub.resolve(None, None, None, None)

    # None retains source absence at the call boundary. The Stub does not invent
    # empty layers or require a concrete source when a result is preconfigured.
    assert result is expected


def test_stub_raises_exact_configured_failure() -> None:
    """Reject resolution without returning a partial or fallback snapshot."""
    failure = ValueError("service access is incomplete")
    stub = StubServiceAccessResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        _resolved_access(),
        error=failure,
    )

    _assert_raises_identity(stub, failure)

    # Repeated calls retain the same deterministic exception object and never
    # degrade into a cached partial result after the first failure.
    _assert_raises_identity(stub, failure)


def test_stub_validates_configuration_eagerly() -> None:
    """Reject malformed metadata, result, and failure configuration."""
    descriptor = ComponentDescriptor("Stub resolver", "1", "application")
    result = _resolved_access()
    invalid_calls = (
        (
            lambda: StubServiceAccessResolver(
                cast(ComponentDescriptor, object()), result
            ),
            "descriptor must be a ComponentDescriptor",
        ),
        (
            lambda: StubServiceAccessResolver(
                descriptor,
                cast(ResolvedServiceAccess, object()),
            ),
            "result must be a ResolvedServiceAccess",
        ),
        (
            lambda: StubServiceAccessResolver(
                descriptor,
                result,
                error=cast(BaseException, "failure"),
            ),
            "error must be a BaseException or None",
        ),
    )

    for action, message in invalid_calls:
        try:
            action()
        except TypeError as error:
            # Field-specific diagnostics distinguish malformed Stub setup from
            # the access-resolution failure that a scenario intends to test.
            assert message in str(error)
        else:
            raise AssertionError("Expected invalid Stub configuration to fail.")


def test_stub_matches_resolver_surface_without_adjacent_controls() -> None:
    """Expose the exact resolver method without merge or execution behavior."""
    stub = StubServiceAccessResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        _resolved_access(),
    )
    method = StubServiceAccessResolver.resolve
    annotations = get_type_hints(method)

    # The concrete synchronous method retains all four priority positions while
    # returning only the complete post-resolution nominal value.
    assert tuple(inspect.signature(method).parameters) == (
        "self",
        "interaction_override",
        "request_service_access",
        "client_default_service_access",
        "protocol_default_service_access",
    )
    assert annotations == {
        "interaction_override": ServiceAccess | None,
        "request_service_access": ServiceAccess | None,
        "client_default_service_access": ServiceAccess | None,
        "protocol_default_service_access": ServiceAccess | None,
        "return": ResolvedServiceAccess,
    }
    assert not inspect.iscoroutinefunction(method)

    # No generic recorder, source merge, credential access, authorization,
    # transport, registry, or dynamic configuration belongs to this Stub.
    for forbidden_member in (
        "calls",
        "configure",
        "reset",
        "merge",
        "read_credential",
        "resolve_credential",
        "authorize",
        "mutate_request",
        "send",
        "register",
    ):
        assert not hasattr(stub, forbidden_member)

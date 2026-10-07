"""Structural and responsibility tests for the service access resolver contract."""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import get_type_hints

from mconet.core.domain import (
    Authorization,
    Extensions,
    Headers,
    OpenIdentifier,
    QueryParameters,
    ResolvedServiceAccess,
    ServiceAccess,
    UriValue,
)
from mconet.core.spi import ComponentDescriptor, ServiceAccessResolver


def _empty_extensions() -> Extensions:
    """Create independent portable storage for access fixtures."""
    # Fresh mappings avoid coupling fixture instances before a resolver observes
    # their complete original source layers.
    return {}


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization fixture retained as one atomic value."""

    kind: OpenIdentifier
    """Non-sensitive handler-selection discriminator."""


@dataclass(frozen=True, slots=True)
class _Access:
    """Complete ordinary structural ServiceAccess implementation."""

    endpoint: UriValue | None
    """Optional endpoint supplied by this configuration layer."""

    authorization: Authorization | None
    """Optional opaque authorization supplied as one atomic value."""

    headers: Headers
    """Ordered non-sensitive header context for this layer."""

    query: QueryParameters
    """Ordered non-sensitive query context for this layer."""

    api_version: str | None = None
    """Optional API version supplied by this layer."""

    project_id: str | None = None
    """Optional project identifier supplied by this layer."""

    tenant_id: str | None = None
    """Optional tenant identifier supplied by this layer."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Portable provider-specific access facts."""


class _Resolver:
    """Ordinary configurable resolver implementation used by contract tests."""

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        result: ResolvedServiceAccess,
    ) -> None:
        """Store component metadata, exact result, and an empty call record."""
        # A prebuilt result isolates the abstract contract from the later default
        # field-merging algorithm while retaining every input for verification.
        self.descriptor = descriptor
        self.result = result
        self.calls: list[
            tuple[
                ServiceAccess | None,
                ServiceAccess | None,
                ServiceAccess | None,
                ServiceAccess | None,
            ]
        ] = []

    def resolve(
        self,
        interaction_override: ServiceAccess | None,
        request_service_access: ServiceAccess | None,
        client_default_service_access: ServiceAccess | None,
        protocol_default_service_access: ServiceAccess | None,
    ) -> ResolvedServiceAccess:
        """Record all ordered sources and return the configured snapshot."""
        # Recording references only proves resolution requires no network,
        # credential access, source mutation, authorization, or transport stage.
        self.calls.append(
            (
                interaction_override,
                request_service_access,
                client_default_service_access,
                protocol_default_service_access,
            )
        )
        return self.result


class _ResolutionFailure(ValueError):
    """Represent one exact access configuration failure in contract tests."""


class _FailingResolver:
    """Ordinary resolver that propagates one configured synchronous failure."""

    descriptor = ComponentDescriptor("Failing resolver", "1.0.0", "application")
    """Valid metadata keeps the failure focused on resolution behavior."""

    def __init__(self, failure: _ResolutionFailure) -> None:
        """Store the exact configuration error to raise."""
        # Exception identity exposes wrapping, fallback, or hidden side effects.
        self.failure = failure

    def resolve(
        self,
        interaction_override: ServiceAccess | None,
        request_service_access: ServiceAccess | None,
        client_default_service_access: ServiceAccess | None,
        protocol_default_service_access: ServiceAccess | None,
    ) -> ResolvedServiceAccess:
        """Reject the complete source set without producing a partial snapshot."""
        # Every source is accepted before failure, but none is mutated or used to
        # perform I/O while the resolver reports its deterministic error.
        del (
            interaction_override,
            request_service_access,
            client_default_service_access,
            protocol_default_service_access,
        )
        raise self.failure


class _IncompleteResolver:
    """Component-shaped fixture intentionally missing access resolution."""

    descriptor = ComponentDescriptor("Incomplete", "1.0.0", "application")
    """Valid metadata isolates absence of the required resolve method."""


def _source(label: str) -> _Access:
    """Build one complete unresolved access layer with distinct safe fields."""
    # Distinct non-sensitive values make source order observable without placing
    # credential material in Headers, Query, Extensions, or debug output.
    return _Access(
        endpoint=UriValue(f"https://{label}.models.example.test", True),
        authorization=_Authorization(OpenIdentifier(f"authorization.{label}")),
        headers=Headers(),
        query=QueryParameters(),
        api_version=f"version-{label}",
        project_id=f"project-{label}",
        tenant_id=f"tenant-{label}",
        extensions={"source": label},
    )


def _resolved_access() -> ResolvedServiceAccess:
    """Build one complete immutable resolved access snapshot."""
    # Every constructor field is explicit so returning this value cannot hide
    # unresolved inheritance or a missing authorization decision.
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


def _accept_resolver(resolver: ServiceAccessResolver) -> ServiceAccessResolver:
    """Return a resolver after crossing the statically checked protocol boundary."""
    # Pyright verifies the ordinary implementation without inheritance,
    # registration, a component ID, or provider-specific access subclasses.
    return resolver


def test_service_access_resolver_accepts_ordinary_structural_class() -> None:
    """Require only component metadata and the documented resolution method."""
    resolver = _Resolver(
        ComponentDescriptor("Fixture resolver", "1.0.0", "application"),
        _resolved_access(),
    )

    accepted = _accept_resolver(resolver)

    # Static and runtime conformance agree without an SDK base class, lifecycle
    # API, registry lookup, or one concrete default-merging implementation.
    assert accepted is resolver
    assert isinstance(resolver, ServiceAccessResolver)
    assert resolver.descriptor.name == "Fixture resolver"


def test_service_access_resolver_preserves_source_order_and_result_identity() -> None:
    """Pass all four original layers and return the exact immutable snapshot."""
    interaction = _source("interaction")
    request = _source("request")
    client = _source("client")
    protocol = _source("protocol")
    expected = _resolved_access()
    resolver = _Resolver(
        ComponentDescriptor("Fixture resolver", "1.0.0", "application"),
        expected,
    )

    result = resolver.resolve(interaction, request, client, protocol)

    # Ordered identity checks prove Core does not collapse the layers before a
    # resolver can perform field-level selection or opaque authorization override.
    assert resolver.calls == [(interaction, request, client, protocol)]
    assert resolver.calls[0][0] is interaction
    assert resolver.calls[0][1] is request
    assert resolver.calls[0][2] is client
    assert resolver.calls[0][3] is protocol
    assert result is expected
    assert result.authorization is expected.authorization


def test_service_access_resolver_preserves_absent_layers() -> None:
    """Keep missing source layers explicit instead of inventing empty access."""
    protocol = _source("protocol")
    expected = _resolved_access()
    resolver = _Resolver(
        ComponentDescriptor("Fixture resolver", "1.0.0", "application"),
        expected,
    )

    result = resolver.resolve(None, None, None, protocol)

    # None retains source absence; only a concrete implementation decides how the
    # remaining protocol default supplies every required resolved field.
    assert resolver.calls == [(None, None, None, protocol)]
    assert resolver.calls[0][3] is protocol
    assert result is expected


def test_service_access_resolver_propagates_failure_without_partial_result() -> None:
    """Preserve a deterministic configuration failure and return no fallback."""
    failure = _ResolutionFailure("service access is incomplete")
    resolver = _FailingResolver(failure)

    try:
        resolver.resolve(None, None, None, None)
    except _ResolutionFailure as error:
        # Exact identity proves the protocol layer neither wraps the failure nor
        # invents a default authorization, endpoint, or partial resolved value.
        assert error is failure
    else:
        raise AssertionError("Expected service access resolution failure.")


def test_service_access_resolver_has_exact_synchronous_method_surface() -> None:
    """Lock the method name, source order, result, and synchronous semantics."""
    method = ServiceAccessResolver.resolve
    annotations = get_type_hints(method)

    # Four independent optional layers are required for per-field merging; no
    # credential, network, request body, transport, or registry input is present.
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


def test_service_access_resolver_requires_complete_behavior_surface() -> None:
    """Reject component metadata when access resolution is absent."""
    incomplete = _IncompleteResolver()

    # Descriptor conformance cannot substitute for the complete resolve method.
    assert not isinstance(incomplete, ServiceAccessResolver)


def test_service_access_resolver_excludes_external_side_effects() -> None:
    """Keep credentials, authorization application, and I/O out of the SPI."""
    resolver = _Resolver(
        ComponentDescriptor("Fixture resolver", "1.0.0", "application"),
        _resolved_access(),
    )

    # The protocol exposes pure resolution only. Negative checks prevent future
    # implementations from absorbing adjacent authorization or transport stages.
    for forbidden_member in (
        "read_credential",
        "resolve_credential",
        "authorize",
        "mutate_request",
        "send",
        "fetch",
        "register",
    ):
        assert not hasattr(resolver, forbidden_member)

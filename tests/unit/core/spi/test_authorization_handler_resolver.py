"""Structural and outcome tests for authorization handler resolution."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import get_type_hints

from mconet.core.domain import (
    Authorization,
    ErrorCategory,
    InteractionPhase,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.core.spi import (
    AuthorizationContext,
    AuthorizationHandler,
    AuthorizationHandlerResolver,
    BodySigningMode,
    BodySigningRequirement,
    ComponentDescriptor,
    MutableTransportRequest,
    ResolvedAuthorizationHandler,
)


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization fixture used only for handler selection."""

    kind: OpenIdentifier
    """Non-sensitive discriminator visible to compatible handlers."""


class _Handler:
    """Ordinary complete authorization handler candidate."""

    def __init__(self, name: str) -> None:
        """Create valid immutable component metadata for one candidate."""
        # Distinct names make candidate identity and order observable while the
        # no-op behavior keeps resolver tests independent from authorization.
        self.descriptor = ComponentDescriptor(name, "1.0.0", "application")

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Report canonical no-signing support for resolver fixtures."""
        # Resolver contract tests configure outcomes directly, so candidate
        # behavior only establishes the complete structural handler boundary.
        del authorization, body_signing_requirement
        return frozenset(("none",))

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Provide complete no-op application behavior for structural checks."""
        # Resolution never invokes apply; accepting the inputs prevents a
        # descriptor-only component from entering the candidate tuple.
        del authorization, context, request


class _Resolver:
    """Configurable structural resolver returning one exact selection."""

    descriptor = ComponentDescriptor("Fixture resolver", "1.0.0", "application")
    """Stable metadata proving the fixture is a runtime component."""

    def __init__(self, result: ResolvedAuthorizationHandler) -> None:
        """Store the result and initialize an ordered invocation record."""
        # A prebuilt result isolates the abstract selection contract from the
        # later concrete matching algorithm and authentication implementations.
        self.result = result
        self.calls: list[
            tuple[
                Authorization,
                BodySigningRequirement,
                tuple[AuthorizationHandler, ...],
            ]
        ] = []

    def resolve(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
        handlers: tuple[AuthorizationHandler, ...],
    ) -> ResolvedAuthorizationHandler:
        """Record the closed candidate set and return the configured selection."""
        # Exact references expose hidden candidate replacement, order-based
        # filtering, or mutation before the resolver makes its unique decision.
        self.calls.append((authorization, body_signing_requirement, handlers))
        return self.result


class _FailingResolver:
    """Structural resolver propagating one configured selection failure."""

    descriptor = ComponentDescriptor("Failing resolver", "1.0.0", "application")
    """Valid metadata keeps each failure focused on resolution semantics."""

    def __init__(self, failure: ModelInteractionError) -> None:
        """Store the exact normalized error produced by resolution."""
        # Error identity makes fallback selection, wrapping, or retries visible.
        self.failure = failure

    def resolve(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
        handlers: tuple[AuthorizationHandler, ...],
    ) -> ResolvedAuthorizationHandler:
        """Reject the complete candidate set without returning a fallback."""
        # Inputs are accepted as a single decision context but never used to
        # reveal credentials, mutate requests, or perform an external effect.
        del authorization, body_signing_requirement, handlers
        raise self.failure


class _IncompleteResolver:
    """Component-shaped fixture intentionally missing handler resolution."""

    descriptor = ComponentDescriptor("Incomplete", "1.0.0", "application")
    """Valid metadata isolates absence of the required resolve method."""


def _authorization() -> _Authorization:
    """Build one opaque authorization value with no exposed credential data."""
    # Selection observes only the open kind; concrete secret-bearing fields are
    # deliberately absent from the resolver contract fixture.
    return _Authorization(OpenIdentifier("authorization.fixture"))


def _resolution_error(code: str) -> ModelInteractionError:
    """Build one normalized pre-interaction handler resolution failure."""
    # Shared category and phase keep the assertions focused on the distinct
    # stable branch code and exact exception propagation.
    return ModelInteractionError(
        ErrorCategory(OpenIdentifier("authentication")),
        InteractionPhase(OpenIdentifier("authorization_resolution")),
        code,
        "Authorization handler resolution failed.",
    )


def _accept_resolver(
    resolver: AuthorizationHandlerResolver,
) -> AuthorizationHandlerResolver:
    """Return a resolver after crossing the statically checked protocol boundary."""
    # Pyright verifies ordinary structural implementation without inheritance,
    # registration, component IDs, or one prescribed selection algorithm.
    return resolver


def test_authorization_handler_resolver_accepts_structural_class() -> None:
    """Require only component metadata and synchronous resolution behavior."""
    handler = _Handler("Only handler")
    resolver = _Resolver(ResolvedAuthorizationHandler(handler, "none"))

    accepted = _accept_resolver(resolver)

    # Static and runtime conformance agree for an ordinary user implementation.
    assert accepted is resolver
    assert isinstance(resolver, AuthorizationHandlerResolver)
    assert resolver.descriptor.name == "Fixture resolver"


def test_authorization_handler_resolver_preserves_inputs_and_result() -> None:
    """Pass the closed candidate tuple and return the exact unique selection."""
    authorization = _authorization()
    requirement = BodySigningRequirement()
    first = _Handler("First handler")
    selected = _Handler("Selected handler")
    handlers: tuple[AuthorizationHandler, ...] = (first, selected)
    expected = ResolvedAuthorizationHandler(selected, "none")
    resolver = _Resolver(expected)

    result = resolver.resolve(authorization, requirement, handlers)

    # Identity checks prove no input is reconstructed, reordered, or replaced
    # before resolution and the selected pair is returned without copying.
    assert resolver.calls == [(authorization, requirement, handlers)]
    assert resolver.calls[0][0] is authorization
    assert resolver.calls[0][1] is requirement
    assert resolver.calls[0][2] is handlers
    assert result is expected
    assert result.handler is selected


def test_authorization_handler_resolver_propagates_no_match_failure() -> None:
    """Reject zero compatible candidates without inventing a default handler."""
    failure = _resolution_error("unsupported_authorization")
    resolver = _FailingResolver(failure)

    try:
        resolver.resolve(_authorization(), BodySigningRequirement(), ())
    except ModelInteractionError as error:
        # Exact identity and code prove absence remains a stable configuration
        # failure rather than triggering a registry lookup or fallback handler.
        assert error is failure
        assert error.code == "unsupported_authorization"
    else:
        raise AssertionError("Expected unsupported authorization failure.")


def test_authorization_handler_resolver_propagates_ambiguity_failure() -> None:
    """Reject multiple compatible candidates without tuple-order selection."""
    failure = _resolution_error("ambiguous_authorization_handler")
    first = _Handler("First handler")
    second = _Handler("Second handler")
    resolver = _FailingResolver(failure)

    try:
        resolver.resolve(
            _authorization(),
            BodySigningRequirement(),
            (first, second),
        )
    except ModelInteractionError as error:
        # Preserving the exact ambiguity proves neither the first nor last
        # candidate wins through an undocumented ordering convention.
        assert error is failure
        assert error.code == "ambiguous_authorization_handler"
    else:
        raise AssertionError("Expected ambiguous authorization handler failure.")


def test_authorization_handler_resolver_has_exact_method_surface() -> None:
    """Lock input order, immutable candidates, result, and sync semantics."""
    method = AuthorizationHandlerResolver.resolve
    annotations = get_type_hints(method)

    # The surface contains only opaque selection facts and excludes credentials,
    # mutable requests, network contexts, registries, and asynchronous effects.
    assert tuple(inspect.signature(method).parameters) == (
        "self",
        "authorization",
        "body_signing_requirement",
        "handlers",
    )
    assert annotations == {
        "authorization": Authorization,
        "body_signing_requirement": BodySigningRequirement,
        "handlers": tuple[AuthorizationHandler, ...],
        "return": ResolvedAuthorizationHandler,
    }
    assert not inspect.iscoroutinefunction(method)


def test_authorization_handler_resolver_requires_complete_surface() -> None:
    """Reject component metadata without the selection operation."""
    incomplete = _IncompleteResolver()

    # Runtime component conformance alone cannot satisfy handler resolution.
    assert not isinstance(incomplete, AuthorizationHandlerResolver)


def test_authorization_handler_resolver_excludes_external_side_effects() -> None:
    """Keep credential access, request mutation, and transport out of the SPI."""
    handler = _Handler("Only handler")
    resolver = _Resolver(ResolvedAuthorizationHandler(handler, "none"))

    # Negative checks preserve the resolver as a deterministic selection stage.
    for forbidden_member in (
        "reveal",
        "resolve_credential",
        "authorize",
        "mutate_request",
        "send",
        "fetch",
        "register",
    ):
        assert not hasattr(resolver, forbidden_member)

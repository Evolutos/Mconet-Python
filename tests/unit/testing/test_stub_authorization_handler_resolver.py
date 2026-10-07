"""Configured outcome tests for StubAuthorizationHandlerResolver."""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import cast, get_type_hints

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
from mconet.testing import StubAuthorizationHandlerResolver


@dataclass(frozen=True, slots=True)
class _Authorization:
    """Opaque authorization fixture used only at the resolver boundary."""

    kind: OpenIdentifier
    """Non-sensitive handler-selection discriminator."""


class _Handler:
    """Complete no-op authorization handler used by configured selections."""

    def __init__(self, name: str) -> None:
        """Create valid immutable component metadata for one candidate."""
        # Distinct diagnostic names make handler identity observable without
        # introducing credentials, registration, or provider-specific behavior.
        self.descriptor = ComponentDescriptor(name, "1", "application")

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Declare canonical no-signing support for structural conformance."""
        # The Stub does not invoke compatibility behavior; the method only makes
        # this ordinary fixture a complete AuthorizationHandler candidate.
        del authorization, body_signing_requirement
        return frozenset(("none",))

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Provide complete no-op asynchronous authorization behavior."""
        # Handler application belongs to the next test-double work item. These
        # arguments are deliberately accepted without reading secrets or mutation.
        del authorization, context, request


def _authorization() -> _Authorization:
    """Build one opaque authorization value with no credential material."""
    # Resolver fixtures need only the open non-sensitive kind discriminator.
    return _Authorization(OpenIdentifier("authorization.fixture"))


def _selection(handler: AuthorizationHandler) -> ResolvedAuthorizationHandler:
    """Build one unique configured handler and signing-mode outcome."""
    # The nominal result retains the exact handler and the explicit no-signing
    # mode without requiring the Stub to run compatibility selection.
    return ResolvedAuthorizationHandler(handler, "none")


def _resolution_error(code: str) -> ModelInteractionError:
    """Build one normalized pre-interaction selection failure."""
    # Missing and ambiguous branches share safe authentication ownership while
    # their stable codes remain independently observable.
    return ModelInteractionError(
        ErrorCategory(OpenIdentifier("authentication")),
        InteractionPhase(OpenIdentifier("authorization_resolution")),
        code,
        "Authorization handler resolution failed.",
    )


def _resolve(
    stub: StubAuthorizationHandlerResolver,
    handlers: tuple[AuthorizationHandler, ...],
) -> ResolvedAuthorizationHandler:
    """Invoke one Stub with a complete selection input tuple."""
    # A fresh requirement and opaque authorization exercise the exact protocol
    # surface while the predetermined Stub avoids a duplicate matching algorithm.
    return stub.resolve(_authorization(), BodySigningRequirement(), handlers)


def _assert_raises_identity(
    stub: StubAuthorizationHandlerResolver,
    handlers: tuple[AuthorizationHandler, ...],
    expected: BaseException,
) -> None:
    """Require one selection call to raise the exact configured failure."""
    try:
        _resolve(stub, handlers)
    except BaseException as error:
        # Identity proves the Stub neither wraps normalized selection errors nor
        # replaces them with fallback or candidate-order decisions.
        assert error is expected
        return
    raise AssertionError(f"Expected {type(expected).__name__} to be raised.")


def test_stub_structurally_implements_authorization_handler_resolver() -> None:
    """Expose complete selection behavior without inheritance or registration."""
    handler = _Handler("Selected handler")
    stub = StubAuthorizationHandlerResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        _selection(handler),
    )

    accepted: AuthorizationHandlerResolver = stub

    # Static and runtime recognition agree on the same ordinary object and its
    # descriptor, without a component ID, base class, or candidate registry.
    assert accepted is stub
    assert isinstance(stub, AuthorizationHandlerResolver)
    assert stub.descriptor.name == "Stub resolver"


def test_stub_returns_exact_unique_selection() -> None:
    """Preserve the configured handler, signing mode, and result identity."""
    first = _Handler("First handler")
    selected = _Handler("Selected handler")
    handlers: tuple[AuthorizationHandler, ...] = (first, selected)
    expected = _selection(selected)
    stub = StubAuthorizationHandlerResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        expected,
    )

    result = _resolve(stub, handlers)

    # The prebuilt selection crosses unchanged; the Stub neither scans candidates
    # nor reconstructs the exact selected handler or signing mode.
    assert result is expected
    assert result.handler is selected
    assert result.body_signing_mode == "none"


def test_stub_raises_exact_missing_handler_failure() -> None:
    """Configure zero compatible candidates without inventing a default."""
    selected = _Handler("Unused configured handler")
    failure = _resolution_error("unsupported_authorization")
    stub = StubAuthorizationHandlerResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        _selection(selected),
        error=failure,
    )

    _assert_raises_identity(stub, (), failure)

    # The stable normalized code remains exactly as configured, and the unused
    # success selection never escapes as a fallback.
    assert failure.code == "unsupported_authorization"


def test_stub_raises_exact_ambiguous_handler_failure() -> None:
    """Configure multiple compatible candidates without tuple-order selection."""
    first = _Handler("First handler")
    second = _Handler("Second handler")
    failure = _resolution_error("ambiguous_authorization_handler")
    stub = StubAuthorizationHandlerResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        _selection(first),
        error=failure,
    )

    _assert_raises_identity(stub, (first, second), failure)

    # Ambiguity remains observable rather than selecting the first or last
    # candidate through an undocumented ordering convention.
    assert failure.code == "ambiguous_authorization_handler"


def test_stub_validates_configuration_eagerly() -> None:
    """Reject malformed metadata, result, and failure configuration."""
    descriptor = ComponentDescriptor("Stub resolver", "1", "application")
    result = _selection(_Handler("Selected handler"))
    invalid_calls = (
        (
            lambda: StubAuthorizationHandlerResolver(
                cast(ComponentDescriptor, object()),
                result,
            ),
            "descriptor must be a ComponentDescriptor",
        ),
        (
            lambda: StubAuthorizationHandlerResolver(
                descriptor,
                cast(ResolvedAuthorizationHandler, object()),
            ),
            "result must be a ResolvedAuthorizationHandler",
        ),
        (
            lambda: StubAuthorizationHandlerResolver(
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
            # Field-specific diagnostics separate malformed Stub setup from the
            # handler-selection failure that a scenario intends to exercise.
            assert message in str(error)
        else:
            raise AssertionError("Expected invalid Stub configuration to fail.")


def test_stub_matches_resolver_surface_without_adjacent_controls() -> None:
    """Expose the exact resolver method without selection or apply behavior."""
    handler = _Handler("Selected handler")
    stub = StubAuthorizationHandlerResolver(
        ComponentDescriptor("Stub resolver", "1", "application"),
        _selection(handler),
    )
    method = StubAuthorizationHandlerResolver.resolve
    annotations = get_type_hints(method)

    # The concrete synchronous signature accepts only opaque selection facts and
    # returns the complete nominal handler-plus-signing-mode result.
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

    # No generic recorder, matching algorithm, credential access, request
    # mutation, handler application, transport, registry, or reconfiguration.
    for forbidden_member in (
        "calls",
        "configure",
        "reset",
        "match",
        "supports",
        "reveal",
        "resolve_credential",
        "authorize",
        "apply",
        "send",
        "register",
    ):
        assert not hasattr(stub, forbidden_member)

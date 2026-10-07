"""Selection boundary tests for immutable resolved authorization handlers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import FrozenInstanceError, dataclass, fields
from typing import cast

from mconet.core.domain import Authorization, OpenIdentifier
from mconet.core.spi import (
    AuthorizationContext,
    AuthorizationHandler,
    BodySigningMode,
    BodySigningRequirement,
    ComponentDescriptor,
    MutableTransportRequest,
    ResolvedAuthorizationHandler,
)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise one expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # Match result-owned wording so malformed fixture setup cannot satisfy
        # an unrelated handler or mode boundary assertion accidentally.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Handler:
    """Concrete selected component fixture with stable handler metadata."""

    descriptor: ComponentDescriptor
    """Immutable component metadata exposed through AuthorizationHandler."""

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Report canonical support for complete handler conformance."""
        # Selection-result tests configure the chosen mode directly; this method
        # proves the stored component has executable matching behavior.
        del authorization, body_signing_requirement
        return frozenset(("none",))

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Provide no-op application behavior for selection-result fixtures."""
        # Result validation must retain a complete Handler even though these
        # immutable-value tests never execute request authorization.
        del authorization, context, request


@dataclass(frozen=True, slots=True)
class _MalformedHandler:
    """Structurally component-shaped fixture returning invalid metadata."""

    descriptor: object
    """Invalid dynamic descriptor used to test the nominal metadata boundary."""

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Expose valid matching behavior beside malformed metadata."""
        # Complete behavior isolates the descriptor validation branch.
        del authorization, body_signing_requirement
        return frozenset(("none",))

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Expose valid application behavior beside malformed metadata."""
        # No request mutation is required to test metadata rejection.
        del authorization, context, request


def _handler(name: str = "Bearer authorization handler") -> _Handler:
    """Build one distinguishable concrete authorization component fixture."""
    # Diagnostic identity and capability facts make it observable that the
    # result retains the exact instance rather than rebuilding a descriptor.
    return _Handler(
        ComponentDescriptor(
            name=name,
            version="1.0.0",
            source="builtin",
            capabilities=frozenset((OpenIdentifier("authorization.bearer"),)),
        )
    )


def test_resolved_authorization_handler_preserves_exact_selection() -> None:
    """Retain the selected component and signing mode without reconstruction."""
    handler = _handler()

    result = ResolvedAuthorizationHandler(handler, "precomputed_digest")

    # Handler identity carries its future behavior implementation, while the
    # exact mode is the sole signing decision passed to authorization apply.
    assert result.handler is handler
    assert result.handler.descriptor is handler.descriptor
    assert result.body_signing_mode == "precomputed_digest"


def test_resolved_authorization_handler_accepts_every_defined_mode() -> None:
    """Preserve every closed signing mode without fallback or normalization."""
    handler = _handler()
    modes: tuple[BodySigningMode, ...] = (
        "none",
        "precomputed_digest",
        "unsigned_payload",
        "buffered_digest",
        "chunked_signature",
    )

    # Mode availability is resolver and release-policy work. The result value
    # faithfully records any architecture-defined mode selected before creation.
    results = tuple(ResolvedAuthorizationHandler(handler, mode) for mode in modes)
    assert tuple(result.body_signing_mode for result in results) == modes


def test_resolved_authorization_handler_has_exact_frozen_value_surface() -> None:
    """Expose only the selected pair and reject either value being replaced."""
    handler = _handler()
    first = ResolvedAuthorizationHandler(handler, "none")
    same = ResolvedAuthorizationHandler(handler, "none")
    different = ResolvedAuthorizationHandler(handler, "unsigned_payload")

    # Equality contains no candidate order or resolver state, and frozen fields
    # prevent a later stage from changing the decision after credential access.
    assert first == same
    assert first != different
    assert tuple(field.name for field in fields(ResolvedAuthorizationHandler)) == (
        "handler",
        "body_signing_mode",
    )
    assert not hasattr(first, "handler_id")
    assert not hasattr(first, "candidates")
    assert not hasattr(first, "authorization")
    assert not hasattr(first, "context")
    assert not hasattr(first, "request")
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("handler", _handler("replacement")),
        "cannot assign to field",
    )


def test_resolved_authorization_handler_requires_concrete_component() -> None:
    """Reject names, descriptors, and arbitrary objects in place of a handler."""
    invalid_handlers: tuple[object, ...] = (
        "bearer",
        _handler().descriptor,
        object(),
        None,
    )

    # Resolution must retain the executable instance; indirect lookup values
    # could drift from the component selected against authorization and body facts.
    for invalid_handler in invalid_handlers:
        _assert_raises(
            TypeError,
            lambda invalid_handler=invalid_handler: ResolvedAuthorizationHandler(
                cast(AuthorizationHandler, invalid_handler),
                "none",
            ),
            "handler must implement AuthorizationHandler",
        )


def test_resolved_authorization_handler_requires_nominal_descriptor() -> None:
    """Reject component-shaped objects whose metadata is not a descriptor."""
    malformed = _MalformedHandler({"name": "bearer"})

    # Runtime structural recognition checks attribute presence only; the result
    # independently protects later monitoring and ownership metadata consumers.
    _assert_raises(
        TypeError,
        lambda: ResolvedAuthorizationHandler(
            cast(AuthorizationHandler, malformed),
            "none",
        ),
        "handler descriptor must be a ComponentDescriptor",
    )


def test_resolved_authorization_handler_rejects_invalid_modes() -> None:
    """Reject non-string and unknown signing decisions without downgrading."""
    handler = _handler()

    # Dynamic callers cannot use an unrecognized provider string or rely on a
    # numeric value being coerced to one of the portable closed modes.
    _assert_raises(
        TypeError,
        lambda: ResolvedAuthorizationHandler(
            handler,
            cast(BodySigningMode, 1),
        ),
        "body_signing_mode must be a string",
    )
    _assert_raises(
        ValueError,
        lambda: ResolvedAuthorizationHandler(
            handler,
            cast(BodySigningMode, "vendor_mode"),
        ),
        "body_signing_mode is unsupported",
    )

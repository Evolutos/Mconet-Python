"""Reusable assertions for AuthorizationHandler implementations."""

from __future__ import annotations

from collections.abc import Callable
from inspect import iscoroutinefunction
from typing import TypeVar, cast

from mconet.core.domain import Authorization, OpenIdentifier
from mconet.core.spi import (
    AuthorizationContext,
    AuthorizationHandler,
    BodySigningMode,
    BodySigningRequirement,
    ComponentDescriptor,
    MutableTransportRequest,
)

_BODY_SIGNING_MODES = frozenset(
    (
        "none",
        "precomputed_digest",
        "unsigned_payload",
        "buffered_digest",
        "chunked_signature",
    )
)
_ValueT = TypeVar("_ValueT")


class AuthorizationHandlerContractSuite:
    """Apply matching and bounded request-authorization contracts.

    The suite is independent of pytest, unittest, fixture formats, concrete
    authorization mechanisms, and credential storage. Callers inspect exact
    supported-mode sets, permitted request replacements, or exact apply failures
    through synchronous assertion callbacks.

    Runtime checks supplement static protocol conformance. ``supports`` must be
    synchronous and return an immutable set of defined modes; ``apply`` must be
    asynchronous, return ``None``, preserve the read-only method, and leave the
    Runtime-owned request mutation window open. Each assertion invokes one
    handler operation exactly once. The suite never reveals credentials, freezes
    or sends a request, performs network I/O, selects a handler, or retries.
    """

    __slots__ = ("_handler",)

    def __init__(self, handler: AuthorizationHandler) -> None:
        """Validate and retain one structurally conforming handler.

        Args:
            handler: Custom or SDK authorization handler under contract test.

        Raises:
            TypeError: If the object, descriptor, or operation shape violates
                the public handler boundary.
        """
        handler_value = cast(object, handler)
        if not isinstance(handler_value, AuthorizationHandler):
            raise TypeError("handler must implement AuthorizationHandler.")
        descriptor_value = cast(object, handler.descriptor)
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("handler descriptor must be a ComponentDescriptor.")

        # Compatibility matching is deterministic and side-effect-free, while
        # application may await dynamic credential acquisition inside the open
        # request window. Enforce those opposite execution shapes at setup.
        supports = handler.supports
        if iscoroutinefunction(supports) or iscoroutinefunction(
            type(supports).__call__
        ):
            raise TypeError("handler supports operation must be synchronous.")
        apply = handler.apply
        if not (
            iscoroutinefunction(apply) or iscoroutinefunction(type(apply).__call__)
        ):
            raise TypeError("handler apply operation must be asynchronous.")
        self._handler = handler

    def assert_supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
        *,
        assertion: Callable[[frozenset[BodySigningMode]], None],
    ) -> None:
        """Validate one immutable supported-mode result.

        Args:
            authorization: Exact opaque authorization value for matching.
            body_signing_requirement: Exact protocol signing constraint.
            assertion: Synchronous callback asserting compatibility facts.

        Raises:
            TypeError: If inputs, callback, or result shape is invalid.
            ValueError: If a returned mode is outside the closed vocabulary.
            BaseException: Any exact handler or assertion callback failure.
        """
        checked_assertion = _validate_assertion(assertion)
        _validate_authorization(authorization)
        requirement_value = cast(object, body_signing_requirement)
        if not isinstance(requirement_value, BodySigningRequirement):
            raise TypeError(
                "body_signing_requirement must be a BodySigningRequirement."
            )

        # Pass both identities directly and call matching once. The suite does
        # not intersect the handler's complete mode set with protocol preference.
        actual = self._handler.supports(
            authorization,
            body_signing_requirement,
        )
        actual_value = cast(object, actual)
        if not isinstance(actual_value, frozenset):
            raise TypeError("handler supports must return a frozenset.")
        for mode in cast(frozenset[object], actual_value):
            if not isinstance(mode, str):
                raise TypeError("handler supported modes must contain strings.")
            if mode not in _BODY_SIGNING_MODES:
                raise ValueError(
                    f"handler supported modes contains an unsupported mode: {mode!r}."
                )
        checked_assertion(actual)

    async def assert_apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
        *,
        assertion: Callable[[MutableTransportRequest], None],
    ) -> None:
        """Validate one successful bounded request-authorization attempt.

        Args:
            authorization: Exact opaque authorization value being applied.
            context: Exact immutable non-sensitive authorization facts.
            request: Exact open request mutation window.
            assertion: Synchronous callback inspecting permitted replacements.

        Raises:
            TypeError: If inputs or callback violate their public shapes.
            ValueError: If the request is already frozen before dispatch.
            AssertionError: If apply returns a value, changes the method, or
                freezes the request.
            BaseException: Any exact handler or assertion callback failure.
        """
        checked_assertion = _validate_assertion(assertion)
        original_method = _validate_apply_inputs(authorization, context, request)

        # Await exactly one application with all input identities unchanged.
        # Network/transport access is absent from the suite and can be observed
        # through caller-owned spies captured by the assertion callback.
        actual = await self._handler.apply(authorization, context, request)
        actual_value = cast(object, actual)
        if actual_value is not None:
            raise AssertionError("handler apply must return None.")
        _validate_request_boundary(request, original_method)
        checked_assertion(request)

    async def assert_apply_failure(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
        *,
        assertion: Callable[[BaseException], None],
    ) -> None:
        """Require apply to fail without closing its request window.

        Args:
            authorization: Exact opaque authorization value being applied.
            context: Exact immutable non-sensitive authorization facts.
            request: Exact open request mutation window.
            assertion: Synchronous callback asserting failure facts and identity.

        Raises:
            TypeError: If inputs or callback violate their public shapes.
            ValueError: If the request is already frozen before dispatch.
            AssertionError: If apply succeeds, changes the method, or freezes the
                request before failing.
            BaseException: Any exact assertion callback failure.
        """
        checked_assertion = _validate_assertion(assertion)
        original_method = _validate_apply_inputs(authorization, context, request)

        try:
            await self._handler.apply(authorization, context, request)
        except BaseException as error:
            captured_error = error
        else:
            # An unexpected success must still satisfy lifecycle ownership; a
            # handler-owned freeze is the more specific contract violation.
            _validate_request_boundary(request, original_method)
            raise AssertionError("handler apply was expected to fail.")

        # Lifecycle and method ownership remain mandatory on failure. Check them
        # before exposing the handler error to a protocol-specific assertion.
        _validate_request_boundary(request, original_method)
        checked_assertion(captured_error)


def _validate_authorization(authorization: Authorization) -> None:
    """Require the opaque authorization shape without reading credentials."""
    authorization_value = cast(object, authorization)
    if not isinstance(authorization_value, Authorization):
        raise TypeError("authorization must implement Authorization.")
    kind_value = cast(object, authorization.kind)
    if not isinstance(kind_value, OpenIdentifier):
        raise TypeError("authorization kind must be an OpenIdentifier.")


def _validate_apply_inputs(
    authorization: Authorization,
    context: AuthorizationContext,
    request: MutableTransportRequest,
) -> str:
    """Validate one apply case and return its Runtime-owned method."""
    _validate_authorization(authorization)
    context_value = cast(object, context)
    request_value = cast(object, request)
    if not isinstance(context_value, AuthorizationContext):
        raise TypeError("context must be an AuthorizationContext.")
    if not isinstance(request_value, MutableTransportRequest):
        raise TypeError("request must be a MutableTransportRequest.")
    if request.is_frozen:
        raise ValueError("request must be open before authorization.")

    # The protocol-selected method is not an authorization replacement point;
    # retain its exact value for the post-operation ownership check.
    return request.method


def _validate_request_boundary(
    request: MutableTransportRequest,
    original_method: str,
) -> None:
    """Require apply to preserve method ownership and the open lifecycle."""
    if request.method != original_method:
        raise AssertionError("handler must not change the request method.")
    if request.is_frozen:
        # Runtime alone freezes after authorization, before Transport dispatch.
        raise AssertionError("handler must not freeze the request.")


def _validate_assertion(
    assertion: Callable[[_ValueT], None],
) -> Callable[[_ValueT], None]:
    """Require one synchronous assertion before invoking handler behavior."""
    assertion_value = cast(object, assertion)
    if not callable(assertion_value):
        raise TypeError("assertion must be callable.")
    if iscoroutinefunction(assertion) or iscoroutinefunction(type(assertion).__call__):
        # Callbacks run synchronously after the operation so an async callable
        # would leave its assertions unexecuted and create a coroutine leak.
        raise TypeError("assertion must be synchronous.")
    return assertion

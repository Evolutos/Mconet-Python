"""Reusable assertions for AuthorizationHandlerResolver implementations."""

from __future__ import annotations

from collections.abc import Callable
from inspect import iscoroutinefunction
from typing import TypeVar, cast

from mconet.core.domain import Authorization, OpenIdentifier
from mconet.core.spi import (
    AuthorizationHandler,
    AuthorizationHandlerResolver,
    BodySigningRequirement,
    ComponentDescriptor,
    ResolvedAuthorizationHandler,
)

_ValueT = TypeVar("_ValueT")


class AuthorizationHandlerResolverContractSuite:
    """Apply zero-, one-, and many-match resolver contracts.

    The suite is independent of pytest, unittest, fixture formats, concrete
    authorization mechanisms, and credential storage. Callers supply one opaque
    authorization value, signing requirement, and closed candidate tuple, then
    inspect the exact unique result or exact failure through synchronous
    assertion callbacks.

    Runtime checks supplement static protocol conformance. A unique result must
    use the nominal public type, retain a handler from the supplied tuple by
    identity, and select a mode accepted by the requirement. Each case invokes
    ``resolve`` exactly once. The suite never calls handler compatibility or
    apply behavior, reveals credentials, mutates requests, performs I/O, consults
    a registry, or implements the concrete matching algorithm.
    """

    __slots__ = ("_resolver",)

    def __init__(self, resolver: AuthorizationHandlerResolver) -> None:
        """Validate and retain one structurally conforming sync resolver.

        Args:
            resolver: Custom or SDK resolver subjected to reusable cases.

        Raises:
            TypeError: If the object, descriptor, or resolve operation violates
                the public resolver boundary.
        """
        resolver_value = cast(object, resolver)
        if not isinstance(resolver_value, AuthorizationHandlerResolver):
            raise TypeError("resolver must implement AuthorizationHandlerResolver.")
        descriptor_value = cast(object, resolver.descriptor)
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("resolver descriptor must be a ComponentDescriptor.")

        # Resolution is a deterministic synchronous selection step. An async
        # look-alike would return a coroutine instead of a fixed interaction plan.
        resolve = resolver.resolve
        if iscoroutinefunction(resolve) or iscoroutinefunction(type(resolve).__call__):
            raise TypeError("resolver operation must be synchronous.")
        self._resolver = resolver

    def assert_unique_match(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
        handlers: tuple[AuthorizationHandler, ...],
        *,
        assertion: Callable[[ResolvedAuthorizationHandler], None],
    ) -> None:
        """Validate one unique candidate and signing-mode selection.

        Args:
            authorization: Exact opaque authorization value for the case.
            body_signing_requirement: Exact protocol signing constraint.
            handlers: Closed candidate tuple containing at least one handler.
            assertion: Synchronous callback asserting selection-specific facts.

        Raises:
            TypeError: If inputs or ``assertion`` violate their public shapes.
            ValueError: If no candidate is supplied for a unique-match case.
            AssertionError: If the result is invalid, selects an external
                handler, or chooses a mode excluded by the requirement.
            BaseException: Any exact resolver or assertion callback failure.
        """
        checked_assertion = _validate_assertion(assertion)
        _validate_inputs(
            authorization,
            body_signing_requirement,
            handlers,
            minimum_handlers=1,
        )

        # One direct call preserves all three input identities and lets an
        # unexpected selection failure reach the owning test unchanged.
        actual = self._resolver.resolve(
            authorization,
            body_signing_requirement,
            handlers,
        )
        actual_value = cast(object, actual)
        if not isinstance(actual_value, ResolvedAuthorizationHandler):
            raise AssertionError("resolver must return a ResolvedAuthorizationHandler.")

        # Identity membership prevents a resolver from constructing, looking up,
        # or substituting a handler outside this interaction's closed snapshot.
        if not any(actual_value.handler is handler for handler in handlers):
            raise AssertionError(
                "resolver must select a handler from the supplied candidates."
            )
        if (
            actual_value.body_signing_mode
            not in body_signing_requirement.acceptable_modes
        ):
            # The immutable protocol preference is authoritative; the resolver
            # cannot silently widen it while selecting handler capabilities.
            raise AssertionError(
                "resolver must select a mode accepted by the signing requirement."
            )
        checked_assertion(actual_value)

    def assert_no_match(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
        handlers: tuple[AuthorizationHandler, ...],
        *,
        assertion: Callable[[BaseException], None],
    ) -> None:
        """Require resolution to reject a candidate set with no match.

        Args:
            authorization: Exact opaque authorization value for the case.
            body_signing_requirement: Exact protocol signing constraint.
            handlers: Closed candidate tuple containing zero or more handlers.
            assertion: Synchronous callback asserting missing-match failure facts.

        Raises:
            TypeError: If inputs or ``assertion`` violate their public shapes.
            AssertionError: If resolution returns a fallback selection.
            BaseException: Any exact assertion callback failure.
        """
        checked_assertion = _validate_assertion(assertion)
        _validate_inputs(
            authorization,
            body_signing_requirement,
            handlers,
            minimum_handlers=0,
        )
        _assert_resolution_failure(
            self._resolver,
            authorization,
            body_signing_requirement,
            handlers,
            assertion=checked_assertion,
            success_message="resolver was expected to find no compatible handler.",
        )

    def assert_ambiguous_match(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
        handlers: tuple[AuthorizationHandler, ...],
        *,
        assertion: Callable[[BaseException], None],
    ) -> None:
        """Require resolution to reject multiple compatible candidates.

        Args:
            authorization: Exact opaque authorization value for the case.
            body_signing_requirement: Exact protocol signing constraint.
            handlers: Closed tuple containing at least two candidate handlers.
            assertion: Synchronous callback asserting ambiguity failure facts.

        Raises:
            TypeError: If inputs or ``assertion`` violate their public shapes.
            ValueError: If fewer than two candidates are supplied.
            AssertionError: If resolution chooses by tuple order.
            BaseException: Any exact assertion callback failure.
        """
        checked_assertion = _validate_assertion(assertion)
        _validate_inputs(
            authorization,
            body_signing_requirement,
            handlers,
            minimum_handlers=2,
        )
        _assert_resolution_failure(
            self._resolver,
            authorization,
            body_signing_requirement,
            handlers,
            assertion=checked_assertion,
            success_message="resolver was expected to reject ambiguous handlers.",
        )


def _validate_inputs(
    authorization: Authorization,
    body_signing_requirement: BodySigningRequirement,
    handlers: tuple[AuthorizationHandler, ...],
    *,
    minimum_handlers: int,
) -> None:
    """Require complete nominal inputs for one resolver contract branch."""
    authorization_value = cast(object, authorization)
    requirement_value = cast(object, body_signing_requirement)
    handlers_value = cast(object, handlers)

    if not isinstance(authorization_value, Authorization):
        raise TypeError("authorization must implement Authorization.")
    kind_value = cast(object, authorization.kind)
    if not isinstance(kind_value, OpenIdentifier):
        raise TypeError("authorization kind must be an OpenIdentifier.")
    if not isinstance(requirement_value, BodySigningRequirement):
        raise TypeError("body_signing_requirement must be a BodySigningRequirement.")
    if not isinstance(handlers_value, tuple):
        raise TypeError("handlers must be a tuple.")

    # Every supplied candidate must be executable and carry stable metadata;
    # validation never invokes supports or apply and therefore has no side effect.
    for handler in cast(tuple[object, ...], handlers_value):
        if not isinstance(handler, AuthorizationHandler):
            raise TypeError("handlers must contain AuthorizationHandler values.")
        descriptor_value = cast(object, handler.descriptor)
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("handler descriptor must be a ComponentDescriptor.")

    if len(handlers) < minimum_handlers:
        raise ValueError(
            f"contract case requires at least {minimum_handlers} handler candidates."
        )


def _assert_resolution_failure(
    resolver: AuthorizationHandlerResolver,
    authorization: Authorization,
    body_signing_requirement: BodySigningRequirement,
    handlers: tuple[AuthorizationHandler, ...],
    *,
    assertion: Callable[[BaseException], None],
    success_message: str,
) -> None:
    """Invoke one failure branch and pass its exact error to the assertion."""
    try:
        resolver.resolve(
            authorization,
            body_signing_requirement,
            handlers,
        )
    except BaseException as error:
        captured_error = error
    else:
        raise AssertionError(success_message)

    # Execute outside the catch block so callback failures cannot be mistaken
    # for or wrapped as the resolver's missing/ambiguous-match failure.
    assertion(captured_error)


def _validate_assertion(
    assertion: Callable[[_ValueT], None],
) -> Callable[[_ValueT], None]:
    """Require one synchronous assertion before invoking the resolver."""
    assertion_value = cast(object, assertion)
    if not callable(assertion_value):
        raise TypeError("assertion must be callable.")
    if iscoroutinefunction(assertion) or iscoroutinefunction(type(assertion).__call__):
        # An async callback would not execute its assertions in this synchronous
        # suite and would leave an unawaited coroutine behind.
        raise TypeError("assertion must be synchronous.")
    return assertion

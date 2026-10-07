"""Configurable test double for authorization handler resolution."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import Authorization
from mconet.core.spi import (
    AuthorizationHandler,
    BodySigningRequirement,
    ComponentDescriptor,
    ResolvedAuthorizationHandler,
)


class StubAuthorizationHandlerResolver:
    """Return or raise one configured authorization selection outcome.

    The stub structurally implements ``AuthorizationHandlerResolver`` without SDK
    inheritance. A unique match is represented by the exact configured
    ``ResolvedAuthorizationHandler``. Missing and ambiguous matches are
    represented by exact configured failures so their normalized fields and
    object identity remain available to contract tests.

    Authorization, signing requirements, and the closed candidate tuple cross
    the complete protocol boundary but are deliberately not inspected, copied,
    reordered, filtered, or retained. The stub performs no credential access,
    compatibility matching, request mutation, authorization, or network I/O.

    Configuration is fixed at construction. The stub records no calls and has no
    reset or dynamic reconfiguration API; cross-component ordering belongs to the
    separate component call recorder.
    """

    __slots__ = ("_descriptor", "_error", "_result")

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        result: ResolvedAuthorizationHandler,
        *,
        error: BaseException | None = None,
    ) -> None:
        """Validate and retain one deterministic handler resolution outcome.

        Args:
            descriptor: Static metadata exposed through ``RuntimeComponent``.
            result: Exact unique handler and signing-mode selection on success.
            error: Optional exact missing, ambiguous, or other failure raised
                instead of ``result``.

        Raises:
            TypeError: If metadata, the result, or the configured failure has an
                invalid nominal type.
        """
        descriptor_value = cast(object, descriptor)
        result_value = cast(object, result)
        error_value = cast(object, error)

        # Validate the fixed outcome at construction so malformed test setup
        # cannot surface later as credential, authorization, or transport logic.
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("descriptor must be a ComponentDescriptor.")
        if not isinstance(result_value, ResolvedAuthorizationHandler):
            raise TypeError("result must be a ResolvedAuthorizationHandler.")
        if error_value is not None and not isinstance(error_value, BaseException):
            raise TypeError("error must be a BaseException or None.")

        self._descriptor = descriptor
        self._result = result
        self._error = error

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the exact immutable component metadata supplied at construction."""
        # Read-only access satisfies RuntimeComponent without permitting metadata
        # replacement after resolver selection or capability validation.
        return self._descriptor

    def resolve(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
        handlers: tuple[AuthorizationHandler, ...],
    ) -> ResolvedAuthorizationHandler:
        """Return the configured selection or raise the configured failure.

        Args:
            authorization: Opaque authorization accepted without inspection.
            body_signing_requirement: Signing constraint accepted unchanged.
            handlers: Closed immutable candidate tuple accepted unchanged.

        Returns:
            The exact configured handler and signing-mode selection.

        Raises:
            BaseException: The exact configured failure when one is present.
        """
        # A predetermined Stub outcome must not inspect secrets, query handler
        # compatibility, reorder candidates, choose by position, or retain inputs.
        del authorization, body_signing_requirement, handlers
        if self._error is not None:
            # Preserve normalized fields, identity, and control-flow class rather
            # than wrapping missing or ambiguous selection failures.
            raise self._error
        return self._result

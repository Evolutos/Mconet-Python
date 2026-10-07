"""Configurable test double for service access resolution."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import ResolvedServiceAccess, ServiceAccess
from mconet.core.spi import ComponentDescriptor


class StubServiceAccessResolver:
    """Return or raise one configured service access resolution outcome.

    The stub structurally implements ``ServiceAccessResolver`` without SDK
    inheritance. Successful calls return the exact configured immutable
    ``ResolvedServiceAccess``; failing calls raise the exact configured failure.

    All four ordered access layers cross the complete protocol boundary but are
    deliberately not inspected, copied, merged, normalized, or retained. This
    test double performs no field precedence resolution, endpoint validation,
    credential access, authorization, request mutation, transport, or network I/O.

    Configuration is fixed at construction. The stub records no calls and has no
    reset or dynamic reconfiguration API; cross-component ordering belongs to the
    separate component call recorder.
    """

    __slots__ = ("_descriptor", "_error", "_result")

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        result: ResolvedServiceAccess,
        *,
        error: BaseException | None = None,
    ) -> None:
        """Validate and retain one deterministic access resolution outcome.

        Args:
            descriptor: Static metadata exposed through ``RuntimeComponent``.
            result: Exact complete access snapshot returned on success.
            error: Optional exact failure raised instead of ``result``.

        Raises:
            TypeError: If metadata, the result, or the configured failure has an
                invalid nominal type.
        """
        descriptor_value = cast(object, descriptor)
        result_value = cast(object, result)
        error_value = cast(object, error)

        # Validate the fixed outcome at construction so malformed test setup
        # cannot surface later as an authorization or transport-stage failure.
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("descriptor must be a ComponentDescriptor.")
        if not isinstance(result_value, ResolvedServiceAccess):
            raise TypeError("result must be a ResolvedServiceAccess.")
        if error_value is not None and not isinstance(error_value, BaseException):
            raise TypeError("error must be a BaseException or None.")

        self._descriptor = descriptor
        self._result = result
        self._error = error

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the exact immutable component metadata supplied at construction."""
        # Read-only access satisfies RuntimeComponent without permitting metadata
        # replacement after resolver selection or compatibility validation.
        return self._descriptor

    def resolve(
        self,
        interaction_override: ServiceAccess | None,
        request_service_access: ServiceAccess | None,
        client_default_service_access: ServiceAccess | None,
        protocol_default_service_access: ServiceAccess | None,
    ) -> ResolvedServiceAccess:
        """Return the configured snapshot or raise the configured failure.

        Args:
            interaction_override: Highest-priority optional access source.
            request_service_access: Optional request-owned access source.
            client_default_service_access: Optional client default source.
            protocol_default_service_access: Lowest-priority protocol default.

        Returns:
            The exact ``ResolvedServiceAccess`` configured at construction.

        Raises:
            BaseException: The exact configured failure when one is present.
        """
        # A predetermined Stub outcome must not merge or retain source layers,
        # inspect authorization, read credentials, or consult external state.
        del (
            interaction_override,
            request_service_access,
            client_default_service_access,
            protocol_default_service_access,
        )
        if self._error is not None:
            # Preserve failure identity, type, message, fields, and control-flow
            # class instead of wrapping it or returning a partial access value.
            raise self._error
        return self._result

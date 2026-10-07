"""Recording configurable test double for authorization application."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import Authorization
from mconet.core.spi import (
    AuthorizationContext,
    BodySigningMode,
    BodySigningRequirement,
    ComponentDescriptor,
    MutableTransportRequest,
    TransportRequest,
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


class StubAuthorizationHandler:
    """Report configured modes and record request state around authorization.

    The stub structurally implements ``AuthorizationHandler`` without SDK
    inheritance. :meth:`supports` returns one fixed immutable signing-mode set.
    :meth:`apply` records immutable ``TransportRequest`` snapshots immediately
    before and after its no-op authorization attempt, then optionally raises one
    configured failure. Failed calls therefore expose both unchanged boundaries.

    The stub deliberately does not inspect authorization values, reveal secrets,
    acquire credentials, add headers or query values, sign a body, replace the
    URL, freeze the request, or perform transport I/O. Concrete authorization
    mutation belongs to production handlers and their contract suites.

    Configuration is fixed at construction. Ordered request records are exposed
    as fresh immutable tuples; no reset or dynamic reconfiguration API exists.
    Cross-component ordering remains the separate component recorder's concern.
    """

    __slots__ = (
        "_apply_error",
        "_descriptor",
        "_requests_after",
        "_requests_before",
        "_supported_modes",
    )

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        supported_modes: frozenset[BodySigningMode],
        *,
        apply_error: BaseException | None = None,
    ) -> None:
        """Validate and retain deterministic support and apply behavior.

        Args:
            descriptor: Static metadata exposed through ``RuntimeComponent``.
            supported_modes: Exact immutable modes returned by :meth:`supports`.
            apply_error: Optional exact failure raised after request snapshots.

        Raises:
            TypeError: If metadata, modes, or the configured failure has an
                invalid nominal type.
            ValueError: If a configured signing mode is unsupported.
        """
        descriptor_value = cast(object, descriptor)
        modes_value = cast(object, supported_modes)
        error_value = cast(object, apply_error)

        # Fail fast on malformed test setup before a resolver observes invalid
        # compatibility facts or an apply test enters the mutation window.
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("descriptor must be a ComponentDescriptor.")
        if not isinstance(modes_value, frozenset):
            raise TypeError("supported_modes must be a frozenset.")
        for mode in cast(frozenset[object], modes_value):
            if not isinstance(mode, str):
                raise TypeError("supported_modes must contain strings.")
            if mode not in _BODY_SIGNING_MODES:
                raise ValueError(
                    f"supported_modes contains an unsupported mode: {mode!r}."
                )
        if error_value is not None and not isinstance(error_value, BaseException):
            raise TypeError("apply_error must be a BaseException or None.")

        self._descriptor = descriptor
        self._supported_modes = supported_modes
        self._apply_error = apply_error
        self._requests_before: list[TransportRequest] = []
        self._requests_after: list[TransportRequest] = []

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the exact immutable component metadata supplied at construction."""
        # Read-only access satisfies RuntimeComponent without permitting metadata
        # replacement after handler selection or capability validation.
        return self._descriptor

    @property
    def requests_before(self) -> tuple[TransportRequest, ...]:
        """Return immutable snapshots taken before authorization attempts."""
        # A new tuple freezes record membership while each immutable request
        # remains detached from later changes to the original mutable builder.
        return tuple(self._requests_before)

    @property
    def requests_after(self) -> tuple[TransportRequest, ...]:
        """Return immutable snapshots taken after authorization attempts."""
        # Success and configured failure both append exactly one terminal state,
        # keeping the two ordered histories aligned by invocation index.
        return tuple(self._requests_after)

    def supports(
        self,
        authorization: Authorization,
        body_signing_requirement: BodySigningRequirement,
    ) -> frozenset[BodySigningMode]:
        """Return the exact configured modes without authorization side effects."""
        # The fixed compatibility result does not inspect opaque authorization,
        # negotiate requirement preferences, reveal secrets, or record a call.
        del authorization, body_signing_requirement
        return self._supported_modes

    async def apply(
        self,
        authorization: Authorization,
        context: AuthorizationContext,
        request: MutableTransportRequest,
    ) -> None:
        """Record request boundaries and optionally raise one configured error.

        Args:
            authorization: Opaque authorization accepted without inspection.
            context: Immutable selected authorization facts accepted unchanged.
            request: Open request window observed without mutation or freezing.

        Raises:
            TypeError: If a dynamic caller supplies a non-mutable request value.
            RuntimeError: If the supplied request is already frozen.
            BaseException: The exact configured application failure.
        """
        request_value = cast(object, request)
        if not isinstance(request_value, MutableTransportRequest):
            raise TypeError("request must be a MutableTransportRequest.")
        if request.is_frozen:
            raise RuntimeError("request must remain open during authorization.")

        # Opaque selection facts are accepted but never retained or interpreted;
        # only non-secret transport request state enters the local test record.
        del authorization, context
        self._requests_before.append(_snapshot_request(request))

        # This Stub is intentionally a no-op handler. Capture the terminal state
        # before raising so failures prove that no partial authorization occurred.
        self._requests_after.append(_snapshot_request(request))
        if self._apply_error is not None:
            # Preserve failure identity, fields, and control-flow class without
            # wrapping, freezing, sending, or selecting a fallback handler.
            raise self._apply_error


def _snapshot_request(request: MutableTransportRequest) -> TransportRequest:
    """Copy current immutable request fields without closing its mutation window."""
    # Constructing TransportRequest snapshots the values but never calls freeze,
    # so Runtime retains sole ownership of the authorization lifecycle transition.
    return TransportRequest(
        method=request.method,
        url=request.url,
        headers=request.headers,
        query=request.query,
        body=request.body,
    )

"""Recording configurable test double for the payload encoder contract."""

from __future__ import annotations

from typing import cast

from mconet.core.spi import ComponentDescriptor, ErasedRuntimeValue, TransportBody


class StubPayloadEncoder:
    """Record payloads and return or raise one configured encoding outcome.

    The stub structurally implements ``PayloadEncoder`` without SDK inheritance.
    Every :meth:`encode` call records the exact ``ErasedRuntimeValue`` instance
    before returning the configured ``TransportBody`` or raising the configured
    failure. Failed calls therefore remain observable to contract tests.

    Results and failures are retained by identity and never copied, encoded,
    wrapped, normalized, or translated. The ordered payload record is exposed as
    a fresh immutable tuple so callers cannot mutate the stub's internal history.

    This test double performs no native-value access, JSON serialization, media
    type inference, authorization, request mutation, transport, decoding, or
    cross-component order recording. Configuration is fixed at construction and
    no reset or dynamic reconfiguration API is provided.
    """

    __slots__ = ("_descriptor", "_error", "_payloads", "_result")

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        result: TransportBody,
        *,
        error: BaseException | None = None,
    ) -> None:
        """Validate and retain metadata plus one deterministic encode outcome.

        Args:
            descriptor: Static metadata exposed through ``RuntimeComponent``.
            result: Exact transport body returned by successful calls.
            error: Optional exact exception raised instead of ``result``.

        Raises:
            TypeError: If metadata, the result, or the configured failure has an
                invalid nominal type.
        """
        descriptor_value = cast(object, descriptor)
        result_value = cast(object, result)
        error_value = cast(object, error)

        # Fail fast on malformed test setup. The Stub must never defer an invalid
        # result until an unrelated Runtime stage consumes its return value.
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("descriptor must be a ComponentDescriptor.")
        if not isinstance(result_value, TransportBody):
            raise TypeError("result must be a TransportBody.")
        if error_value is not None and not isinstance(error_value, BaseException):
            raise TypeError("error must be a BaseException or None.")

        self._descriptor = descriptor
        self._result = result
        self._error = error
        self._payloads: list[ErasedRuntimeValue] = []

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the exact immutable component metadata supplied at construction."""
        # Read-only access satisfies RuntimeComponent without permitting metadata
        # replacement after component selection or type-contract validation.
        return self._descriptor

    @property
    def payloads(self) -> tuple[ErasedRuntimeValue, ...]:
        """Return an immutable snapshot of payloads received in invocation order."""
        # A new tuple freezes current membership while preserving exact payload
        # identities; later calls cannot retroactively modify an earlier snapshot.
        return tuple(self._payloads)

    def encode(self, payload: ErasedRuntimeValue) -> TransportBody:
        """Record one exact payload, then return or raise the configured outcome.

        Args:
            payload: Protocol-native value supplied to the selected encoder.

        Returns:
            The exact ``TransportBody`` configured at construction.

        Raises:
            TypeError: If a dynamic caller supplies a non-ErasedRuntimeValue.
            BaseException: The exact configured failure when one is present.
        """
        payload_value = cast(object, payload)
        if not isinstance(payload_value, ErasedRuntimeValue):
            raise TypeError("payload must be an ErasedRuntimeValue.")

        # Record before evaluating the configured outcome so failed encoding
        # attempts remain assertable with the same ordering as successful calls.
        self._payloads.append(payload)
        if self._error is not None:
            # Preserve failure identity, type, message, and custom state rather
            # than wrapping it in a generic testing or encoding exception.
            raise self._error
        return self._result

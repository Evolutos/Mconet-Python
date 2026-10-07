"""Recording configurable test double for the payload decoder contract."""

from __future__ import annotations

from typing import cast

from mconet.core.domain import Bytes
from mconet.core.spi import ComponentDescriptor, ErasedRuntimeValue


class StubPayloadDecoder:
    """Record byte inputs and return or raise one configured decoding outcome.

    The stub structurally implements ``PayloadDecoder`` without SDK inheritance.
    Every :meth:`decode` call records the exact complete ``Bytes`` value before
    returning the configured ``ErasedRuntimeValue`` or raising the configured
    failure. Failed calls therefore remain observable to contract tests.

    Results and failures are retained by identity and never copied, parsed,
    wrapped, normalized, or translated. The ordered byte record is exposed as a
    fresh immutable tuple so callers cannot mutate the internal history.

    This test double performs no media-type validation, component selection,
    deserialization, task parsing, message mapping, output assembly, transport,
    or cross-component order recording. Configuration is fixed at construction
    and no reset or dynamic reconfiguration API is provided.
    """

    __slots__ = ("_descriptor", "_error", "_raw_data", "_result")

    def __init__(
        self,
        descriptor: ComponentDescriptor,
        result: ErasedRuntimeValue,
        *,
        error: BaseException | None = None,
    ) -> None:
        """Validate and retain metadata plus one deterministic decode outcome.

        Args:
            descriptor: Static metadata exposed through ``RuntimeComponent``.
            result: Exact protocol-native value returned by successful calls.
            error: Optional exact exception raised instead of ``result``.

        Raises:
            TypeError: If metadata, the result, or the configured failure has an
                invalid nominal type.
        """
        descriptor_value = cast(object, descriptor)
        result_value = cast(object, result)
        error_value = cast(object, error)

        # Fail fast on malformed test setup so invalid configured output cannot
        # escape into a later protocol-adapter or response-mapping operation.
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("descriptor must be a ComponentDescriptor.")
        if not isinstance(result_value, ErasedRuntimeValue):
            raise TypeError("result must be an ErasedRuntimeValue.")
        if error_value is not None and not isinstance(error_value, BaseException):
            raise TypeError("error must be a BaseException or None.")

        self._descriptor = descriptor
        self._result = result
        self._error = error
        self._raw_data: list[Bytes] = []

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return the exact immutable component metadata supplied at construction."""
        # Read-only access satisfies RuntimeComponent without permitting metadata
        # replacement after component selection or type-contract validation.
        return self._descriptor

    @property
    def raw_data(self) -> tuple[Bytes, ...]:
        """Return an immutable snapshot of byte inputs in invocation order."""
        # A fresh tuple freezes current membership while preserving each bytes
        # object's identity; later decode calls cannot alter an earlier snapshot.
        return tuple(self._raw_data)

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Record one complete byte input, then return or raise the outcome.

        Args:
            raw_data: Complete immutable response bytes supplied to the decoder.

        Returns:
            The exact ``ErasedRuntimeValue`` configured at construction.

        Raises:
            TypeError: If a dynamic caller supplies a mutable or non-byte value.
            BaseException: The exact configured failure when one is present.
        """
        raw_data_value = cast(object, raw_data)
        # Bytes is a static NewType over immutable bytes, so bytes is its runtime
        # boundary and deliberately excludes bytearray and memoryview inputs.
        if not isinstance(raw_data_value, bytes):
            raise TypeError("raw_data must be an immutable bytes value.")

        # Record before evaluating the configured outcome so failed decoding
        # attempts remain assertable with the same ordering as successful calls.
        self._raw_data.append(raw_data)
        if self._error is not None:
            # Preserve failure identity, type, message, and custom state rather
            # than wrapping it in a generic testing or decoding exception.
            raise self._error
        return self._result

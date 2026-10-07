"""Reusable runtime assertions for successful PayloadDecoder implementations."""

from __future__ import annotations

from collections.abc import Callable
from inspect import iscoroutinefunction
from typing import TypeVar, cast

from mconet.core.domain import Bytes
from mconet.core.spi import ComponentDescriptor, ErasedRuntimeValue, PayloadDecoder

_ValueT = TypeVar("_ValueT")


class SuccessPayloadDecoderContractSuite:
    """Apply the successful-response contract to one payload decoder.

    The suite is independent of pytest, unittest, fixture formats, and concrete
    response protocols. Callers provide complete response bytes and inspect the
    exact decoded value or exact raised failure through a synchronous assertion
    callback. Callback and decoder failures pass through unchanged so the owning
    test framework retains its normal diagnostics.

    Runtime checks supplement static protocol conformance: component metadata
    and successful results must use their nominal public SDK types. Each
    assertion invokes ``decode`` exactly once and performs no media-type
    validation, component selection, parsing of native values, task adaptation,
    message mapping, output assembly, transport, fixture loading, or retry.
    """

    __slots__ = ("_decoder",)

    def __init__(self, decoder: PayloadDecoder) -> None:
        """Validate and retain one structurally conforming synchronous decoder.

        Args:
            decoder: Custom or SDK success decoder subjected to contract cases.

        Raises:
            TypeError: If the object, descriptor, or decode operation violates
                the public decoder boundary.
        """
        decoder_value = cast(object, decoder)
        if not isinstance(decoder_value, PayloadDecoder):
            raise TypeError("decoder must implement PayloadDecoder.")
        descriptor_value = cast(object, decoder.descriptor)
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("decoder descriptor must be a ComponentDescriptor.")

        # A coroutine result cannot satisfy the synchronous complete-byte SPI,
        # so reject async methods and callable objects before any contract case.
        decode = decoder.decode
        if iscoroutinefunction(decode) or iscoroutinefunction(type(decode).__call__):
            raise TypeError("decoder operation must be synchronous.")
        self._decoder = decoder

    def assert_decode(
        self,
        raw_data: Bytes,
        *,
        assertion: Callable[[ErasedRuntimeValue], None],
    ) -> None:
        """Validate one successful decode result with a caller assertion.

        Args:
            raw_data: Exact complete response bytes from the contract case.
            assertion: Synchronous callback asserting decoded protocol facts.

        Raises:
            TypeError: If ``assertion`` is not a synchronous callable.
            AssertionError: If the decoder returns no ErasedRuntimeValue.
            BaseException: Any exact decoder or assertion callback failure.
        """
        checked_assertion = _validate_assertion(assertion)

        # One direct invocation preserves the exact immutable byte input and
        # lets unexpected decoder failures reach the test without translation.
        actual = self._decoder.decode(raw_data)
        actual_value = cast(object, actual)
        if not isinstance(actual_value, ErasedRuntimeValue):
            raise AssertionError("decoder must return an ErasedRuntimeValue.")
        checked_assertion(actual_value)

    def assert_decode_failure(
        self,
        raw_data: Bytes,
        *,
        assertion: Callable[[BaseException], None],
    ) -> None:
        """Require decoding to fail and pass the exact error to an assertion.

        Args:
            raw_data: Exact complete response bytes from the negative case.
            assertion: Synchronous callback asserting failure facts and identity.

        Raises:
            TypeError: If ``assertion`` is not a synchronous callable.
            AssertionError: If the decoder completes successfully.
            BaseException: Any exact assertion callback failure.
        """
        checked_assertion = _validate_assertion(assertion)

        try:
            # BaseException preserves every observable decoder failure category,
            # including cancellation or interruption used by contract fixtures.
            self._decoder.decode(raw_data)
        except BaseException as error:
            captured_error = error
        else:
            raise AssertionError("decoder was expected to fail.")

        # Run outside the catch block so callback failures remain distinguishable
        # from the exact decoding failure supplied to the callback.
        checked_assertion(captured_error)


def _validate_assertion(
    assertion: Callable[[_ValueT], None],
) -> Callable[[_ValueT], None]:
    """Require one synchronous callable before invoking the decoder operation."""
    assertion_value = cast(object, assertion)
    if not callable(assertion_value):
        raise TypeError("assertion must be callable.")
    if iscoroutinefunction(assertion) or iscoroutinefunction(type(assertion).__call__):
        # Async callbacks would leave their assertions unexecuted and create an
        # unawaited coroutine in this deliberately synchronous contract suite.
        raise TypeError("assertion must be synchronous.")
    return assertion

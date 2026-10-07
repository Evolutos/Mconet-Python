"""Reusable runtime assertions for PayloadEncoder implementations."""

from __future__ import annotations

from collections.abc import Callable
from inspect import iscoroutinefunction
from typing import TypeVar, cast

from mconet.core.spi import (
    ComponentDescriptor,
    ErasedRuntimeValue,
    PayloadEncoder,
    TransportBody,
)

_ValueT = TypeVar("_ValueT")


class PayloadEncoderContractSuite:
    """Apply the shared synchronous contract to one payload encoder.

    The suite is independent of pytest, unittest, fixture formats, and concrete
    protocol payloads. Callers provide an ``ErasedRuntimeValue`` and inspect the
    exact encoded body or exact raised failure through a synchronous assertion
    callback. Callback and encoder failures pass through unchanged so the owning
    test framework retains its normal diagnostics.

    Runtime checks supplement static protocol conformance: component metadata
    and successful results must use their nominal public SDK types. Each
    assertion invokes ``encode`` exactly once and performs no native-value
    access, serialization, media-type inference, authorization, transport,
    decoding, fixture loading, or protocol-specific comparison.
    """

    __slots__ = ("_encoder",)

    def __init__(self, encoder: PayloadEncoder) -> None:
        """Validate and retain one structurally conforming synchronous encoder.

        Args:
            encoder: Custom or SDK encoder subjected to reusable contract cases.

        Raises:
            TypeError: If the object, descriptor, or encode operation violates
                the public encoder boundary.
        """
        encoder_value = cast(object, encoder)
        if not isinstance(encoder_value, PayloadEncoder):
            raise TypeError("encoder must implement PayloadEncoder.")
        descriptor_value = cast(object, encoder.descriptor)
        if not isinstance(descriptor_value, ComponentDescriptor):
            raise TypeError("encoder descriptor must be a ComponentDescriptor.")

        # Calling an async encoder would only create a coroutine where the SPI
        # requires a complete TransportBody immediately, so reject it at setup.
        encode = encoder.encode
        if iscoroutinefunction(encode) or iscoroutinefunction(type(encode).__call__):
            raise TypeError("encoder operation must be synchronous.")
        self._encoder = encoder

    def assert_encode(
        self,
        payload: ErasedRuntimeValue,
        *,
        assertion: Callable[[TransportBody], None],
    ) -> None:
        """Validate one successful encoding result with a caller assertion.

        Args:
            payload: Exact protocol-native wrapper supplied by the contract case.
            assertion: Synchronous callback asserting encoded body facts.

        Raises:
            TypeError: If ``assertion`` is not a synchronous callable.
            AssertionError: If the encoder returns no nominal TransportBody.
            BaseException: Any exact encoder or assertion callback failure.
        """
        checked_assertion = _validate_assertion(assertion)

        # One direct invocation preserves payload identity and lets unexpected
        # encoder failures reach the owning test framework without translation.
        actual = self._encoder.encode(payload)
        actual_value = cast(object, actual)
        if not isinstance(actual_value, TransportBody):
            raise AssertionError("encoder must return a TransportBody.")
        checked_assertion(actual_value)

    def assert_encode_failure(
        self,
        payload: ErasedRuntimeValue,
        *,
        assertion: Callable[[BaseException], None],
    ) -> None:
        """Require encoding to fail and pass the exact error to an assertion.

        Args:
            payload: Exact protocol-native wrapper supplied by the contract case.
            assertion: Synchronous callback asserting failure facts and identity.

        Raises:
            TypeError: If ``assertion`` is not a synchronous callable.
            AssertionError: If the encoder completes successfully.
            BaseException: Any exact assertion callback failure.
        """
        checked_assertion = _validate_assertion(assertion)

        try:
            # Catch BaseException deliberately because the SPI permits callers
            # to verify any exact failure without the suite narrowing its type.
            self._encoder.encode(payload)
        except BaseException as error:
            captured_error = error
        else:
            raise AssertionError("encoder was expected to fail.")

        # Invoke outside the catch block so a callback failure cannot be mistaken
        # for, wrapped with, or otherwise conflated with the encoder failure.
        checked_assertion(captured_error)


def _validate_assertion(
    assertion: Callable[[_ValueT], None],
) -> Callable[[_ValueT], None]:
    """Require one synchronous callable before invoking the encoder operation."""
    assertion_value = cast(object, assertion)
    if not callable(assertion_value):
        raise TypeError("assertion must be callable.")
    if iscoroutinefunction(assertion) or iscoroutinefunction(type(assertion).__call__):
        # An async callback would not execute its assertions in this synchronous
        # suite and would leave an unawaited coroutine behind.
        raise TypeError("assertion must be synchronous.")
    return assertion

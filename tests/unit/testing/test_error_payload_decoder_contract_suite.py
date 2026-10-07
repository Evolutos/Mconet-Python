"""Behavior and boundary tests for ErrorPayloadDecoderContractSuite."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import cast, get_type_hints

from mconet.core.domain import Bytes, OpenIdentifier
from mconet.core.spi import ComponentDescriptor, ErasedRuntimeValue, PayloadDecoder
from mconet.testing import (
    ComponentCallRecorder,
    ErrorPayloadDecoderContractSuite,
    StubPayloadDecoder,
)


def _result(value: object = None) -> ErasedRuntimeValue:
    """Build one protocol error wrapper for decoder contract cases."""
    return ErasedRuntimeValue(
        OpenIdentifier("protocol.error"),
        value,
        "error.v1",
    )


def _assert_raises_identity(
    action: Callable[[], object],
    expected: BaseException,
) -> None:
    """Require one action to raise the exact expected failure instance."""
    try:
        action()
    except BaseException as error:
        assert error is expected
        return
    raise AssertionError(f"Expected {type(expected).__name__} to be raised.")


class _RecordingDecoder:
    """Structural error decoder exposing inputs, output, and call order."""

    __slots__ = ("_descriptor", "_raw_data", "_recorder", "_result")

    def __init__(
        self,
        result: ErasedRuntimeValue,
        recorder: ComponentCallRecorder,
    ) -> None:
        """Retain one exact result and external invocation recorder."""
        self._descriptor = ComponentDescriptor(
            "Recording error decoder", "1", "application"
        )
        self._result = result
        self._recorder = recorder
        self._raw_data: list[Bytes] = []

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return valid immutable component metadata."""
        return self._descriptor

    @property
    def raw_data(self) -> tuple[Bytes, ...]:
        """Return an immutable snapshot of exact received byte values."""
        return tuple(self._raw_data)

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Record one exact input and return the configured error payload."""
        self._recorder.record("decode_error")
        self._raw_data.append(raw_data)
        return self._result


class _InvalidResultDecoder:
    """Claim the decoder signature while returning an invalid runtime value."""

    descriptor = ComponentDescriptor("Invalid error decoder", "1", "application")

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Discard the bytes and expose malformed implementation behavior."""
        del raw_data
        return cast(ErasedRuntimeValue, object())


class _InvalidDescriptorDecoder:
    """Expose a structurally present but nominally invalid descriptor."""

    descriptor = cast(ComponentDescriptor, object())

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Provide the method shape required for descriptor validation."""
        del raw_data
        return _result()


class _AsyncDecoder:
    """Expose an invalid asynchronous implementation of the sync SPI."""

    descriptor = ComponentDescriptor("Async error decoder", "1", "application")

    async def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Return an error payload asynchronously to exercise rejection."""
        del raw_data
        return _result()


def test_suite_validates_stub_input_and_decoded_error_contract() -> None:
    """Preserve exact bytes and expose the complete error wrapper."""
    native_result = {"error": {"code": "rate_limit"}}
    result = _result(native_result)
    raw_data = Bytes(b'{"error":{"code":"rate_limit"}}')
    decoder = StubPayloadDecoder(
        ComponentDescriptor("Stub error decoder", "1", "application"),
        result,
    )
    observed: list[ErasedRuntimeValue] = []

    def assert_result(actual: ErasedRuntimeValue) -> None:
        """Verify wrapper identity and protocol-owned error facts."""
        assert actual is result
        assert actual.type_id == OpenIdentifier("protocol.error")
        assert actual.schema_id == "error.v1"
        assert actual.value is native_result
        observed.append(actual)

    ErrorPayloadDecoderContractSuite(decoder).assert_decode(
        raw_data,
        assertion=assert_result,
    )

    assert observed == [result]
    assert decoder.raw_data == (raw_data,)
    assert decoder.raw_data[0] is raw_data


def test_suite_accepts_structural_decoder_and_invokes_it_once() -> None:
    """Require no SDK inheritance while retaining input and result identity."""
    recorder = ComponentCallRecorder()
    result = _result("service-unavailable")
    raw_data = Bytes(bytes((0, 127, 255)))
    decoder = _RecordingDecoder(result, recorder)

    def assert_identity(actual: ErasedRuntimeValue) -> None:
        """Require the exact custom decoder result without reconstruction."""
        assert actual is result

    ErrorPayloadDecoderContractSuite(decoder).assert_decode(
        raw_data,
        assertion=assert_identity,
    )

    assert recorder.calls == ("decode_error",)
    assert decoder.raw_data == (raw_data,)
    assert decoder.raw_data[0] is raw_data


def test_suite_passes_exact_decoder_failure_to_assertion() -> None:
    """Retain BaseException identity and failed-call byte evidence."""
    failure = KeyboardInterrupt("configured error decoding interruption")
    raw_data = Bytes(b"malformed-error")
    decoder = StubPayloadDecoder(
        ComponentDescriptor("Failing error decoder", "1", "application"),
        _result(),
        error=failure,
    )
    observed: list[BaseException] = []

    def assert_failure(actual: BaseException) -> None:
        """Require the exact configured failure rather than a wrapper."""
        assert actual is failure
        observed.append(actual)

    ErrorPayloadDecoderContractSuite(decoder).assert_decode_failure(
        raw_data,
        assertion=assert_failure,
    )

    assert observed == [failure]
    assert decoder.raw_data == (raw_data,)


def test_failure_assertion_rejects_success_after_one_invocation() -> None:
    """Fail a negative case without calling its failure callback."""
    recorder = ComponentCallRecorder()
    decoder = _RecordingDecoder(_result(), recorder)
    callback_calls: list[BaseException] = []

    def record_unexpected_failure(error: BaseException) -> None:
        """Record a callback invocation that must not occur on success."""
        callback_calls.append(error)

    try:
        ErrorPayloadDecoderContractSuite(decoder).assert_decode_failure(
            Bytes(b"valid-error"),
            assertion=record_unexpected_failure,
        )
    except AssertionError as error:
        assert str(error) == "decoder was expected to fail."
    else:
        raise AssertionError("Expected a successful decoder to fail the case.")

    assert recorder.calls == ("decode_error",)
    assert callback_calls == []


def test_decode_assertion_rejects_invalid_runtime_result() -> None:
    """Require a nominal error wrapper before caller assertions."""
    callback_calls: list[ErasedRuntimeValue] = []

    def record_unexpected_result(result: ErasedRuntimeValue) -> None:
        """Record a callback invocation that malformed output must prevent."""
        callback_calls.append(result)

    try:
        ErrorPayloadDecoderContractSuite(_InvalidResultDecoder()).assert_decode(
            Bytes(b"valid-error"),
            assertion=record_unexpected_result,
        )
    except AssertionError as error:
        assert str(error) == "decoder must return an ErasedRuntimeValue."
    else:
        raise AssertionError("Expected malformed decoder output to fail.")

    assert callback_calls == []


def test_suite_preserves_unexpected_decoder_and_callback_failures() -> None:
    """Propagate decoder and callback failures by exact identity."""
    decoder_failure = RuntimeError("unexpected error decoder failure")
    failing_decoder = StubPayloadDecoder(
        ComponentDescriptor("Failing error decoder", "1", "application"),
        _result(),
        error=decoder_failure,
    )
    callback_failure = AssertionError("decoded error payload mismatch")

    def fail_result_callback(result: ErasedRuntimeValue) -> None:
        """Raise the exact owning-framework result assertion failure."""
        del result
        raise callback_failure

    _assert_raises_identity(
        lambda: ErrorPayloadDecoderContractSuite(failing_decoder).assert_decode(
            Bytes(b"error"),
            assertion=fail_result_callback,
        ),
        decoder_failure,
    )
    _assert_raises_identity(
        lambda: ErrorPayloadDecoderContractSuite(
            _RecordingDecoder(_result(), ComponentCallRecorder())
        ).assert_decode(Bytes(b"error"), assertion=fail_result_callback),
        callback_failure,
    )

    def fail_error_callback(error: BaseException) -> None:
        """Raise the exact callback failure after observing decoder failure."""
        assert error is decoder_failure
        raise callback_failure

    _assert_raises_identity(
        lambda: ErrorPayloadDecoderContractSuite(failing_decoder).assert_decode_failure(
            Bytes(b"malformed-error"),
            assertion=fail_error_callback,
        ),
        callback_failure,
    )


def test_suite_validates_decoder_and_assertion_boundaries_before_calls() -> None:
    """Reject malformed setup and callbacks at their exact boundaries."""
    invalid_decoders = (
        cast(PayloadDecoder, object()),
        cast(PayloadDecoder, _InvalidDescriptorDecoder()),
        cast(PayloadDecoder, _AsyncDecoder()),
    )
    expected_messages = (
        "decoder must implement PayloadDecoder.",
        "decoder descriptor must be a ComponentDescriptor.",
        "decoder operation must be synchronous.",
    )
    for decoder, message in zip(invalid_decoders, expected_messages, strict=True):
        try:
            ErrorPayloadDecoderContractSuite(decoder)
        except TypeError as error:
            assert str(error) == message
        else:
            raise AssertionError("Expected invalid error decoder setup to fail.")

    recorder = ComponentCallRecorder()
    suite = ErrorPayloadDecoderContractSuite(_RecordingDecoder(_result(), recorder))

    async def async_assertion(result: ErasedRuntimeValue) -> None:
        """Provide an invalid coroutine callback without executing it."""
        del result

    invalid_assertions = (
        cast(Callable[[ErasedRuntimeValue], None], object()),
        cast(Callable[[ErasedRuntimeValue], None], async_assertion),
    )
    for assertion in invalid_assertions:
        try:
            suite.assert_decode(Bytes(b"error"), assertion=assertion)
        except TypeError:
            pass
        else:
            raise AssertionError("Expected invalid assertion callback to fail.")

    assert recorder.calls == ()


def test_suite_exposes_only_atomic_error_decoder_operations() -> None:
    """Keep signatures synchronous and exclude adjacent error behavior."""
    decode = ErrorPayloadDecoderContractSuite.assert_decode
    failure = ErrorPayloadDecoderContractSuite.assert_decode_failure

    assert tuple(inspect.signature(decode).parameters) == (
        "self",
        "raw_data",
        "assertion",
    )
    assert tuple(inspect.signature(failure).parameters) == (
        "self",
        "raw_data",
        "assertion",
    )
    assert get_type_hints(decode) == {
        "raw_data": Bytes,
        "assertion": Callable[[ErasedRuntimeValue], None],
        "return": type(None),
    }
    assert get_type_hints(failure) == {
        "raw_data": Bytes,
        "assertion": Callable[[BaseException], None],
        "return": type(None),
    }
    assert not inspect.iscoroutinefunction(decode)
    assert not inspect.iscoroutinefunction(failure)

    suite = ErrorPayloadDecoderContractSuite(
        _RecordingDecoder(_result(), ComponentCallRecorder())
    )
    for forbidden_member in (
        "load_fixture",
        "select_decoder",
        "validate_media_type",
        "parse_error",
        "map_error",
        "build_fallback_error",
        "send",
        "reset",
        "run",
    ):
        assert not hasattr(suite, forbidden_member)

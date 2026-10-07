"""Reusable behavior and boundary tests for PayloadEncoderContractSuite."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import cast, get_type_hints

from mconet.core.domain import Bytes, MediaType, OpenIdentifier
from mconet.core.spi import (
    ComponentDescriptor,
    ErasedRuntimeValue,
    PayloadEncoder,
    TransportBody,
)
from mconet.testing import (
    ComponentCallRecorder,
    PayloadEncoderContractSuite,
    StubPayloadEncoder,
)


def _body(content: bytes = b'{"message":"hello"}') -> TransportBody:
    """Build one complete immutable body for encoder contract cases."""
    return TransportBody(Bytes(content), MediaType("application", "json"))


def _payload() -> ErasedRuntimeValue:
    """Build one protocol-native wrapper retained by exact identity."""
    return ErasedRuntimeValue(
        OpenIdentifier("protocol.request"),
        {"message": "hello"},
        "request.v1",
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


class _RecordingEncoder:
    """Structural encoder exposing exact inputs, output, and call order."""

    __slots__ = ("_descriptor", "_payloads", "_recorder", "_result")

    def __init__(
        self,
        result: TransportBody,
        recorder: ComponentCallRecorder,
    ) -> None:
        """Retain one exact output and external invocation recorder."""
        self._descriptor = ComponentDescriptor("Recording encoder", "1", "application")
        self._result = result
        self._recorder = recorder
        self._payloads: list[ErasedRuntimeValue] = []

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return valid immutable component metadata."""
        return self._descriptor

    @property
    def payloads(self) -> tuple[ErasedRuntimeValue, ...]:
        """Return an immutable snapshot of exact received wrappers."""
        return tuple(self._payloads)

    def encode(self, payload: ErasedRuntimeValue) -> TransportBody:
        """Record one exact input and return the configured exact body."""
        self._recorder.record("encode")
        self._payloads.append(payload)
        return self._result


class _InvalidResultEncoder:
    """Claim the protocol signature while returning an invalid runtime value."""

    descriptor = ComponentDescriptor("Invalid encoder", "1", "application")

    def encode(self, payload: ErasedRuntimeValue) -> TransportBody:
        """Discard the input and expose malformed implementation behavior."""
        del payload
        return cast(TransportBody, object())


class _InvalidDescriptorEncoder:
    """Expose a structurally present but nominally invalid descriptor."""

    descriptor = cast(ComponentDescriptor, object())

    def encode(self, payload: ErasedRuntimeValue) -> TransportBody:
        """Provide the method shape required for descriptor validation."""
        del payload
        return _body()


class _AsyncEncoder:
    """Expose an invalid asynchronous implementation of the sync SPI."""

    descriptor = ComponentDescriptor("Async encoder", "1", "application")

    async def encode(self, payload: ErasedRuntimeValue) -> TransportBody:
        """Return a body asynchronously to exercise setup rejection."""
        del payload
        return _body()


def test_suite_validates_stub_input_and_successful_output_contract() -> None:
    """Preserve the exact input and expose complete encoded body facts."""
    body = _body()
    payload = _payload()
    encoder = StubPayloadEncoder(
        ComponentDescriptor("Stub encoder", "1", "application"),
        body,
    )
    observed: list[TransportBody] = []

    def assert_body(actual: TransportBody) -> None:
        """Verify identity plus protocol-owned bytes and media type."""
        assert actual is body
        assert actual.bytes == b'{"message":"hello"}'
        assert actual.media_type == MediaType("application", "json")
        observed.append(actual)

    PayloadEncoderContractSuite(encoder).assert_encode(
        payload,
        assertion=assert_body,
    )

    assert observed == [body]
    assert encoder.payloads == (payload,)
    assert encoder.payloads[0] is payload


def test_suite_accepts_structural_encoder_and_invokes_it_once() -> None:
    """Require no SDK inheritance while retaining input and output identity."""
    recorder = ComponentCallRecorder()
    body = _body(b"encoded")
    payload = _payload()
    encoder = _RecordingEncoder(body, recorder)

    def assert_identity(actual: TransportBody) -> None:
        """Require the exact custom encoder result without reconstruction."""
        assert actual is body

    PayloadEncoderContractSuite(encoder).assert_encode(
        payload,
        assertion=assert_identity,
    )

    assert recorder.calls == ("encode",)
    assert encoder.payloads == (payload,)
    assert encoder.payloads[0] is payload


def test_suite_passes_exact_encoder_failure_to_assertion() -> None:
    """Retain BaseException identity and failed-call input evidence."""
    failure = KeyboardInterrupt("configured encoding interruption")
    payload = _payload()
    encoder = StubPayloadEncoder(
        ComponentDescriptor("Failing encoder", "1", "application"),
        _body(),
        error=failure,
    )
    observed: list[BaseException] = []

    def assert_failure(actual: BaseException) -> None:
        """Require the exact configured failure rather than a wrapper."""
        assert actual is failure
        observed.append(actual)

    PayloadEncoderContractSuite(encoder).assert_encode_failure(
        payload,
        assertion=assert_failure,
    )

    assert observed == [failure]
    assert encoder.payloads == (payload,)


def test_failure_assertion_rejects_success_after_one_invocation() -> None:
    """Fail a negative case without calling its failure callback."""
    recorder = ComponentCallRecorder()
    encoder = _RecordingEncoder(_body(), recorder)
    callback_calls: list[BaseException] = []

    def record_unexpected_failure(error: BaseException) -> None:
        """Record a callback invocation that must not occur on success."""
        callback_calls.append(error)

    try:
        PayloadEncoderContractSuite(encoder).assert_encode_failure(
            _payload(),
            assertion=record_unexpected_failure,
        )
    except AssertionError as error:
        assert str(error) == "encoder was expected to fail."
    else:
        raise AssertionError("Expected a successful encoder to fail the case.")

    assert recorder.calls == ("encode",)
    assert callback_calls == []


def test_success_assertion_rejects_invalid_runtime_result() -> None:
    """Require a nominal TransportBody before invoking caller assertions."""
    callback_calls: list[TransportBody] = []

    def record_unexpected_body(body: TransportBody) -> None:
        """Record a callback invocation that malformed output must prevent."""
        callback_calls.append(body)

    try:
        PayloadEncoderContractSuite(_InvalidResultEncoder()).assert_encode(
            _payload(),
            assertion=record_unexpected_body,
        )
    except AssertionError as error:
        assert str(error) == "encoder must return a TransportBody."
    else:
        raise AssertionError("Expected malformed encoder output to fail.")

    assert callback_calls == []


def test_suite_preserves_unexpected_encoder_and_callback_failures() -> None:
    """Propagate both failure sources by identity without translation."""
    encoder_failure = RuntimeError("unexpected encoder failure")
    failing_encoder = StubPayloadEncoder(
        ComponentDescriptor("Failing encoder", "1", "application"),
        _body(),
        error=encoder_failure,
    )
    callback_failure = AssertionError("protocol body mismatch")

    def fail_callback(body: TransportBody) -> None:
        """Raise the exact owning-framework assertion failure."""
        del body
        raise callback_failure

    _assert_raises_identity(
        lambda: PayloadEncoderContractSuite(failing_encoder).assert_encode(
            _payload(),
            assertion=fail_callback,
        ),
        encoder_failure,
    )
    _assert_raises_identity(
        lambda: PayloadEncoderContractSuite(
            _RecordingEncoder(_body(), ComponentCallRecorder())
        ).assert_encode(_payload(), assertion=fail_callback),
        callback_failure,
    )

    def fail_error_callback(error: BaseException) -> None:
        """Raise the exact callback failure after observing an encoder error."""
        assert error is encoder_failure
        raise callback_failure

    _assert_raises_identity(
        lambda: PayloadEncoderContractSuite(failing_encoder).assert_encode_failure(
            _payload(),
            assertion=fail_error_callback,
        ),
        callback_failure,
    )


def test_suite_validates_encoder_and_assertion_boundaries_before_calls() -> None:
    """Reject malformed setup and callbacks at their exact boundaries."""
    invalid_encoders = (
        cast(PayloadEncoder, object()),
        cast(PayloadEncoder, _InvalidDescriptorEncoder()),
        cast(PayloadEncoder, _AsyncEncoder()),
    )
    expected_messages = (
        "encoder must implement PayloadEncoder.",
        "encoder descriptor must be a ComponentDescriptor.",
        "encoder operation must be synchronous.",
    )
    for encoder, message in zip(invalid_encoders, expected_messages, strict=True):
        try:
            PayloadEncoderContractSuite(encoder)
        except TypeError as error:
            assert str(error) == message
        else:
            raise AssertionError("Expected invalid encoder setup to fail.")

    recorder = ComponentCallRecorder()
    suite = PayloadEncoderContractSuite(_RecordingEncoder(_body(), recorder))

    async def async_assertion(body: TransportBody) -> None:
        """Provide an invalid coroutine callback without executing it."""
        del body

    invalid_assertions = (
        cast(Callable[[TransportBody], None], object()),
        cast(Callable[[TransportBody], None], async_assertion),
    )
    for assertion in invalid_assertions:
        try:
            suite.assert_encode(_payload(), assertion=assertion)
        except TypeError:
            pass
        else:
            raise AssertionError("Expected invalid assertion callback to fail.")

    assert recorder.calls == ()


def test_suite_exposes_only_atomic_encoder_contract_operations() -> None:
    """Keep signatures synchronous and exclude adjacent pipeline behavior."""
    encode = PayloadEncoderContractSuite.assert_encode
    failure = PayloadEncoderContractSuite.assert_encode_failure

    assert tuple(inspect.signature(encode).parameters) == (
        "self",
        "payload",
        "assertion",
    )
    assert tuple(inspect.signature(failure).parameters) == (
        "self",
        "payload",
        "assertion",
    )
    assert get_type_hints(encode) == {
        "payload": ErasedRuntimeValue,
        "assertion": Callable[[TransportBody], None],
        "return": type(None),
    }
    assert get_type_hints(failure) == {
        "payload": ErasedRuntimeValue,
        "assertion": Callable[[BaseException], None],
        "return": type(None),
    }
    assert not inspect.iscoroutinefunction(encode)
    assert not inspect.iscoroutinefunction(failure)

    suite = PayloadEncoderContractSuite(
        _RecordingEncoder(_body(), ComponentCallRecorder())
    )
    for forbidden_member in (
        "load_fixture",
        "serialize",
        "authorize",
        "send",
        "decode",
        "reset",
        "run",
    ):
        assert not hasattr(suite, forbidden_member)

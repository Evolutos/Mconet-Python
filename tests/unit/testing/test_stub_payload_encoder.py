"""Input recording and outcome tests for StubPayloadEncoder."""

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
from mconet.testing import StubPayloadEncoder


def _body(content: bytes = b'{"message":"hello"}') -> TransportBody:
    """Build one complete immutable body used as the configured result."""
    # Explicit values keep Stub tests independent from a real JSON serializer
    # while exercising the complete-byte transport representation.
    return TransportBody(Bytes(content), MediaType("application", "json"))


def _encoder(
    *,
    result: TransportBody | None = None,
    error: BaseException | None = None,
) -> StubPayloadEncoder:
    """Create one valid encoder Stub with an optional configured failure."""
    # None selects a fresh default body only in this test helper; production
    # construction always requires an explicit nominal TransportBody.
    selected_result = _body() if result is None else result
    return StubPayloadEncoder(
        ComponentDescriptor("Stub encoder", "1", "application"),
        selected_result,
        error=error,
    )


def _assert_raises_identity(
    action: Callable[[], object],
    expected: BaseException,
) -> None:
    """Require one call to raise the exact configured failure instance."""
    try:
        action()
    except BaseException as error:
        # Identity proves the Stub does not wrap, normalize, copy, or replace the
        # configured exception with a generic encoding failure.
        assert error is expected
        return
    raise AssertionError(f"Expected {type(expected).__name__} to be raised.")


def test_stub_structurally_implements_payload_encoder() -> None:
    """Expose complete encoding behavior without inheritance or registration."""
    encoder = _encoder()

    accepted: PayloadEncoder = encoder

    # Static and runtime recognition agree on the same exact ordinary object and
    # descriptor, without a component ID, base class, or generic codec wrapper.
    assert accepted is encoder
    assert isinstance(encoder, PayloadEncoder)
    assert encoder.descriptor.name == "Stub encoder"


def test_stub_records_exact_payloads_and_returns_exact_result() -> None:
    """Preserve ordered input identities and one configured body identity."""
    body = _body()
    encoder = _encoder(result=body)
    first_native = {"message": "first"}
    first = ErasedRuntimeValue(
        OpenIdentifier("protocol.request"),
        first_native,
        "request.v1",
    )
    second = ErasedRuntimeValue(OpenIdentifier("protocol.request"), None)

    first_result = encoder.encode(first)
    second_result = encoder.encode(second)

    # Each call returns the prebuilt body without encoding or copying, while the
    # record retains exact payload objects and their original native value.
    assert first_result is body
    assert second_result is body
    assert encoder.payloads == (first, second)
    assert encoder.payloads[0] is first
    assert encoder.payloads[1] is second
    assert encoder.payloads[0].value is first_native


def test_stub_records_failed_attempt_before_raising_exact_error() -> None:
    """Make every failed encoding input observable without replacing its error."""
    failure = RuntimeError("configured encoding failure")
    encoder = _encoder(error=failure)
    first = ErasedRuntimeValue(OpenIdentifier("protocol.request"), {"index": 1})
    second = ErasedRuntimeValue(OpenIdentifier("protocol.request"), {"index": 2})

    _assert_raises_identity(lambda: encoder.encode(first), failure)
    _assert_raises_identity(lambda: encoder.encode(second), failure)

    # Recording occurs before the failure branch on every call, so tests can
    # assert both attempted values and ordering after deterministic faults.
    assert encoder.payloads == (first, second)


def test_payload_record_snapshots_are_immutable_and_time_bounded() -> None:
    """Prevent callers and later encode calls from changing prior snapshots."""
    encoder = _encoder()
    first = ErasedRuntimeValue(OpenIdentifier("protocol.request"), "first")
    second = ErasedRuntimeValue(OpenIdentifier("protocol.request"), "second")

    encoder.encode(first)
    first_snapshot = encoder.payloads
    encoder.encode(second)

    # Tuple storage rejects membership mutation, and an earlier returned tuple
    # remains a one-call view after the Stub records a later input.
    assert first_snapshot == (first,)
    assert encoder.payloads == (first, second)
    assert not hasattr(first_snapshot, "append")


def test_stub_preserves_an_explicit_empty_transport_body() -> None:
    """Return zero encoded bytes as a present result without inventing content."""
    body = _body(b"")
    encoder = _encoder(result=body)
    payload = ErasedRuntimeValue(OpenIdentifier("protocol.empty"), None)

    result = encoder.encode(payload)

    # Empty bytes are not treated as an absent result, a default body, or a
    # signal to inspect and serialize the native payload.
    assert result is body
    assert result.bytes == b""
    assert encoder.payloads == (payload,)


def test_stub_validates_configuration_and_dynamic_payloads() -> None:
    """Reject malformed setup and inputs at their exact test-double boundaries."""
    descriptor = ComponentDescriptor("Stub encoder", "1", "application")
    body = _body()
    invalid_calls: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: StubPayloadEncoder(cast(ComponentDescriptor, object()), body),
            "descriptor must be a ComponentDescriptor",
        ),
        (
            lambda: StubPayloadEncoder(
                descriptor,
                cast(TransportBody, object()),
            ),
            "result must be a TransportBody",
        ),
        (
            lambda: StubPayloadEncoder(
                descriptor,
                body,
                error=cast(BaseException, "failure"),
            ),
            "error must be a BaseException or None",
        ),
        (
            lambda: StubPayloadEncoder(descriptor, body).encode(
                cast(ErasedRuntimeValue, object())
            ),
            "payload must be an ErasedRuntimeValue",
        ),
    )

    for action, message in invalid_calls:
        try:
            action()
        except TypeError as error:
            # Stable field-specific diagnostics keep test setup failures distinct
            # from actual codec or Runtime behavior under test.
            assert message in str(error)
        else:
            raise AssertionError("Expected invalid Stub configuration to fail.")


def test_stub_matches_encoder_surface_without_adjacent_pipeline_controls() -> None:
    """Expose exact encoder behavior plus its required local payload record."""
    encoder = _encoder()
    method = StubPayloadEncoder.encode
    annotations = get_type_hints(method)

    # The concrete method preserves the SPI's single synchronous payload input;
    # the payload record is the only additional surface required by this Stub.
    assert tuple(inspect.signature(method).parameters) == ("self", "payload")
    assert annotations == {
        "payload": ErasedRuntimeValue,
        "return": TransportBody,
    }
    assert not inspect.iscoroutinefunction(method)
    assert isinstance(inspect.getattr_static(StubPayloadEncoder, "payloads"), property)

    # No generic call recorder, dynamic reconfiguration, or adjacent execution
    # stages are included in this atomic test double.
    for forbidden_member in (
        "calls",
        "configure",
        "reset",
        "prepare_plan",
        "authorize",
        "send",
        "decode",
    ):
        assert not hasattr(encoder, forbidden_member)

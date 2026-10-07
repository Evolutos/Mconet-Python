"""Byte recording and outcome tests for StubPayloadDecoder."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import cast, get_type_hints

from mconet.core.domain import Bytes, OpenIdentifier
from mconet.core.spi import ComponentDescriptor, ErasedRuntimeValue, PayloadDecoder
from mconet.testing import StubPayloadDecoder


def _result(value: object = None) -> ErasedRuntimeValue:
    """Build one protocol-native value used as the configured result."""
    # A fixed portable type ID keeps the Stub tests independent from a real
    # response schema while allowing every native Python value, including None.
    return ErasedRuntimeValue(OpenIdentifier("protocol.response"), value)


def _decoder(
    *,
    result: ErasedRuntimeValue | None = None,
    error: BaseException | None = None,
) -> StubPayloadDecoder:
    """Create one valid decoder Stub with an optional configured failure."""
    # None selects a fresh default wrapper only in this helper; production
    # construction always requires an explicit ErasedRuntimeValue result.
    selected_result = _result() if result is None else result
    return StubPayloadDecoder(
        ComponentDescriptor("Stub decoder", "1", "application"),
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
        # configured exception with a generic decoding failure.
        assert error is expected
        return
    raise AssertionError(f"Expected {type(expected).__name__} to be raised.")


def test_stub_structurally_implements_payload_decoder() -> None:
    """Expose complete decoding behavior without inheritance or registration."""
    decoder = _decoder()

    accepted: PayloadDecoder = decoder

    # Static and runtime recognition agree on the same ordinary object and its
    # descriptor, without a component ID, base class, or generic codec wrapper.
    assert accepted is decoder
    assert isinstance(decoder, PayloadDecoder)
    assert decoder.descriptor.name == "Stub decoder"


def test_stub_records_exact_bytes_and_returns_exact_result() -> None:
    """Preserve ordered byte identities and one configured result identity."""
    native_result = {"status": "completed"}
    result = _result(native_result)
    decoder = _decoder(result=result)
    first = Bytes(bytes((0, 127, 255)))
    second = Bytes(b'{"status":"completed"}')

    first_result = decoder.decode(first)
    second_result = decoder.decode(second)

    # Calls retain each exact immutable input without parsing or copying, and
    # both return the same configured wrapper and native value identities.
    assert first_result is result
    assert second_result is result
    assert decoder.raw_data == (first, second)
    assert decoder.raw_data[0] is first
    assert decoder.raw_data[1] is second
    assert first_result.value is native_result


def test_stub_records_failed_attempt_before_raising_exact_error() -> None:
    """Make every failed decoding input observable without replacing its error."""
    failure = ValueError("configured decoding failure")
    decoder = _decoder(error=failure)
    first = Bytes(b"first")
    second = Bytes(b"second")

    _assert_raises_identity(lambda: decoder.decode(first), failure)
    _assert_raises_identity(lambda: decoder.decode(second), failure)

    # Recording occurs before the failure branch on every call, so tests can
    # assert both attempted byte sequences and their ordering after faults.
    assert decoder.raw_data == (first, second)


def test_raw_data_snapshots_are_immutable_and_time_bounded() -> None:
    """Prevent callers and later decode calls from changing prior snapshots."""
    decoder = _decoder()
    first = Bytes(b"first")
    second = Bytes(b"second")

    decoder.decode(first)
    first_snapshot = decoder.raw_data
    decoder.decode(second)

    # Tuple storage rejects membership mutation, and an earlier returned tuple
    # remains a one-call view after the Stub records a later byte input.
    assert first_snapshot == (first,)
    assert decoder.raw_data == (first, second)
    assert not hasattr(first_snapshot, "append")


def test_stub_records_explicit_empty_bytes() -> None:
    """Preserve zero response bytes as a present complete decoder input."""
    result = _result(None)
    decoder = _decoder(result=result)
    raw_data = Bytes(b"")

    decoded = decoder.decode(raw_data)

    # Empty bytes are neither absent nor replaced with a default representation;
    # the selected concrete decoder alone decides their protocol validity.
    assert decoded is result
    assert decoder.raw_data == (raw_data,)
    assert decoder.raw_data[0] is raw_data


def test_stub_validates_configuration_and_dynamic_byte_inputs() -> None:
    """Reject malformed setup and inputs at their exact test-double boundaries."""
    descriptor = ComponentDescriptor("Stub decoder", "1", "application")
    result = _result()
    invalid_calls: tuple[tuple[Callable[[], object], str], ...] = (
        (
            lambda: StubPayloadDecoder(cast(ComponentDescriptor, object()), result),
            "descriptor must be a ComponentDescriptor",
        ),
        (
            lambda: StubPayloadDecoder(
                descriptor,
                cast(ErasedRuntimeValue, object()),
            ),
            "result must be an ErasedRuntimeValue",
        ),
        (
            lambda: StubPayloadDecoder(
                descriptor,
                result,
                error=cast(BaseException, "failure"),
            ),
            "error must be a BaseException or None",
        ),
        (
            lambda: StubPayloadDecoder(descriptor, result).decode(
                cast(Bytes, bytearray(b"mutable"))
            ),
            "raw_data must be an immutable bytes value",
        ),
    )

    for action, message in invalid_calls:
        try:
            action()
        except TypeError as error:
            # Stable field-specific diagnostics distinguish malformed Stub use
            # from the concrete codec behavior that a contract test exercises.
            assert message in str(error)
        else:
            raise AssertionError("Expected invalid Stub configuration to fail.")


def test_stub_matches_decoder_surface_without_adjacent_pipeline_controls() -> None:
    """Expose exact decoder behavior plus its required local byte record."""
    decoder = _decoder()
    method = StubPayloadDecoder.decode
    annotations = get_type_hints(method)

    # The concrete method preserves the SPI's single synchronous byte input;
    # the raw-data record is the only additional surface required by this Stub.
    assert tuple(inspect.signature(method).parameters) == ("self", "raw_data")
    assert annotations == {
        "raw_data": Bytes,
        "return": ErasedRuntimeValue,
    }
    assert not inspect.iscoroutinefunction(method)
    assert isinstance(inspect.getattr_static(StubPayloadDecoder, "raw_data"), property)

    # No generic call recorder, dynamic reconfiguration, or adjacent response
    # stages are included in this atomic test double.
    for forbidden_member in (
        "calls",
        "configure",
        "reset",
        "select_decoder",
        "parse_response",
        "map_response",
        "assemble_output",
        "send",
    ):
        assert not hasattr(decoder, forbidden_member)

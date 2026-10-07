"""Tests for normalized-outcome payload decoder dispatch."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from mconet.core.domain import Bytes, OpenIdentifier
from mconet.core.runtime._payload_decoder_dispatch import dispatch_payload_decoder
from mconet.core.spi import (
    ComponentDescriptor,
    ErasedRuntimeValue,
    PayloadDecoder,
    TransportOutcome,
)


@dataclass(slots=True)
class _Decoder:
    """Complete decoder fixture that records forbidden dispatch execution."""

    descriptor: ComponentDescriptor
    decode_calls: int = 0

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Record actual decoding while returning a valid erased payload."""
        # Dispatch must never enter this behavior. The complete implementation
        # ensures runtime protocol checks exercise the real PayloadDecoder shape.
        self.decode_calls += 1
        return ErasedRuntimeValue(OpenIdentifier("protocol.payload"), raw_data)


@dataclass(frozen=True, slots=True)
class _DescriptorOnlyComponent:
    """Runtime component fixture that deliberately omits decoder behavior."""

    descriptor: ComponentDescriptor


def _decoder(name: str) -> _Decoder:
    """Build one identifiable preselected decoder fixture."""
    # Type-contract compatibility belongs to the completed preselection stage;
    # dispatch needs only the RuntimeComponent and decode behavior boundary.
    return _Decoder(ComponentDescriptor(name, "1", "plugin"))


def _outcome(value: str) -> TransportOutcome:
    """Build a normalized standard or extension transport outcome."""
    # Use the same open identifier construction available to real transports so
    # unknown outcomes exercise the production forward-compatibility path.
    return TransportOutcome(OpenIdentifier(value))


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require the intended programming error and stable message fragment."""
    try:
        action()
    except exception_type as error:
        # Stable text distinguishes nominal argument validation from incidental
        # protocol, fixture, or attribute-access failures.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_success_outcome_returns_exact_preselected_success_decoder() -> None:
    """Route only normalized success to the successful-response instance."""
    success = _decoder("success")
    error = _decoder("error")

    selected = dispatch_payload_decoder(_outcome("success"), success, error)

    # Identity and untouched counters prove dispatch neither wraps, replaces,
    # nor executes either already preselected component.
    assert selected is success
    assert success.decode_calls == error.decode_calls == 0


def test_service_error_returns_exact_preselected_error_decoder() -> None:
    """Route a normalized service failure to the error-response instance."""
    success = _decoder("success")
    error = _decoder("error")

    selected = dispatch_payload_decoder(_outcome("service_error"), success, error)

    assert selected is error
    assert success.decode_calls == error.decode_calls == 0


def test_transport_error_returns_preselected_error_decoder() -> None:
    """Route a normalized transport failure without inspecting native status."""
    success = _decoder("success")
    error = _decoder("error")

    selected = dispatch_payload_decoder(_outcome("transport_error"), success, error)

    # The dispatcher sees only normalized identity, so transport-specific status,
    # exception, headers, and body facts cannot alter this branch.
    assert selected is error
    assert success.decode_calls == error.decode_calls == 0


def test_future_non_success_outcome_uses_error_decoder() -> None:
    """Give an unknown open outcome conservative non-success semantics."""
    success = _decoder("success")
    error = _decoder("error")

    selected = dispatch_payload_decoder(
        _outcome("vendor.partial_response"),
        success,
        error,
    )

    # Unknown values remain exact in TransportOutcome, but cannot silently enter
    # the success parsing path without a future explicit Core contract change.
    assert selected is error
    assert success.decode_calls == error.decode_calls == 0


def test_same_instance_is_preserved_when_preselected_for_both_paths() -> None:
    """Allow two snapshot fields to intentionally reference one decoder object."""
    shared = _decoder("shared")

    selected_success = dispatch_payload_decoder(
        _outcome("success"),
        shared,
        shared,
    )
    selected_error = dispatch_payload_decoder(
        _outcome("service_error"),
        shared,
        shared,
    )

    # Dispatch selects fields rather than enforcing component distinctness; a
    # codec that supports both planned schemas may legitimately occupy both.
    assert selected_success is shared
    assert selected_error is shared
    assert shared.decode_calls == 0


def test_rejects_bare_outcome_text_before_dispatch() -> None:
    """Reject native or primitive substitutes for normalized outcome values."""
    success = _decoder("success")
    error = _decoder("error")

    _assert_raises(
        TypeError,
        lambda: dispatch_payload_decoder(
            cast(TransportOutcome, "success"),
            success,
            error,
        ),
        "outcome must be a TransportOutcome",
    )
    assert success.decode_calls == error.decode_calls == 0


def test_validates_both_preselected_decoders_before_branching() -> None:
    """Reject either malformed snapshot field regardless of current outcome."""
    decoder = _decoder("valid")
    not_decoder = _DescriptorOnlyComponent(
        ComponentDescriptor("not-decoder", "1", "application")
    )

    _assert_raises(
        TypeError,
        lambda: dispatch_payload_decoder(
            _outcome("service_error"),
            cast(PayloadDecoder, not_decoder),
            decoder,
        ),
        "success_payload_decoder must be a PayloadDecoder",
    )
    _assert_raises(
        TypeError,
        lambda: dispatch_payload_decoder(
            _outcome("success"),
            decoder,
            cast(PayloadDecoder, not_decoder),
        ),
        "error_payload_decoder must be a PayloadDecoder",
    )
    assert decoder.decode_calls == 0

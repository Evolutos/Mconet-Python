"""Tests for error-response payload decoder preselection."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from mconet.core.domain import Bytes, MediaType, ModelInteractionError, OpenIdentifier
from mconet.core.runtime._component_source_merge import ComponentSourceLayers
from mconet.core.runtime._payload_decoder_selection import (
    select_error_payload_decoder,
    select_success_payload_decoder,
)
from mconet.core.spi import (
    ComponentDescriptor,
    ComponentTypeContract,
    ComponentTypePort,
    DecoderSelection,
    ErasedRuntimeValue,
)

_JSON = MediaType("application", "json")
_PROBLEM_JSON = MediaType("application", "problem+json")


@dataclass(slots=True)
class _Decoder:
    """Complete payload decoder fixture with observable execution count."""

    descriptor: ComponentDescriptor
    decode_calls: int = 0

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Record actual decoding without participating in preselection."""
        # A valid implementation keeps runtime protocol checks meaningful. Every
        # preselection test asserts that this behavior remains uncalled.
        self.decode_calls += 1
        return ErasedRuntimeValue(OpenIdentifier("protocol.error"), raw_data)


def _decoder(
    name: str,
    media_type: MediaType,
    schema_id: str,
) -> _Decoder:
    """Build one decoder with explicit encoded-input and payload-output facts."""
    # Media type belongs to bytes consumed by the decoder, while schema identity
    # belongs to the decoded protocol payload returned to the adapter.
    contract = ComponentTypeContract(
        inputs=(
            ComponentTypePort(
                "encodedError",
                OpenIdentifier("transport.bytes"),
                media_type=media_type,
            ),
        ),
        outputs=(
            ComponentTypePort(
                "errorPayload",
                OpenIdentifier("protocol.error"),
                schema_id=schema_id,
            ),
        ),
    )
    return _Decoder(ComponentDescriptor(name, "1", "plugin", contract))


def _layers(
    *,
    interaction: tuple[_Decoder, ...] = (),
    client: tuple[_Decoder, ...] = (),
    integration: tuple[_Decoder, ...] = (),
    defaults: tuple[_Decoder, ...] = (),
) -> ComponentSourceLayers:
    """Assemble the exact four immutable candidate source layers."""
    # Fixtures already implement RuntimeComponent structurally; the cast only
    # bridges tuple invariance at this internal test boundary.
    return cast(
        ComponentSourceLayers,
        (interaction, client, integration, defaults),
    )


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Require the intended exception branch and stable message fragment."""
    try:
        action()
    except exception_type as error:
        # Checking stable text prevents an unrelated fixture failure from making
        # a negative selection test appear successful.
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_selects_exact_error_decoder_before_execution() -> None:
    """Return the sole error decoder matching planned media type and schema."""
    success = _decoder("success", _JSON, "schema.success")
    error = _decoder("error", _PROBLEM_JSON, "schema.error")

    result = select_error_payload_decoder(
        DecoderSelection(_PROBLEM_JSON, "schema.error"),
        _layers(integration=(success, error)),
    )

    # Exact identity proves the resolver neither wraps nor copies the selected
    # candidate; untouched counters prove no candidate behavior was executed.
    assert result is error
    assert success.decode_calls == 0
    assert error.decode_calls == 0


def test_success_and_error_plans_fix_independent_decoders() -> None:
    """Use separate plans to select different instances from shared candidates."""
    success = _decoder("success", _JSON, "schema.success")
    error = _decoder("error", _PROBLEM_JSON, "schema.error")
    layers = _layers(integration=(success, error))

    selected_success = select_success_payload_decoder(
        DecoderSelection(_JSON, "schema.success"),
        layers,
    )
    selected_error = select_error_payload_decoder(
        DecoderSelection(_PROBLEM_JSON, "schema.error"),
        layers,
    )

    # Independent snapshots are determined entirely before an outcome exists;
    # later outcome dispatch may choose between them but cannot reselect either.
    assert selected_success is success
    assert selected_error is error
    assert selected_success is not selected_error
    assert success.decode_calls == error.decode_calls == 0


def test_error_decoder_honors_highest_present_source_without_fallback() -> None:
    """Reject an incompatible direct error decoder instead of using a default."""
    explicit = _decoder("explicit", _JSON, "schema.success")
    fallback = _decoder("fallback", _PROBLEM_JSON, "schema.error")

    raised = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: select_error_payload_decoder(
                DecoderSelection(_PROBLEM_JSON, "schema.error"),
                _layers(interaction=(explicit,), defaults=(fallback,)),
            ),
            "No matching component was found",
        ),
    )

    # The explicit layer owns the field even when incompatible. Falling through
    # would silently replace an application-supplied error decoder after planning.
    assert raised.code == "component_not_found"
    assert explicit.decode_calls == fallback.decode_calls == 0


def test_error_decoder_rejects_same_layer_ambiguity() -> None:
    """Fail before I/O when an error plan cannot identify one candidate."""
    first = _decoder("first", _PROBLEM_JSON, "schema.error")
    second = _decoder("second", _PROBLEM_JSON, "schema.error")

    raised = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: select_error_payload_decoder(
                DecoderSelection(_PROBLEM_JSON, "schema.error"),
                _layers(client=(first, second)),
            ),
            "Multiple matching components were found",
        ),
    )

    # Candidate order and diagnostic names cannot break a same-priority tie.
    assert raised.code == "ambiguous_component_selection"
    assert first.decode_calls == second.decode_calls == 0


def test_error_decoder_applies_optional_criteria_independently() -> None:
    """Allow an error plan to constrain only representation or payload schema."""
    media_match = _decoder("media", _PROBLEM_JSON, "schema.other")
    schema_match = _decoder("schema", _JSON, "schema.error")
    layers = _layers(integration=(media_match, schema_match))

    assert (
        select_error_payload_decoder(
            DecoderSelection(media_type=_PROBLEM_JSON),
            layers,
        )
        is media_match
    )
    assert (
        select_error_payload_decoder(
            DecoderSelection(schema_id="schema.error"),
            layers,
        )
        is schema_match
    )


def test_error_decoder_rejects_non_selection_before_resolution() -> None:
    """Reject a structural look-alike before examining error candidates."""
    decoder = _decoder("error", _PROBLEM_JSON, "schema.error")

    _assert_raises(
        TypeError,
        lambda: select_error_payload_decoder(
            cast(DecoderSelection, object()),
            _layers(defaults=(decoder,)),
        ),
        "selection must be a DecoderSelection",
    )
    assert decoder.decode_calls == 0

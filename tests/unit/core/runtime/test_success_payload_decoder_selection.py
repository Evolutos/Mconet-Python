"""Tests for successful-response payload decoder preselection."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from mconet.core.domain import Bytes, MediaType, ModelInteractionError, OpenIdentifier
from mconet.core.runtime._component_source_merge import ComponentSourceLayers
from mconet.core.runtime._payload_decoder_selection import (
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
_VENDOR_JSON = MediaType(
    "application",
    "json",
    (("profile", "vendor"),),
)


@dataclass(slots=True)
class _Decoder:
    """Payload decoder fixture that records forbidden preselection execution."""

    descriptor: ComponentDescriptor
    decode_calls: int = 0

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Record decoding so tests can prove selection remains side-effect free."""
        # Preselection must never enter this method. Keeping a valid result makes
        # the fixture a complete PayloadDecoder rather than a failure-only stub.
        self.decode_calls += 1
        return ErasedRuntimeValue(OpenIdentifier("protocol.payload"), raw_data)


@dataclass(frozen=True, slots=True)
class _DescriptorOnlyComponent:
    """Non-decoder fixture with a decoder-shaped component type contract."""

    descriptor: ComponentDescriptor


def _decoder(
    name: str,
    *,
    media_type: MediaType | None = _JSON,
    schema_id: str | None = "schema.success",
    contract: ComponentTypeContract | None = None,
) -> _Decoder:
    """Build a decoder with independently configurable input and output facts."""
    # A caller-supplied contract supports direction and missing-contract tests.
    # Otherwise the input models encoded bytes and the output decoded payload.
    type_contract = contract
    if type_contract is None:
        type_contract = ComponentTypeContract(
            inputs=(
                ComponentTypePort(
                    "encoded",
                    OpenIdentifier("transport.bytes"),
                    media_type=media_type,
                ),
            ),
            outputs=(
                ComponentTypePort(
                    "payload",
                    OpenIdentifier("protocol.payload"),
                    schema_id=schema_id,
                ),
            ),
        )
    return _Decoder(ComponentDescriptor(name, "1", "plugin", type_contract))


def _layers(
    *,
    interaction: tuple[object, ...] = (),
    client: tuple[object, ...] = (),
    integration: tuple[object, ...] = (),
    defaults: tuple[object, ...] = (),
) -> ComponentSourceLayers:
    """Build four immutable source layers while retaining negative-test inputs."""
    # The cast is deliberately confined to the test boundary. Runtime validation
    # still decides whether every supplied object is a RuntimeComponent.
    return cast(
        ComponentSourceLayers,
        (interaction, client, integration, defaults),
    )


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Require one action to raise the expected type and stable text fragment."""
    try:
        action()
    except exception_type as error:
        # Stable fragments distinguish the intended validation or resolution
        # branch from unrelated fixture and protocol failures.
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_selects_exact_decoder_by_input_media_and_output_schema() -> None:
    """Select the sole integration decoder satisfying both directional facts."""
    wrong_media = _decoder("wrong-media", media_type=MediaType("text", "plain"))
    selected = _decoder("selected")
    wrong_schema = _decoder("wrong-schema", schema_id="schema.other")

    result = select_success_payload_decoder(
        DecoderSelection(_JSON, "schema.success"),
        _layers(integration=(wrong_media, selected, wrong_schema)),
    )

    # Object identity and untouched counters prove preselection does not copy,
    # wrap, or execute any candidate decoder.
    assert result is selected
    assert tuple(
        decoder.decode_calls for decoder in (wrong_media, selected, wrong_schema)
    ) == (0, 0, 0)


def test_optional_criteria_filter_independently() -> None:
    """Apply media-only and schema-only plans without inventing missing facts."""
    media_decoder = _decoder("media", schema_id="schema.media")
    schema_decoder = _decoder(
        "schema",
        media_type=MediaType("application", "cbor"),
    )

    # Separate candidate sets avoid ambiguity and demonstrate that each omitted
    # plan field has no hidden default value.
    assert (
        select_success_payload_decoder(
            DecoderSelection(media_type=_JSON),
            _layers(integration=(media_decoder, schema_decoder)),
        )
        is media_decoder
    )
    assert (
        select_success_payload_decoder(
            DecoderSelection(schema_id="schema.success"),
            _layers(integration=(media_decoder, schema_decoder)),
        )
        is schema_decoder
    )


def test_unconstrained_plan_requires_one_contracted_decoder() -> None:
    """Accept one contracted decoder and reject insufficient multi-candidate plans."""
    first = _decoder("first")
    second = _decoder("second")

    assert (
        select_success_payload_decoder(
            DecoderSelection(),
            _layers(defaults=(first,)),
        )
        is first
    )
    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: select_success_payload_decoder(
                DecoderSelection(),
                _layers(defaults=(first, second)),
            ),
            "Multiple matching components were found",
        ),
    )
    assert error.code == "ambiguous_component_selection"


def test_present_explicit_layer_never_falls_back_when_incompatible() -> None:
    """Reject an incompatible direct decoder without consulting lower sources."""
    explicit = _decoder("explicit", media_type=MediaType("text", "plain"))
    fallback = _decoder("fallback")

    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: select_success_payload_decoder(
                DecoderSelection(_JSON, "schema.success"),
                _layers(interaction=(explicit,), defaults=(fallback,)),
            ),
            "No matching component was found",
        ),
    )

    # Missing, rather than selecting the compatible default, enforces explicit
    # override authority and avoids a hidden source-precedence fallback.
    assert error.code == "component_not_found"
    assert fallback.decode_calls == 0


def test_media_type_matching_preserves_parameters_exactly() -> None:
    """Treat structured media-type parameters as part of planned compatibility."""
    plain = _decoder("plain", media_type=_JSON)
    profiled = _decoder("profiled", media_type=_VENDOR_JSON)

    result = select_success_payload_decoder(
        DecoderSelection(media_type=_VENDOR_JSON),
        _layers(integration=(plain, profiled)),
    )

    assert result is profiled


def test_selection_respects_port_direction() -> None:
    """Do not satisfy media from outputs or schema from encoded inputs."""
    reversed_contract = ComponentTypeContract(
        inputs=(
            ComponentTypePort(
                "encoded",
                OpenIdentifier("transport.bytes"),
                schema_id="schema.success",
            ),
        ),
        outputs=(
            ComponentTypePort(
                "payload",
                OpenIdentifier("protocol.payload"),
                media_type=_JSON,
            ),
        ),
    )
    reversed_decoder = _decoder("reversed", contract=reversed_contract)

    error = cast(
        ModelInteractionError,
        _assert_raises(
            ModelInteractionError,
            lambda: select_success_payload_decoder(
                DecoderSelection(_JSON, "schema.success"),
                _layers(integration=(reversed_decoder,)),
            ),
            "No matching component was found",
        ),
    )
    assert error.code == "component_not_found"


def test_non_decoder_does_not_match_decoder_selection() -> None:
    """Ignore a component that has matching metadata but no decoder behavior."""
    contract = _decoder("template").descriptor.type_contract
    assert contract is not None
    descriptor_only = _DescriptorOnlyComponent(
        ComponentDescriptor("descriptor-only", "1", "plugin", contract)
    )
    decoder = _decoder("decoder")

    result = select_success_payload_decoder(
        DecoderSelection(_JSON, "schema.success"),
        _layers(integration=(descriptor_only, decoder)),
    )

    assert result is decoder


def test_unconstrained_selection_defers_missing_contract_validation() -> None:
    """Keep a behavioral decoder eligible until the later contract validator."""
    no_contract = _Decoder(ComponentDescriptor("no-contract", "1", "plugin"))

    result = select_success_payload_decoder(
        DecoderSelection(),
        _layers(integration=(no_contract,)),
    )

    # Selection owns candidate cardinality, not the subsequent requirement that
    # every codec participating in port connections declare a non-null contract.
    assert result is no_contract


def test_rejects_non_selection_before_component_resolution() -> None:
    """Reject structural look-alikes at the role-specific plan boundary."""
    decoder = _decoder("decoder")

    _assert_raises(
        TypeError,
        lambda: select_success_payload_decoder(
            cast(DecoderSelection, object()),
            _layers(defaults=(decoder,)),
        ),
        "selection must be a DecoderSelection",
    )
    assert decoder.decode_calls == 0

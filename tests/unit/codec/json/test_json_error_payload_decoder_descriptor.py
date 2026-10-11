"""Stability tests for the JSON error payload decoder descriptor."""

from mconet.codec.json import (
    JSON_ERROR_PAYLOAD_DECODER_DESCRIPTOR,
    JSON_SUCCESS_PAYLOAD_DECODER_DESCRIPTOR,
    JsonErrorPayloadDecoder,
)
from mconet.core.domain import OpenIdentifier
from mconet.core.runtime._component_source_merge import ComponentSourceLayers
from mconet.core.runtime._single_component_selection import select_single_component
from mconet.core.spi import ComponentRole, RuntimeComponent

_MAXIMUM_DECODED_BODY_BYTES = 64


def _role() -> ComponentRole:
    """Build the error-decoder role without using the descriptor name."""
    return ComponentRole(OpenIdentifier("codec.response.error-decoder"))


def _layers(*components: RuntimeComponent) -> ComponentSourceLayers:
    """Place components only in the SDK-default source layer."""
    # The other layers stay empty so this test isolates descriptor identity
    # from source precedence.
    return (), (), (), components


def test_json_error_payload_decoder_descriptor_is_stable() -> None:
    """Verify name, version, and source stay fixed, shared, and distinct."""
    first = JsonErrorPayloadDecoder(_MAXIMUM_DECODED_BODY_BYTES)
    second = JsonErrorPayloadDecoder(_MAXIMUM_DECODED_BODY_BYTES)

    # Labels are diagnostic. The type contract and capabilities stay unset, and
    # the success decoder keeps a different descriptor object.
    assert JSON_ERROR_PAYLOAD_DECODER_DESCRIPTOR.name == "json-error-payload-decoder"
    assert JSON_ERROR_PAYLOAD_DECODER_DESCRIPTOR.version == "1.0.0"
    assert JSON_ERROR_PAYLOAD_DECODER_DESCRIPTOR.source == "builtin"
    assert JSON_ERROR_PAYLOAD_DECODER_DESCRIPTOR.type_contract is None
    assert JSON_ERROR_PAYLOAD_DECODER_DESCRIPTOR.capabilities == frozenset()
    assert first.descriptor is JSON_ERROR_PAYLOAD_DECODER_DESCRIPTOR
    assert second.descriptor is first.descriptor
    assert first.descriptor is not JSON_SUCCESS_PAYLOAD_DECODER_DESCRIPTOR


def test_json_error_payload_decoder_descriptor_does_not_select() -> None:
    """Verify equal descriptor labels do not uniquify an error decoder."""
    first = JsonErrorPayloadDecoder(_MAXIMUM_DECODED_BODY_BYTES)
    second = JsonErrorPayloadDecoder(_MAXIMUM_DECODED_BODY_BYTES)
    role = _role()

    # Two instances share one descriptor. Selection remains ambiguous because
    # it does not collapse candidates by name, version, or source.
    assert select_single_component(role, _layers(first, second), lambda _: True) is None

    selected = select_single_component(
        role,
        _layers(first),
        lambda component: isinstance(component, JsonErrorPayloadDecoder),
    )
    assert selected is not None
    assert selected.component is first
    assert selected.descriptor is JSON_ERROR_PAYLOAD_DECODER_DESCRIPTOR

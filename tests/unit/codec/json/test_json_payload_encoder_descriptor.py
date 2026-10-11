"""Stability tests for the JSON payload encoder descriptor."""

from mconet.codec.json import (
    JSON_PAYLOAD_ENCODER_CAPABILITY,
    JSON_PAYLOAD_ENCODER_DESCRIPTOR,
    JsonPayloadEncoder,
)
from mconet.core.domain import OpenIdentifier
from mconet.core.runtime._component_source_merge import ComponentSourceLayers
from mconet.core.runtime._single_component_selection import select_single_component
from mconet.core.spi import ComponentRole, RuntimeComponent


def _role() -> ComponentRole:
    """Build the encoder role without using the descriptor name as its id."""
    return ComponentRole(OpenIdentifier("codec.request.encoder"))


def _layers(*components: RuntimeComponent) -> ComponentSourceLayers:
    """Place components only in the SDK-default source layer."""
    # The other layers stay empty so this test isolates descriptor identity
    # from source precedence.
    return (), (), (), components


def test_json_payload_encoder_descriptor_is_stable_diagnostic_metadata() -> None:
    """Verify name, version, and source stay fixed and shared."""
    first = JsonPayloadEncoder()
    second = JsonPayloadEncoder()

    # Labels are diagnostic. Every encoder publishes the same object, including
    # the encode capability, and selection does not read that capability.
    assert JSON_PAYLOAD_ENCODER_DESCRIPTOR.name == "json-payload-encoder"
    assert JSON_PAYLOAD_ENCODER_DESCRIPTOR.version == "1.0.0"
    assert JSON_PAYLOAD_ENCODER_DESCRIPTOR.source == "builtin"
    assert JSON_PAYLOAD_ENCODER_DESCRIPTOR.capabilities == frozenset(
        (JSON_PAYLOAD_ENCODER_CAPABILITY,)
    )
    assert first.descriptor is JSON_PAYLOAD_ENCODER_DESCRIPTOR
    assert second.descriptor is first.descriptor


def test_json_payload_encoder_descriptor_does_not_select_the_component() -> None:
    """Verify equal descriptor labels do not uniquify or identify an instance."""
    first = JsonPayloadEncoder()
    second = JsonPayloadEncoder()
    role = _role()

    # Two instances share one descriptor. Selection remains ambiguous because
    # it does not collapse candidates by name, version, or source.
    assert select_single_component(role, _layers(first, second), lambda _: True) is None

    selected = select_single_component(
        role,
        _layers(first),
        lambda component: isinstance(component, JsonPayloadEncoder),
    )
    assert selected is not None
    assert selected.component is first
    assert selected.descriptor is JSON_PAYLOAD_ENCODER_DESCRIPTOR
    assert selected.role.id == OpenIdentifier("codec.request.encoder")

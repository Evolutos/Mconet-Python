"""Connection tests for the JSON payload encoder type contract."""

from mconet.codec.json import (
    JSON_PAYLOAD_ENCODER_DESCRIPTOR,
    JSON_PAYLOAD_ENCODER_TYPE_CONTRACT,
)
from mconet.core.domain import MediaType, OpenIdentifier
from mconet.core.spi import ComponentTypePort


def _connects(producer: ComponentTypePort, consumer: ComponentTypePort) -> bool:
    """Return whether one output port can feed one input port.

    Type identifiers must match. A schema or media type declared on the
    consumer is an exact constraint. An omitted consumer constraint accepts
    the producer, so an adapter can keep its own payload schema.
    """
    if producer.type_id != consumer.type_id:
        return False
    if consumer.schema_id is not None and producer.schema_id != consumer.schema_id:
        return False
    if consumer.media_type is not None and producer.media_type != consumer.media_type:
        return False
    return True


def test_json_payload_encoder_type_contract_connects_adapter_payload() -> None:
    """Verify an adapter JSON payload port connects to the encoder input."""
    contract = JSON_PAYLOAD_ENCODER_TYPE_CONTRACT
    encoder_input = contract.inputs[0]
    json_media_type = MediaType("application", "json")
    adapter_output = ComponentTypePort(
        "output",
        OpenIdentifier("json.value"),
        "schema://adapter/request",
        json_media_type,
    )

    # The encoder accepts any JSON schema. Bytes are the encode result, so the
    # contract does not invent a second JSON or transport-body port.
    assert encoder_input.name == "input"
    assert encoder_input.type_id == OpenIdentifier("json.value")
    assert encoder_input.schema_id is None
    assert encoder_input.media_type == json_media_type
    assert contract.outputs == ()
    assert _connects(adapter_output, encoder_input)
    assert JSON_PAYLOAD_ENCODER_DESCRIPTOR.type_contract is contract


def test_json_payload_encoder_type_contract_rejects_a_different_value_type() -> None:
    """Verify a non-JSON producer cannot use the encoder input port."""
    encoder_input = JSON_PAYLOAD_ENCODER_TYPE_CONTRACT.inputs[0]
    other_output = ComponentTypePort(
        "output",
        OpenIdentifier("text.value"),
        None,
        MediaType("text", "plain"),
    )

    # A different type id is a different port, even when both omit a schema.
    assert not _connects(other_output, encoder_input)

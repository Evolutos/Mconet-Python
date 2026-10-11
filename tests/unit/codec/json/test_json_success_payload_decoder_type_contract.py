"""Connection tests for the JSON success payload decoder type contract."""

from mconet.codec.json import (
    JSON_PAYLOAD_ENCODER_TYPE_CONTRACT,
    JSON_SUCCESS_PAYLOAD_DECODER_DESCRIPTOR,
    JSON_SUCCESS_PAYLOAD_DECODER_TYPE_CONTRACT,
)
from mconet.core.domain import MediaType, OpenIdentifier
from mconet.core.spi import ComponentTypePort


def _connects(producer: ComponentTypePort, consumer: ComponentTypePort) -> bool:
    """Return whether one output port can feed one input port.

    Type identifiers and declared media types must match. A schema declared on
    either port is an exact constraint. An omitted schema lets a consumer
    accept the payload without adopting a protocol schema.
    """
    if producer.type_id != consumer.type_id:
        return False
    if producer.media_type != consumer.media_type:
        return False
    if producer.schema_id is not None and producer.schema_id != consumer.schema_id:
        return False
    if consumer.schema_id is not None and producer.schema_id != consumer.schema_id:
        return False
    return True


def test_json_success_payload_decoder_type_contract_connects_response_port() -> None:
    """Verify a schema-free JSON consumer can accept the success payload."""
    contract = JSON_SUCCESS_PAYLOAD_DECODER_TYPE_CONTRACT
    decoder_output = contract.outputs[0]
    json_media_type = MediaType("application", "json")
    consumer_input = ComponentTypePort(
        "input",
        OpenIdentifier("json.value"),
        None,
        json_media_type,
    )

    # Bytes are the decoder input, so the contract exposes only the payload.
    assert contract.inputs == ()
    assert decoder_output.name == "output"
    assert decoder_output.type_id == OpenIdentifier("json.value")
    assert decoder_output.schema_id is None
    assert decoder_output.media_type == json_media_type
    assert _connects(decoder_output, consumer_input)
    assert JSON_SUCCESS_PAYLOAD_DECODER_DESCRIPTOR.type_contract is contract
    assert contract is not JSON_PAYLOAD_ENCODER_TYPE_CONTRACT


def test_json_success_payload_decoder_type_contract_rejects_a_required_schema() -> None:
    """Verify a consumer that requires a protocol schema does not connect."""
    decoder_output = JSON_SUCCESS_PAYLOAD_DECODER_TYPE_CONTRACT.outputs[0]
    schema_consumer = ComponentTypePort(
        "input",
        OpenIdentifier("json.value"),
        "schema://protocol/success",
        MediaType("application", "json"),
    )
    other_type = ComponentTypePort(
        "input",
        OpenIdentifier("text.value"),
        None,
        MediaType("text", "plain"),
    )

    # Omitted schema identity is not a promise that every protocol schema fits.
    assert not _connects(decoder_output, schema_consumer)
    assert not _connects(decoder_output, other_type)

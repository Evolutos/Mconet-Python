"""Bounded-parse tests for the JSON error payload decoder."""

from collections.abc import Callable
from typing import cast

from mconet.codec.json import (
    JSON_ERROR_PAYLOAD_DECODER_DESCRIPTOR,
    JsonErrorPayloadDecoder,
    JsonSuccessPayloadDecoder,
)
from mconet.core.domain import Bytes, ModelInteractionError, OpenIdentifier
from mconet.core.spi import PayloadDecoder

_MAXIMUM_DECODED_BODY_BYTES = 64


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Return the expected exception after checking its stable message fragment."""
    try:
        action()
    except exception_type as error:
        # The fragment identifies the error-decoder failure without accepting
        # an unrelated fixture error.
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _json_bytes(json_text: str) -> Bytes:
    """Encode one JSON fixture without using the codec UTF-8 helper."""
    return Bytes(json_text.encode("utf-8"))


def test_json_error_payload_decoder_is_a_distinct_component() -> None:
    """Verify error and success decoding do not share one component identity."""
    error_decoder = JsonErrorPayloadDecoder(_MAXIMUM_DECODED_BODY_BYTES)
    success_decoder = JsonSuccessPayloadDecoder(_MAXIMUM_DECODED_BODY_BYTES)

    # Outcome selection depends on distinct instances and distinct descriptors.
    # The error type contract stays empty until its own metadata work item.
    assert error_decoder is not success_decoder
    assert error_decoder.descriptor is JSON_ERROR_PAYLOAD_DECODER_DESCRIPTOR
    assert error_decoder.descriptor is not success_decoder.descriptor
    assert error_decoder.descriptor.name == "json-error-payload-decoder"
    assert error_decoder.descriptor.version == "1.0.0"
    assert error_decoder.descriptor.source == "builtin"
    assert error_decoder.descriptor.type_contract is None
    assert success_decoder.descriptor.type_contract is not None
    assert error_decoder.descriptor.capabilities == frozenset()
    assert isinstance(error_decoder, PayloadDecoder)


def test_json_error_payload_decoder_decodes_an_error_object() -> None:
    """Verify provider fields stay inside the JSON value."""
    decoder = JsonErrorPayloadDecoder(_MAXIMUM_DECODED_BODY_BYTES)
    decoded = decoder.decode(_json_bytes('{"code":"rate_limit","message":"slow down"}'))

    # No protocol schema is inferred from an error object.
    assert decoded.type_id == OpenIdentifier("json.value")
    assert decoded.schema_id is None
    assert decoded.value == {"code": "rate_limit", "message": "slow down"}


def test_json_error_payload_decoder_omits_the_body_from_a_decode_failure() -> None:
    """Verify an incomplete provider body is not copied into the SDK error."""
    decoder = JsonErrorPayloadDecoder(_MAXIMUM_DECODED_BODY_BYTES)
    error = _assert_raises(
        ModelInteractionError,
        lambda: decoder.decode(_json_bytes('{"message":"provider failed"')),
        "cannot be decoded",
    )

    interaction_error = cast(ModelInteractionError, error)
    assert interaction_error.category.id == OpenIdentifier("deserialization")
    assert interaction_error.code == "deserialization"
    assert interaction_error.cause is None
    assert "provider failed" not in str(interaction_error)


def test_json_error_payload_decoder_rejects_an_oversized_body_without_its_text() -> (
    None
):
    """Verify the limit stops parsing and the diagnostic omits the body."""
    decoder = JsonErrorPayloadDecoder(1)
    error = _assert_raises(
        ModelInteractionError,
        lambda: decoder.decode(_json_bytes('{"detail":"too large"}')),
        "exceeds its byte limit",
    )

    interaction_error = cast(ModelInteractionError, error)
    assert interaction_error.code == "response_body_too_large"
    assert interaction_error.cause is None
    assert "too large" not in str(interaction_error)


def test_json_error_payload_decoder_rejects_an_unusable_limit_at_construction() -> None:
    """Verify a bad limit fails before an error body is supplied."""
    error = _assert_raises(
        ModelInteractionError,
        lambda: JsonErrorPayloadDecoder(0),
        "positive safe integer",
    )
    assert cast(ModelInteractionError, error).code == "invalid_component_configuration"

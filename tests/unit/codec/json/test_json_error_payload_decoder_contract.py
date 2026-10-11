"""Error-decoder contract fixtures for bounded JSON error bodies.

These cases run the real error decoder through
``ErrorPayloadDecoderContractSuite``. A normal fixture keeps provider fields
inside the JSON value. Malformed and oversized fixtures must fail without
copying the response text into the diagnostic.
"""

from mconet.codec.json import (
    JSON_ERROR_PAYLOAD_DECODER_DESCRIPTOR,
    JSON_SUCCESS_PAYLOAD_DECODER_DESCRIPTOR,
    JsonErrorPayloadDecoder,
)
from mconet.core.domain import Bytes, ModelInteractionError, OpenIdentifier
from mconet.core.spi import ErasedRuntimeValue
from mconet.testing import ErrorPayloadDecoderContractSuite

_PROVIDER_MESSAGE = "provider failed: secret-token"


def _json_bytes(json_text: str) -> Bytes:
    """Encode one JSON fixture without using the codec UTF-8 helper."""
    return Bytes(json_text.encode("utf-8"))


def test_json_error_payload_decoder_contract_decodes_a_normal_fixture() -> None:
    """Verify a provider error document stays a JSON value."""
    decoder = JsonErrorPayloadDecoder(64)
    suite = ErrorPayloadDecoderContractSuite(decoder)
    # The error suite must be bound to the error descriptor. Sharing the
    # success descriptor would collapse the two outcome components.
    assert decoder.descriptor is JSON_ERROR_PAYLOAD_DECODER_DESCRIPTOR
    assert decoder.descriptor is not JSON_SUCCESS_PAYLOAD_DECODER_DESCRIPTOR

    def assertion(decoded: ErasedRuntimeValue) -> None:
        # Provider fields remain data. Decoding does not turn them into an
        # SDK error or attach a protocol schema.
        assert decoded.type_id == OpenIdentifier("json.value")
        assert decoded.schema_id is None
        assert decoded.value == {
            "code": "rate_limit",
            "message": _PROVIDER_MESSAGE,
        }

    suite.assert_decode(
        _json_bytes('{"code":"rate_limit","message":"' + _PROVIDER_MESSAGE + '"}'),
        assertion=assertion,
    )


def test_json_error_payload_decoder_contract_redacts_a_malformed_fixture() -> None:
    """Verify a broken provider body is not copied into the SDK error."""
    suite = ErrorPayloadDecoderContractSuite(JsonErrorPayloadDecoder(64))
    raw_data = _json_bytes('{"message":"' + _PROVIDER_MESSAGE + '"')

    def assertion(error: BaseException) -> None:
        # The body fit the limit, so this is deserialization. The provider
        # text is the sensitive part and must stay out of the diagnostic.
        assert isinstance(error, ModelInteractionError)
        assert error.category.id == OpenIdentifier("deserialization")
        assert error.phase.id == OpenIdentifier("decoding")
        assert error.code == "deserialization"
        assert error.message == "JSON response body cannot be decoded."
        assert error.cause is None
        assert _PROVIDER_MESSAGE not in str(error)
        assert "secret-token" not in str(error)

    suite.assert_decode_failure(raw_data, assertion=assertion)


def test_json_error_payload_decoder_contract_redacts_an_oversized_fixture() -> None:
    """Verify a too-large error body is neither parsed nor quoted."""
    suite = ErrorPayloadDecoderContractSuite(JsonErrorPayloadDecoder(1))

    def assertion(error: BaseException) -> None:
        # Over-limit is not rewritten as a JSON parse failure, and the unread
        # provider text does not enter the diagnostic.
        assert isinstance(error, ModelInteractionError)
        assert error.code == "response_body_too_large"
        assert error.cause is None
        assert _PROVIDER_MESSAGE not in str(error)
        assert "secret-token" not in str(error)

    suite.assert_decode_failure(
        _json_bytes('{"message":"' + _PROVIDER_MESSAGE + '"}'),
        assertion=assertion,
    )

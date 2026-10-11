"""Success-decoder contract fixtures for bounded JSON bodies.

These cases run the real success decoder through
``SuccessPayloadDecoderContractSuite``. Normal fixtures check the decoded
JSON value. Malformed fixtures must fail as deserialization without quoting
the body. An oversized fixture must keep the separate size-limit failure.
"""

from collections.abc import Callable

from mconet.codec.json import (
    JSON_SUCCESS_PAYLOAD_DECODER_DESCRIPTOR,
    JsonSuccessPayloadDecoder,
)
from mconet.core.domain import Bytes, JsonValue, ModelInteractionError, OpenIdentifier
from mconet.core.spi import ErasedRuntimeValue
from mconet.testing import SuccessPayloadDecoderContractSuite

_MAXIMUM_DECODED_BODY_BYTES = 64


def _json_bytes(json_text: str) -> Bytes:
    """Encode one JSON fixture without using the codec UTF-8 helper."""
    return Bytes(json_text.encode("utf-8"))


def _expect_value(expected: JsonValue) -> Callable[[ErasedRuntimeValue], None]:
    """Return a suite callback for one decoded JSON value."""

    def assertion(decoded: ErasedRuntimeValue) -> None:
        # The decoded port is a JSON value. No protocol schema is inferred
        # from the response body.
        assert decoded.type_id == OpenIdentifier("json.value")
        assert decoded.schema_id is None
        assert decoded.value == expected

    return assertion


def _expect_deserialization(absent: str) -> Callable[[BaseException], None]:
    """Return a suite callback for one body that cannot be decoded."""

    def assertion(error: BaseException) -> None:
        # Malformed JSON stays a deserialization failure. Wrapping it as a
        # size-limit error would hide a body that did fit.
        assert isinstance(error, ModelInteractionError)
        assert error.category.id == OpenIdentifier("deserialization")
        assert error.phase.id == OpenIdentifier("decoding")
        assert error.code == "deserialization"
        assert error.message == "JSON response body cannot be decoded."
        assert error.cause is None
        assert absent not in str(error)

    return assertion


def test_json_success_payload_decoder_contract_decodes_normal_fixtures() -> None:
    """Verify object, null, empty, and scalar fixtures decode through the suite."""
    decoder = JsonSuccessPayloadDecoder(_MAXIMUM_DECODED_BODY_BYTES)
    suite = SuccessPayloadDecoderContractSuite(decoder)
    # Descriptor identity proves the suite is running the success decoder,
    # not another component that happens to implement decode.
    assert decoder.descriptor is JSON_SUCCESS_PAYLOAD_DECODER_DESCRIPTOR

    cases: tuple[tuple[str, JsonValue], ...] = (
        ('{"b":1,"a":false}', {"b": 1, "a": False}),
        ("null", None),
        ("{}", {}),
        ("[]", []),
        ('""', ""),
        ('"A𐀀😀"', "A𐀀😀"),
        ("0", 0),
        ("false", False),
        ('{"a":1,"a":2,"extra":true}', {"a": 2, "extra": True}),
    )

    for json_text, expected in cases:
        suite.assert_decode(_json_bytes(json_text), assertion=_expect_value(expected))


def test_json_success_payload_decoder_contract_accepts_the_exact_limit() -> None:
    """Verify a body that fills the limit is still a normal fixture."""
    raw_data = _json_bytes("null")
    suite = SuccessPayloadDecoderContractSuite(JsonSuccessPayloadDecoder(len(raw_data)))

    # Equality with the limit is acceptance. The next test is the first byte
    # past that boundary.
    suite.assert_decode(raw_data, assertion=_expect_value(None))


def test_json_success_payload_decoder_contract_rejects_malformed_fixtures() -> None:
    """Verify empty, invalid, and non-portable bodies stay unquoted."""
    suite = SuccessPayloadDecoderContractSuite(
        JsonSuccessPayloadDecoder(_MAXIMUM_DECODED_BODY_BYTES)
    )
    rejected: tuple[tuple[bytes, str], ...] = (
        (b"", "{"),
        (b"{", "{"),
        (bytes((0xFF,)), "\ufffd"),
        (b"-0", "-0"),
        (b"1e309", "1e309"),
        (str(2**53).encode("utf-8"), str(2**53)),
    )

    for raw_data, absent in rejected:
        suite.assert_decode_failure(
            Bytes(raw_data),
            assertion=_expect_deserialization(absent),
        )


def test_json_success_payload_decoder_contract_rejects_an_oversized_fixture() -> None:
    """Verify a too-large body is not reported as malformed JSON."""
    suite = SuccessPayloadDecoderContractSuite(JsonSuccessPayloadDecoder(1))

    def assertion(error: BaseException) -> None:
        # The size limit is a different code from deserialization, and the
        # unread JSON text does not enter the diagnostic.
        assert isinstance(error, ModelInteractionError)
        assert error.code == "response_body_too_large"
        assert error.cause is None
        assert "null" not in str(error)

    suite.assert_decode_failure(_json_bytes("null"), assertion=assertion)

"""Branch tests for the JSON success payload decoder."""

from collections.abc import Callable
from typing import cast

from mconet.codec.json import JsonSuccessPayloadDecoder
from mconet.core.domain import Bytes, JsonValue, ModelInteractionError, OpenIdentifier
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
        # The fragment identifies the decode failure without accepting an
        # unrelated fixture error.
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _json_bytes(json_text: str) -> Bytes:
    """Encode one JSON fixture without using the codec UTF-8 helper."""
    return Bytes(json_text.encode("utf-8"))


def test_json_success_payload_decoder_decodes_object_null_and_empty_values() -> None:
    """Verify the required JSON branches and preserved object order."""
    decoder = JsonSuccessPayloadDecoder(_MAXIMUM_DECODED_BODY_BYTES)
    cases: tuple[tuple[str, JsonValue], ...] = (
        ('{"b":1,"a":false}', {"b": 1, "a": False}),
        ("null", None),
        ("{}", {}),
        ("[]", []),
        ('""', ""),
        ('"A𐀀😀"', "A𐀀😀"),
        ("0", 0),
        ("false", False),
    )

    for json_text, value in cases:
        decoded = decoder.decode(_json_bytes(json_text))
        # The decoded port carries the JSON value only. Protocol schema identity
        # is not inferred from the body.
        assert decoded.type_id == OpenIdentifier("json.value")
        assert decoded.schema_id is None
        assert decoded.value == value

    # Duplicate keys are unambiguous: the last value remains, and an unknown
    # member is retained rather than dropped as an extension.
    duplicate = decoder.decode(_json_bytes('{"a":1,"a":2,"extra":true}'))
    assert duplicate.value == {"a": 2, "extra": True}
    assert isinstance(decoder, PayloadDecoder)
    assert decoder.descriptor.name == "json-success-payload-decoder"
    assert decoder.descriptor.type_contract is None


def test_json_success_payload_decoder_accepts_a_body_at_the_exact_limit() -> None:
    """Verify a body whose UTF-8 length equals the limit is decoded."""
    raw_data = _json_bytes("null")
    decoder = JsonSuccessPayloadDecoder(len(raw_data))

    assert decoder.decode(raw_data).value is None


def test_json_success_payload_decoder_rejects_malformed_bodies_without_quoting_them() -> (
    None
):
    """Verify empty, invalid UTF-8, invalid JSON, and non-portable numbers fail."""
    decoder = JsonSuccessPayloadDecoder(_MAXIMUM_DECODED_BODY_BYTES)
    rejected = (
        b"",
        b"{",
        bytes((0xFF,)),
        b"-0",
        b"1e309",
        _unsafe_integer_token().encode("utf-8"),
    )

    for raw_data in rejected:
        error = _assert_raises(
            ModelInteractionError,
            lambda raw_data=raw_data: decoder.decode(Bytes(raw_data)),
            "cannot be decoded",
        )
        interaction_error = cast(ModelInteractionError, error)
        # The message must not quote the rejected body. The code stays
        # deserialization rather than the oversized-body code.
        assert interaction_error.code == "deserialization"
        assert interaction_error.category.id == OpenIdentifier("deserialization")
        assert interaction_error.phase.id == OpenIdentifier("decoding")
        assert interaction_error.cause is None
        assert b"1e309".decode() not in str(interaction_error)
        assert "{" not in str(interaction_error)


def test_json_success_payload_decoder_reports_an_oversized_body_separately() -> None:
    """Verify a too-large body is not parsed or copied into the error."""
    decoder = JsonSuccessPayloadDecoder(1)
    error = _assert_raises(
        ModelInteractionError,
        lambda: decoder.decode(_json_bytes("null")),
        "exceeds its byte limit",
    )

    interaction_error = cast(ModelInteractionError, error)
    assert interaction_error.code == "response_body_too_large"
    assert "null" not in str(interaction_error)


def test_json_success_payload_decoder_rejects_an_unusable_limit_at_construction() -> (
    None
):
    """Verify a bad limit fails before any body is supplied."""
    for limit in (0, -1, cast(int, True), 2**53):
        error = _assert_raises(
            ModelInteractionError,
            lambda limit=limit: JsonSuccessPayloadDecoder(limit),
            "positive safe integer",
        )
        assert cast(ModelInteractionError, error).code == (
            "invalid_component_configuration"
        )
        assert str(limit) not in str(error)


def test_json_success_payload_decoder_rejects_non_bytes() -> None:
    """Verify a mutable buffer cannot skip the byte boundary."""
    decoder = JsonSuccessPayloadDecoder(_MAXIMUM_DECODED_BODY_BYTES)
    _assert_raises(
        TypeError,
        lambda: decoder.decode(cast(Bytes, bytearray(b"null"))),
        "raw_data must be bytes",
    )


def _unsafe_integer_token() -> str:
    """Return one integer token just outside the portable range."""
    return str(2**53)

"""Encoder-contract fixtures for the JSON payload encoder.

These cases run the real encoder through ``PayloadEncoderContractSuite``.
The suite checks the public encoder boundary once; each fixture then checks
one encoded body or one exact failure. Failure values that are not portable
JSON stay in this module because a JSON fixture document cannot represent
them.
"""

from collections.abc import Callable
from typing import cast

from mconet.codec.json import (
    JSON_PAYLOAD_ENCODER_DESCRIPTOR,
    JsonPayloadEncoder,
)
from mconet.core.domain import (
    JsonValue,
    MediaType,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.core.spi import ErasedRuntimeValue, TransportBody
from mconet.testing import PayloadEncoderContractSuite

_JSON_MEDIA_TYPE = MediaType("application", "json")
_PRIVATE_MARKER = "private-payload-marker"


def _payload(
    value: JsonValue,
    *,
    type_id: str = "json.value",
    schema_id: str | None = None,
) -> ErasedRuntimeValue:
    """Build one erased payload without copying its JSON value."""
    if schema_id is None:
        return ErasedRuntimeValue(OpenIdentifier(type_id), value)
    return ErasedRuntimeValue(OpenIdentifier(type_id), value, schema_id)


def _expect_text(
    expected_text: str,
    *absent: str,
) -> Callable[[TransportBody], None]:
    """Return a suite callback for one compact JSON body."""

    def assertion(body: TransportBody) -> None:
        # Decode with the standard library so the contract does not depend on
        # the codec UTF-8 helper it is checking.
        text = bytes(body.bytes).decode("utf-8")
        assert text == expected_text
        # The media type is fixed by the encoder. It is not read from the
        # payload type id, schema id, or JSON contents.
        assert body.media_type == _JSON_MEDIA_TYPE
        for fragment in absent:
            assert fragment not in text

    return assertion


def _expect_serialization_failure(secret: str) -> Callable[[BaseException], None]:
    """Return a suite callback for one content-safe serialization failure."""

    def assertion(error: BaseException) -> None:
        # The suite must surface the encoder error unchanged. A second wrapper
        # would be a different failure than the one the encoder raised.
        assert isinstance(error, ModelInteractionError)
        assert error.category.id == OpenIdentifier("serialization")
        assert error.phase.id == OpenIdentifier("encoding")
        assert error.code == "serialization"
        assert error.message == "JSON payload cannot be serialized."
        assert error.cause is None
        assert secret not in str(error)

    return assertion


def test_json_payload_encoder_contract_encodes_each_fixture() -> None:
    """Verify portable JSON fixtures become compact UTF-8 transport bodies."""
    encoder = JsonPayloadEncoder()
    suite = PayloadEncoderContractSuite(encoder)
    # The suite retains the SDK encoder. Descriptor identity proves the run
    # uses the frozen metadata rather than a stub with the same method.
    assert encoder.descriptor is JSON_PAYLOAD_ENCODER_DESCRIPTOR

    cases: tuple[tuple[ErasedRuntimeValue, str, tuple[str, ...]], ...] = (
        (_payload(None), "null", ()),
        (_payload(False), "false", ()),
        (_payload(True), "true", ()),
        (_payload(0), "0", ()),
        (_payload(""), '""', ()),
        (_payload("A𐀀😀"), '"A𐀀😀"', ()),
        (_payload([]), "[]", ()),
        (_payload({}), "{}", ()),
        (
            _payload(
                {"b": 1, "a": {"enabled": False, "items": ["hello", None]}},
                type_id="task.input.conversation",
                schema_id="schema://example/request",
            ),
            '{"b":1,"a":{"enabled":false,"items":["hello",null]}}',
            ("task.input.conversation", "schema://example/request"),
        ),
        (
            _payload({"ok": True}, schema_id=""),
            '{"ok":true}',
            (),
        ),
    )

    for payload, expected_text, absent in cases:
        suite.assert_encode(
            payload,
            assertion=_expect_text(expected_text, *absent),
        )


def test_json_payload_encoder_contract_rejects_non_portable_fixtures() -> None:
    """Verify lossy and non-JSON fixtures fail without exposing their contents."""
    suite = PayloadEncoderContractSuite(JsonPayloadEncoder())
    cyclic: dict[str, JsonValue] = {}
    cyclic["self"] = cyclic
    rejected: tuple[JsonValue, ...] = (
        cast(JsonValue, float("nan")),
        cast(JsonValue, float("-0.0")),
        cast(JsonValue, {"secret": _PRIVATE_MARKER, "count": float("-0.0")}),
        cyclic,
        cast(JsonValue, b"bytes"),
        cast(JsonValue, ("tuple",)),
        cast(JsonValue, {"text": "\ud800", "secret": _PRIVATE_MARKER}),
        cast(JsonValue, 2**53),
    )

    for value in rejected:
        suite.assert_encode_failure(
            _payload(value),
            assertion=_expect_serialization_failure(_PRIVATE_MARKER),
        )


def test_json_payload_encoder_contract_rejects_a_non_erased_fixture() -> None:
    """Verify a value outside the erased port fails before serialization."""
    suite = PayloadEncoderContractSuite(JsonPayloadEncoder())

    def assertion(error: BaseException) -> None:
        # This boundary is a type error, not a serialization error, and it
        # must not quote the rejected object.
        assert isinstance(error, TypeError)
        assert str(error) == "payload must be an ErasedRuntimeValue."
        assert _PRIVATE_MARKER not in str(error)

    suite.assert_encode_failure(
        cast(ErasedRuntimeValue, {"secret": _PRIVATE_MARKER}),
        assertion=assertion,
    )

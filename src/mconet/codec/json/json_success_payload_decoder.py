"""Success decoder for one bounded UTF-8 JSON response body."""

from __future__ import annotations

import json
import math
from typing import cast

from mconet.codec.json.collect_bounded_bytes import collect_bounded_bytes
from mconet.codec.json.json_payload import JsonPayload
from mconet.codec.json.json_success_payload_decoder_descriptor import (
    JSON_SUCCESS_PAYLOAD_DECODER_DESCRIPTOR,
)
from mconet.core.domain import (
    Bytes,
    ErrorCategory,
    InteractionPhase,
    JsonValue,
    ModelInteractionError,
    OpenIdentifier,
    validate_json_value_numbers,
)
from mconet.core.spi.component_descriptor import ComponentDescriptor
from mconet.core.spi.erased_runtime_value import ErasedRuntimeValue

_JSON_VALUE_TYPE_ID = OpenIdentifier("json.value")
_MIN_SAFE_INTEGER = -(2**53 - 1)
_MAX_SAFE_INTEGER = 2**53 - 1
_DECODING_PHASE = InteractionPhase(OpenIdentifier("decoding"))
_DESERIALIZATION_CATEGORY = ErrorCategory(OpenIdentifier("deserialization"))
_DESERIALIZATION_CODE = "deserialization"
_DESERIALIZATION_MESSAGE = "JSON response body cannot be decoded."


class JsonSuccessPayloadDecoder:
    """Decode one bounded UTF-8 JSON body into an erased JSON value.

    The decoder accepts any portable JSON value, including null and empty
    containers. An empty body, ill-formed UTF-8, and ill-formed JSON are
    separate failures from a body that exceeds the configured limit. Duplicate
    object keys keep the last value. Unknown object members are retained.
    Negative zero and integers outside the interoperable range are rejected
    because their text would not round-trip as the same portable number.

    The decoder does not interpret task or provider error semantics, choose a
    component, or retain the source bytes in a failure. Its descriptor carries
    diagnostic name, version, and source only; the success type contract is a
    separate metadata work item.
    """

    __slots__ = ("_max_body_bytes",)

    def __init__(self, max_body_bytes: int) -> None:
        """Create a decoder that refuses bodies larger than ``max_body_bytes``.

        Args:
            max_body_bytes: Maximum accepted UTF-8 body length as a positive
                safe integer.

        Raises:
            ModelInteractionError: If ``max_body_bytes`` cannot enforce a
                finite positive limit. The rejected number is not included.
        """
        # An empty collection validates the limit before any response is seen,
        # so a bad limit cannot later be reported as malformed JSON.
        collect_bounded_bytes((), max_body_bytes)
        self._max_body_bytes = max_body_bytes

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return diagnostic metadata that decode does not consult."""
        # Every instance publishes the same diagnostic descriptor. Selection uses
        # the instance and execution plan, not these labels.
        return JSON_SUCCESS_PAYLOAD_DECODER_DESCRIPTOR

    def decode(self, raw_data: Bytes) -> ErasedRuntimeValue:
        """Decode one complete response body into a JSON value.

        Args:
            raw_data: Caller-owned response bytes. They are measured and copied
                only when they fit the configured limit.

        Returns:
            An erased JSON value. No schema identity is invented for the
            payload.

        Raises:
            TypeError: If ``raw_data`` is not ``bytes``.
            ModelInteractionError: If the body is too large, is not valid
                UTF-8, or is not portable JSON. The error does not include the
                body.
        """
        candidate = cast(object, raw_data)
        if not isinstance(candidate, bytes):
            raise TypeError("raw_data must be bytes.")

        # The collector stops before an oversized chunk is copied. Its size
        # error is already content-safe and stays distinct from malformed JSON.
        bounded = collect_bounded_bytes((candidate,), self._max_body_bytes)
        try:
            json_text = _decode_utf8(bounded)
            value = _parse_json_value(json_text)
        except (UnicodeError, ValueError, json.JSONDecodeError):
            raise _deserialization_error() from None

        return JsonPayload(_JSON_VALUE_TYPE_ID, value)


def _decode_utf8(raw_data: Bytes) -> str:
    """Decode UTF-8 bytes without replacing invalid sequences.

    Args:
        raw_data: Bounded bytes already accepted by the collector.

    Returns:
        Unicode text for those bytes.

    Raises:
        UnicodeDecodeError: If the bytes are not valid UTF-8.
    """
    # strict rejects ill-formed UTF-8 instead of inserting U+FFFD, which would
    # change the JSON text before parsing.
    return bytes(raw_data).decode("utf-8")


def _parse_json_value(json_text: str) -> JsonValue:
    """Parse JSON text and reject numbers that cannot round-trip.

    Args:
        json_text: UTF-8 text from the bounded body.

    Returns:
        A portable JSON value. Duplicate keys keep the last value.

    Raises:
        json.JSONDecodeError: If the text is not JSON.
        ValueError: If a number is not portable.
    """
    parsed = json.loads(
        json_text,
        parse_int=_parse_json_integer,
        parse_float=_parse_json_float,
    )
    # The parser hooks reject non-portable numbers. This second walk rejects
    # any remaining structure the JSON port does not accept.
    return validate_json_value_numbers(cast(JsonValue, parsed))


def _parse_json_integer(text: str) -> int:
    """Parse one JSON integer without losing its sign or safe range.

    Args:
        text: Decimal integer text supplied by the JSON parser.

    Returns:
        The integer value when it is portable.

    Raises:
        ValueError: If the text is negative zero or outside the safe range.
    """
    # "-0" is an integer token. Parsing it as 0 would drop the sign, so it
    # fails before a portable zero is returned.
    if text.startswith("-") and int(text) == 0:
        raise ValueError("JSON number must not be negative zero.")
    value = int(text)
    if not _MIN_SAFE_INTEGER <= value <= _MAX_SAFE_INTEGER:
        raise ValueError("JSON integer must be within the interoperable safe range.")
    return value


def _parse_json_float(text: str) -> float:
    """Parse one JSON fraction or exponent without producing a non-portable float.

    Args:
        text: Numeric text supplied by the JSON parser.

    Returns:
        A finite float that is not negative zero.

    Raises:
        ValueError: If the value is non-finite or negative zero.
    """
    value = float(text)
    # The token still carries the minus sign. float("-0.0") compares equal to
    # zero, so the text is what shows that the sign would be lost.
    if text.startswith("-") and value == 0.0:
        raise ValueError("JSON number must not be negative zero.")
    if not math.isfinite(value):
        raise ValueError("JSON floating-point value must be finite.")
    return value


def _deserialization_error() -> ModelInteractionError:
    """Create the content-safe failure for JSON or UTF-8 that cannot be decoded."""
    # The message does not quote response text, bytes, or the parser's own
    # diagnostic, which can include a fragment of the body.
    return ModelInteractionError(
        category=_DESERIALIZATION_CATEGORY,
        phase=_DECODING_PHASE,
        code=_DESERIALIZATION_CODE,
        message=_DESERIALIZATION_MESSAGE,
    )

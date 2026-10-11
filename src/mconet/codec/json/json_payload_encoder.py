"""JSON payload encoder that writes only the payload value."""

from __future__ import annotations

import json
import math
from typing import cast

from mconet.codec.json.json_payload import JsonPayload
from mconet.codec.json.json_payload_encoder_descriptor import (
    JSON_PAYLOAD_ENCODER_DESCRIPTOR,
)
from mconet.codec.json.utf8 import encode_utf8
from mconet.core.domain import (
    ErrorCategory,
    InteractionPhase,
    JsonValue,
    MediaType,
    ModelInteractionError,
    OpenIdentifier,
)
from mconet.core.spi.component_descriptor import ComponentDescriptor
from mconet.core.spi.erased_runtime_value import ErasedRuntimeValue
from mconet.core.spi.transport_body import TransportBody

_JSON_MEDIA_TYPE = MediaType("application", "json")
_SERIALIZATION_CATEGORY = ErrorCategory(OpenIdentifier("serialization"))
_ENCODING_PHASE = InteractionPhase(OpenIdentifier("encoding"))
_SERIALIZATION_CODE = "serialization"
_SERIALIZATION_MESSAGE = "JSON payload cannot be serialized."


class JsonPayloadEncoder:
    """Encode one JSON payload value into a buffered UTF-8 transport body.

    Only the JSON value is serialized. The type id and schema id stay port
    metadata and are not written into the body. The encoder does not read
    tasks, service access, credentials, or authorization, and it does not
    choose another component. Its descriptor currently carries diagnostic
    name, version, and source only; the type contract and capability declaration
    are separate component-metadata work.

    Non-finite numbers, negative zero, surrogate code points, cycles, and values
    that are not JSON fail before any body is returned. Object member order is
    preserved.
    """

    __slots__ = ()

    @property
    def descriptor(self) -> ComponentDescriptor:
        """Return diagnostic metadata that encode does not consult."""
        # Every instance publishes the same diagnostic descriptor. Selection uses
        # the component instance and the execution plan, not these labels.
        return JSON_PAYLOAD_ENCODER_DESCRIPTOR

    def encode(self, payload: ErasedRuntimeValue) -> TransportBody:
        """Serialize the payload value and return caller-owned UTF-8 bytes.

        Args:
            payload: Erased runtime value whose JSON value is the only encoded
                data.

        Returns:
            A complete transport body containing compact UTF-8 JSON text and
            the fixed ``application/json`` media type.

        Raises:
            TypeError: If ``payload`` is not an erased runtime value.
            ModelInteractionError: If the value cannot be serialized as JSON
                without changing its meaning. The error does not include the
                payload.
        """
        candidate = cast(object, payload)
        if not isinstance(candidate, ErasedRuntimeValue):
            raise TypeError("payload must be an ErasedRuntimeValue.")

        try:
            # Narrowing checks the JSON port. Metadata is validated and then
            # deliberately left out of the text that follows.
            json_payload = JsonPayload.from_erased(candidate)
            _reject_lossy_json_values(json_payload.value)
            json_text = _serialize_json_value(json_payload.value)
        except (TypeError, ValueError, UnicodeError):
            # Replace the underlying failure so its message cannot carry payload
            # text, type ids, or schema ids to the caller.
            raise _serialization_error() from None

        return TransportBody(
            bytes=encode_utf8(json_text),
            media_type=_JSON_MEDIA_TYPE,
        )


def _serialize_json_value(value: JsonValue) -> str:
    """Render one validated JSON value as compact JSON text.

    Args:
        value: A structurally valid JSON value with portable numbers.

    Returns:
        JSON text with source object order and no added spaces.

    Raises:
        TypeError: If a nested value is not JSON-serializable.
        ValueError: If a number or cycle cannot be represented as JSON.
        UnicodeError: If a string contains a surrogate code point.
    """
    # Compact separators match the canonical JSON text used by other SDKs.
    # ensure_ascii leaves non-ASCII scalars in the text so UTF-8 encoding can
    # preserve them. allow_nan refuses non-finite floats that are not JSON.
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    )


def _reject_lossy_json_values(value: JsonValue) -> None:
    """Reject JSON values whose text form would change their meaning.

    Args:
        value: A JSON value that has already passed structural validation.

    Raises:
        ValueError: If a negative zero or a surrogate code point is present.
    """
    pending: list[object] = [value]
    while pending:
        current = pending.pop()
        if isinstance(current, float):
            # JSON text cannot preserve the sign of zero. Fail instead of
            # emitting either 0 or -0 and changing the caller's number.
            if current == 0.0 and math.copysign(1.0, current) < 0:
                raise ValueError("JSON number must not be negative zero.")
            continue
        if isinstance(current, str):
            # A surrogate is not a Unicode scalar. Replacing it while encoding
            # UTF-8 would change the JSON string, so serialization stops first.
            if any(0xD800 <= ord(character) <= 0xDFFF for character in current):
                raise ValueError("JSON string must not contain a surrogate.")
            continue
        if isinstance(current, bool) or current is None or isinstance(current, int):
            continue
        if isinstance(current, list):
            pending.extend(cast(list[object], current))
            continue
        if isinstance(current, dict):
            pending.extend(cast(dict[str, object], current).values())


def _serialization_error() -> ModelInteractionError:
    """Create the content-safe failure for one non-serializable payload."""
    # The message, category, phase, and code identify the failure without
    # echoing payload bytes, identifiers, or the underlying exception text.
    return ModelInteractionError(
        category=_SERIALIZATION_CATEGORY,
        phase=_ENCODING_PHASE,
        code=_SERIALIZATION_CODE,
        message=_SERIALIZATION_MESSAGE,
    )

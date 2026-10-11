"""Behavior tests for the JSON payload encoder."""

import ast
from collections.abc import Callable
from pathlib import Path
from typing import cast

from mconet.codec.json import (
    JSON_PAYLOAD_ENCODER_TYPE_CONTRACT,
    JsonPayloadEncoder,
)
from mconet.codec.json.json_payload_encoder import JsonPayloadEncoder as EncoderClass
from mconet.core.domain import JsonValue, ModelInteractionError, OpenIdentifier
from mconet.core.spi import ErasedRuntimeValue, PayloadEncoder


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> BaseException:
    """Return the expected exception after checking its stable message fragment."""
    try:
        action()
    except exception_type as error:
        # The fragment identifies the encoding failure without accepting an
        # unrelated fixture or runtime error.
        assert message in str(error)
        return error
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _payload(
    value: JsonValue,
    *,
    type_id: str = "json.value",
    schema_id: str | None = None,
) -> ErasedRuntimeValue:
    """Build an erased payload whose metadata must stay out of the body."""
    if schema_id is None:
        return ErasedRuntimeValue(OpenIdentifier(type_id), value)
    return ErasedRuntimeValue(OpenIdentifier(type_id), value, schema_id)


def _text(encoder: JsonPayloadEncoder, payload: ErasedRuntimeValue) -> str:
    """Decode one encoded body without using the codec UTF-8 helper."""
    body = encoder.encode(payload)
    return bytes(body.bytes).decode("utf-8")


def test_json_payload_encoder_writes_only_the_json_value() -> None:
    """Verify port metadata and caller order stay out of the component choice."""
    encoder = JsonPayloadEncoder()
    payload = _payload(
        {"b": 1, "a": {"enabled": False, "items": ["hello", None]}},
        type_id="task.input.conversation",
        schema_id="schema://example/request",
    )

    body = encoder.encode(payload)
    text = bytes(body.bytes).decode("utf-8")

    # Encoding reads the value and leaves both the envelope and its JSON object
    # unchanged for the caller.
    assert payload.value == {
        "b": 1,
        "a": {"enabled": False, "items": ["hello", None]},
    }

    # The body is compact JSON for the value alone. Type and schema identities
    # are not fields and are not used to choose a media type or component.
    assert text == '{"b":1,"a":{"enabled":false,"items":["hello",null]}}'
    assert "task.input.conversation" not in text
    assert "schema://example/request" not in text
    assert body.media_type.type == "application"
    assert body.media_type.subtype == "json"
    assert body.media_type.parameters == ()
    assert isinstance(encoder, PayloadEncoder)
    assert encoder.descriptor.name == "json-payload-encoder"
    assert encoder.descriptor.version == "1.0.0"
    assert encoder.descriptor.source == "builtin"
    assert encoder.descriptor.type_contract is JSON_PAYLOAD_ENCODER_TYPE_CONTRACT
    assert encoder.descriptor.capabilities == frozenset()


def test_json_payload_encoder_encodes_each_json_category() -> None:
    """Verify scalars, empty containers, and non-ASCII text stay canonical."""
    encoder = JsonPayloadEncoder()
    cases: tuple[tuple[JsonValue, str], ...] = (
        (None, "null"),
        (False, "false"),
        (True, "true"),
        (0, "0"),
        ("", '""'),
        ("A𐀀😀", '"A𐀀😀"'),
        ([], "[]"),
        ({}, "{}"),
    )

    for value, expected in cases:
        assert _text(encoder, _payload(value)) == expected

    # An explicit empty schema id is distinct on the port and still absent
    # from the encoded document.
    empty_schema = _text(encoder, _payload({"ok": True}, schema_id=""))
    assert empty_schema == '{"ok":true}'


def test_json_payload_encoder_does_not_import_task_access_or_authorization() -> None:
    """Verify the encoder module cannot read those runtime concerns."""
    source_path = Path(EncoderClass.__module__.replace(".", "/"))
    module_path = (
        Path(__file__).resolve().parents[4] / "src" / source_path.with_suffix(".py")
    )
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)

    # Payload encoding is a value-to-bytes function. Those imports would make
    # it possible to read task, access, or authorization state.
    for module_name in imported:
        assert "authorization" not in module_name
        assert "service_access" not in module_name
        assert "task" not in module_name


def test_json_payload_encoder_rejects_values_that_cannot_round_trip() -> None:
    """Verify unsafe JSON fails without exposing the payload."""
    encoder = JsonPayloadEncoder()
    private_marker = "private-payload-marker"
    cyclic: dict[str, JsonValue] = {}
    cyclic["self"] = cyclic
    rejected: tuple[JsonValue, ...] = (
        cast(JsonValue, float("nan")),
        cast(JsonValue, float("-0.0")),
        cast(JsonValue, {"secret": private_marker, "count": float("-0.0")}),
        cyclic,
        cast(JsonValue, b"bytes"),
        cast(JsonValue, ("tuple",)),
        cast(JsonValue, {"text": "\ud800", "secret": private_marker}),
    )

    for value in rejected:
        error = _assert_raises(
            ModelInteractionError,
            lambda value=value: encoder.encode(_payload(value)),
            "cannot be serialized",
        )
        interaction_error = cast(ModelInteractionError, error)
        error_text = str(interaction_error)
        assert interaction_error.category.id == OpenIdentifier("serialization")
        assert interaction_error.phase.id == OpenIdentifier("encoding")
        assert interaction_error.code == "serialization"
        assert interaction_error.cause is None
        assert private_marker not in error_text
        assert "self" not in error_text


def test_json_payload_encoder_rejects_a_non_erased_argument() -> None:
    """Verify a dynamic caller cannot skip the erased port check."""
    _assert_raises(
        TypeError,
        lambda: JsonPayloadEncoder().encode(cast(ErasedRuntimeValue, {"value": None})),
        "payload must be an ErasedRuntimeValue",
    )

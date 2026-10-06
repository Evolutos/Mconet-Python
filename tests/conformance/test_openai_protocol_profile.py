"""Conformance contract for the R1 OpenAI-compatible wire-field baseline."""

import json
from pathlib import Path
from typing import cast

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_PROTOCOL_PATH = _PROJECT_ROOT / "spec" / "compatibility" / "r1-openai-protocol.json"
_ENDPOINT_PATH = _PROJECT_ROOT / "spec" / "compatibility" / "r1-openai-endpoint.json"
_EXPECTED_FIELDS = {
    "error": ["message", "type", "code"],
    "error_response": ["error"],
    "message": ["role", "content"],
    "request": [
        "model",
        "messages",
        "temperature",
        "top_p",
        "max_tokens",
        "stop",
        "seed",
        "stream",
    ],
    "response": ["id", "model", "choices", "usage"],
    "response_choice": ["index", "message", "finish_reason"],
    "usage": ["prompt_tokens", "completion_tokens", "total_tokens"],
}
_REQUIRED_FIELDS: dict[str, set[str]] = {
    "error": {"message"},
    "error_response": {"error"},
    "message": {"role", "content"},
    "request": {"model", "messages"},
    "response": {"choices"},
    "response_choice": {"index", "message", "finish_reason"},
    "usage": set[str](),
}
_PRIMITIVE_TYPES = {
    "boolean",
    "integer",
    "number",
    "string",
    "string-or-array:string",
    "string-or-integer",
}


def _as_string_mapping(value: object) -> dict[str, object]:
    """Narrow an untyped JSON object to a string-keyed mapping."""
    assert isinstance(value, dict)
    mapping: dict[str, object] = {}
    for key, item in cast(dict[object, object], value).items():
        assert isinstance(key, str)
        mapping[key] = item
    return mapping


def _load_json_object(path: Path) -> dict[str, object]:
    """Load one protocol document through an explicit JSON type boundary."""
    document: object = json.loads(path.read_text(encoding="utf-8"))
    return _as_string_mapping(document)


def _shape_fields(shape: object) -> list[dict[str, object]]:
    """Return the ordered field definitions from one protocol shape."""
    fields = _as_string_mapping(shape).get("fields")
    assert isinstance(fields, list)
    return [_as_string_mapping(field) for field in cast(list[object], fields)]


def test_protocol_metadata_matches_endpoint_profile() -> None:
    """Require the field baseline to use the frozen protocol and path version."""
    # Endpoint and field profiles are separate review units, but they must name
    # the same release profile, protocol identifier, and path version.
    protocol = _load_json_object(_PROTOCOL_PATH)
    endpoint = _load_json_object(_ENDPOINT_PATH)
    version = _as_string_mapping(endpoint["version"])

    assert protocol["format_version"] == 1
    assert protocol["profile"] == endpoint["profile"]
    assert protocol["protocol"] == endpoint["protocol"]
    assert protocol["protocol_version"] == version["value"]
    assert protocol["endpoint_profile"] == _ENDPOINT_PATH.name
    assert protocol["unknown_request_fields"] == "forbidden"
    assert protocol["unknown_response_fields"] == "ignored-after-metadata-capture"


def test_protocol_shapes_have_frozen_order_and_optionality() -> None:
    """Require every R1 wire shape to expose only its reviewed fields."""
    # Ordered definitions make later fixture generation deterministic, while the
    # required set prevents missing fields from being silently treated as null.
    protocol = _load_json_object(_PROTOCOL_PATH)
    shapes = _as_string_mapping(protocol["shapes"])
    assert list(shapes) == sorted(_EXPECTED_FIELDS)

    for shape_name, expected_names in _EXPECTED_FIELDS.items():
        fields = _shape_fields(shapes[shape_name])
        names = [field["name"] for field in fields]
        assert names == expected_names
        assert len(names) == len(set(names))
        assert {
            cast(str, field["name"]) for field in fields if field["required"] is True
        } == _REQUIRED_FIELDS[shape_name]
        assert all(isinstance(field["nullable"], bool) for field in fields)
        assert all(isinstance(field["type"], str) for field in fields)


def test_protocol_shape_references_are_resolvable() -> None:
    """Require nested field types to resolve before Fixture generation."""
    # Future fixture builders can traverse shape:/array: references without
    # embedding protocol-specific fallback names.
    protocol = _load_json_object(_PROTOCOL_PATH)
    shapes = _as_string_mapping(protocol["shapes"])
    for shape in shapes.values():
        for field in _shape_fields(shape):
            field_type = field["type"]
            assert isinstance(field_type, str)
            if field_type.startswith("shape:") or field_type.startswith("array:"):
                referenced = field_type.split(":", maxsplit=1)[1]
                assert referenced in shapes
            else:
                assert field_type in _PRIMITIVE_TYPES

    request_fields = _shape_fields(shapes["request"])
    stream = next(field for field in request_fields if field["name"] == "stream")
    assert stream["const"] is False

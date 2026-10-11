"""Conformance checks for the R1 JSON payload schema."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast

from mconet.codec.json import JsonPayload
from mconet.core.domain import JsonValue, OpenIdentifier, validate_open_identifier
from mconet.testing import (
    SchemaLoader,
    SchemaValidationIssue,
    SchemaValidatorAdapter,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_ROOT = _PROJECT_ROOT / "spec" / "schemas"
_SCHEMA_PATH = _SCHEMA_ROOT / "json-payload.json"
_SCHEMA_INDEX_PATH = _SCHEMA_ROOT / "index.json"
_ARTIFACT_SCHEMA_PATH = _SCHEMA_ROOT / "artifact.json"
_SCHEMA_ID = OpenIdentifier("schema.json_payload")
_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"
_MAX_SAFE_INTEGER = 2**53 - 1


def _load_object(path: Path) -> dict[str, JsonValue]:
    """Load one committed UTF-8 JSON object document."""
    # An object root is required before the document can be registered or compared
    # with the frozen payload port.
    document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError(f"Expected a JSON object in {path}.")
    return document


def _adapter() -> SchemaValidatorAdapter:
    """Load the committed payload schema through the public toolchain."""
    # Identity and dialect are part of the resource contract. Checking them here
    # keeps later acceptance tests from hiding a renamed or redialected schema.
    schema = _load_object(_SCHEMA_PATH)
    assert schema.get("$id") == _SCHEMA_ID.value
    assert schema.get("$schema") == _SCHEMA_DIALECT
    return SchemaValidatorAdapter(SchemaLoader({_SCHEMA_ID: schema}))


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        # The fragment identifies the portable JSON failure without requiring
        # the schema adapter and payload type to share one error class.
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def _definitions(schema: dict[str, JsonValue]) -> dict[str, JsonValue]:
    """Return the object-valued local definition map."""
    definitions = schema.get("$defs")
    if not isinstance(definitions, dict):
        raise AssertionError("Schema definitions must be an object.")
    return definitions


def _payload_from_document(document: dict[str, JsonValue]) -> JsonPayload:
    """Build the frozen payload port from one schema-valid document."""
    type_id = document["typeId"]
    value = document["value"]
    if not isinstance(type_id, str):
        raise AssertionError("typeId must be a string.")
    # Absence and an explicit string are different port states. Null is not a
    # stand-in for either one.
    if "schemaId" not in document:
        return JsonPayload(OpenIdentifier(type_id), value)
    schema_id = document["schemaId"]
    if not isinstance(schema_id, str):
        raise AssertionError("schemaId must be a string when present.")
    return JsonPayload(OpenIdentifier(type_id), value, schema_id)


def test_json_payload_schema_is_registered_and_matches_the_port() -> None:
    """Verify discovery, port fields, and the shared open-identifier grammar."""
    schema = _load_object(_SCHEMA_PATH)
    index = _load_object(_SCHEMA_INDEX_PATH)
    properties = schema.get("properties")
    resources = index.get("resources")
    definitions = _definitions(schema)
    artifact_identifier = _definitions(_load_object(_ARTIFACT_SCHEMA_PATH)).get(
        "openIdentifier"
    )
    payload_identifier = definitions.get("openIdentifier")
    json_value = definitions.get("jsonValue")
    if (
        not isinstance(properties, dict)
        or not isinstance(resources, list)
        or not isinstance(artifact_identifier, dict)
        or not isinstance(payload_identifier, dict)
        or not isinstance(json_value, dict)
    ):
        raise AssertionError("Payload schema structure is incomplete.")

    # The serializable port has the same three facts as JsonPayload and no codec,
    # task, access, or authorization members.
    assert "json-payload.json" in resources
    assert schema.get("additionalProperties") is False
    assert schema.get("required") == ["typeId", "value"]
    assert tuple(properties) == ("typeId", "schemaId", "value")
    for unrelated_name in (
        "authorization",
        "bytes",
        "mediaType",
        "task",
        "transport",
    ):
        assert unrelated_name not in properties

    # typeId uses the existing portable identifier grammar. schemaId is absent
    # from that definition because the payload port preserves it as plain text.
    assert payload_identifier.get("pattern") == artifact_identifier.get("pattern")
    assert payload_identifier.get("maxLength") == artifact_identifier.get("maxLength")
    assert payload_identifier.get("type") == "string"
    alternatives = json_value.get("oneOf")
    if not isinstance(alternatives, list):
        raise AssertionError("JSON value must be a oneOf composition.")
    integer_branch = next(
        branch
        for branch in alternatives
        if isinstance(branch, dict) and branch.get("type") == "integer"
    )
    assert integer_branch.get("minimum") == -_MAX_SAFE_INTEGER
    assert integer_branch.get("maximum") == _MAX_SAFE_INTEGER


def test_json_payload_schema_accepts_documents_that_build_the_port() -> None:
    """Verify every accepted document is the same payload port."""
    adapter = _adapter()
    documents: tuple[dict[str, JsonValue], ...] = (
        {"typeId": "json.null", "value": None},
        {"typeId": "json.boolean", "value": True},
        {"typeId": "json.boolean", "value": False},
        {"typeId": "json.number", "value": 0},
        {"typeId": "json.number", "value": _MAX_SAFE_INTEGER},
        {"typeId": "json.number", "value": -_MAX_SAFE_INTEGER},
        {"typeId": "json.number", "value": 0.5},
        {"typeId": "json.string", "value": ""},
        {"typeId": "json.string", "value": "café😀𠀋"},
        {"typeId": "json.array", "value": []},
        {"typeId": "json.array", "value": ["hello", 42, False, None]},
        {"typeId": "json.object", "value": {}},
        {
            "typeId": "json.object",
            "schemaId": "schema://json.contract/object/1",
            "value": {"nested": {"enabled": True}, "items": [1, 2, 3]},
        },
        {"typeId": "a", "schemaId": "", "value": "kept"},
        {"typeId": "a" * 128, "value": None},
    )

    for document in documents:
        # Schema acceptance and payload construction are one contract: the same
        # type id, schema id, and JSON object must survive both checks.
        assert adapter.validate(_SCHEMA_ID, document) == ()
        payload = _payload_from_document(document)
        assert payload.type_id == OpenIdentifier(cast(str, document["typeId"]))
        assert payload.value == document["value"]
        if "schemaId" in document:
            assert payload.schema_id == document["schemaId"]
        else:
            assert payload.schema_id is None


def test_json_payload_schema_rejects_port_violations() -> None:
    """Verify metadata, extra fields, and identifier grammar fail stably."""
    adapter = _adapter()
    invalid_documents: tuple[
        tuple[dict[str, JsonValue], tuple[SchemaValidationIssue, ...]], ...
    ] = (
        (
            {"value": None},
            (
                SchemaValidationIssue(
                    "/typeId", "required", "Required property is missing."
                ),
            ),
        ),
        (
            {"typeId": "json.null"},
            (
                SchemaValidationIssue(
                    "/value", "required", "Required property is missing."
                ),
            ),
        ),
        (
            {"typeId": "json.null", "schemaId": None, "value": None},
            (
                SchemaValidationIssue(
                    "/schemaId", "type", "Value has an unexpected JSON type."
                ),
            ),
        ),
        (
            {"typeId": "json.null", "value": None, "authorization": "secret"},
            (
                SchemaValidationIssue(
                    "/authorization",
                    "additionalProperties",
                    "Additional property is not allowed.",
                ),
            ),
        ),
        (
            {"typeId": "", "value": None},
            (
                SchemaValidationIssue(
                    "/typeId", "pattern", "String does not match pattern."
                ),
            ),
        ),
        (
            {"typeId": "JSON", "value": None},
            (
                SchemaValidationIssue(
                    "/typeId", "pattern", "String does not match pattern."
                ),
            ),
        ),
        (
            {"typeId": "a" * 129, "value": None},
            (
                SchemaValidationIssue(
                    "/typeId", "maxLength", "String is longer than maxLength."
                ),
            ),
        ),
    )

    for document, expected in invalid_documents:
        assert adapter.validate(_SCHEMA_ID, document) == expected

    # Identifier failures use the same portable grammar as the domain validator.
    # The payload constructor remains lossless, matching ErasedRuntimeValue.
    for invalid_type_id in ("", "JSON", "a" * 129, "a.", "has space"):
        _assert_raises(
            ValueError,
            lambda invalid_type_id=invalid_type_id: validate_open_identifier(
                OpenIdentifier(invalid_type_id)
            ),
            "OpenIdentifier",
        )


def test_json_payload_schema_rejects_non_portable_values_with_the_port() -> None:
    """Verify unsafe and non-finite numbers fail before keyword matching."""
    adapter = _adapter()
    unsafe_integer = _MAX_SAFE_INTEGER + 1
    documents = (
        {"typeId": "json.number", "value": unsafe_integer},
        {"typeId": "json.object", "value": {"count": unsafe_integer}},
        {"typeId": "json.number", "value": float("nan")},
        {"typeId": "json.number", "value": float("inf")},
    )

    for document in documents:
        # The toolchain and JsonPayload share the domain numeric policy, so a
        # value rejected here cannot become a frozen payload either.
        _assert_raises(
            ValueError,
            lambda document=document: adapter.validate(
                _SCHEMA_ID, cast(JsonValue, document)
            ),
            "JSON",
        )
        _assert_raises(
            ValueError,
            lambda document=document: JsonPayload(
                OpenIdentifier("json.number"),
                cast(JsonValue, document["value"]),
            ),
            "portable JSON numbers",
        )

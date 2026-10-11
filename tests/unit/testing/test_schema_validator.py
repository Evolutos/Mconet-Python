"""Deterministic basic-schema tests for SchemaValidatorAdapter."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import JsonValue, OpenIdentifier
from mconet.testing import (
    SchemaLoader,
    SchemaValidationIssue,
    SchemaValidatorAdapter,
)

_SCHEMA_ID = OpenIdentifier("schema.example")
_SCHEMA: JsonValue = {
    "type": "object",
    "required": ["name", "scores"],
    "properties": {
        "name": {"type": "string", "minLength": 2, "pattern": "^[a-z]+$"},
        "scores": {
            "type": "array",
            "items": {"type": "number", "minimum": 0, "maximum": 10},
        },
        "state": {"enum": ["ready", "pending"]},
    },
    "additionalProperties": False,
}


def _adapter() -> SchemaValidatorAdapter:
    """Build an isolated adapter using the representative object schema."""
    return SchemaValidatorAdapter(SchemaLoader({_SCHEMA_ID: _SCHEMA}))


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_schema_validator_accepts_valid_basic_fixture() -> None:
    """Verify a fixture satisfying nested basic assertions has no issues."""
    issues = _adapter().validate(
        _SCHEMA_ID,
        {"name": "valid", "scores": [0, 7.5, 10], "state": "ready"},
    )

    assert issues == ()


def test_schema_validator_returns_stable_invalid_fixture_issues() -> None:
    """Verify invalid fields produce deterministic paths and keyword results."""
    issues = _adapter().validate(
        _SCHEMA_ID,
        {"name": "A", "scores": [-1, 11], "extra/key": True},
    )

    # Schema field names are sorted while array indexes keep source order; JSON
    # Pointer escaping makes diagnostics stable for arbitrary object keys.
    assert issues == (
        SchemaValidationIssue(
            "/name", "minLength", "String is shorter than minLength."
        ),
        SchemaValidationIssue("/name", "pattern", "String does not match pattern."),
        SchemaValidationIssue("/scores/0", "minimum", "Number is below minimum."),
        SchemaValidationIssue("/scores/1", "maximum", "Number is above maximum."),
        SchemaValidationIssue(
            "/extra~1key",
            "additionalProperties",
            "Additional property is not allowed.",
        ),
    )


def test_schema_validator_reports_required_and_type_without_cascading() -> None:
    """Verify missing fields and a node type mismatch remain concise."""
    issues = _adapter().validate(_SCHEMA_ID, {"scores": "not-an-array"})

    assert issues == (
        SchemaValidationIssue("/name", "required", "Required property is missing."),
        SchemaValidationIssue("/scores", "type", "Value has an unexpected JSON type."),
    )


def test_schema_validator_distinguishes_boolean_and_number() -> None:
    """Verify Python boolean subclassing cannot satisfy a number schema."""
    schema_id = OpenIdentifier("schema.number")
    adapter = SchemaValidatorAdapter(SchemaLoader({schema_id: {"type": "number"}}))

    assert adapter.validate(schema_id, 1) == ()
    assert adapter.validate(schema_id, 1.0) == ()
    assert adapter.validate(schema_id, True) == (
        SchemaValidationIssue("", "type", "Value has an unexpected JSON type."),
    )


def test_schema_validator_supports_const_union_types_and_escaped_paths() -> None:
    """Verify union types, canonical const equality, and pointer escaping."""
    schema_id = OpenIdentifier("schema.union")
    adapter = SchemaValidatorAdapter(
        SchemaLoader(
            {
                schema_id: {
                    "type": ["object", "null"],
                    "properties": {"a~b/c": {"const": 2.0}},
                }
            }
        )
    )

    assert adapter.validate(schema_id, None) == ()
    assert adapter.validate(schema_id, {"a~b/c": 2}) == ()
    assert adapter.validate(schema_id, {"a~b/c": 3}) == (
        SchemaValidationIssue("/a~0b~1c", "const", "Value does not match const."),
    )


def test_schema_validator_supports_recursive_local_composition() -> None:
    """Verify local refs, oneOf/not, and minItems validate recursive arrays."""
    schema_id = OpenIdentifier("schema.recursive")
    schema: JsonValue = {
        "type": "object",
        "$defs": {
            "node": {
                "oneOf": [
                    {
                        "type": "object",
                        "properties": {
                            "kind": {"const": "leaf"},
                            "children": {"const": []},
                        },
                        "required": ["children", "kind"],
                        "additionalProperties": False,
                    },
                    {
                        "type": "object",
                        "properties": {
                            "kind": {"const": "branch"},
                            "children": {
                                "type": "array",
                                "minItems": 1,
                                "items": {"$ref": "#/$defs/node"},
                            },
                        },
                        "required": ["children", "kind"],
                        "additionalProperties": False,
                    },
                ]
            }
        },
        "properties": {
            "root": {"$ref": "#/$defs/node"},
            "state": {"not": {"const": "forbidden"}},
        },
        "required": ["root", "state"],
        "additionalProperties": False,
    }
    adapter = SchemaValidatorAdapter(SchemaLoader({schema_id: schema}))

    # The recursive child reference consumes one instance level on every use;
    # oneOf selects exactly one shape and not rejects only its matching value.
    assert (
        adapter.validate(
            schema_id,
            {
                "root": {
                    "kind": "branch",
                    "children": [{"kind": "leaf", "children": []}],
                },
                "state": "ready",
            },
        )
        == ()
    )
    assert adapter.validate(
        schema_id,
        {"root": {"kind": "branch", "children": []}, "state": "forbidden"},
    ) == (
        SchemaValidationIssue(
            "/root",
            "oneOf",
            "Value must match exactly one schema alternative.",
        ),
        SchemaValidationIssue("/state", "not", "Value matches a forbidden schema."),
    )

    overlapping_id = OpenIdentifier("schema.overlapping")
    overlapping_adapter = SchemaValidatorAdapter(
        SchemaLoader(
            {overlapping_id: {"oneOf": [{"type": "string"}, {"const": "same"}]}}
        )
    )
    # oneOf requires exactly one successful branch; two matches are as invalid
    # as zero matches and receive the same deterministic composition issue.
    assert overlapping_adapter.validate(overlapping_id, "same") == (
        SchemaValidationIssue(
            "", "oneOf", "Value must match exactly one schema alternative."
        ),
    )


def test_schema_validator_supports_array_cardinality_bounds() -> None:
    """Verify array lower and upper bounds report independent stable issues."""
    schema_id = OpenIdentifier("schema.array_bounds")
    adapter = SchemaValidatorAdapter(
        SchemaLoader(
            {
                schema_id: {
                    "type": "array",
                    "minItems": 1,
                    "maxItems": 1,
                    "items": {"type": "string"},
                }
            }
        )
    )

    # Exact cardinality accepts one item, while each side of the interval reports
    # its own keyword at the array path without suppressing item validation.
    assert adapter.validate(schema_id, ["value"]) == ()
    assert adapter.validate(schema_id, []) == (
        SchemaValidationIssue("", "minItems", "Array is shorter than minItems."),
    )
    assert adapter.validate(schema_id, ["first", "second"]) == (
        SchemaValidationIssue("", "maxItems", "Array is longer than maxItems."),
    )


def test_schema_validator_rejects_invalid_schema_definitions() -> None:
    """Verify malformed supported keywords fail as schema errors."""
    invalid_schemas: tuple[tuple[JsonValue, JsonValue, str], ...] = (
        ({"type": None}, "x", "type must be a string"),
        ({"type": ["string", "string"]}, "x", "invalid or duplicate"),
        ({"enum": None}, "x", "enum must be a non-empty array"),
        ({"minLength": -1}, "x", "non-negative integer"),
        ({"pattern": None}, "x", "pattern must be a string"),
        ({"pattern": "["}, "x", "pattern is invalid"),
        (
            {"required": ["value", "value"]},
            {"value": "x"},
            "required names must be unique",
        ),
        (
            {"properties": {"value": True}},
            {"value": "x"},
            "must contain an object schema",
        ),
        ({"additionalProperties": "no"}, {"value": "x"}, "must be a boolean"),
        ({"items": None}, [], "items must be an object"),
        ({"items": []}, [], "items must be an object"),
        ({"minItems": -1}, [], "minItems must be a non-negative integer"),
        ({"maxItems": -1}, [], "maxItems must be a non-negative integer"),
        ({"oneOf": []}, "x", "oneOf must be a non-empty array of objects"),
        ({"not": []}, "x", "not must be an object"),
        ({"$ref": 1}, "x", "$ref must be a string"),
        ({"$ref": "schema.external"}, "x", "$ref must be a local JSON Pointer"),
        ({"$ref": "#/$defs/missing"}, "x", "$ref target does not exist"),
        (
            {"$defs": {"invalid~escape": {}}, "$ref": "#/$defs/invalid~2escape"},
            "x",
            "$ref contains an invalid escape",
        ),
        (
            {"$defs": {"scalar": "value"}, "$ref": "#/$defs/scalar"},
            "x",
            "$ref target must be an object",
        ),
        (
            {
                "$defs": {
                    "first": {"$ref": "#/$defs/second"},
                    "second": {"$ref": "#/$defs/first"},
                },
                "$ref": "#/$defs/first",
            },
            "x",
            "$ref cycle does not consume data",
        ),
        ({"$ref": "#"}, "x", "$ref cycle does not consume data"),
    )

    for index, (schema, instance, message) in enumerate(invalid_schemas):
        schema_id = OpenIdentifier(f"schema.invalid_{index}")
        adapter = SchemaValidatorAdapter(SchemaLoader({schema_id: schema}))
        _assert_raises(
            ValueError,
            lambda adapter=adapter, schema_id=schema_id, instance=instance: (
                adapter.validate(schema_id, instance)
            ),
            message,
        )


def test_schema_validator_checks_values_of_undeclared_object_members() -> None:
    """Verify an object additionalProperties schema validates extra members."""
    schema_id = OpenIdentifier("schema.additional")
    schema: JsonValue = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "additionalProperties": {"type": "integer", "minimum": 0},
    }
    adapter = SchemaValidatorAdapter(SchemaLoader({schema_id: schema}))

    # Declared members keep their own schema. Undeclared members use the
    # additional schema instead of being ignored or rejected as a boolean flag.
    assert adapter.validate(schema_id, {"name": "item", "count": 2}) == ()
    assert adapter.validate(schema_id, {"count": -1}) == (
        SchemaValidationIssue("/count", "minimum", "Number is below minimum."),
    )
    assert adapter.validate(schema_id, {"name": 1}) == (
        SchemaValidationIssue("/name", "type", "Value has an unexpected JSON type."),
    )


def test_schema_validator_requires_loader_and_valid_fixture() -> None:
    """Verify adapter and fixture boundaries cannot be bypassed dynamically."""
    _assert_raises(
        TypeError,
        lambda: SchemaValidatorAdapter(cast(SchemaLoader, object())),
        "loader must be a SchemaLoader",
    )
    _assert_raises(
        TypeError,
        lambda: _adapter().validate(_SCHEMA_ID, cast(JsonValue, (1, 2))),
        "structurally valid JsonValue",
    )

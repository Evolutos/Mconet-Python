"""Deterministic validation adapter for basic JSON fixture schemas."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import cast

from mconet.core.domain import JsonValue, OpenIdentifier, validate_json_value_numbers
from mconet.testing.json_fixture import json_fixtures_equal
from mconet.testing.schema_loader import SchemaLoader

_JSON_TYPES = frozenset(
    ("null", "boolean", "integer", "number", "string", "array", "object")
)


@dataclass(frozen=True, slots=True)
class SchemaValidationIssue:
    """Describe one stable fixture validation failure."""

    path: str
    """RFC 6901 JSON Pointer to the invalid value; empty means the root."""

    keyword: str
    """Schema keyword that produced the failure."""

    message: str
    """Stable human-readable description without embedding fixture content."""


class SchemaValidatorAdapter:
    """Validate JSON fixtures against schemas selected by stable identifier.

    The adapter implements the assertion keywords needed by foundational value
    schemas: type, const, enum, numeric bounds, string bounds/pattern, object
    required/properties/additionalProperties, and array items. Unsupported
    annotation keywords remain inert as required by JSON Schema vocabulary
    extensibility; malformed supported keywords raise schema definition errors.
    """

    __slots__ = ("_loader",)

    def __init__(self, loader: SchemaLoader) -> None:
        """Bind validation to one explicit schema loader."""
        candidate = cast(object, loader)
        if not isinstance(candidate, SchemaLoader):
            raise TypeError("loader must be a SchemaLoader.")
        object.__setattr__(self, "_loader", candidate)

    def validate(
        self,
        schema_id: OpenIdentifier,
        instance: JsonValue,
    ) -> tuple[SchemaValidationIssue, ...]:
        """Return every deterministic validation issue for one JSON fixture.

        Args:
            schema_id: Stable identifier of the schema to apply.
            instance: Decoded JSON fixture value to validate.

        Returns:
            Issues in deterministic schema/path order, or an empty tuple.

        Raises:
            TypeError: If the instance is not structurally valid JSON data.
            ValueError: If the instance number policy or schema is invalid.
            KeyError: If the schema identifier is not registered.
        """
        # Reject invalid fixture data before schema evaluation so malformed JSON
        # cannot be misreported as an ordinary schema mismatch.
        validate_json_value_numbers(instance)
        schema = self._loader.load(schema_id)

        issues: list[SchemaValidationIssue] = []
        _validate_node(schema, instance, "", issues)
        return tuple(issues)


def _validate_node(
    schema: dict[str, JsonValue],
    instance: JsonValue,
    path: str,
    issues: list[SchemaValidationIssue],
) -> None:
    """Validate one schema node and append issues in stable keyword order."""
    # A type mismatch stops type-specific keyword evaluation at this node while
    # leaving sibling nodes available to report their own independent issues.
    allowed_types = _schema_types(schema["type"], path) if "type" in schema else None
    if allowed_types is not None and not any(
        _matches_json_type(instance, expected) for expected in allowed_types
    ):
        issues.append(
            SchemaValidationIssue(path, "type", "Value has an unexpected JSON type.")
        )
        return

    if "const" in schema and not json_fixtures_equal(instance, schema["const"]):
        issues.append(
            SchemaValidationIssue(path, "const", "Value does not match const.")
        )

    if "enum" in schema:
        enum = schema["enum"]
        if not isinstance(enum, list) or not enum:
            raise ValueError(f"Schema enum must be a non-empty array at {path!r}.")
        if not any(json_fixtures_equal(instance, option) for option in enum):
            issues.append(
                SchemaValidationIssue(
                    path, "enum", "Value is not an allowed enum member."
                )
            )

    # bool is excluded explicitly because Python otherwise treats it as a
    # numeric subtype even though JSON Schema does not.
    if type(instance) in (int, float):
        _validate_number(schema, cast(int | float, instance), path, issues)
    if isinstance(instance, str):
        _validate_string(schema, instance, path, issues)
    if isinstance(instance, list):
        _validate_array(schema, instance, path, issues)
    if isinstance(instance, dict):
        _validate_object(schema, instance, path, issues)


def _schema_types(value: JsonValue, path: str) -> tuple[str, ...]:
    """Normalize a schema type declaration into validated names."""
    if isinstance(value, str):
        names = (value,)
    elif isinstance(value, list) and value:
        if any(not isinstance(item, str) for item in value):
            raise ValueError(f"Schema type array must contain strings at {path!r}.")
        names = tuple(cast(list[str], value))
    else:
        raise ValueError(
            f"Schema type must be a string or non-empty array at {path!r}."
        )
    if len(names) != len(set(names)) or any(name not in _JSON_TYPES for name in names):
        raise ValueError(
            f"Schema type contains invalid or duplicate names at {path!r}."
        )
    return names


def _matches_json_type(value: JsonValue, expected: str) -> bool:
    """Match one value without Python boolean/integer type leakage."""
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return type(value) is int
    if expected == "number":
        return type(value) in (int, float)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    return isinstance(value, dict)


def _validate_number(
    schema: dict[str, JsonValue],
    value: int | float,
    path: str,
    issues: list[SchemaValidationIssue],
) -> None:
    """Apply inclusive minimum and maximum numeric assertions."""
    if "minimum" in schema:
        minimum = schema["minimum"]
        if type(minimum) not in (int, float):
            raise ValueError(f"Schema minimum must be a number at {path!r}.")
        if value < cast(int | float, minimum):
            issues.append(
                SchemaValidationIssue(path, "minimum", "Number is below minimum.")
            )
    if "maximum" in schema:
        maximum = schema["maximum"]
        if type(maximum) not in (int, float):
            raise ValueError(f"Schema maximum must be a number at {path!r}.")
        if value > cast(int | float, maximum):
            issues.append(
                SchemaValidationIssue(path, "maximum", "Number is above maximum.")
            )


def _validate_string(
    schema: dict[str, JsonValue],
    value: str,
    path: str,
    issues: list[SchemaValidationIssue],
) -> None:
    """Apply Unicode code-point length and regular-expression assertions."""
    if "minLength" in schema:
        minimum_length = schema["minLength"]
        if type(minimum_length) is not int or minimum_length < 0:
            raise ValueError(
                f"Schema minLength must be a non-negative integer at {path!r}."
            )
        if len(value) < minimum_length:
            issues.append(
                SchemaValidationIssue(
                    path, "minLength", "String is shorter than minLength."
                )
            )
    if "maxLength" in schema:
        maximum_length = schema["maxLength"]
        if type(maximum_length) is not int or maximum_length < 0:
            raise ValueError(
                f"Schema maxLength must be a non-negative integer at {path!r}."
            )
        if len(value) > maximum_length:
            issues.append(
                SchemaValidationIssue(
                    path, "maxLength", "String is longer than maxLength."
                )
            )

    if "pattern" in schema:
        pattern = schema["pattern"]
        if not isinstance(pattern, str):
            raise ValueError(f"Schema pattern must be a string at {path!r}.")
        try:
            matches = re.search(pattern, value) is not None
        except re.error as error:
            raise ValueError(f"Schema pattern is invalid at {path!r}.") from error
        if not matches:
            issues.append(
                SchemaValidationIssue(path, "pattern", "String does not match pattern.")
            )


def _validate_array(
    schema: dict[str, JsonValue],
    value: list[JsonValue],
    path: str,
    issues: list[SchemaValidationIssue],
) -> None:
    """Apply one object items schema to every ordered array element."""
    if "items" not in schema:
        return
    items = schema["items"]
    if not isinstance(items, dict):
        raise ValueError(f"Schema items must be an object at {path!r}.")
    item_schema = cast(dict[str, JsonValue], items)
    # Array indexes are traversed in source order so issue ordering and JSON
    # Pointer paths remain deterministic and preserve array semantics.
    for index, item in enumerate(value):
        _validate_node(item_schema, item, f"{path}/{index}", issues)


def _validate_object(
    schema: dict[str, JsonValue],
    value: dict[str, JsonValue],
    path: str,
    issues: list[SchemaValidationIssue],
) -> None:
    """Apply required, properties, and additionalProperties assertions."""
    properties_value = schema.get("properties", {})
    if not isinstance(properties_value, dict):
        raise ValueError(f"Schema properties must be an object at {path!r}.")
    properties = cast(dict[str, JsonValue], properties_value)

    required_value = schema.get("required", [])
    if not isinstance(required_value, list) or any(
        not isinstance(item, str) for item in required_value
    ):
        raise ValueError(f"Schema required must be an array of strings at {path!r}.")
    required = cast(list[str], required_value)
    if len(required) != len(set(required)):
        raise ValueError(f"Schema required names must be unique at {path!r}.")

    # Sort schema-driven names so issue ordering never depends on JSON object
    # insertion order in either the schema or fixture.
    for name in sorted(required):
        if name not in value:
            issues.append(
                SchemaValidationIssue(
                    _child_path(path, name),
                    "required",
                    "Required property is missing.",
                )
            )

    for name in sorted(properties):
        property_schema = properties[name]
        if not isinstance(property_schema, dict):
            raise ValueError(
                f"Schema property {name!r} must contain an object schema at {path!r}."
            )
        if name in value:
            _validate_node(
                cast(dict[str, JsonValue], property_schema),
                value[name],
                _child_path(path, name),
                issues,
            )

    additional = schema.get("additionalProperties", True)
    if type(additional) is not bool:
        raise ValueError(f"Schema additionalProperties must be a boolean at {path!r}.")
    if not additional:
        for name in sorted(value.keys() - properties.keys()):
            issues.append(
                SchemaValidationIssue(
                    _child_path(path, name),
                    "additionalProperties",
                    "Additional property is not allowed.",
                )
            )


def _child_path(path: str, token: str) -> str:
    """Append one RFC 6901-escaped object key to a JSON Pointer."""
    escaped = token.replace("~", "~0").replace("/", "~1")
    return f"{path}/{escaped}"

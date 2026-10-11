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

    The adapter implements the assertion keywords used by committed schemas:
    local references, type, const, enum, oneOf/not composition, numeric and
    string bounds, object required/properties/additionalProperties, and array
    items/minItems/maxItems. ``additionalProperties`` may be a boolean or an
    object schema, so recursive JSON values can constrain every object member.
    Unsupported annotation keywords remain inert as required by JSON Schema
    vocabulary extensibility; malformed supported keywords raise schema
    definition errors.
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
        _validate_node(schema, instance, "", issues, schema)
        return tuple(issues)


def _validate_node(
    schema: dict[str, JsonValue],
    instance: JsonValue,
    path: str,
    issues: list[SchemaValidationIssue],
    root_schema: dict[str, JsonValue],
    reference_chain: tuple[str, ...] = (),
) -> None:
    """Validate one schema node and append issues in stable keyword order."""
    # Resolve local references against the originally loaded document. A chain
    # applies only to this instance node; child values begin a new chain so a
    # recursive tree schema can consume data while true reference loops fail.
    if "$ref" in schema:
        reference = schema["$ref"]
        if not isinstance(reference, str):
            raise ValueError(f"Schema $ref must be a string at {path!r}.")
        if reference in reference_chain:
            raise ValueError(f"Schema $ref cycle does not consume data at {path!r}.")
        target = _resolve_local_reference(root_schema, reference, path)
        _validate_node(
            target,
            instance,
            path,
            issues,
            root_schema,
            (*reference_chain, reference),
        )

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

    _validate_composition(schema, instance, path, issues, root_schema)

    # bool is excluded explicitly because Python otherwise treats it as a
    # numeric subtype even though JSON Schema does not.
    if type(instance) in (int, float):
        _validate_number(schema, cast(int | float, instance), path, issues)
    if isinstance(instance, str):
        _validate_string(schema, instance, path, issues)
    if isinstance(instance, list):
        _validate_array(schema, instance, path, issues, root_schema)
    if isinstance(instance, dict):
        _validate_object(schema, instance, path, issues, root_schema)


def _resolve_local_reference(
    root_schema: dict[str, JsonValue], reference: str, path: str
) -> dict[str, JsonValue]:
    """Resolve one RFC 6901 fragment reference to an object schema node."""
    # This deterministic adapter deliberately resolves only the current schema
    # document. External fetching and mutable global schema registries remain out
    # of scope for isolated conformance validation.
    if reference == "#":
        return root_schema
    if not reference.startswith("#/"):
        raise ValueError(f"Schema $ref must be a local JSON Pointer at {path!r}.")

    current: JsonValue = root_schema
    for raw_token in reference[2:].split("/"):
        token = _decode_reference_token(raw_token, path)
        if not isinstance(current, dict) or token not in current:
            raise ValueError(f"Schema $ref target does not exist at {path!r}.")
        current = current[token]
    if not isinstance(current, dict):
        raise ValueError(f"Schema $ref target must be an object at {path!r}.")
    return cast(dict[str, JsonValue], current)


def _decode_reference_token(token: str, path: str) -> str:
    """Decode one JSON Pointer token while rejecting malformed escapes."""
    decoded: list[str] = []
    index = 0
    # Decode explicitly instead of chained replacements so invalid or ambiguous
    # tilde sequences never resolve to a different schema location by accident.
    while index < len(token):
        character = token[index]
        if character != "~":
            decoded.append(character)
            index += 1
            continue
        if index + 1 >= len(token) or token[index + 1] not in ("0", "1"):
            raise ValueError(f"Schema $ref contains an invalid escape at {path!r}.")
        decoded.append("~" if token[index + 1] == "0" else "/")
        index += 2
    return "".join(decoded)


def _validate_composition(
    schema: dict[str, JsonValue],
    instance: JsonValue,
    path: str,
    issues: list[SchemaValidationIssue],
    root_schema: dict[str, JsonValue],
) -> None:
    """Apply oneOf and not assertions without leaking branch diagnostics."""
    if "oneOf" in schema:
        raw_branches = schema["oneOf"]
        if (
            not isinstance(raw_branches, list)
            or not raw_branches
            or any(not isinstance(branch, dict) for branch in raw_branches)
        ):
            raise ValueError(
                f"Schema oneOf must be a non-empty array of objects at {path!r}."
            )
        matches = 0
        for raw_branch in raw_branches:
            # Branch issues are private matching evidence. Exposing every failed
            # alternative would create noisy, ordering-sensitive diagnostics.
            branch_issues: list[SchemaValidationIssue] = []
            _validate_node(
                cast(dict[str, JsonValue], raw_branch),
                instance,
                path,
                branch_issues,
                root_schema,
            )
            if not branch_issues:
                matches += 1
        if matches != 1:
            issues.append(
                SchemaValidationIssue(
                    path,
                    "oneOf",
                    "Value must match exactly one schema alternative.",
                )
            )

    if "not" in schema:
        raw_negative = schema["not"]
        if not isinstance(raw_negative, dict):
            raise ValueError(f"Schema not must be an object at {path!r}.")
        negative_issues: list[SchemaValidationIssue] = []
        _validate_node(
            cast(dict[str, JsonValue], raw_negative),
            instance,
            path,
            negative_issues,
            root_schema,
        )
        # A not schema fails precisely when its nested schema matches completely.
        if not negative_issues:
            issues.append(
                SchemaValidationIssue(path, "not", "Value matches a forbidden schema.")
            )


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
    root_schema: dict[str, JsonValue],
) -> None:
    """Apply length and one object items schema to an ordered array."""
    if "minItems" in schema:
        minimum_items = schema["minItems"]
        if type(minimum_items) is not int or minimum_items < 0:
            raise ValueError(
                f"Schema minItems must be a non-negative integer at {path!r}."
            )
        if len(value) < minimum_items:
            issues.append(
                SchemaValidationIssue(
                    path, "minItems", "Array is shorter than minItems."
                )
            )

    if "maxItems" in schema:
        maximum_items = schema["maxItems"]
        # JSON Schema cardinality is an exact non-negative integer. Explicit type
        # membership rejects bool despite Python's integer subclass relationship.
        if type(maximum_items) is not int or maximum_items < 0:
            raise ValueError(
                f"Schema maxItems must be a non-negative integer at {path!r}."
            )
        # Report the array itself because the violation concerns collection
        # membership count rather than any particular otherwise-valid item.
        if len(value) > maximum_items:
            issues.append(
                SchemaValidationIssue(
                    path, "maxItems", "Array is longer than maxItems."
                )
            )

    if "items" not in schema:
        return
    items = schema["items"]
    if not isinstance(items, dict):
        raise ValueError(f"Schema items must be an object at {path!r}.")
    item_schema = cast(dict[str, JsonValue], items)
    # Array indexes are traversed in source order so issue ordering and JSON
    # Pointer paths remain deterministic and preserve array semantics.
    for index, item in enumerate(value):
        _validate_node(item_schema, item, f"{path}/{index}", issues, root_schema)


def _validate_object(
    schema: dict[str, JsonValue],
    value: dict[str, JsonValue],
    path: str,
    issues: list[SchemaValidationIssue],
    root_schema: dict[str, JsonValue],
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
                root_schema,
            )

    additional = schema.get("additionalProperties", True)
    extra_names = sorted(value.keys() - properties.keys())
    if isinstance(additional, dict):
        # A schema applies to every undeclared member. Recursive JSON objects
        # need this form; a boolean cannot describe their nested value contract.
        additional_schema = cast(dict[str, JsonValue], additional)
        for name in extra_names:
            _validate_node(
                additional_schema,
                value[name],
                _child_path(path, name),
                issues,
                root_schema,
            )
        return
    if type(additional) is not bool:
        raise ValueError(
            "Schema additionalProperties must be a boolean or an object schema "
            f"at {path!r}."
        )
    if not additional:
        for name in extra_names:
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

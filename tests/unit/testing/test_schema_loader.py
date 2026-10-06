"""Stable lookup and isolation tests for SchemaLoader."""

import math
from collections.abc import Callable, Mapping
from typing import cast

from mconet.core.domain import JsonValue, OpenIdentifier
from mconet.testing import SchemaLoader


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


def test_schema_loader_loads_one_schema_by_stable_identifier() -> None:
    """Verify lookup selects exactly the requested registered document."""
    first_id = OpenIdentifier("schema.open_identifier")
    second_id = OpenIdentifier("schema.timestamp")
    loader = SchemaLoader(
        {
            first_id: {"type": "string", "maxLength": 128},
            second_id: {"type": "string", "format": "date-time"},
        }
    )

    # A load returns only the selected document; registry order and unrelated
    # documents cannot affect the result.
    assert loader.load(first_id) == {"type": "string", "maxLength": 128}
    assert loader.load(second_id) == {"type": "string", "format": "date-time"}


def test_schema_loader_isolates_source_and_loaded_documents() -> None:
    """Verify mutations cannot cross the registry or load boundaries."""
    identifier = OpenIdentifier("schema.example")
    source: dict[str, JsonValue] = {
        "type": "object",
        "required": ["value"],
    }
    loader = SchemaLoader({identifier: source})

    # Mutating the caller's source after construction must not change the
    # snapshot, and mutating one returned tree must not affect a later load.
    source["type"] = "array"
    loaded = loader.load(identifier)
    loaded["type"] = "number"

    assert loader.load(identifier) == {
        "type": "object",
        "required": ["value"],
    }


def test_schema_loader_rejects_unknown_identifier() -> None:
    """Verify an unregistered stable identifier produces a precise failure."""
    loader = SchemaLoader({OpenIdentifier("schema.known"): {"type": "null"}})

    _assert_raises(
        KeyError,
        lambda: loader.load(OpenIdentifier("schema.missing")),
        "Unknown schema identifier: schema.missing",
    )


def test_schema_loader_validates_registry_and_identifier_types() -> None:
    """Verify dynamic callers cannot bypass mapping and nominal key contracts."""
    _assert_raises(
        TypeError,
        lambda: SchemaLoader(cast(Mapping[OpenIdentifier, JsonValue], [])),
        "schemas must be a mapping",
    )
    _assert_raises(
        TypeError,
        lambda: SchemaLoader(
            cast(Mapping[OpenIdentifier, JsonValue], {"schema.example": {}})
        ),
        "Schema identifiers must be OpenIdentifier",
    )
    loader = SchemaLoader({OpenIdentifier("schema.example"): {}})
    _assert_raises(
        TypeError,
        lambda: loader.load(cast(OpenIdentifier, "schema.example")),
        "identifier must be an OpenIdentifier",
    )


def test_schema_loader_requires_valid_object_documents() -> None:
    """Verify schema roots and nested JSON values satisfy shared policies."""
    identifier = OpenIdentifier("schema.invalid")
    _assert_raises(
        ValueError,
        lambda: SchemaLoader({identifier: []}),
        "root must be a JSON object",
    )
    _assert_raises(
        ValueError,
        lambda: SchemaLoader({identifier: {"maximum": 2**53}}),
        "safe range",
    )
    _assert_raises(
        ValueError,
        lambda: SchemaLoader({identifier: {"const": math.nan}}),
        "must be finite",
    )

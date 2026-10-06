"""Conformance checks for language-neutral foundational value fixtures."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Literal, cast

from mconet.core.domain import (
    Bytes,
    JsonValue,
    OpenIdentifier,
    UriValue,
    parse_media_type,
    parse_timestamp,
    validate_duration,
    validate_json_value_numbers,
    validate_open_identifier,
    validate_uri,
)
from mconet.testing import SchemaLoader, SchemaValidatorAdapter

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _PROJECT_ROOT / "spec" / "schemas" / "foundation-values.json"
_FIXTURE_PATH = (
    _PROJECT_ROOT / "spec" / "fixtures" / "r1-text-unary" / "foundation-values.json"
)
DurationUnit = Literal["seconds", "milliseconds", "microseconds", "nanoseconds"]


def _load_object(path: Path) -> dict[str, JsonValue]:
    """Load one committed UTF-8 JSON object for conformance execution."""
    document: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError(f"Expected a JSON object fixture in {path}.")
    return document


def _case_lists(
    fixture: dict[str, JsonValue],
    type_name: str,
) -> tuple[list[JsonValue], list[JsonValue]]:
    """Return validated valid/invalid case arrays for one named value type."""
    types = fixture.get("types")
    if not isinstance(types, dict):
        raise AssertionError("Fixture types must be an object.")
    cases = types.get(type_name)
    if not isinstance(cases, dict):
        raise AssertionError(f"Fixture cases are missing for {type_name}.")
    valid = cases.get("valid")
    invalid = cases.get("invalid")
    if not isinstance(valid, list) or not isinstance(invalid, list):
        raise AssertionError(f"Fixture cases must be arrays for {type_name}.")
    return valid, invalid


def _assert_invalid(action: Callable[[], object]) -> None:
    """Require a Golden invalid case to fail through its public value boundary."""
    try:
        action()
    except (TypeError, ValueError):
        return
    raise AssertionError("Expected the Golden invalid case to be rejected.")


def _validate_duration_case(case: JsonValue) -> object:
    """Apply one structured duration case to the public validator."""
    if not isinstance(case, dict):
        raise TypeError("Duration case must be an object.")
    return validate_duration(
        cast(int, case.get("value")),
        cast(DurationUnit, case.get("unit")),
    )


def _validate_uri_case(case: JsonValue) -> object:
    """Apply one structured URI case to the public value and validator."""
    if not isinstance(case, dict):
        raise TypeError("URI case must be an object.")
    uri = UriValue(
        cast(str, case.get("value")),
        cast(bool, case.get("isAbsolute")),
    )
    return validate_uri(uri)


def test_foundation_fixture_structure_matches_registered_schema() -> None:
    """Verify the committed Golden collection has the canonical envelope."""
    schema = _load_object(_SCHEMA_PATH)
    fixture = _load_object(_FIXTURE_PATH)
    schema_id_value = schema.get("$id")
    fixture_schema_id = fixture.get("schemaId")
    if not isinstance(schema_id_value, str) or not isinstance(fixture_schema_id, str):
        raise AssertionError("Schema identifiers must be strings.")

    # The same stable identifier connects the separately indexed schema and
    # fixture resources; the loader and adapter exercise their public path.
    schema_id = OpenIdentifier(schema_id_value)
    assert fixture_schema_id == schema_id.value
    adapter = SchemaValidatorAdapter(SchemaLoader({schema_id: schema}))
    assert adapter.validate(schema_id, fixture) == ()


def test_foundation_golden_cases_match_public_value_behavior() -> None:
    """Verify every foundational type has passing valid and failing invalid cases."""
    fixture = _load_object(_FIXTURE_PATH)

    # Each case is executed through the same public constructor, parser, or
    # validator used by SDK consumers; fixtures do not duplicate implementation.
    valid, invalid = _case_lists(fixture, "open_identifier")
    for value in valid:
        validate_open_identifier(OpenIdentifier(cast(str, value)))
    for value in invalid:
        _assert_invalid(
            lambda value=value: validate_open_identifier(
                OpenIdentifier(cast(str, value))
            )
        )

    valid, invalid = _case_lists(fixture, "json_value")
    for value in valid:
        validate_json_value_numbers(value)
    for encoded in invalid:
        _assert_invalid(
            lambda encoded=encoded: validate_json_value_numbers(
                cast(JsonValue, json.loads(cast(str, encoded)))
            )
        )

    valid, invalid = _case_lists(fixture, "bytes")
    for value in valid:
        Bytes(bytes.fromhex(cast(str, value)))
    for value in invalid:
        _assert_invalid(lambda value=value: Bytes(bytes.fromhex(cast(str, value))))

    valid, invalid = _case_lists(fixture, "timestamp")
    for value in valid:
        parse_timestamp(cast(str, value))
    for value in invalid:
        _assert_invalid(lambda value=value: parse_timestamp(cast(str, value)))

    valid, invalid = _case_lists(fixture, "duration")
    for case in valid:
        _validate_duration_case(case)
    for case in invalid:
        _assert_invalid(lambda case=case: _validate_duration_case(case))

    valid, invalid = _case_lists(fixture, "uri")
    for case in valid:
        _validate_uri_case(case)
    for case in invalid:
        _assert_invalid(lambda case=case: _validate_uri_case(case))

    valid, invalid = _case_lists(fixture, "media_type")
    for value in valid:
        parse_media_type(cast(str, value))
    for value in invalid:
        _assert_invalid(lambda value=value: parse_media_type(cast(str, value)))

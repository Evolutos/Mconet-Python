"""Serialization tests for presence-aware optional fields."""

from collections.abc import Callable, Mapping
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import JsonValue, OptionalField, serialize_optional_fields


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


def test_optional_serialization_distinguishes_missing_null_and_default() -> None:
    """Verify omission, explicit null, and explicit default remain distinct."""
    serialized = serialize_optional_fields(
        {
            "missingValue": OptionalField(is_present=False),
            "nullValue": OptionalField(is_present=True, value=None),
            "explicitDefault": OptionalField(is_present=True, value=1.0),
        }
    )

    assert "missingValue" not in serialized
    assert serialized["nullValue"] is None
    assert serialized["explicitDefault"] == 1.0


def test_optional_serialization_returns_read_only_snapshot() -> None:
    """Verify source membership changes cannot alter serialized field presence."""
    source = {"name": OptionalField(True, "example")}
    serialized = serialize_optional_fields(source)

    source.clear()

    assert serialized == {"name": "example"}
    assert not hasattr(serialized, "__setitem__")


def test_optional_field_has_immutable_value_semantics() -> None:
    """Verify presence and value drive equality and cannot be reassigned."""
    missing = OptionalField(False)
    null = OptionalField(True, None)
    same_null = OptionalField(True, None)

    assert missing != null
    assert null == same_null
    _assert_raises(
        FrozenInstanceError,
        lambda: null.__setattr__("is_present", False),
        "cannot assign to field",
    )


def test_optional_field_rejects_invalid_presence_states() -> None:
    """Verify truthy flags and values attached to missing fields are invalid."""
    _assert_raises(
        TypeError,
        lambda: OptionalField(cast(bool, 1)),
        "is_present must be a boolean",
    )
    _assert_raises(
        ValueError,
        lambda: OptionalField(False, "unexpected"),
        "missing OptionalField cannot contain a value",
    )


def test_optional_field_rejects_non_json_present_values() -> None:
    """Verify non-JSON and cyclic values cannot enter serialization output."""
    cyclic: list[JsonValue] = []
    cyclic.append(cyclic)

    for value in (cast(JsonValue, ("tuple",)), cyclic):
        _assert_raises(
            TypeError,
            lambda value=value: OptionalField(True, value),
            "must be a JsonValue",
        )


def test_optional_serializer_rejects_invalid_mapping_contracts() -> None:
    """Verify the serializer requires mapping, string keys, and field wrappers."""
    _assert_raises(
        TypeError,
        lambda: serialize_optional_fields(
            cast(Mapping[str, OptionalField], []),
        ),
        "fields must be a mapping",
    )
    _assert_raises(
        TypeError,
        lambda: serialize_optional_fields(
            cast(Mapping[str, OptionalField], {1: OptionalField(False)}),
        ),
        "fields keys must be strings",
    )
    _assert_raises(
        TypeError,
        lambda: serialize_optional_fields(
            cast(Mapping[str, OptionalField], {"name": "example"}),
        ),
        "fields values must be OptionalField instances",
    )

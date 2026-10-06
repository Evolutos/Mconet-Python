"""Round-trip tests for forward-compatible unknown JSON fields."""

from collections.abc import Callable, Mapping
from typing import cast

from mconet.core.domain import (
    JsonValue,
    SchemaVersion,
    preserve_unknown_fields,
    restore_preserved_fields,
)


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


def test_unknown_fields_survive_newer_schema_round_trip() -> None:
    """Verify an older reader restores fields introduced by a future schema."""
    future_version = SchemaVersion("99.0")
    document: dict[str, JsonValue] = {
        "schemaVersion": future_version.value,
        "name": "example",
        "futureFlag": True,
        "futureOptions": {"modes": ["fast", "safe"], "limit": 4},
        "futureNullable": None,
    }
    known_names = frozenset(("schemaVersion", "name"))

    preserved = preserve_unknown_fields(document, known_names)
    restored = restore_preserved_fields(
        {
            "schemaVersion": future_version.value,
            "name": "example",
        },
        preserved,
    )

    assert preserved == {
        "futureFlag": True,
        "futureOptions": {"modes": ["fast", "safe"], "limit": 4},
        "futureNullable": None,
    }
    assert restored == document


def test_unknown_field_snapshots_are_read_only_and_structurally_independent() -> None:
    """Verify membership snapshots do not follow later source-map mutations."""
    source: dict[str, JsonValue] = {"known": 1, "future": "retained"}
    preserved = preserve_unknown_fields(source, ("known",))

    source["anotherFuture"] = False
    del source["future"]

    assert preserved == {"future": "retained"}
    assert not hasattr(preserved, "__setitem__")


def test_restore_preserved_fields_rejects_collisions() -> None:
    """Verify a newly known field cannot silently replace preserved data."""
    _assert_raises(
        ValueError,
        lambda: restore_preserved_fields(
            {"futureFlag": False},
            {"futureFlag": True},
        ),
        "collides with known field: futureFlag",
    )


def test_unknown_field_helpers_require_string_mapping_keys() -> None:
    """Verify dynamic inputs cannot create invalid JSON object field names."""
    invalid = cast(Mapping[str, JsonValue], {1: "value"})

    _assert_raises(
        TypeError,
        lambda: preserve_unknown_fields(invalid, ()),
        "fields keys must be strings",
    )
    _assert_raises(
        TypeError,
        lambda: restore_preserved_fields({}, invalid),
        "preserved_fields keys must be strings",
    )


def test_unknown_field_helpers_require_mapping_inputs() -> None:
    """Verify dynamic callers cannot substitute sequences for JSON objects."""
    _assert_raises(
        TypeError,
        lambda: preserve_unknown_fields(
            cast(Mapping[str, JsonValue], []),
            (),
        ),
        "fields must be a mapping",
    )
    _assert_raises(
        TypeError,
        lambda: restore_preserved_fields(
            cast(Mapping[str, JsonValue], []),
            {},
        ),
        "known_fields must be a mapping",
    )


def test_preserve_unknown_fields_requires_string_name_collection() -> None:
    """Verify a single string and non-string collection members are rejected."""
    _assert_raises(
        TypeError,
        lambda: preserve_unknown_fields(
            {},
            cast(frozenset[str], "known"),
        ),
        "collection of strings",
    )
    _assert_raises(
        TypeError,
        lambda: preserve_unknown_fields(
            {},
            cast(frozenset[str], frozenset((1,))),
        ),
        "contain only strings",
    )

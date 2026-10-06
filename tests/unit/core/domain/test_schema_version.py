"""Format and value-semantics tests for SchemaVersion."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import SchemaVersion


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


def test_schema_version_accepts_canonical_versions() -> None:
    """Verify zero, ordinary, and unknown future components remain exact."""
    values = ("0.0", "1.0", "2.15", f"{'9' * 5_000}.0")

    for value in values:
        version = SchemaVersion(value)

        assert version.value == value
        assert str(version) == value


def test_schema_version_compares_components_numerically() -> None:
    """Verify major and minor decimal magnitude drives total ordering."""
    assert SchemaVersion("1.9") < SchemaVersion("1.10") < SchemaVersion("2.0")
    assert SchemaVersion("9.0") < SchemaVersion(f"{'1' + '0' * 5_000}.0")
    assert SchemaVersion("3.4") <= SchemaVersion("3.4")
    assert SchemaVersion("3.5") > SchemaVersion("3.4")


def test_schema_version_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and immutability use canonical version text."""
    first = SchemaVersion("3.4")
    same = SchemaVersion("3.4")
    different = SchemaVersion("3.5")

    assert first == same
    assert hash(first) == hash(same)
    assert first != different
    assert first != "3.4"
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("value", "3.5"),
        "cannot assign to field",
    )


def test_schema_version_rejects_noncanonical_formats() -> None:
    """Verify signs, leading zeroes, missing parts, and non-ASCII text fail."""
    invalid_values = (
        "",
        "1",
        "1.2.3",
        "v1.0",
        "01.0",
        "1.00",
        "-1.0",
        "+1.0",
        "1.a",
        "1 0",
        " 1.0",
        "1.0 ",
        "\u0661.0",
    )

    for value in invalid_values:
        _assert_raises(
            ValueError,
            lambda value=value: SchemaVersion(value),
            "canonical unsigned major.minor format",
        )


def test_schema_version_rejects_non_string_input() -> None:
    """Verify dynamic callers cannot bypass the string representation."""
    _assert_raises(
        TypeError,
        lambda: SchemaVersion(cast(str, (1, 0))),
        "value must be a string",
    )


def test_schema_version_does_not_order_against_unrelated_types() -> None:
    """Verify comparison never invents ordering across domain types."""
    _assert_raises(
        TypeError,
        lambda: SchemaVersion("1.0") < cast(SchemaVersion, "2.0"),
        "not supported",
    )

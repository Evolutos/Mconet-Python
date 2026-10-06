"""Value-semantics tests for OpenIdentifier."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import OpenIdentifier


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str | None = None,
) -> None:
    """Require an action to raise the expected exception and optional message."""
    try:
        action()
    except exception_type as error:
        if message is not None:
            assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_open_identifier_preserves_unknown_text_exactly() -> None:
    """Verify unknown values survive without trimming or Unicode normalization."""
    # The validator owns format acceptance; this value type retains producer
    # spelling so a newer namespace can round-trip through an older client.
    value = "Vendor.Future/β "
    identifier = OpenIdentifier(value)

    assert identifier.value == value
    assert str(identifier) == value


def test_open_identifier_has_case_sensitive_value_equality() -> None:
    """Verify equality and hashing use the exact string and concrete value type."""
    lowercase = OpenIdentifier("vendor.feature")
    same = OpenIdentifier("vendor.feature")
    uppercase = OpenIdentifier("Vendor.Feature")

    assert lowercase == same
    assert hash(lowercase) == hash(same)
    assert lowercase != uppercase
    assert lowercase != "vendor.feature"
    assert {lowercase, same, uppercase} == {lowercase, uppercase}


def test_open_identifier_is_immutable() -> None:
    """Verify a constructed identifier cannot change its preserved value."""
    identifier = OpenIdentifier("vendor.feature")

    _assert_raises(
        FrozenInstanceError,
        lambda: identifier.__setattr__("value", "vendor.changed"),
    )


def test_open_identifier_rejects_non_string_storage() -> None:
    """Verify the value object cannot hold a non-portable primitive type."""
    # The cast deliberately crosses the static boundary to verify the runtime
    # invariant without weakening the public constructor annotation.
    _assert_raises(
        TypeError,
        lambda: OpenIdentifier(cast(str, 42)),
        "must be a string",
    )

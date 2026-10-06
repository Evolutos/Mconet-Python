"""Value-contract tests for immutable HeaderField records."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import HeaderField


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Keep exception assertions dependency-free while checking the stable domain
    # diagnostic rather than accepting any failure of the requested type.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_header_field_preserves_exact_caller_text() -> None:
    """Verify construction performs no HTTP normalization or value trimming."""
    field = HeaderField("X-Vendor-Trace", "  Mixed Case Value  ")

    # Exact text preservation keeps transport policy out of the domain value;
    # later components can apply the rules of their actual wire protocol.
    assert field.name == "X-Vendor-Trace"
    assert field.value == "  Mixed Case Value  "


def test_header_field_is_immutable_and_has_value_equality() -> None:
    """Verify equal pairs compare by value and cannot be reassigned."""
    first = HeaderField("X-Feature", "enabled")
    same = HeaderField("X-Feature", "enabled")

    # Frozen records make header input safe to share without mutation while
    # retaining ordinary value equality for later ordered collections.
    assert first == same
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("value", "disabled"),
        "cannot assign to field",
    )


def test_header_field_rejects_non_string_storage() -> None:
    """Verify dynamic callers cannot bypass the primitive field contract."""
    invalid_fields = (
        lambda: HeaderField(cast(str, 1), "value"),
        lambda: HeaderField("name", cast(str, b"value")),
    )

    # Each field is checked independently so failures occur at construction,
    # before any collection or transport attempts to interpret the pair.
    for create_field in invalid_fields:
        _assert_raises(TypeError, create_field, "must be a string")

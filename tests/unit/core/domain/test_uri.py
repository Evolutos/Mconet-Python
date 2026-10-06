"""Value-semantics tests for immutable UriValue references."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import UriValue


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


def test_uri_value_preserves_absolute_and_relative_references() -> None:
    """Verify both forms retain exact producer text without normalization."""
    absolute = UriValue("HTTPS://example.com/a/../b?q=%2f#Part", is_absolute=True)
    relative = UriValue("../items/%2F?q=a+b", is_absolute=False)

    assert absolute.value == "HTTPS://example.com/a/../b?q=%2f#Part"
    assert str(absolute) == absolute.value
    assert absolute.is_absolute is True
    assert relative.value == "../items/%2F?q=a+b"
    assert relative.is_absolute is False


def test_uri_value_has_case_sensitive_immutable_value_semantics() -> None:
    """Verify equality, hashing, and immutability use text and reference form."""
    first = UriValue("https://example.com", is_absolute=True)
    same = UriValue("https://example.com", is_absolute=True)
    different_case = UriValue("HTTPS://example.com", is_absolute=True)
    relative_form = UriValue("https://example.com", is_absolute=False)

    assert first == same
    assert hash(first) == hash(same)
    assert first != different_case
    assert first != relative_form
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("value", "https://example.org"),
        "cannot assign to field",
    )


def test_uri_value_rejects_non_primitive_storage() -> None:
    """Verify dynamic callers cannot bypass string and boolean storage."""
    _assert_raises(
        TypeError,
        lambda: UriValue(cast(str, 1), is_absolute=True),
        "value must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: UriValue("path", is_absolute=cast(bool, 1)),
        "is_absolute must be a boolean",
    )

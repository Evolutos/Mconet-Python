"""Value-semantics tests for structured MediaType values."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import MediaType


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


def test_media_type_preserves_structured_parameters() -> None:
    """Verify type, subtype, order, spelling, and parameter values survive."""
    media_type = MediaType(
        "Application",
        "Problem+JSON",
        (("Charset", "UTF-8"), ("profile", "vendor value")),
    )

    assert media_type.type == "Application"
    assert media_type.subtype == "Problem+JSON"
    assert media_type.parameters == (
        ("Charset", "UTF-8"),
        ("profile", "vendor value"),
    )
    assert str(media_type) == "Application/Problem+JSON"


def test_media_type_has_immutable_value_semantics() -> None:
    """Verify equality, hashing, and immutability include parameter structure."""
    parameters = (("charset", "utf-8"), ("format", "flowed"))
    first = MediaType("text", "plain", parameters)
    same = MediaType("text", "plain", parameters)
    reordered = MediaType(
        "text",
        "plain",
        (("format", "flowed"), ("charset", "utf-8")),
    )

    assert first == same
    assert hash(first) == hash(same)
    assert first != reordered
    _assert_raises(
        FrozenInstanceError,
        lambda: first.__setattr__("subtype", "html"),
        "cannot assign to field",
    )


def test_media_type_rejects_mutable_or_non_string_storage() -> None:
    """Verify dynamic callers cannot introduce mutable or non-text fields."""
    _assert_raises(
        TypeError,
        lambda: MediaType(cast(str, 1), "plain"),
        "type must be a string",
    )
    _assert_raises(
        TypeError,
        lambda: MediaType("text", "plain", cast(tuple[tuple[str, str], ...], [])),
        "parameters must be a tuple",
    )
    _assert_raises(
        TypeError,
        lambda: MediaType(
            "text",
            "plain",
            cast(tuple[tuple[str, str], ...], (("charset", 1),)),
        ),
        "string name/value pairs",
    )

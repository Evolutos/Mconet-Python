"""Ordered multi-value and lookup tests for immutable Headers."""

from collections.abc import Callable
from dataclasses import FrozenInstanceError
from typing import cast

from mconet.core.domain import HeaderField, Headers


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Check the stable domain diagnostic so an unrelated exception cannot make
    # a negative boundary test pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_headers_preserve_order_and_repeated_names() -> None:
    """Verify every repeated field remains in exact caller order."""
    fields = (
        HeaderField("Set-Cookie", "first=1"),
        HeaderField("X-Trace", "trace-a"),
        HeaderField("set-cookie", "second=2"),
    )
    headers = Headers(fields)

    # The stored representation is lossless: duplicates are not collapsed and
    # original name spelling remains available to the eventual transport.
    assert headers.values == fields
    assert headers.values[0].name == "Set-Cookie"
    assert headers.values[2].name == "set-cookie"


def test_headers_match_names_case_insensitively() -> None:
    """Verify lookup returns all matching values without changing their order."""
    headers = Headers(
        (
            HeaderField("X-Feature", "first"),
            HeaderField("x-feature", "second"),
            HeaderField("X-Other", "ignored"),
            HeaderField("X-FEATURE", "third"),
        )
    )

    # Name comparison is case-insensitive, but filtering walks the original
    # tuple from left to right and therefore preserves multi-value order.
    assert headers.get_all("x-FeAtUrE") == ("first", "second", "third")
    assert headers.get_all("missing") == ()


def test_headers_are_immutable() -> None:
    """Verify neither the record nor its tuple storage can be reassigned."""
    headers = Headers((HeaderField("X-Feature", "enabled"),))

    # Frozen dataclass storage and a tuple prevent replacement and in-place
    # collection mutation without adding a separate defensive-copy layer.
    _assert_raises(
        FrozenInstanceError,
        lambda: headers.__setattr__("values", ()),
        "cannot assign to field",
    )
    assert isinstance(headers.values, tuple)


def test_headers_reject_invalid_storage_and_lookup_types() -> None:
    """Verify dynamic callers cannot bypass collection and lookup contracts."""
    invalid_collections = (
        lambda: Headers(cast(tuple[HeaderField, ...], [])),
        lambda: Headers(cast(tuple[HeaderField, ...], ("field",))),
    )

    # Validate the immutable container first, then its members; lookup applies
    # the same explicit string boundary before attempting case normalization.
    for create_headers in invalid_collections:
        _assert_raises(TypeError, create_headers, "Headers values must")
    _assert_raises(
        TypeError,
        lambda: Headers().get_all(cast(str, 1)),
        "lookup name must be a string",
    )

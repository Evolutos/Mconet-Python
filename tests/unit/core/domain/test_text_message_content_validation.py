"""Semantic validation tests for TextMessageContent values."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from mconet.core.domain import (
    Extensions,
    JsonValue,
    MessageContentKind,
    OpenIdentifier,
    TextMessageContent,
    validate_text_message_content,
)


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected exception and message fragment."""
    # Keep failure capture narrow so an unexpected exception type or successful
    # invalid branch remains visible to the test runner.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


def test_validator_preserves_unicode_emoji_multiline_and_empty_text() -> None:
    """Verify every required valid text category passes without normalization."""
    texts = (
        "",
        "你好世界",
        "wave 👋🏽 and smile 🙂",
        "first line\nsecond line\r\nthird line",
        "e\u0301",
    )

    # Object identity and exact text equality prove validation neither replaces
    # the value nor trims, normalizes, or rewrites line endings and Unicode.
    for text in texts:
        content = TextMessageContent("content-1", text)
        validated = validate_text_message_content(content)
        assert validated is content
        assert validated.text == text


def test_validator_applies_inclusive_code_point_length_boundaries() -> None:
    """Verify zero, exact-limit, and over-limit text branches independently."""
    empty = TextMessageContent("empty", "")
    boundary = TextMessageContent("boundary", "a🙂e\u0301")
    over_boundary = TextMessageContent("over", "a🙂e\u0301!")

    # Python counts the supplementary emoji as one code point and the combining
    # accent as a separate point, making the boundary text length exactly four.
    assert len(boundary.text) == 4
    assert validate_text_message_content(empty, maximum_code_points=0) is empty
    assert validate_text_message_content(boundary, maximum_code_points=4) is boundary
    _assert_raises(
        ValueError,
        lambda: validate_text_message_content(over_boundary, maximum_code_points=4),
        "exceeds maximum_code_points",
    )


def test_validator_has_no_implicit_text_length_limit() -> None:
    """Verify default domain validation does not invent a model context limit."""
    content = TextMessageContent("long", "文🙂" * 10_000)

    # Model and protocol context windows vary, so a caller must opt into a known
    # limit instead of the Core silently truncating or rejecting valid text.
    assert validate_text_message_content(content) is content
    assert len(content.text) == 20_000


def test_validator_rejects_invalid_explicit_length_limits() -> None:
    """Verify boolean, non-integer, and negative limit policies fail clearly."""
    content = TextMessageContent("content-1", "text")

    # Exact runtime checks keep accidental truthy configuration values from
    # becoming a one- or zero-code-point policy.
    for value in (True, 1.5, "4"):
        _assert_raises(
            TypeError,
            lambda value=value: validate_text_message_content(
                content,
                maximum_code_points=cast(int, value),
            ),
            "must be an integer or None",
        )
    _assert_raises(
        ValueError,
        lambda: validate_text_message_content(content, maximum_code_points=-1),
        "must not be negative",
    )


def test_validator_checks_metadata_and_extensions_as_portable_json() -> None:
    """Verify both shared data channels reject malformed recursive JSON."""
    cyclic: list[JsonValue] = []
    cyclic.append(cyclic)

    # Construction snapshots mapping membership but intentionally defers deep
    # JSON validation, so each invalid channel is exercised at this boundary.
    for field_name, value, exception_type, message in (
        ("metadata", cast(JsonValue, ("tuple",)), TypeError, "JsonValue"),
        ("metadata", cyclic, TypeError, "JsonValue"),
        ("extensions", 2**53, ValueError, "safe range"),
        ("extensions", float("inf"), ValueError, "finite"),
    ):
        arguments: dict[str, Extensions] = {
            field_name: {"invalid": value},
        }
        content = TextMessageContent("content-1", "text", **arguments)
        _assert_raises(
            exception_type,
            lambda content=content: validate_text_message_content(content),
            message,
        )


def test_validator_rejects_non_text_content_and_overridden_kind() -> None:
    """Verify nominal type and fixed content-kind invariants cannot be bypassed."""

    @dataclass(frozen=True, slots=True)
    class _OtherKind:
        """Represent a non-text kind returned by a dynamic subclass."""

        id: OpenIdentifier
        """Open content identifier deliberately different from content.text."""

    class _MisclassifiedTextContent(TextMessageContent):
        """Override the fixed kind to exercise validator defense in depth."""

        @property
        def kind(self) -> MessageContentKind:
            """Return a valid open identifier with the wrong content semantics."""
            # A structurally valid Kind still fails because text content requires
            # the exact standard content.text identity.
            return _OtherKind(OpenIdentifier("vendor.not_text"))

    _assert_raises(
        TypeError,
        lambda: validate_text_message_content(cast(TextMessageContent, object())),
        "must be a TextMessageContent",
    )
    _assert_raises(
        ValueError,
        lambda: validate_text_message_content(
            _MisclassifiedTextContent("content-1", "text")
        ),
        "kind must be content.text",
    )

"""Syntax and normalization tests for the media type parser."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import MediaType, parse_media_type


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


def test_parse_media_type_normalizes_case_insensitive_tokens() -> None:
    """Verify type, subtype, and parameter names use canonical lowercase."""
    assert parse_media_type("Application/Problem+JSON; Charset=UTF-8") == MediaType(
        "application",
        "problem+json",
        (("charset", "UTF-8"),),
    )


def test_parse_media_type_decodes_parameters_and_preserves_order() -> None:
    """Verify ordered token and quoted parameters retain decoded value case."""
    parsed = parse_media_type(
        r' text/plain ; format=Flowed; note="semi; quote=\" and slash=\\"' + "\t"
    )

    assert parsed.parameters == (
        ("format", "Flowed"),
        ("note", 'semi; quote=" and slash=\\'),
    )


def test_parse_media_type_accepts_empty_and_extended_quoted_values() -> None:
    """Verify quoted strings accept empty, tab, and HTTP obs-text content."""
    parsed = parse_media_type('text/plain; empty=""; label="a\tb\u00e9"')

    assert parsed.parameters == (("empty", ""), ("label", "a\tb\u00e9"))


def test_parse_media_type_rejects_invalid_type_and_parameter_syntax() -> None:
    """Verify empty tokens, separators, whitespace, and trailing text fail."""
    invalid_values = (
        "",
        "/plain",
        "text/",
        "text /plain",
        "text/plain/extra",
        "text/plain;",
        "text/plain; charset",
        "text/plain; charset =utf-8",
        "text/plain; charset= utf-8",
        "text/plain; charset=utf-8 extra",
        "t\u00e9xt/plain",
    )

    for value in invalid_values:
        _assert_raises(
            ValueError,
            lambda value=value: parse_media_type(value),
            "Media type",
        )


def test_parse_media_type_rejects_invalid_quoted_values() -> None:
    """Verify unterminated, control, Unicode, and invalid escapes fail."""
    invalid_values = (
        'text/plain; note="unterminated',
        'text/plain; note="line\nbreak"',
        'text/plain; note="emoji \U0001f642"',
        'text/plain; note="trailing\\',
        'text/plain; note="bad\\\n"',
        'text/plain; note="done"extra',
    )

    for value in invalid_values:
        _assert_raises(
            ValueError,
            lambda value=value: parse_media_type(value),
            "Media type",
        )


def test_parse_media_type_rejects_duplicate_parameter_names() -> None:
    """Verify parameter-name uniqueness is case-insensitive."""
    _assert_raises(
        ValueError,
        lambda: parse_media_type("text/plain; charset=utf-8; CHARSET=ascii"),
        "duplicate parameter",
    )


def test_parse_media_type_requires_string_input() -> None:
    """Verify dynamic callers cannot pass non-text input."""
    _assert_raises(
        TypeError,
        lambda: parse_media_type(cast(str, b"text/plain")),
        "must be a string",
    )

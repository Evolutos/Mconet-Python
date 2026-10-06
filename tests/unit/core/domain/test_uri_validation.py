"""Boundary tests for RFC 3986 UriValue validation."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import UriValue, validate_uri


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


def test_validate_uri_accepts_absolute_and_relative_forms() -> None:
    """Verify hierarchical, opaque, network-path, path, and empty references."""
    values = (
        UriValue("https://example.com/a?q=1#part", is_absolute=True),
        UriValue("mailto:user@example.com", is_absolute=True),
        UriValue("vendor+v1:data%2Fvalue", is_absolute=True),
        UriValue("http://[::1]:8080/path", is_absolute=True),
        UriValue("//example.com/path", is_absolute=False),
        UriValue("//[v1.host]/path", is_absolute=False),
        UriValue("../items/%2F?q=a+b", is_absolute=False),
        UriValue("", is_absolute=False),
    )

    for value in values:
        assert validate_uri(value) is value


def test_validate_uri_rejects_reference_form_mismatches() -> None:
    """Verify declared absolute and relative forms agree with scheme syntax."""
    invalid_values = (
        (UriValue("path/item", is_absolute=True), "must contain a valid scheme"),
        (
            UriValue("https://example.com", is_absolute=False),
            "must not contain a scheme",
        ),
        (UriValue("1http:value", is_absolute=False), "must not contain ':'"),
    )

    for value, message in invalid_values:
        _assert_raises(ValueError, lambda value=value: validate_uri(value), message)


def test_validate_uri_rejects_invalid_percent_escapes() -> None:
    """Verify percent encoding always contains exactly two hex digits."""
    for text in ("path%", "path%2", "path%2G", "path%%20"):
        _assert_raises(
            ValueError,
            lambda text=text: validate_uri(UriValue(text, is_absolute=False)),
            "invalid percent escape",
        )


def test_validate_uri_rejects_non_uri_characters() -> None:
    """Verify whitespace, Unicode, controls, and excluded ASCII fail."""
    for text in ("path item", "路径", "path\nitem", 'path"item', "path\\item"):
        _assert_raises(
            ValueError,
            lambda text=text: validate_uri(UriValue(text, is_absolute=False)),
            "outside RFC 3986",
        )


def test_validate_uri_rejects_invalid_delimiter_and_authority_structure() -> None:
    """Verify fragment, IP-literal, IPv6, and port delimiters are structural."""
    invalid_values = (
        ("path#one#two", "multiple fragment delimiters"),
        ("path/[::1]", "IP literal must appear inside authority"),
        ("//[::1/path", "invalid IP literal authority"),
        ("//::1/path", "IPv6 host must use square brackets"),
        ("//example.com:http/path", "port must contain only digits"),
    )

    for text, message in invalid_values:
        _assert_raises(
            ValueError,
            lambda text=text: validate_uri(UriValue(text, is_absolute=False)),
            message,
        )


def test_validate_uri_requires_uri_value() -> None:
    """Verify callers cannot bypass reference-form semantics with raw text."""
    _assert_raises(
        TypeError,
        lambda: validate_uri(cast(UriValue, "https://example.com")),
        "must be a UriValue",
    )

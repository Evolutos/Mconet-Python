"""Boundary tests for portable OpenIdentifier validation."""

from collections.abc import Callable
from typing import cast

from mconet.core.domain import OpenIdentifier, validate_open_identifier


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


def test_validator_accepts_standard_and_unknown_namespaces() -> None:
    """Verify valid known and future names pass without a closed value list."""
    values = (
        "unary",
        "conversation.generate",
        "openai.chat-completions",
        "server_stream",
        "vendor.feature_v2",
        "3d.model",
    )

    for value in values:
        identifier = OpenIdentifier(value)

        # Returning the input object proves validation does not rewrite an
        # unknown namespace or allocate a normalized replacement.
        assert validate_open_identifier(identifier) is identifier


def test_validator_enforces_length_boundaries() -> None:
    """Verify the inclusive 1-to-128-character portable length range."""
    assert validate_open_identifier(OpenIdentifier("a" * 128)).value == "a" * 128

    _assert_raises(
        ValueError,
        lambda: validate_open_identifier(OpenIdentifier("")),
        "must not be empty",
    )
    _assert_raises(
        ValueError,
        lambda: validate_open_identifier(OpenIdentifier("a" * 129)),
        "at most 128 characters",
    )


def test_validator_rejects_whitespace_at_every_position() -> None:
    """Verify leading, embedded, and trailing whitespace are invalid."""
    for value in (" vendor.feature", "vendor. feature", "vendor.feature\n"):
        _assert_raises(
            ValueError,
            lambda value=value: validate_open_identifier(OpenIdentifier(value)),
            "must not contain whitespace",
        )


def test_validator_rejects_uppercase_ascii() -> None:
    """Verify identifier matching remains predictably case-sensitive."""
    _assert_raises(
        ValueError,
        lambda: validate_open_identifier(OpenIdentifier("Vendor.Feature")),
        "must use lowercase ASCII",
    )


def test_validator_rejects_invalid_namespace_boundaries() -> None:
    """Verify namespace segments and their portable characters are unambiguous."""
    invalid_values = (
        ".vendor",
        "vendor.",
        "vendor..feature",
        "vendor.-feature",
        "vendor.feature_",
        "vendor/feature",
        "vendor:feature",
        "vendor.féature",
    )

    for value in invalid_values:
        _assert_raises(
            ValueError,
            lambda value=value: validate_open_identifier(OpenIdentifier(value)),
            "invalid namespace format",
        )


def test_validator_requires_open_identifier_value_object() -> None:
    """Verify callers cannot bypass exact-value semantics with a raw string."""
    _assert_raises(
        TypeError,
        lambda: validate_open_identifier(cast(OpenIdentifier, "vendor.feature")),
        "must be an OpenIdentifier",
    )

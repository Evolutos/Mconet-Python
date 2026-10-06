"""Semantic validation tests for open MessageRole implementations."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import cast

from mconet.core.domain import (
    Extensions,
    MessageRole,
    OpenIdentifier,
    validate_message_role,
)

_STANDARD_ROLES = (
    "message.system",
    "message.developer",
    "message.user",
    "message.assistant",
    "message.tool",
)


def _empty_extensions() -> Extensions:
    """Create independent extension storage for each custom role fixture."""
    # Per-instance dictionaries avoid shared mutable state while satisfying the
    # protocol's read-only Mapping annotation.
    return {}


def _assert_raises(
    exception_type: type[BaseException],
    action: Callable[[], object],
    message: str,
) -> None:
    """Require an action to raise the expected type and diagnostic fragment."""
    # Matching the field-specific message prevents an unrelated structural or
    # extension error from making a negative role test pass accidentally.
    try:
        action()
    except exception_type as error:
        assert message in str(error)
        return
    raise AssertionError(f"Expected {exception_type.__name__} to be raised.")


@dataclass(frozen=True, slots=True)
class _Role:
    """Custom structural role used to exercise every validator field."""

    id: OpenIdentifier
    """Open role identifier under validation."""

    semantic: str | None = None
    """Optional producer-supplied role meaning."""

    raw_value: str | None = None
    """Optional original external spelling."""

    extensions: Extensions = field(default_factory=_empty_extensions)
    """Unknown role fields retained as JSON-compatible mapping data."""


def test_message_role_validator_accepts_every_standard_role() -> None:
    """Verify all architecture-standard identifiers pass without replacement."""
    roles = tuple(_Role(OpenIdentifier(value)) for value in _STANDARD_ROLES)

    # Identity checks prove validation is non-normalizing and does not replace a
    # standard custom implementation with an SDK-owned enum or singleton.
    for role in roles:
        assert validate_message_role(role) is role
    assert tuple(role.id.value for role in roles) == _STANDARD_ROLES


def test_message_role_validator_preserves_unknown_role() -> None:
    """Verify valid unknown identity and all optional data remain exact."""
    identifier = OpenIdentifier("vendor.moderator")
    extensions: Extensions = {
        "vendor.reviewScope": {
            "channels": ["safety", "quality"],
            "required": True,
        }
    }
    role = _Role(
        id=identifier,
        semantic="Reviews content before delivery.",
        raw_value="Moderator",
        extensions=extensions,
    )

    validated = validate_message_role(role)

    # The validator checks portable structure but never maps an unknown value to
    # a standard role, alters raw spelling, or copies uninterpreted extensions.
    assert validated is role
    assert role.id is identifier
    assert role.raw_value == "Moderator"
    assert role.extensions is extensions


def test_message_role_validator_rejects_incomplete_surface() -> None:
    """Verify absence of optional-field properties fails structural validation."""

    @dataclass(frozen=True, slots=True)
    class _IncompleteRole:
        """Intentionally omit semantic, raw_value, and extensions properties."""

        id: OpenIdentifier
        """Identity alone cannot preserve the complete MessageRole contract."""

    role = _IncompleteRole(OpenIdentifier("message.user"))

    # None is a valid optional value only when the corresponding property exists;
    # an incomplete object must fail before any identifier-specific processing.
    _assert_raises(
        TypeError,
        lambda: validate_message_role(cast(MessageRole, role)),
        "must implement MessageRole",
    )


def test_message_role_validator_rejects_invalid_identifier_type_and_syntax() -> None:
    """Verify role identity uses a nominal portable OpenIdentifier."""
    _assert_raises(
        TypeError,
        lambda: validate_message_role(_Role(cast(OpenIdentifier, "message.user"))),
        "id must be an OpenIdentifier",
    )

    # Each malformed value reaches the shared identifier validator; unknown but
    # syntactically valid namespaces remain accepted by the preceding test.
    for value in ("", "Message.User", "message user", "message..user"):
        _assert_raises(
            ValueError,
            lambda value=value: validate_message_role(_Role(OpenIdentifier(value))),
            "OpenIdentifier",
        )


def test_message_role_validator_checks_optional_text_types_without_normalizing() -> (
    None
):
    """Verify optional strings accept empty text but reject every other type."""
    empty_text = _Role(
        OpenIdentifier("vendor.moderator"),
        semantic="",
        raw_value="",
    )

    # Architecture defines both fields as nullable strings and assigns no shared
    # non-empty rule, so validation preserves explicit empty text unchanged.
    assert validate_message_role(empty_text) is empty_text
    for role, field_name in (
        (
            _Role(
                OpenIdentifier("message.user"),
                semantic=cast(str, 1),
            ),
            "semantic",
        ),
        (
            _Role(
                OpenIdentifier("message.user"),
                raw_value=cast(str, True),
            ),
            "raw_value",
        ),
    ):
        _assert_raises(
            TypeError,
            lambda role=role: validate_message_role(role),
            f"{field_name} must be a string or None",
        )


def test_message_role_validator_checks_portable_extensions() -> None:
    """Verify extension container, keys, shapes, and numbers are portable JSON."""
    invalid_cases: tuple[tuple[Extensions, type[BaseException], str], ...] = (
        (cast(Extensions, []), TypeError, "extensions must be a mapping"),
        (cast(Extensions, {1: "value"}), TypeError, "keys must be strings"),
        (
            cast(Extensions, {"vendor.value": (1, 2)}),
            TypeError,
            "structurally valid JsonValue",
        ),
        (
            {"vendor.value": 2**53},
            ValueError,
            "safe range",
        ),
        (
            {"vendor.value": math.inf},
            ValueError,
            "must be finite",
        ),
    )

    # Unknown keys remain legal; only mapping shape and cross-language JSON
    # portability are enforced before later message processing can observe them.
    for extensions, exception_type, message in invalid_cases:
        _assert_raises(
            exception_type,
            lambda extensions=extensions: validate_message_role(
                _Role(OpenIdentifier("vendor.moderator"), extensions=extensions)
            ),
            message,
        )

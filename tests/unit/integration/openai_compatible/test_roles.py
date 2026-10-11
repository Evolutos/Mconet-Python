"""Tests for mapping message roles to and from OpenAI wire spellings."""

from collections.abc import Callable
from dataclasses import dataclass, field

from mconet.core.domain import (
    Extensions,
    ModelInteractionError,
    OpenIdentifier,
    validate_message_role,
)
from mconet.integration.openai_compatible._roles import (
    UNSUPPORTED_MESSAGE_ROLE_CODE,
    domain_role,
    wire_role,
)

_STANDARD_ROLES = (
    ("message.system", "system"),
    ("message.user", "user"),
    ("message.assistant", "assistant"),
)
_ROLE_PATH = "/choices/0/message/role"


def _empty_extensions() -> Extensions:
    """Create independent empty extension storage for a test role."""
    return {}


@dataclass(frozen=True, slots=True)
class _Role:
    """Caller-defined role used as request input."""

    id: OpenIdentifier
    semantic: str | None = None
    raw_value: str | None = None
    extensions: Extensions = field(default_factory=_empty_extensions)


def _capture(action: Callable[[], object]) -> BaseException:
    """Run one action and return the exception it raises."""
    try:
        action()
    except BaseException as error:
        return error
    raise AssertionError("Expected the action to fail.")


def _assert_unsupported_role(error: BaseException, role: _Role) -> None:
    """Assert the stable unsupported-role error for one request role."""
    assert isinstance(error, ModelInteractionError)
    assert error.category.id.value == "unsupported_feature"
    assert error.phase.id.value == "protocol_adaptation"
    assert error.code == UNSUPPORTED_MESSAGE_ROLE_CODE
    assert error.message == (
        f"Message role {role.id} is not supported by the "
        "OpenAI-compatible chat completions protocol."
    )


def test_standard_request_roles_map_to_their_wire_spelling() -> None:
    """Verify system, user, and assistant map one to one under any policy."""
    for enforce in (True, False):
        for role_id, spelling in _STANDARD_ROLES:
            role = _Role(OpenIdentifier(role_id))

            assert wire_role(role, enforce_profile=enforce) == spelling


def test_request_role_selection_ignores_descriptive_fields() -> None:
    """Verify only the identifier selects a standard role's spelling."""
    role = _Role(
        OpenIdentifier("message.user"), semantic="assistant", raw_value="SYSTEM"
    )

    assert wire_role(role, enforce_profile=True) == "user"
    assert wire_role(role, enforce_profile=False) == "user"


def test_strict_profile_rejects_unknown_roles_with_no_fallback() -> None:
    """Verify an enforced profile fails even when raw_value names a wire role."""
    for role in (
        _Role(OpenIdentifier("message.tool")),
        _Role(OpenIdentifier("message.developer"), raw_value="developer"),
        _Role(OpenIdentifier("vendor.reviewer"), semantic="user", raw_value="user"),
    ):
        error = _capture(lambda role=role: wire_role(role, enforce_profile=True))

        _assert_unsupported_role(error, role)


def test_relaxed_profile_sends_the_raw_value_of_an_unknown_role() -> None:
    """Verify a relaxed policy keeps the caller's original role spelling."""
    for raw_value in ("developer", "tool", "Reviewer"):
        role = _Role(
            OpenIdentifier("vendor.role"), semantic="user", raw_value=raw_value
        )

        assert wire_role(role, enforce_profile=False) == raw_value


def test_relaxed_profile_still_rejects_an_unknown_role_without_raw_value() -> None:
    """Verify neither the identifier nor semantic is used to guess a spelling."""
    for role in (
        _Role(OpenIdentifier("message.developer")),
        _Role(OpenIdentifier("vendor.reviewer"), semantic="user"),
    ):
        error = _capture(lambda role=role: wire_role(role, enforce_profile=False))

        _assert_unsupported_role(error, role)


def test_response_spellings_map_to_valid_standard_roles() -> None:
    """Verify response roles map back and keep the exact wire spelling."""
    for role_id, spelling in _STANDARD_ROLES:
        role = domain_role(spelling, _ROLE_PATH)

        assert validate_message_role(role) is role
        assert role.id == OpenIdentifier(role_id)
        assert role.raw_value == spelling
        assert role.semantic is None
        assert dict(role.extensions) == {}


def test_unknown_response_spellings_are_protocol_errors() -> None:
    """Verify matching is exact and an unknown spelling is not coerced."""
    for spelling in ("tool", "Assistant", "", " assistant"):
        error = _capture(lambda spelling=spelling: domain_role(spelling, _ROLE_PATH))

        assert isinstance(error, ModelInteractionError)
        assert error.category.id.value == "protocol"
        assert error.phase.id.value == "response_parsing"
        assert error.code == "invalid_protocol_response"
        assert error.message == (
            "OpenAI-compatible response field /choices/0/message/role "
            "must be assistant, system, or user."
        )

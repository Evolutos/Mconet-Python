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


def test_standard_request_roles_map_to_their_wire_spelling() -> None:
    """Verify system, user, and assistant map one to one."""
    for role_id, spelling in _STANDARD_ROLES:
        assert wire_role(_Role(OpenIdentifier(role_id))) == spelling


def test_request_role_selection_ignores_descriptive_fields() -> None:
    """Verify only the identifier selects the spelling."""
    role = _Role(
        OpenIdentifier("message.user"), semantic="assistant", raw_value="SYSTEM"
    )

    assert wire_role(role) == "user"


def test_unknown_request_roles_are_unsupported_with_no_fallback() -> None:
    """Verify an unknown role fails instead of falling back to another role."""
    for role in (
        _Role(OpenIdentifier("message.tool")),
        _Role(OpenIdentifier("message.developer")),
        _Role(OpenIdentifier("vendor.reviewer"), semantic="user", raw_value="user"),
    ):
        error = _capture(lambda role=role: wire_role(role))

        assert isinstance(error, ModelInteractionError)
        assert error.category.id.value == "unsupported_feature"
        assert error.phase.id.value == "protocol_adaptation"
        assert error.code == UNSUPPORTED_MESSAGE_ROLE_CODE
        assert error.message == (
            f"Message role {role.id} is not supported by the "
            "OpenAI-compatible chat completions protocol."
        )


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
